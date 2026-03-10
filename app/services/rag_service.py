import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from app.core.config import settings
from app.core.logging import logger, LogLatency
from app.schemas.schemas import RAGResponse
from app.services.advanced_retriever import AdvancedRetriever
from app.services.qdrant_store import get_qdrant_store
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class RAGService:
    def __init__(self):
        self.embeddings = self._init_embeddings()
        self.vector_store = self._load_vector_store()
        
        # 🚀 Semantic Cache
        self._cache = {}
        self._cache_ttl = 3600 # 1 hour
        
        # P1 Fix: LLM service reference set externally to avoid circular import
        self._llm_service = None
        
        # Initialize AdvancedRetriever
        documents = []
        # Qdrant manages documents internally, no need to extract them
        
        self.retriever = AdvancedRetriever(
            vector_store=self.vector_store,
            documents=documents,
            embeddings=self.embeddings
        )
        
        self.langfuse_enabled = os.getenv("LANGFUSE_PUBLIC_KEY") is not None
        logger.info(f"[RAGService] Initialized with {type(self.vector_store).__name__}")

    def set_llm_service(self, llm_service):
        """Set LLM service reference (called from main.py lifespan to avoid circular import)."""
        self._llm_service = llm_service

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text: return text
        return text.encode('utf-8', errors='replace').decode('utf-8')

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
                # Fallback to community version if new one not found
                from langchain_community.embeddings import HuggingFaceEmbeddings
                return HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
        except Exception as e:
            logger.error(f"Embedding init failed: {e}")
            return None

    def _load_vector_store(self):
        """
        Load Qdrant vector store for production deployment.
        """
        if not self.embeddings:
            logger.warning("Embeddings not initialized, cannot load vector store.")
            return None

        try:
            # Use Qdrant for all deployments
            logger.info("[VectorStore] Connecting to Qdrant...")
            store = get_qdrant_store()
            return store
        except Exception as e:
            logger.error(f"Qdrant connection failed: {e}")
            return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True, language: str = 'en', system_prompt: Optional[str] = None) -> RAGResponse:
        logger.info(f"RAG Query: {text[:50]}")
        try:
            # 0. Empty/Media Message Check
            if not text or text.strip() == "" or text.startswith("["):
                # If it's just media like "[Image Received]", don't try to query RAG
                ans = "I received your file/media. How can I help you with it?"
                if language == 'id': ans = "Saya telah menerima file/media Anda. Ada yang bisa saya bantu terkait hal tersebut?"
                elif language == 'zh': ans = "我收到了您的文件/媒体。有什么我可以帮您的吗？"
                return RAGResponse(answer=ans, confidence=1.0, source_documents=[], retrieval_method="media_bypass")

            # 1. Greeting Check
            if self._is_greeting(text):
                logger.info("Greeting detected")
                return await self._handle_greeting(text, language)

            # 2. Cache Check
            cache_key = f"{text.lower().strip()}_{language}_{hash(system_prompt) if system_prompt else 'default'}"
            if cache_key in self._cache:
                if (datetime.now().timestamp() - self._cache[cache_key]['timestamp']) < self._cache_ttl:
                    return self._cache[cache_key]['response']

            # 3. Retrieval
            retrieval_result = await self.retriever.retrieve(original_query=text, k_final=5)
            context = retrieval_result.context_text
            confidence = retrieval_result.confidence
            
            # 4. LLM using centralized LLMService (Much faster)
            # P1 Fix: Use injected LLM service instead of circular import from main
            llm_svc = self._llm_service
            
            if system_prompt:
                prompt = f"{system_prompt}\n\nDOCUMENT CONTEXT:\n{context}\n\nUSER QUESTION: {text}\n\nGenerate your response based on your identity and the context provided above. Be natural and engaging."
            else:
                prompt = f"Context: {context}\n\nQuestion: {text}\n\nAnswer concisely in {language}:"
            
            if llm_svc:
                # Use centralized instance which is already warmed up
                res = await asyncio.wait_for(llm_svc.llm.ainvoke(prompt), timeout=15.0)
                answer = self._sanitize_text(res.content)
            else:
                # Fallback if app state not ready
                llm = self._get_llm()
                res = await asyncio.wait_for(asyncio.to_thread(llm.invoke, prompt), timeout=15.0)
                answer = self._sanitize_text(res.content)
            
            # Guard against empty LLM responses
            if not answer or answer.strip() == "":
                logger.warning(f"LLM returned empty response for query: {text[:50]}")
                answer = "I'm processing that, but I'm having a bit of trouble finding the right words. Could you rephrase your question?"
                if language == 'id': answer = "Saya sedang memprosesnya, tetapi saya kesulitan menemukan kata-kata yang tepat. Bisa tolong ulangi pertanyaannya?"
            
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
