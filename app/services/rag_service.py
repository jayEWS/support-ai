import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from app.core.config import settings
from app.core.logging import logger, LogLatency
from app.schemas.schemas import RAGResponse
from app.core.database import db_manager
from app.services.advanced_retriever import AdvancedRetriever
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class RAGService:
    def __init__(self):
        self.embeddings = self._init_embeddings()
        self.vector_store = self._load_vector_store()
        
        # 🚀 Semantic Cache
        self._cache = {}
        self._cache_ttl = 3600 # 1 hour
        
        # Initialize AdvancedRetriever
        documents = []
        if self.vector_store and hasattr(self.vector_store, 'docstore'):
             documents = list(self.vector_store.docstore._dict.values())
        
        self.retriever = AdvancedRetriever(
            vector_store=self.vector_store,
            documents=documents,
            embeddings=self.embeddings
        )
        
        self.langfuse_enabled = os.getenv("LANGFUSE_PUBLIC_KEY") is not None
        logger.info("[RAGService] Initialized successfully")

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text: return text
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def _init_embeddings(self):
        try:
            if settings.EMBEDDINGS_TYPE == "vertex":
                from langchain_google_vertexai import VertexAIEmbeddings
                return VertexAIEmbeddings(model_name="text-embedding-005", project=settings.GCP_PROJECT_ID)
            if settings.EMBEDDINGS_TYPE == "openai":
                return OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
            from langchain_huggingface import HuggingFaceEmbeddings
            return HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
        except Exception as e:
            logger.error(f"Embedding init failed: {e}")
            return None

    def _load_vector_store(self):
        if os.path.exists(settings.DB_DIR) and self.embeddings:
            try:
                return FAISS.load_local(settings.DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logger.error(f"FAISS load error: {e}")
        return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True, language: str = 'en') -> RAGResponse:
        logger.info(f"RAG Query: {text[:50]}")
        try:
            # 1. Greeting Check
            if self._is_greeting(text):
                logger.info("Greeting detected")
                return await self._handle_greeting(text, language)

            # 2. Cache Check
            cache_key = f"{text.lower().strip()}_{language}"
            if cache_key in self._cache:
                if (datetime.now().timestamp() - self._cache[cache_key]['timestamp']) < self._cache_ttl:
                    return self._cache[cache_key]['response']

            # 3. Retrieval
            retrieval_result = await self.retriever.retrieve(original_query=text, k_final=5)
            context = retrieval_result.context_text
            confidence = retrieval_result.confidence
            
            # 4. LLM
            llm = self._get_llm()
            prompt = f"Context: {context}\n\nQuestion: {text}\n\nAnswer concisely in {language}:"
            
            # Use wait_for to prevent infinite hang
            res = await asyncio.wait_for(asyncio.to_thread(llm.invoke, prompt), timeout=15.0)
            answer = self._sanitize_text(res.content)
            
            result = RAGResponse(
                answer=answer, confidence=confidence, 
                source_documents=[c['file'] for c in retrieval_result.source_citations],
                retrieval_method="advanced_hybrid"
            )
            
            self._cache[cache_key] = {'response': result, 'timestamp': datetime.now().timestamp()}
            return result

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return RAGResponse(answer="I'm sorry, I'm having trouble connecting to my brain. Please try again later.", confidence=0, source_documents=[])

    def _is_greeting(self, text: str) -> bool:
        greetings = {"hi", "hello", "hey", "halo", "hai", "good", "morning", "afternoon", "pm", "am", "pagi", "siang"}
        words = set(text.lower().strip().split())
        return len(words) <= 3 and bool(words.intersection(greetings))

    async def _handle_greeting(self, text: str, language: str) -> RAGResponse:
        fallbacks = {"en": "Hello! How can I help you?", "id": "Halo! Ada yang bisa saya bantu?", "zh": "你好！有什么我可以帮你的吗？"}
        ans = fallbacks.get(language, fallbacks["en"])
        return RAGResponse(answer=ans, confidence=1.0, source_documents=[], retrieval_method="greeting")

    def _get_llm(self):
        return ChatOpenAI(model_name=settings.MODEL_NAME, openai_api_key=settings.OPENAI_API_KEY, temperature=0)
