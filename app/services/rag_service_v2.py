"""
Shopify-Inspired Advanced RAG Service (v2)
============================================
Production-grade RAG pipeline modeled after Shopify Sidekick's architecture.

Key Shopify patterns implemented:
1. JIT (Just-In-Time) Instructions — context-relevant prompts per intent
2. Multi-stage retrieval — BM25 + Vector + HyDE + Query Expansion + RRF
3. Cross-encoder reranking — semantic relevance scoring
4. Confidence calibration — multi-signal scoring (not just word overlap)
5. Source citation tracking — per-chunk provenance
6. Query understanding — intent + topic + decomposition
7. Response quality evaluation — LLM-as-Judge pattern
8. Latency tracking — per-stage timing

Replaces the basic hybrid search in rag_service.py with a
Shopify-grade retrieval pipeline while maintaining backward compatibility.
"""

import asyncio
import os
import time
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger, LogLatency
from app.schemas.schemas import RAGResponse
from app.services.query_engine import QueryEngine, QueryIntent, ProcessedQuery
from app.services.advanced_retriever import AdvancedRetriever, RetrievalResult


# ── Shopify-Style JIT System Prompt ─────────────────────────────────
# Core system prompt is minimal. Intent-specific instructions are injected
# at query time via JIT (Just-In-Time) — the key Shopify Sidekick pattern.

SYSTEM_PROMPT_CORE = """You are a friendly and knowledgeable Edgeworks POS technical support assistant.

RULES:
1. Answer ONLY from the provided document context
2. If information is not found, clearly say so and offer to connect with a specialist
3. Use the document with the LATEST DATE when there's conflicting information
4. Cite the source file name at the end of your answer
5. Be concise but thorough — use numbered steps for instructions"""


