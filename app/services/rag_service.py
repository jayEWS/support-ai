import os
import asyncio
from typing import List, Optional, Dict, Any
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from app.core.config import settings
from app.core.logging import logger
from app.core.logging import LogLatency
from app.schemas.schemas import RAGResponse
from app.core.database import db_manager
from app.services.advanced_retriever import AdvancedRetriever
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class RAGService:
    def __init__(self):
        self.embeddings = self._init_embeddings()
        self.vector_store = self._load_vector_store()
        
        # Initialize AdvancedRetriever with loaded vector store and documents
        documents = []
        if self.vector_store and hasattr(self.vector_store, 'docstore'):
             documents = list(self.vector_store.docstore._dict.values())
        
        self.retriever = AdvancedRetriever(
            vector_store=self.vector_store,
            documents=documents,
            embeddings=self.embeddings
        )
        
        # Langfuse tracing (optional)
        self.langfuse_enabled = os.getenv("LANGFUSE_PUBLIC_KEY") is not None

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Remove surrogate characters that break UTF-8 encoding"""
        if not text: return text
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def _init_embeddings(self):
        """Initialize embeddings with fallback options"""
        if settings.EMBEDDINGS_TYPE == "vertex":
            try:
                from langchain_google_vertexai import VertexAIEmbeddings
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
                model_name = settings.VERTEX_AI_EMBEDDINGS_MODEL or "text-embedding-005"
                if project_id:
                    return VertexAIEmbeddings(model_name=model_name, project=project_id, location=location)
            except Exception: pass
        
        if settings.EMBEDDINGS_TYPE == "openai":
            return OpenAIEmbeddings(
                openai_api_key=settings.OPENAI_API_KEY,
                model=settings.EMBEDDINGS_MODEL_NAME,
                openai_api_base=settings.EMBEDDINGS_BASE_URL
            )
        
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            return HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
        except Exception:
            return None

    def _load_vector_store(self):
        """Load persistent FAISS vector store"""
        if os.path.exists(settings.DB_DIR) and os.path.exists(os.path.join(settings.DB_DIR, "index.faiss")) and self.embeddings:
            try:
                return FAISS.load_local(settings.DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logger.error(f"Error loading FAISS: {e}")
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True, language: str = 'en') -> RAGResponse:
        """
        Query RAG using AdvancedRetriever pipeline (Hybrid + Reranking)
        Retries up to 3 times with exponential backoff on failure.
        """
        lang_instructions = {
            'id': "Jawab dalam Bahasa Indonesia. Gunakan nada santai tapi profesional.",
            'en': "Answer in English. Use a friendly and professional tone.",
            'zh': "请用中文回答。使用友好且专业的语气。",
        }
        lang_instruction = lang_instructions.get(language, lang_instructions['en'])
        
        with LogLatency("rag_service", "query"):
            # 1. Handle Greetings (Fast Path)
            if self._is_greeting(text):
                return await self._handle_greeting(text, language, lang_instruction)

            # 2. Advanced Retrieval (Hybrid + Rerank)
            try:
                retrieval_result = await self.retriever.retrieve(
                    original_query=text,
                    k_per_method=5,
                    k_final=5
                )
                
                context = retrieval_result.context_text
                confidence = retrieval_result.confidence
                
                # 3. LLM Generation
                llm = self._get_llm()
                
                if confidence >= threshold:
                    prompt = f"""You are a friendly Edgeworks technical support assistant. Answer based on the following documents.

{context}

Question: {text}

Instructions:
1. Use ONLY information from the documents above.
2. {lang_instruction}
3. Keep the answer concise and easy to follow.
4. Mention the source file name at the end.

Answer:"""
                else:
                     prompt = f"""You are a friendly Edgeworks technical support assistant.

Context found (may not be fully relevant):
{context}

Question: {text}

Instructions:
1. Try to answer using the context provided.
2. If context is not relevant, answer from general knowledge about POS systems.
3. If you truly cannot answer, apologize and offer further help.
4. {lang_instruction}

