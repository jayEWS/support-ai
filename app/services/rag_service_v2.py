"""
Shopify-Inspired Advanced RAG Service (v2)
============================================
Production-grade RAG pipeline modeled after Shopify Sidekick's architecture.
"""

import asyncio
import os
import time
import hashlib
from typing import List, Optional
from collections import OrderedDict
from app.core.config import settings
from app.core.logging import logger, LogLatency
from app.schemas.schemas import RAGResponse
from app.services.query_engine import QueryEngine, QueryIntent, ProcessedQuery
from app.services.advanced_retriever import AdvancedRetriever, RetrievalResult
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

# ── In-Memory TTL Cache for repeated queries ────────────────────────
class _QueryCache:
    def __init__(self, max_size: int = 200, ttl_seconds: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _key(self, text: str, language: str) -> str:
        return hashlib.md5(f"{text.strip().lower()}|{language}".encode()).hexdigest()

    def get(self, text: str, language: str) -> Optional[RAGResponse]:
        k = self._key(text, language)
        if k not in self._cache:
            return None
        entry = self._cache[k]
        if time.time() - entry["ts"] > self._ttl:
            del self._cache[k]
            return None
        self._cache.move_to_end(k)
        return entry["result"]

    def put(self, text: str, language: str, result: RAGResponse):
        k = self._key(text, language)
        self._cache[k] = {"result": result, "ts": time.time()}
        self._cache.move_to_end(k)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

_query_cache = _QueryCache()

SYSTEM_PROMPT_CORE = """You are a friendly and knowledgeable Edgeworks POS technical support assistant.
Answer ONLY using facts explicitly stated in the DOCUMENT CONTEXT below."""

class RAGServiceV2:
    def __init__(self):
        self.embeddings = self._init_embeddings()
        self.vector_store = self._load_vector_store()
        self.all_documents = self._extract_documents()
        self.query_engine = QueryEngine()
        self.retriever = AdvancedRetriever(
            vector_store=self.vector_store,
            documents=self.all_documents,
            embeddings=self.embeddings,
        )
        self.langfuse_enabled = os.getenv("LANGFUSE_PUBLIC_KEY") is not None
        doc_count = len(self.all_documents) if self.all_documents else 0
        self._llm_service = None # P1 Fix: Circular dependency fix
        logger.info(f"[RAGServiceV2] Initialized — {doc_count} documents")

    def set_llm_service(self, llm_service):
        """Set LLM service reference (called from main.py lifespan to avoid circular import)."""
        self._llm_service = llm_service
        if llm_service and llm_service.llm:
            self.query_engine.set_llm(llm_service.llm)

    def _init_embeddings(self):
        try:
            if settings.EMBEDDINGS_TYPE == "vertex":
                from langchain_google_vertexai import VertexAIEmbeddings
                return VertexAIEmbeddings(model_name="text-embedding-005", project=settings.GCP_PROJECT_ID)
            if settings.EMBEDDINGS_TYPE == "openai" and settings.OPENAI_API_KEY:
                return OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
            
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
                return HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
            except ImportError:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                return HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
        except Exception as e:
            logger.warning(f"Embeddings init failed: {e}")
            return None

    def _load_vector_store(self):
        from langchain_community.vectorstores import FAISS
        if (os.path.exists(settings.DB_DIR) and 
            os.path.exists(os.path.join(settings.DB_DIR, "index.faiss")) and 
            self.embeddings):
            try:
                return FAISS.load_local(settings.DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logger.error(f"FAISS load error: {e}")
        return None

    def _extract_documents(self) -> List:
        if not self.vector_store or not hasattr(self.vector_store, 'docstore'):
            return []
        try:
            return list(self.vector_store.docstore._dict.values())
        except Exception as e:
            logger.warning(f"Document extraction failed: {e}")
            return []

    def _get_llm(self):
        # P1 Fix: Use injected service instead of app.state from circular import
        llm_svc = self._llm_service
        if llm_svc and llm_svc.llm:
            self.query_engine.set_llm(llm_svc.llm)
            return llm_svc.llm
        
        # Fallback
        llm = ChatOpenAI(model_name=settings.MODEL_NAME, openai_api_key=settings.OPENAI_API_KEY, temperature=0)
        self.query_engine.set_llm(llm)
        return llm

    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True, language: str = 'en', system_prompt: Optional[str] = None) -> RAGResponse:
        cached = _query_cache.get(f"{text}_{hash(system_prompt)}", language)
        if cached: return cached

        processed = await self.query_engine.process(text, language)
        if processed.is_greeting:
            return await self._handle_greeting(text, language)

        if not self.vector_store:
            return await self._handle_no_vectorstore(text, language)

        k_final = 8
        retrieval_result = await self.retriever.retrieve(
            original_query=text,
            expanded_query=processed.expanded_query,
            hyde_passage=processed.hyde_passage,
            sub_queries=processed.sub_queries,
            k_final=k_final,
            intent=processed.intent.value,
        )

        if not retrieval_result.chunks:
            return RAGResponse(answer="No relevant documents found.", confidence=0.0, source_documents=[])

        if system_prompt:
            prompt = f"{system_prompt}\n\nDOCUMENT CONTEXT:\n{retrieval_result.context_text}\n\nUSER QUESTION: {text}"
        else:
            prompt = f"{SYSTEM_PROMPT_CORE}\n\nContext: {retrieval_result.context_text}\n\nQuestion: {text}"
            
        llm = self._get_llm()
        try:
            res = await llm.ainvoke(prompt)
            answer = res.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer = "Error processing question."

        result = RAGResponse(
            answer=answer,
            confidence=retrieval_result.confidence,
            source_documents=[c["file"] for c in retrieval_result.source_citations],
            retrieval_method="shopify_v2"
        )
        _query_cache.put(text, language, result)
        return result

    async def _handle_greeting(self, text: str, language: str) -> RAGResponse:
        return RAGResponse(answer="Hello! How can I help you?", confidence=1.0, source_documents=[])

    async def _handle_no_vectorstore(self, text: str, language: str) -> RAGResponse:
        return RAGResponse(answer="I'm still learning. Please try again later.", confidence=0.0, source_documents=[])

    def refresh_stores(self):
        self.vector_store = self._load_vector_store()
        self.all_documents = self._extract_documents()
        self.retriever.update_stores(self.vector_store, self.all_documents)
        self.query_engine = QueryEngine()
        _query_cache._cache.clear()