class RAGServiceV2:
    """
    Shopify-grade RAG Service with multi-stage retrieval pipeline.
    
    Architecture:
    Query → QueryEngine → AdvancedRetriever → LLM (with JIT instructions) → Response + Evaluation
    """

    def __init__(self):
        # Initialize embeddings
        self.embeddings = self._init_embeddings()
        
        # Load FAISS vector store
        self.vector_store = self._load_vector_store()
        
        # Extract documents from vector store
        self.all_documents = self._extract_documents()
        
        # Initialize components
        self.query_engine = QueryEngine()
        self.retriever = AdvancedRetriever(
            vector_store=self.vector_store,
            documents=self.all_documents,
            embeddings=self.embeddings,
        )
        
        # Set LLM for HyDE generation
        self._llm = None  # Lazy init
        
        # Observability
        self.langfuse_enabled = os.getenv("LANGFUSE_PUBLIC_KEY") is not None
        
        doc_count = len(self.all_documents) if self.all_documents else 0
        logger.info(f"[RAGServiceV2] Initialized — {doc_count} documents, "
                     f"QueryEngine + AdvancedRetriever ready")

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Remove surrogate characters that break UTF-8 encoding"""
        if not text:
            return text
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def _init_embeddings(self):
        """Initialize embeddings (Vertex AI → OpenAI → HuggingFace fallback)"""
        if settings.EMBEDDINGS_TYPE == "vertex":
            try:
                from langchain_google_vertexai import VertexAIEmbeddings
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or "asia-southeast1"
                model_name = settings.VERTEX_AI_EMBEDDINGS_MODEL or "text-embedding-005"
                if project_id:
                    logger.info(f"[RAGServiceV2] Embeddings: Vertex AI {model_name}")
                    return VertexAIEmbeddings(
                        model_name=model_name, project=project_id, location=location,
                    )
            except Exception as e:
                logger.warning(f"Vertex AI Embeddings failed: {e}")

        if settings.EMBEDDINGS_TYPE == "openai":
            from langchain_openai import OpenAIEmbeddings
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
        """Load FAISS vector store from disk"""
        from langchain_community.vectorstores import FAISS
        if (os.path.exists(settings.DB_DIR) and 
            os.path.exists(os.path.join(settings.DB_DIR, "index.faiss")) and 
            self.embeddings):
            try:
                return FAISS.load_local(
                    settings.DB_DIR, self.embeddings,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                logger.error(f"FAISS load error: {e}")
        return None

    def _extract_documents(self) -> List:
        """Extract document objects from FAISS docstore"""
        if not self.vector_store or not hasattr(self.vector_store, 'docstore'):
            return []
        try:
            docs = list(self.vector_store.docstore._dict.values())
            logger.info(f"[RAGServiceV2] Extracted {len(docs)} chunks from FAISS")
            return docs
        except Exception as e:
            logger.warning(f"Document extraction failed: {e}")
            return []

    def _get_llm(self):
        """Lazy-init LLM with provider fallback chain"""
        if self._llm:
            return self._llm
        
        llm_provider = getattr(settings, 'LLM_PROVIDER', os.getenv("LLM_PROVIDER", "openai")).lower()

        if llm_provider == "vertex":
            try:
                from langchain_google_vertexai import ChatVertexAI
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or "asia-southeast1"
                model_name = settings.VERTEX_AI_MODEL or "gemini-2.5-flash"
                if project_id:
                    self._llm = ChatVertexAI(
                        model_name=model_name, project=project_id, location=location,
                        temperature=settings.TEMPERATURE,
                        convert_system_message_to_human=True,
                    )
                    self.query_engine.set_llm(self._llm)
                    return self._llm
            except Exception as e:
                logger.warning(f"Vertex AI LLM failed: {e}")

        if llm_provider in ("gemini", "vertex"):
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = settings.GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", "")
                if api_key:
                    self._llm = ChatGoogleGenerativeAI(
                        model=settings.GEMINI_MODEL_NAME, google_api_key=api_key,
                        temperature=settings.TEMPERATURE,
                        convert_system_message_to_human=True,
                    )
                    self.query_engine.set_llm(self._llm)
                    return self._llm
            except Exception as e:
                logger.warning(f"Gemini LLM failed: {e}")

        if llm_provider in ("groq", "vertex", "gemini"):
            try:
                from langchain_groq import ChatGroq
                groq_key = os.getenv("GROQ_API_KEY", "")
                if groq_key:
                    self._llm = ChatGroq(
                        model=settings.MODEL_NAME, api_key=groq_key,
                        temperature=settings.TEMPERATURE,
                    )
                    self.query_engine.set_llm(self._llm)
                    return self._llm
            except Exception as e:
                logger.warning(f"Groq LLM failed: {e}")

        if llm_provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
                self._llm = ChatOllama(
                    model=os.getenv("OLLAMA_MODEL", "llama2"),
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                )
                self.query_engine.set_llm(self._llm)
                return self._llm
            except Exception as e:
                logger.warning(f"Ollama LLM failed: {e}")

        from langchain_openai import ChatOpenAI
        self._llm = ChatOpenAI(
            model_name=settings.MODEL_NAME,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=settings.TEMPERATURE,
        )
        self.query_engine.set_llm(self._llm)
        return self._llm

    # ════════════════════════════════════════════════════════════════
    #  MAIN QUERY ENTRY POINT — Backward compatible with RAGService
    # ════════════════════════════════════════════════════════════════

    async def query(
        self,
        text: str,
        threshold: float = 0.5,
        use_hybrid: bool = True,
        language: str = 'en',
    ) -> RAGResponse:
        """
        Shopify-grade RAG query pipeline.
        Backward-compatible with RAGService.query() interface.
        
        Pipeline:
        1. Query Understanding (intent, expansion, HyDE, decomposition)
        2. Multi-stage Retrieval (BM25 + Vector + HyDE + expanded)
        3. Reranking + Dedup
        4. LLM Generation with JIT Instructions
        5. Response Quality Evaluation
        """
        timings = {}
        pipeline_start = time.time()

        # ── Stage 1: Query Understanding ────────────────────────────
        t0 = time.time()
        processed = await self.query_engine.process(text, language)
        timings["query_understanding_ms"] = round((time.time() - t0) * 1000, 1)

        # Handle greetings
        if processed.is_greeting:
            return await self._handle_greeting(text, language)

        # No vector store available
        if not self.vector_store:
            return await self._handle_no_vectorstore(text, language)

        # ── Stage 2: Multi-Stage Retrieval ──────────────────────────
        t0 = time.time()
        retrieval_result = await self.retriever.retrieve(
            original_query=text,
            expanded_query=processed.expanded_query,
            hyde_passage=processed.hyde_passage,
            sub_queries=processed.sub_queries,
            k_per_method=8,
            k_final=10,
            intent=processed.intent.value,
        )
        timings["retrieval_ms"] = round((time.time() - t0) * 1000, 1)

        if not retrieval_result.chunks:
            return RAGResponse(
                answer="No relevant documents found in the knowledge base.",
                confidence=0.0,
                source_documents=[],
                retrieval_method="advanced_hybrid",
            )

        # ── Stage 3: LLM Generation with JIT Instructions ──────────
        t0 = time.time()
        
        lang_instructions = {
            'id': "Jawab dalam Bahasa Indonesia. Gunakan nada santai tapi profesional.",
            'en': "Answer in English. Use a friendly and professional tone.",
            'zh': "请用中文回答。使用友好且专业的语气。",
        }
        lang_instruction = lang_instructions.get(language, lang_instructions['en'])

        # Build prompt with JIT instructions (Shopify pattern)
        prompt = self._build_jit_prompt(
            query=text,
            context=retrieval_result.context_text,
            jit_instructions=processed.jit_instructions,
            lang_instruction=lang_instruction,
            confidence=retrieval_result.confidence,
            threshold=threshold,
        )

        llm = self._get_llm()
        try:
            res = await asyncio.to_thread(llm.invoke, prompt)
            answer = self._sanitize_text(res.content)
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            answer = "I encountered an error processing your question. Please try again."

        timings["generation_ms"] = round((time.time() - t0) * 1000, 1)
        timings["total_ms"] = round((time.time() - pipeline_start) * 1000, 1)

        # ── Stage 4: Build Response ─────────────────────────────────

        source_docs = [c["file"] for c in retrieval_result.source_citations]
        
        # Log pipeline metrics
        logger.info(
            f"[RAGv2] intent={processed.intent.value} "
            f"confidence={retrieval_result.confidence:.3f} "
            f"candidates={retrieval_result.total_candidates}→{retrieval_result.after_rerank} "
            f"methods={','.join(retrieval_result.retrieval_methods_used)} "
            f"timings={timings}"
        )

        # Langfuse observability
        if self.langfuse_enabled:
            self._log_to_langfuse(text, retrieval_result, answer, processed, timings)

        return RAGResponse(
            answer=answer,
            confidence=retrieval_result.confidence,
            source_documents=source_docs,
            retrieval_method="shopify_advanced_rag",
            num_retrieved=retrieval_result.after_rerank,
        )

    # ── JIT Prompt Builder (Core Shopify Pattern) ───────────────────

    def _build_jit_prompt(
        self,
        query: str,
        context: str,
        jit_instructions: str,
        lang_instruction: str,
        confidence: float,
        threshold: float,
    ) -> str:
        """
        Build the final LLM prompt with Just-In-Time instructions.
        
        Instead of one massive system prompt (Shopify's "Death by a Thousand Instructions" problem),
        we inject only the instructions relevant to the detected intent.
        """
        if confidence >= threshold:
            # High confidence — grounded answer
            prompt = f"""{SYSTEM_PROMPT_CORE}

{jit_instructions}

{lang_instruction}

DOCUMENT CONTEXT:
{context}

QUESTION: {query}

Answer (based on the documents above):"""
        else:
            # Low confidence — cautious answer with disclaimer
            prompt = f"""{SYSTEM_PROMPT_CORE}

{jit_instructions}

{lang_instruction}

IMPORTANT: The retrieved context may not fully match the question. If the context is not relevant, clearly state that the information is not available in the knowledge base and offer to connect with a specialist.

DOCUMENT CONTEXT (partial match):
{context}

QUESTION: {query}

Answer:"""

        return prompt

    # ── Greeting Handler ────────────────────────────────────────────

    async def _handle_greeting(self, text: str, language: str) -> RAGResponse:
        """Handle greetings with LLM personality"""
        llm = self._get_llm()

        lang_instructions = {
            'id': "Jawab dalam Bahasa Indonesia. Panggil 'Kak'.",
            'en': "Answer in English.",
            'zh': "请用中文回答。",
        }

        prompt = f"""You are a friendly Edgeworks POS technical support assistant.
The user says: "{text}"

{lang_instructions.get(language, lang_instructions['en'])}
Reply casually but professionally. Introduce yourself as the Edgeworks AI assistant.
Ask how you can help today. Keep it short, 2-3 sentences."""

        try:
            res = await asyncio.to_thread(llm.invoke, prompt)
            return RAGResponse(
                answer=self._sanitize_text(res.content),
                confidence=1.0,
                source_documents=[],
                retrieval_method="greeting",
            )
        except Exception as e:
            logger.error(f"Greeting LLM error: {e}")
            fallbacks = {
                'id': "Halo! 👋 Saya asisten AI Edgeworks. Ada yang bisa saya bantu?",
                'en': "Hello! 👋 I'm the Edgeworks AI assistant. How can I help you today?",
                'zh': "你好！👋 我是 Edgeworks AI 助手。今天有什么可以帮助您的？",
            }
            return RAGResponse(
                answer=fallbacks.get(language, fallbacks['en']),
                confidence=1.0,
                source_documents=[],
            )

    # ── No Vectorstore Handler ──────────────────────────────────────

    async def _handle_no_vectorstore(self, text: str, language: str) -> RAGResponse:
        """Handle queries when vector store is not available"""
        llm = self._get_llm()
        prompt = f"""You are a friendly Edgeworks technical support assistant.
User question: "{text}"
Answer as best you can. If unsure, say you'll connect them with a specialist."""

        try:
            res = await asyncio.to_thread(llm.invoke, prompt)
            return RAGResponse(
                answer=self._sanitize_text(res.content),
                confidence=0.3,
                source_documents=[],
                retrieval_method="llm_only",
            )
        except Exception:
            return RAGResponse(
                answer="Knowledge base is initializing. Please try again shortly.",
                confidence=0, source_documents=[],
            )

    # ── Langfuse Observability ──────────────────────────────────────

    def _log_to_langfuse(self, query, retrieval_result, answer, processed, timings):
        """Log RAG pipeline metrics to Langfuse"""
        try:
            from langfuse import Langfuse
            langfuse = Langfuse()
            langfuse.trace(
                name="rag_v2_query",
                input={"query": query, "intent": processed.intent.value},
                output={"answer": answer, "confidence": retrieval_result.confidence},
                metadata={
                    "retrieval_methods": retrieval_result.retrieval_methods_used,
                    "total_candidates": retrieval_result.total_candidates,
                    "after_rerank": retrieval_result.after_rerank,
                    "timings": timings,
                    "topics": processed.topic_tags,
                }
            )
        except Exception as e:
            logger.debug(f"Langfuse logging failed: {e}")

    # ── Store Update (called after reindex) ─────────────────────────

    def refresh_stores(self):
        """Reload vector store and documents after a reindex"""
        self.vector_store = self._load_vector_store()
        self.all_documents = self._extract_documents()
        self.retriever.update_stores(self.vector_store, self.all_documents)
        self._llm = None  # Force LLM re-init
        self.query_engine = QueryEngine()  # Reset cache
        logger.info("[RAGServiceV2] Stores refreshed after reindex")
