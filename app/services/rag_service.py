import os
import asyncio
from typing import List, Optional
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core.logging import logger
from app.core.logging import LogLatency
from app.utils.retrieval_utils import HybridRetriever, reciprocal_rank_fusion, calculate_confidence
from app.schemas.schemas import RAGResponse
from app.core.database import db_manager

class RAGService:
    def __init__(self):
        self.embeddings = self._init_embeddings()
        self.vector_store = self._load_vector_store()
        self.hybrid_retriever = None
        self.bm25_retriever = None
        self.all_documents = []
        self._initialize_hybrid_search()
        
        # Langfuse tracing (optional, logs to Langfuse if configured)
        self.langfuse_enabled = os.getenv("LANGFUSE_PUBLIC_KEY") is not None

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Remove surrogate characters that break UTF-8 encoding"""
        if not text:
            return text
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
                    logger.info(f"Using Vertex AI Embeddings: {model_name} (project={project_id})")
                    return VertexAIEmbeddings(
                        model_name=model_name,
                        project=project_id,
                        location=location,
                    )
                else:
                    logger.warning("GCP_PROJECT_ID not set for Vertex AI Embeddings, falling back to local")
            except Exception as e:
                logger.warning(f"Vertex AI Embeddings init failed: {e}, falling back to local")
        
        if settings.EMBEDDINGS_TYPE == "openai":
            return OpenAIEmbeddings(
                openai_api_key=settings.OPENAI_API_KEY,
                model=settings.EMBEDDINGS_MODEL_NAME,
                openai_api_base=settings.EMBEDDINGS_BASE_URL
            )
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            return HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
        except Exception as e:
            logger.warning(f"Embeddings init failed: {e}")
            return None

    def _load_vector_store(self):
        """Load persistent FAISS vector store"""
        if os.path.exists(settings.DB_DIR) and os.path.exists(os.path.join(settings.DB_DIR, "index.faiss")) and self.embeddings:
            try:
                return FAISS.load_local(settings.DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logger.error(f"Error loading FAISS: {e}")
        return None

    def _initialize_hybrid_search(self):
        """Initialize hybrid search (BM25 + Vector) for better retrieval"""
        if not self.vector_store:
            logger.warning("Vector store not available, hybrid search disabled")
            return

        try:
            # Extract documents from vector store
            if hasattr(self.vector_store, 'docstore'):
                self.all_documents = list(self.vector_store.docstore._dict.values())
                
                if self.all_documents:
                    # Initialize BM25 retriever
                    texts = [doc.page_content for doc in self.all_documents]
                    self.bm25_retriever = BM25Okapi(texts)
                    logger.info(f"[OK] Hybrid search initialized with {len(self.all_documents)} documents")
        except Exception as e:
            logger.warning(f"Hybrid search initialization failed: {e}")

    def _bm25_search(self, query: str, k: int = 5) -> List:
        """BM25 keyword-based search"""
        if not self.bm25_retriever or not self.all_documents:
            return []
        
        try:
            scores = self.bm25_retriever.get_scores(query.split())
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            return [self.all_documents[i] for i in top_indices if i < len(self.all_documents)]
        except Exception as e:
            logger.warning(f"BM25 search error: {e}")
            return []

    async def _hybrid_query(self, text: str, k_bm25: int = 5, k_vector: int = 5) -> List:
        """Hybrid search combining BM25 (keyword) + Vector (semantic)"""
        bm25_docs = self._bm25_search(text, k=k_bm25)
        vector_docs = await asyncio.to_thread(self.vector_store.similarity_search, text, k=k_vector) if self.vector_store else []
        
        # Combine results with RRF (Reciprocal Rank Fusion)
        all_docs = []
        seen = set()
        
        # Add BM25 results (40% weight)
        for i, doc in enumerate(bm25_docs):
            if doc.page_content not in seen:
                all_docs.append((doc, 0.4 * (1 / (i + 1))))
                seen.add(doc.page_content)
        
        # Add vector results (60% weight)
        for i, doc in enumerate(vector_docs):
            if doc.page_content in seen:
                # Boost existing doc score
                for j, (d, score) in enumerate(all_docs):
                    if d.page_content == doc.page_content:
                        all_docs[j] = (d, score + 0.6 * (1 / (i + 1)))
                        break
            else:
                all_docs.append((doc, 0.6 * (1 / (i + 1))))
                seen.add(doc.page_content)
        
        # Sort by combined score
        all_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in all_docs[:k_vector + k_bm25]]

    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True, language: str = 'id') -> RAGResponse:
        """
        Query RAG with optional hybrid search
        - use_hybrid=True: Uses BM25 + Vector search (better recall)
        - use_hybrid=False: Uses only vector search (faster)
        - language: 'id' (Indonesian), 'en' (English), 'zh' (Chinese)
        """
        lang_instructions = {
            'id': "Jawab dalam Bahasa Indonesia. Gunakan nada santai tapi profesional, panggil 'Kak' atau langsung saja.",
            'en': "Answer in English. Use a friendly and professional tone.",
            'zh': "请用中文回答。使用友好且专业的语气。",
        }
        lang_instruction = lang_instructions.get(language, lang_instructions['id'])
        
        with LogLatency("rag_service", "query"):
            # Handle greetings and short conversational queries directly via LLM
            greeting_words = {"hi", "hello", "hey", "halo", "hai", "selamat", "pagi", "siang", "sore", "malam", "thanks", "terima", "kasih", "ok", "oke", "bye", "test", "你好", "谢谢", "早上好", "晚上好"}
            query_words = set(text.lower().strip().split())
            is_greeting = len(query_words) <= 3 and query_words.intersection(greeting_words)
            
            if is_greeting:
                llm = self._get_llm()
                prompt = f"""You are a friendly Edgeworks technical support assistant.