Answer:"""

                res = await asyncio.to_thread(llm.invoke, prompt)
                answer = self._sanitize_text(res.content)
                
                # 4. Log Metrics (New Requirement)
                self._log_metrics(text, answer, confidence, retrieval_result)

                return RAGResponse(
                    answer=answer,
                    confidence=confidence,
                    source_documents=[c['file'] for c in retrieval_result.source_citations],
                    retrieval_method="advanced_hybrid",
                    num_retrieved=len(retrieval_result.chunks)
                )

            except Exception as e:
                logger.error(f"RAG query error: {e}")
                return RAGResponse(answer="I encountered an error processing your request.", confidence=0, source_documents=[])

    def _is_greeting(self, text: str) -> bool:
        greeting_words = {"hi", "hello", "hey", "halo", "hai", "selamat", "pagi", "siang", "sore", "malam", "thanks", "terima", "kasih"}
        words = set(text.lower().strip().split())
        return len(words) <= 3 and bool(words.intersection(greeting_words))

    async def _handle_greeting(self, text: str, language: str, instruction: str) -> RAGResponse:
        llm = self._get_llm()
        prompt = f"""You are a friendly Edgeworks technical support assistant. User says: "{text}". {instruction}. Reply casually. Ask how you can help."""
        try:
            res = await asyncio.to_thread(llm.invoke, prompt)
            return RAGResponse(answer=self._sanitize_text(res.content), confidence=1.0, source_documents=[], retrieval_method="greeting")
        except Exception:
            return RAGResponse(answer="Hello! How can I help you today?", confidence=1.0, source_documents=[])

    def _log_metrics(self, query: str, answer: str, confidence: float, result: Any):
        """Log key AI metrics for dashboard"""
        try:
            # In a real app, this would go to a DB table 'ai_metrics'
            # For now, we struct log it so it can be parsed
            metric_entry = {
                "event": "ai_interaction",
                "query_length": len(query),
                "answer_length": len(answer),
                "confidence": confidence,
                "retrieved_chunks": len(result.chunks),
                "methods_used": result.retrieval_methods_used,
                "resolution_status": "automated" if confidence > 0.7 else "potential_escalation"
            }
            logger.info(f"AI_METRIC: {metric_entry}")
            
            if self.langfuse_enabled:
                 self._log_to_langfuse(query, result.context_text, answer, confidence)
        except Exception as e:
            logger.warning(f"Failed to log metrics: {e}")

    def _get_llm(self):
        """Get LLM with fallback support"""
        llm_provider = getattr(settings, 'LLM_PROVIDER', os.getenv("LLM_PROVIDER", "openai")).lower()
        
        if llm_provider == "vertex":
            try:
                from langchain_google_vertexai import ChatVertexAI
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
                model_name = settings.VERTEX_AI_MODEL or os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")
                if project_id:
                    return ChatVertexAI(
                        model_name=model_name,
                        project=project_id,
                        location=location,
                        temperature=settings.TEMPERATURE,
                        convert_system_message_to_human=True,
                    )
            except Exception: pass
        
        if llm_provider in ("gemini", "vertex"):
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = settings.GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", "")
                if api_key:
                    return ChatGoogleGenerativeAI(
                        model=settings.GEMINI_MODEL_NAME,
                        google_api_key=api_key,
                        temperature=settings.TEMPERATURE,
                        convert_system_message_to_human=True,
                    )
            except Exception: pass
        
        if llm_provider in ("groq", "vertex", "gemini"):
            try:
                from langchain_groq import ChatGroq
                return ChatGroq(
                    model=settings.MODEL_NAME,
                    api_key=os.getenv("GROQ_API_KEY"),
                    temperature=settings.TEMPERATURE
                )
            except Exception: pass
        
        # Default to OpenAI
        return ChatOpenAI(
            model_name=settings.MODEL_NAME,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=settings.TEMPERATURE
        )

    def _log_to_langfuse(self, query: str, context: str, answer: str, confidence: float):
        try:
            from langfuse import Langfuse
            langfuse = Langfuse()
            langfuse.trace(
                name="rag_query",
                input={"query": query},
                output={"answer": answer, "confidence": confidence},
                metadata={"retrieval_method": "advanced_hybrid"}
            )
        except Exception: pass
