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

    def _init_embeddings(self):
        """Initialize embeddings with fallback options"""
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

    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True) -> RAGResponse:
        """
        Query RAG with optional hybrid search
        - use_hybrid=True: Uses BM25 + Vector search (better recall)
        - use_hybrid=False: Uses only vector search (faster)
        """
        with LogLatency("rag_service", "query"):
            if not self.vector_store:
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
                
                if confidence < threshold:
                    return RAGResponse(
                        answer="Low confidence in retrieved context",
                        confidence=confidence,
                        source_documents=[d.metadata.get('filename', 'unknown') for d in docs],
                        retrieval_method=retrieval_method
                    )

                # Call LLM for final answer synthesis
                llm = self._get_llm()
                prompt = f"""Answer based on context:

Context:
{context}

Question: {text}

Provide a helpful, concise answer based on the context above."""
                
                res = await asyncio.to_thread(llm.invoke, prompt)
                
                response = RAGResponse(
                    answer=res.content,
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
                logger.error(f"RAG query error: {e}")
                return RAGResponse(
                    answer=f"Error processing query: {str(e)}",
                    confidence=0,
                    source_documents=[]
                )

    def _get_llm(self):
        """Get LLM with fallback support (Gemini, Groq, OpenAI, local)"""
        llm_provider = getattr(settings, 'LLM_PROVIDER', os.getenv("LLM_PROVIDER", "openai")).lower()
        
        if llm_provider == "gemini":
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
        
        if llm_provider == "groq" or (llm_provider == "gemini" and True):  # fallback chain
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