The user says: "{text}"

{lang_instruction}
Reply casually but professionally. Introduce yourself as the Edgeworks AI assistant.
Ask how you can help today. Keep it short, 2-3 sentences."""
                try:
                    res = await asyncio.to_thread(llm.invoke, prompt)
                    return RAGResponse(
                        answer=self._sanitize_text(res.content),
                        confidence=1.0,
                        source_documents=[],
                        retrieval_method="greeting"
                    )
                except Exception as e:
                    logger.error(f"LLM greeting error: {e}")
                    fallbacks = {
                        'id': "Halo! 👋 Saya asisten AI Edgeworks. Ada yang bisa saya bantu hari ini?",
                        'en': "Hello! 👋 I'm the Edgeworks AI assistant. How can I help you today?",
                        'zh': "你好！👋 我是 Edgeworks AI 助手。今天有什么可以帮助您的？",
                    }
                    return RAGResponse(
                        answer=fallbacks.get(language, fallbacks['id']),
                        confidence=1.0,
                        source_documents=[]
                    )

            if not self.vector_store:
                # No vector store - still try LLM for general questions
                llm = self._get_llm()
                prompt = f"""You are a friendly Edgeworks technical support assistant.
User question: "{text}"

{lang_instruction}
Answer as best as you can.
If unsure, say you'll connect them with a team that can help."""
                try:
                    res = await asyncio.to_thread(llm.invoke, prompt)
                    return RAGResponse(
                        answer=self._sanitize_text(res.content),
                        confidence=0.3,
                        source_documents=[],
                        retrieval_method="llm_only"
                    )
                except Exception as e:
                    logger.error(f"LLM fallback error: {e}")
                    return RAGResponse(
                        answer="Knowledge base not ready.",
                        confidence=0,
                        source_documents=[]
                    )

            try:
                # Retrieve documents using hybrid search if available
                if use_hybrid and self.bm25_retriever:
                    docs = await self._hybrid_query(text, k_bm25=5, k_vector=5)
                    retrieval_method = "hybrid"
                else:
                    docs = await asyncio.to_thread(self.vector_store.similarity_search, text, k=4)
                    retrieval_method = "vector"
                
                if not docs:
                    return RAGResponse(
                        answer="No relevant documents found.",
                        confidence=0,
                        source_documents=[]
                    )
                
                context = "\n".join([d.page_content for d in docs])
                confidence = calculate_confidence(text, context)

                # Call LLM for final answer - always, even with low confidence
                # Let the LLM decide if context is relevant enough
                llm = self._get_llm()
                
                if confidence >= threshold:
                    # High confidence - use context-grounded prompt
                    prompt = f"""You are a friendly Edgeworks technical support assistant. Answer based on the following documents.

Document Context:
{context}

Question: {text}

Instructions:
1. Use ONLY information from the documents above
2. {lang_instruction}
3. Keep the answer concise and easy to follow (use bullet points/numbered steps)
4. Mention the source file name at the end
5. If information is incomplete, say so and offer further help

Answer:"""
                else:
                    # Low confidence - let LLM try but with disclaimer
                    prompt = f"""You are a friendly Edgeworks technical support assistant.

Context found (may not be fully relevant):
{context}

Question: {text}

Instructions:
1. Try to answer using the context provided
2. If context is not relevant, answer from general knowledge about POS/Edgeworks systems
3. If you truly cannot answer, apologize and offer to connect with a team that can help
4. {lang_instruction}

Answer:"""
                
                res = await asyncio.to_thread(llm.invoke, prompt)
                
                response = RAGResponse(
                    answer=self._sanitize_text(res.content),
                    confidence=confidence,
                    source_documents=[d.metadata.get('filename', 'unknown') for d in docs],
                    retrieval_method=retrieval_method,
                    num_retrieved=len(docs)
                )
                
                # Optional: Log to Langfuse if enabled
                if self.langfuse_enabled:
                    self._log_to_langfuse(text, context, res.content, confidence)
                
                return response
                
            except Exception as e:
                import traceback
                err_msg = str(e).encode('utf-8', errors='replace').decode('utf-8') or type(e).__name__
                tb = traceback.format_exc().encode('utf-8', errors='replace').decode('utf-8')
                logger.error(f"RAG query error: {err_msg}\n{tb}")
                return RAGResponse(
                    answer=f"Error processing query: {err_msg}",
                    confidence=0,
                    source_documents=[]
                )

    def _get_llm(self):
        """Get LLM with fallback support (Vertex AI, Gemini, Groq, OpenAI, local)"""
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
                else:
                    logger.warning("GCP_PROJECT_ID not set for Vertex AI, falling back to Gemini")
            except Exception as e:
                logger.warning(f"Vertex AI init failed in RAG: {e}, falling back to Gemini")
        
        if llm_provider in ("gemini", "vertex"):  # vertex fallback chain
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = settings.GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", "")
                if not api_key:
                    logger.warning("GOOGLE_GEMINI_API_KEY not set, falling back to Groq")
                else:
                    return ChatGoogleGenerativeAI(
                        model=settings.GEMINI_MODEL_NAME,
                        google_api_key=api_key,
                        temperature=settings.TEMPERATURE,
                        convert_system_message_to_human=True,
                    )
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}, falling back to Groq")
        
        if llm_provider in ("groq", "vertex", "gemini"):  # fallback chain
            try:
                from langchain_groq import ChatGroq
                return ChatGroq(
                    model=settings.MODEL_NAME,
                    api_key=os.getenv("GROQ_API_KEY"),
                    temperature=settings.TEMPERATURE
                )
            except Exception as e:
                logger.warning(f"Groq initialization failed: {e}, falling back to OpenAI")
        
        if llm_provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
                return ChatOllama(
                    model=os.getenv("OLLAMA_MODEL", "llama2"),
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                )
            except Exception as e:
                logger.warning(f"Ollama initialization failed: {e}, falling back to OpenAI")
        
        # Default to OpenAI
        return ChatOpenAI(
            model_name=settings.MODEL_NAME,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=settings.TEMPERATURE
        )

    def _log_to_langfuse(self, query: str, context: str, answer: str, confidence: float):
        """Log RAG query to Langfuse for observability (optional)"""
        try:
            from langfuse import Langfuse
            langfuse = Langfuse()
            langfuse.trace(
                name="rag_query",
                input={"query": query},
                output={"answer": answer, "confidence": confidence},
                metadata={"retrieval_method": "hybrid", "context_length": len(context)}
            )
        except Exception as e:
            logger.debug(f"Langfuse logging failed: {e}")

