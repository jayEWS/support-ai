import os
import asyncio
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from langchain_groq import ChatGroq
from app.core.config import settings
from app.core.database import db_manager
from app.core.logging import logger, LogLatency
from app.schemas.schemas import RAGResponse
from app.services.advanced_retriever import AdvancedRetriever
from app.services.qdrant_store import get_qdrant_store
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ── Chunking settings (shared with start_worker.py) ───────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
TEXT_EXTS     = {".txt", ".md", ".csv", ".json", ".log", ".text"}
PDF_EXTS      = {".pdf"}
DOC_EXTS      = {".doc", ".docx"}
SUPPORTED     = TEXT_EXTS | PDF_EXTS | DOC_EXTS

class RAGService:
    def __init__(self):
        # ✅ FIXED: Use Groq embeddings API or fallback to local embeddings
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
            # ✅ FIXED: Skip OpenAI embeddings (using Groq LLM instead)
            if settings.EMBEDDINGS_TYPE == "openai":
                logger.warning("OpenAI embeddings not available. Using HuggingFace fallback.")
            
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
    async def query(self, text: str, threshold: float = 0.5, use_hybrid: bool = True, language: str = 'en', system_prompt: Optional[str] = None, conversation_history: Optional[List[Dict]] = None) -> RAGResponse:
        logger.info(f"RAG Query: {text[:50]}")
        try:
            # 0. Empty/Media Message Check
            if not text or text.strip() == "" or text.startswith("["):
                ans = "I received your file/media. How can I help you with it?"
                if language == 'id': ans = "Saya telah menerima file/media Anda. Ada yang bisa saya bantu terkait hal tersebut?"
                elif language == 'zh': ans = "我收到了您的文件/媒体。有什么我可以帮您的吗？"
                return RAGResponse(answer=ans, confidence=1.0, source_documents=[], retrieval_method="media_bypass")

            # 1. Greeting Check
            if self._is_greeting(text):
                logger.info("Greeting detected")
                return await self._handle_greeting(text, language)

            # 2. Cache Check (skip cache when conversation context present)
            cache_key = f"{text.lower().strip()}_{language}_{hash(system_prompt) if system_prompt else 'default'}"
            if not conversation_history and cache_key in self._cache:
                if (datetime.now().timestamp() - self._cache[cache_key]['timestamp']) < self._cache_ttl:
                    return self._cache[cache_key]['response']

            # 3. Smart Query Expansion — enrich short/vague queries
            expanded_query = self._expand_query(text, conversation_history)
            
            # --- Power Upgrade: Multi-Query Generation ---
            # Generate 2 additional sub-queries to capture different perspectives
            sub_queries = await self._generate_sub_queries(text, expanded_query, language)

            # 4. Retrieval with expanded query and sub-queries
            retrieval_result = await self.retriever.retrieve(
                original_query=text,
                expanded_query=expanded_query if expanded_query != text else None,
                sub_queries=sub_queries,
                k_final=8, # Increase results for better context
                intent=self._detect_category(text) # Pass intent for adaptive filtering
            )
            context = retrieval_result.context_text
            confidence = retrieval_result.confidence

            # 5. Build structured LLM prompt
            llm_svc = self._llm_service
            prompt = self._build_llm_prompt(
                system_prompt=system_prompt,
                context=context,
                question=text,
                language=language,
                conversation_history=conversation_history,
                confidence=confidence
            )

            if llm_svc and llm_svc.llm:
                res = await asyncio.wait_for(llm_svc.llm.ainvoke(prompt), timeout=20.0)
                answer = self._sanitize_text(res.content)
            else:
                if context and context.strip():
                    answer = f"Based on our knowledge base:\n\n{context[:1500]}"
                else:
                    answer = "I found related information but I'm unable to generate a detailed response right now. Please try again later or contact a support agent."
                logger.warning("No LLM provider available — returning raw context or fallback")

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

            if not conversation_history:
                self._cache[cache_key] = {'response': result, 'timestamp': datetime.now().timestamp()}
            return result

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return RAGResponse(answer="I'm sorry, I'm having trouble connecting to my brain. Please try again later.", confidence=0, source_documents=[])

    # ── Query Expansion ──────────────────────────────────────────────────────

    def _expand_query(self, query: str, conversation_history: Optional[List[Dict]] = None) -> str:
        """
        Expand short or ambiguous queries using conversation context.
        E.g. "how to fix it?" → "how to fix printer not printing receipt POS"
        """
        words = query.strip().split()

        # Only expand if query is very short or contains pronouns
        pronouns = {'it', 'this', 'that', 'they', 'them', 'its', 'itu', 'ini', 'nya'}
        needs_expansion = len(words) <= 4 or bool(set(w.lower() for w in words) & pronouns)

        if not needs_expansion:
            return query

        if not conversation_history:
            return query

        # Pull topic keywords from last 3 messages
        recent_texts = []
        for msg in conversation_history[-3:]:
            content = msg.get('content', '')
            if content and len(content) > 5:
                recent_texts.append(content)

        if not recent_texts:
            return query

        # Extract key nouns/topics from conversation (simple keyword extraction)
        import re
        all_words = []
        stop = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'to', 'of', 'in',
                'for', 'on', 'with', 'at', 'by', 'it', 'this', 'that', 'i', 'you', 'we', 'my',
                'your', 'can', 'do', 'did', 'have', 'has', 'had', 'will', 'would', 'could',
                'should', 'may', 'not', 'yes', 'no', 'ok', 'hi', 'hello', 'thanks', 'thank',
                'dan', 'di', 'ke', 'dari', 'yang', 'ini', 'itu', 'untuk', 'dengan', 'ada',
                'pada', 'atau', 'tidak', 'sudah', 'bisa', 'akan', 'saya', 'kami'}
        for text in recent_texts:
            for w in re.split(r'\W+', text.lower()):
                if len(w) > 2 and w not in stop:
                    all_words.append(w)

        # Get top-5 most frequent topic words
        from collections import Counter
        top_keywords = [w for w, _ in Counter(all_words).most_common(5)]

        if top_keywords:
            expanded = f"{query} ({' '.join(top_keywords)})"
            logger.info(f"[QueryExpansion] '{query}' → '{expanded}'")
            return expanded

        return query

    # ── Structured LLM Prompt Builder ────────────────────────────────────────

    def _build_llm_prompt(self, system_prompt: Optional[str], context: str, question: str,
                          language: str, conversation_history: Optional[List[Dict]],
                          confidence: float) -> str:
        """
        Build a well-structured prompt that grounds the LLM in documents,
        includes conversation history for context, and handles low-confidence
        scenarios gracefully.
        """
        parts = []

        # 1. System prompt (persona)
        if system_prompt:
            parts.append(system_prompt)

        # 2. Conversation history (last 6 messages for context)
        if conversation_history:
            recent = conversation_history[-6:]
            history_lines = []
            for msg in recent:
                role = msg.get('role', 'user').upper()
                content = msg.get('content', '')[:300]  # Truncate long messages
                if content.strip():
                    history_lines.append(f"[{role}]: {content}")
            if history_lines:
                parts.append(f"CONVERSATION HISTORY:\n" + "\n".join(history_lines))

        # 3. Document context with confidence signal
        if context and context.strip():
            parts.append(f"DOCUMENT CONTEXT (retrieval confidence: {confidence:.0%}):\n{context}")
        else:
            parts.append("DOCUMENT CONTEXT: No relevant documents found.")

        # 4. Confidence-aware instruction
        if confidence < 0.3:
            parts.append(
                "⚠️ LOW CONFIDENCE: The retrieved documents may not be relevant. "
                "Be honest that you don't have specific information. Offer general "
                "troubleshooting advice and suggest contacting a human agent if needed."
            )

        # 5. The user's question
        parts.append(f"USER QUESTION: {question}")

        # 6. Generation instruction
        parts.append(
            f"Reply in the same language as the user's question. "
            f"Be natural, concise, and helpful. Base your answer on the DOCUMENT CONTEXT when available."
        )

        return "\n\n".join(parts)

    # ── Knowledge Management Methods ─────────────────────────────────────────

    @property
    def all_documents(self) -> list:
        """Return a list of indexed chunks (used by /stats endpoint)."""
        if not self.vector_store or not self.vector_store.client:
            return []
        try:
            info = self.vector_store.get_collection_info()
            return [None] * info.get("points_count", 0)  # lightweight proxy
        except Exception:
            return []

    async def reload_knowledge(self):
        """
        Re-index ALL files in data/knowledge/ into Qdrant.
        Called by Train AI / reindex endpoint and after uploads.
        """
        knowledge_dir = Path(settings.KNOWLEDGE_DIR)
        if not knowledge_dir.exists():
            logger.warning(f"[RAG] Knowledge dir not found: {knowledge_dir}")
            return

        store = self.vector_store
        if not store or not store.client:
            logger.error("[RAG] Cannot reload — Qdrant store not available")
            return

        logger.info("[RAG] Starting full knowledge reload...")

        # Clear existing vectors and rebuild
        store.clear_collection()

        files = sorted(
            p for p in knowledge_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED
        )

        if not files:
            logger.warning("[RAG] No supported files found in knowledge dir")
            return

        total_chunks = 0
        for path in files:
            try:
                raw_text = self._read_file(path)
                if not raw_text.strip():
                    db_manager.update_knowledge_status(path.name, "Empty")
                    continue

                chunks = self._chunk_text(raw_text, path.name)
                if not chunks:
                    continue

                # Embed in batches
                BATCH = 64
                for i in range(0, len(chunks), BATCH):
                    batch = chunks[i:i + BATCH]
                    texts = [c["content"] for c in batch]
                    vectors = self.embeddings.embed_documents(texts)

                    class _Doc:
                        def __init__(self, content, meta):
                            self.page_content = content
                            self.metadata = meta

                    docs = [_Doc(c["content"], {
                        "filename": c["filename"],
                        "chunk_index": c["chunk_index"],
                        "chunk_id": c["chunk_id"],
                        "source": c["source"],
                        "category": c["category"],
                    }) for c in batch]

                    store.add_documents(docs, vectors)

                total_chunks += len(chunks)
                db_manager.update_knowledge_status(path.name, "Indexed")
                logger.info(f"[RAG] Indexed: {path.name} → {len(chunks)} chunks")

            except Exception as e:
                logger.error(f"[RAG] Failed to index {path.name}: {e}")
                db_manager.update_knowledge_status(path.name, "Error")

        # Rebuild the retriever with fresh data
        self.retriever = AdvancedRetriever(
            vector_store=self.vector_store,
            documents=[],
            embeddings=self.embeddings,
        )

        info = store.get_collection_info()
        logger.info(f"[RAG] Reload complete — {total_chunks} chunks, "
                     f"Qdrant vectors: {info.get('points_count', 0)}")

    async def ingest_from_url(self, url: str, uploaded_by: str = "System") -> str:
        """Fetch content from a URL, save as a KB document, and index it."""
        import re
        try:
            import httpx
        except ImportError:
            import urllib.request
            # Fallback for missing httpx
            class _HttpxFallback:
                @staticmethod
                async def get(u, **kw):
                    class _Resp:
                        def __init__(self, text, code):
                            self.text = text
                            self.status_code = code
                    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                    resp = urllib.request.urlopen(req, timeout=30)
                    return _Resp(resp.read().decode("utf-8", errors="replace"), resp.status)
            httpx = _HttpxFallback()

        logger.info(f"[RAG] Ingesting from URL: {url}")

        # Fetch
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code} fetching {url}")

        # Extract text (strip HTML tags)
        text = resp.text
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 50:
            raise Exception("URL content too short or empty after extraction")

        # Save as file
        from app.utils.security import safe_filename
        domain = re.sub(r'https?://(www\.)?', '', url).split('/')[0].replace('.', '_')
        filename = safe_filename(f"url_{domain}_{hashlib.md5(url.encode()).hexdigest()[:8]}.txt")
        dest_path = os.path.join(settings.KNOWLEDGE_DIR, filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(f"Source URL: {url}\nFetched: {datetime.now().isoformat()}\n\n{text}")

        db_manager.save_knowledge_metadata(
            filename=filename,
            file_path=dest_path,
            uploaded_by=uploaded_by,
            status="Processing",
            source_url=url,
        )

        # Index immediately
        await self.reload_knowledge()
        return filename

    def delete_knowledge_document(self, filename: str):
        """Delete a single KB document from disk, DB, and trigger re-index."""
        self._delete_file(filename)
        db_manager.delete_knowledge_metadata(filename)
        logger.info(f"[RAG] Deleted: {filename}")

    def delete_knowledge_documents(self, filenames: list):
        """Delete multiple KB documents."""
        for f in filenames:
            self._delete_file(f)
            db_manager.delete_knowledge_metadata(f)
        logger.info(f"[RAG] Batch deleted {len(filenames)} file(s)")

    def _delete_file(self, filename: str):
        """Safely delete a KB file from disk."""
        from app.utils.security import safe_filename, safe_path
        sanitized = safe_filename(filename)
        file_path = safe_path(settings.KNOWLEDGE_DIR, sanitized)
        if os.path.exists(file_path):
            os.remove(file_path)

    # ── File Reading / Chunking Helpers ────────────────────────────────────────

    @staticmethod
    def _read_file(path: Path) -> str:
        """Extract text from a file based on extension."""
        ext = path.suffix.lower()
        if ext in TEXT_EXTS:
            return path.read_text(encoding="utf-8", errors="replace")
        if ext in PDF_EXTS:
            return RAGService._extract_pdf(path)
        if ext in DOC_EXTS:
            return RAGService._extract_docx(path)
        return ""

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
            return text
        except ImportError:
            pass
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
            return text
        except ImportError:
            logger.warning(f"No PDF parser for {path.name}. Install pypdf.")
        return ""

    @staticmethod
    def _extract_docx(path: Path) -> str:
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            logger.warning(f"python-docx not installed, cannot read {path.name}")
        except Exception as e:
            logger.error(f"DOCX extraction failed for {path.name}: {e}")
        return ""

    @staticmethod
    def _chunk_text(text: str, filename: str) -> list:
        """
        Paragraph-aware chunking: splits on natural boundaries (headers,
        double-newlines, numbered sections) instead of fixed character offsets.
        Preserves semantic coherence within each chunk.
        """
        import re
        text = text.strip()
        if not text:
            return []

        # Step 1: Split into semantic paragraphs/sections
        # Split on markdown headers, numbered sections, or double newlines
        section_splits = re.split(
            r'(?:\n\s*\n)|'            # Double newline (paragraph break)
            r'(?=\n#{1,3}\s)|'         # Markdown headers
            r'(?=\n\d+\.\s)|'          # Numbered list items at root level
            r'(?=\n-{3,})|'            # Horizontal rules
            r'(?=\n={3,})',            # Section separators
            text
        )

        # Clean up and filter empty sections
        paragraphs = [p.strip() for p in section_splits if p and p.strip()]

        # Step 2: Merge small paragraphs and split oversized ones
        chunks = []
        current_chunk = ""
        idx = 0

        for para in paragraphs:
            # If adding this paragraph keeps us under the limit, merge
            if len(current_chunk) + len(para) + 2 <= CHUNK_SIZE:
                current_chunk = f"{current_chunk}\n\n{para}".strip() if current_chunk else para
            else:
                # Save current chunk if it has content
                if current_chunk:
                    chunk_id = hashlib.md5(f"{filename}:{idx}:{current_chunk[:50]}".encode()).hexdigest()[:12]
                    chunks.append({
                        "content": current_chunk,
                        "filename": filename,
                        "chunk_index": idx,
                        "chunk_id": chunk_id,
                        "source": filename,
                        "category": RAGService._guess_category(filename),
                    })
                    idx += 1

                # Handle oversized paragraphs — split with overlap
                if len(para) > CHUNK_SIZE:
                    start = 0
                    while start < len(para):
                        # Try to break at sentence boundary
                        end = min(start + CHUNK_SIZE, len(para))
                        if end < len(para):
                            # Look for sentence boundary near the end
                            for sep in ['. ', '.\n', '! ', '? ', '\n']:
                                boundary = para[start:end].rfind(sep)
                                if boundary > CHUNK_SIZE * 0.5:
                                    end = start + boundary + len(sep)
                                    break

                        content = para[start:end].strip()
                        if content:
                            chunk_id = hashlib.md5(f"{filename}:{idx}:{content[:50]}".encode()).hexdigest()[:12]
                            chunks.append({
                                "content": content,
                                "filename": filename,
                                "chunk_index": idx,
                                "chunk_id": chunk_id,
                                "source": filename,
                                "category": RAGService._guess_category(filename),
                            })
                            idx += 1

                        if end >= len(para):
                            break
                        start = max(end - CHUNK_OVERLAP, start + 1)

                    current_chunk = ""
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk:
            chunk_id = hashlib.md5(f"{filename}:{idx}:{current_chunk[:50]}".encode()).hexdigest()[:12]
            chunks.append({
                "content": current_chunk,
                "filename": filename,
                "chunk_index": idx,
                "chunk_id": chunk_id,
                "source": filename,
                "category": RAGService._guess_category(filename),
            })

        return chunks

    @staticmethod
    def _guess_category(filename: str) -> str:
        name = filename.lower()
        if any(w in name for w in ("payment", "fomopay", "nets")):
            return "payment"
        if any(w in name for w in ("voucher", "promo", "reward")):
            return "voucher"
        if any(w in name for w in ("inventory", "stock")):
            return "inventory"
        if any(w in name for w in ("printer", "kds", "kiosk")):
            return "hardware"
        if any(w in name for w in ("tax", "iras", "gst")):
            return "compliance"
        if any(w in name for w in ("xero", "accounting")):
            return "integration"
        return "general"

    def _is_greeting(self, text: str) -> bool:
        greetings = {"hi", "hello", "hey", "halo", "hai", "good", "morning", "afternoon", "pm", "am", "pagi", "siang"}
        words = set(text.lower().strip().split())
        return len(words) <= 3 and bool(words.intersection(greetings))

    async def _handle_greeting(self, text: str, language: str) -> RAGResponse:
        fallbacks = {"en": "Hello! How can I help you?", "id": "Halo! Ada yang bisa saya bantu?", "zh": "你好！有什么我可以帮你的吗？"}
        ans = fallbacks.get(language, fallbacks["en"])
        return RAGResponse(answer=ans, confidence=1.0, source_documents=[], retrieval_method="greeting")

    def _get_llm(self):
        # ✅ FIXED: Use Groq ChatGroq instead of OpenAI
        return ChatGroq(model=settings.MODEL_NAME, api_key=settings.GROQ_API_KEY, temperature=0)

    async def _generate_sub_queries(self, query: str, expanded: str, lang: str) -> List[str]:
        """Generate 2 multi-perspective search queries for better coverage (Free Power Upgrade)."""
        if len(query.split()) < 3: return []
        
        try:
            # We use a very simplified prompt to avoid too much overhead but gain "Multi-Query" RAG power
            # This mimics what advanced apps like Perplexity or Sidekick do.
            if self._llm_service and self._llm_service.llm:
                prompt = (
                    f"Given this support query: '{query}', generate 2 alternative search keywords in {lang} "
                    f"that would help find technical documentation. Return only the strings separated by pipe."
                )
                res = await asyncio.wait_for(self._llm_service.llm.ainvoke(prompt), timeout=1.5)
                queries = [q.strip() for q in res.content.split('|') if q.strip()]
                return queries[:2]
        except Exception:
            return []
        return []

    @classmethod
    def _detect_category(cls, query: str) -> str:
        # Simple local detection for RAG hints
        q = query.lower()
        if any(w in q for w in ["how", "cara", "step"]): return "how_to"
        if any(w in q for w in ["error", "rusak", "fail", "fix"]): return "troubleshooting"
        return "simple_faq"
