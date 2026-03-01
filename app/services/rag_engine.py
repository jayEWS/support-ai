from datetime import datetime, timezone
from typing import List, Optional
import os
import asyncio
import aiofiles
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, CSVLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from app.core.config import settings
from app.core.logging import logger
from app.utils.retrieval_utils import HybridRetriever, reciprocal_rank_fusion, calculate_confidence
from app.utils.security_utils import SecurityEngine

from langchain.prompts import PromptTemplate

SUPPORT_PROMPT_TEMPLATE = """Anda adalah spesialis dukungan teknis profesional. Tugas Anda adalah memberikan solusi paling akurat dan TERBARU berdasarkan berbagai dokumen resmi yang disediakan.

Konteks Dokumen (termasuk tanggal unggah):
{context}

Pertanyaan Pengguna: {question}

Panduan Merespons:
1. PRIORITAS: Jika terdapat informasi yang berbeda antar dokumen, pilih informasi dari dokumen dengan TANGGAL UNGGAH TERBARU.
2. BAHASA ({target_language}): Gunakan nada bisnis formal yang sangat sopan.
3. AKURASI: Hanya gunakan informasi dari Konteks Dokumen. Jangan mengarang fitur.
4. SUMBER: Sebutkan nama file sumber dan tanggal informasinya di akhir jawaban.
5. TIDAK TAHU: Jika informasi tidak ditemukan secara lengkap, katakan: "Mohon maaf, informasi tersebut tidak ditemukan secara lengkap dalam panduan teknis terbaru kami. Mohon tunggu sejenak sementara saya menghubungkan Anda dengan spesialis produk kami."

Jawaban Profesional (Prioritaskan Langkah Terbaru):"""

from app.core.database import db_manager

class RAGEngine:
    def __init__(self):
        self._indexing_lock = asyncio.Lock()
        self.is_indexing = False
        
        # Embeddings
        if settings.EMBEDDINGS_TYPE == "openai":
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=settings.OPENAI_API_KEY,
                model=settings.EMBEDDINGS_MODEL_NAME,
                openai_api_base=settings.EMBEDDINGS_BASE_URL
            )
        else:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
                self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
            except Exception as e:
                logger.warning(f"Could not initialize local embeddings (missing dependencies?): {e}. Falling back to keyword-only search.")
                self.embeddings = None

        self.llm = ChatOpenAI(
            model_name=settings.MODEL_NAME, 
            temperature=0.1, 
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.AI_BASE_URL
        )
        self._background_tasks = set()
        task = asyncio.create_task(self._initialize_knowledge_base())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _initialize_knowledge_base(self):
        try:
            if os.path.exists(settings.DB_DIR) and os.path.exists(os.path.join(settings.DB_DIR, "index.faiss")) and self.embeddings:
                logger.info("✅ Loading existing Knowledge Base (FAISS)...")
                try:
                    self.vector_store = FAISS.load_local(settings.DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
                except Exception as e:
                    logger.error(f"Error loading FAISS, will re-index: {e}")
                    self.vector_store = None
                # Still run ingestion to populate BM25/all_documents with fresh dates
                await self.ingest_documents()
            else:
                logger.info("🔧 No index found. Starting initial ingestion...")
                await self.ingest_documents()
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")

    async def ingest_documents(self):
        """Async document ingestion with metadata enrichment (dates)."""
        if self._indexing_lock.locked():
            logger.warning("Indexing already in progress. Skipping.")
            return

        async with self._indexing_lock:
            self.is_indexing = True
            try:
                # Wrap the blocking ingestion logic in a separate method or use to_thread
                await asyncio.to_thread(self._sync_ingest_documents)
            except Exception as e:
                logger.error(f"Ingestion Error: {e}")
            finally:
                self.is_indexing = False

    def _sync_ingest_documents(self):
        """Synchronous part of document ingestion."""
        try:
            raw_docs = []
            if not os.path.exists(settings.KNOWLEDGE_DIR):
                os.makedirs(settings.KNOWLEDGE_DIR, exist_ok=True)
                return

            file_list = [f for f in os.listdir(settings.KNOWLEDGE_DIR) if f != ".gitkeep" and os.path.isfile(os.path.join(settings.KNOWLEDGE_DIR, f))]
            logger.info(f"Ingesting {len(file_list)} files with metadata tracking...")
            
            for file in file_list:
                self._process_single_file(file, raw_docs)

            if not raw_docs:
                logger.warning("No documents found to index.")
                self.vector_store = None
                self.all_documents = []
                self.hybrid_retriever = None
                return

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            self.all_documents = text_splitter.split_documents(raw_docs)
            
            if self.embeddings:
                self.vector_store = FAISS.from_documents(self.all_documents, self.embeddings)
                self.vector_store.save_local(settings.DB_DIR)
            else:
                self.vector_store = None
                logger.info("Skipping FAISS vector indexing (no embeddings available).")
            
            self.hybrid_retriever = HybridRetriever(self.all_documents)
            logger.info(f"✅ Re-indexing complete: {len(self.all_documents)} chunks with dates.")
        except Exception as e:
            logger.error(f"Ingestion Error: {e}")
        finally:
            pass # Lock is handled by async context manager

    def _process_single_file(self, file: str, raw_docs: list):
        """Helper to process a single file for ingestion."""
        file_path = os.path.join(settings.KNOWLEDGE_DIR, file)
        try:
            loader = self._get_loader_for_file(file_path)
            if not loader:
                return

            docs = loader.load()
            
            # Fetch metadata from DB to get the actual upload date
            db_meta = db_manager.get_knowledge_metadata(file)
            upload_date = db_meta.upload_date.strftime("%Y-%m-%d %H:%M") if db_meta and db_meta.upload_date else "2026-01-01"
            
            for d in docs:
                d.metadata['upload_date'] = upload_date
                d.metadata['filename'] = file
            
            raw_docs.extend(docs)
            db_manager.update_knowledge_status(file, "Indexed")
        except Exception as e:
            logger.error(f"Error loading {file}: {e}")
            db_manager.update_knowledge_status(file, f"Error: {str(e)[:50]}")

    def _get_loader_for_file(self, file_path: str):
        """Returns the appropriate loader based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf": return PyPDFLoader(file_path)
        if ext == ".docx": return Docx2txtLoader(file_path)
        if ext == ".csv": return CSVLoader(file_path)
        if ext in [".txt", ".md", ".json", ".log"]: return TextLoader(file_path, encoding='utf-8')
        
        # Fallback for unknown extensions
        try:
            return TextLoader(file_path, encoding='utf-8')
        except (UnicodeDecodeError, Exception):
            return None

    async def ingest_from_url(self, url: str, uploaded_by: str):
        try:
            loader = WebBaseLoader(url)
            data = await asyncio.to_thread(loader.load)
            if not data: raise ValueError("No content found at URL")
            
            filename = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_")[:100] + ".txt"
            file_path = os.path.join(settings.KNOWLEDGE_DIR, filename)
            
            content = "\n".join([d.page_content for d in data])
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(f"Source URL: {url}\n\n")
                await f.write(content)
            
            db_manager.save_knowledge_metadata(filename=filename, file_path=file_path, uploaded_by=uploaded_by, status="Processing")
            task = asyncio.create_task(self.ingest_documents())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return filename
        except Exception as e:
            logger.error(f"URL Ingestion Error: {e}")
            raise

    def delete_knowledge_document(self, filename: str):
        file_path = os.path.join(settings.KNOWLEDGE_DIR, filename)
        try:
            if os.path.exists(file_path): os.remove(file_path)
            db_manager.delete_knowledge_metadata(filename)
            task = asyncio.create_task(self.ingest_documents())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except Exception as e:
            logger.error(f"Failed to delete {filename}: {e}")
            raise e

    def delete_knowledge_documents(self, filenames: List[str]):
        errors = []
        for filename in filenames:
            try:
                file_path = os.path.join(settings.KNOWLEDGE_DIR, filename)
                if os.path.exists(file_path): os.remove(file_path)
                db_manager.delete_knowledge_metadata(filename)
            except Exception as e: errors.append(f"{filename}: {str(e)}")
        task = asyncio.create_task(self.ingest_documents())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        if errors: raise ValueError(f"Errors: {', '.join(errors)}")

    async def ask(self, query: str, user_id: str = "default", language: str = 'id') -> str:
        """Enterprise query flow with Version Awareness."""
        if SecurityEngine.check_jailbreak(query):
            return "Maaf, sistem mendeteksi aktivitas yang tidak diizinkan."
        
        masked_query = SecurityEngine.mask_pii(query)
        # db_manager.save_message(user_id, "user", masked_query) # Handled by callers now

        if not self.vector_store and not self.hybrid_retriever:
            return "Sistem sedang memproses data. Mohon tunggu."

        # Retrieve more chunks to ensure we catch latest versions
        k_val = 10
        top_context_docs = []
        
        if self.vector_store:
            vector_docs = self.vector_store.similarity_search(masked_query, k=k_val)
        else:
            vector_docs = []

        if self.hybrid_retriever:
            bm25_indices = self.hybrid_retriever.get_bm25_scores(masked_query, k=k_val)
            bm25_docs = [self.all_documents[i] for i in bm25_indices]
        else:
            bm25_docs = []

        if vector_docs and bm25_docs:
            top_context_docs = reciprocal_rank_fusion(vector_docs, bm25_docs)[:8]
        else:
            # Fallback to whichever is available
            top_context_docs = (vector_docs or bm25_docs)[:8]
        
        # Build context with explicit dates for the LLM to compare
        context_items = []
        for d in top_context_docs:
            fname = d.metadata.get('filename') or os.path.basename(d.metadata.get('source',''))
            udate = d.metadata.get('upload_date', 'Unknown Date')
            context_items.append(f"--- SOURCE: {fname} | UPLOADED: {udate} ---\n{d.page_content}")
        
        context_text = "\n\n".join(context_items)

        confidence = calculate_confidence(masked_query, context_text)
        if confidence < 0.05 and "status" not in masked_query.lower():
            return "Informasi tidak ditemukan secara memadai dalam basis pengetahuan kami. Mohon tunggu sejenak sementara saya menghubungkan Anda dengan spesialis produk kami."

        target_lang = "Bahasa Indonesia" if language == 'id' else "English"
        prompt = PromptTemplate(template=SUPPORT_PROMPT_TEMPLATE, input_variables=["context", "question", "target_language"])
        final_prompt = prompt.format(context=context_text, question=masked_query, target_language=target_lang)
        
        try:
            res = await self.llm.ainvoke(final_prompt)
            ai_response = res.content.strip()
            db_manager.save_message(user_id, "ai", ai_response)
            return ai_response
        except Exception as e:
            logger.error(f"Synthesis Error: {e}")
            return "Terjadi gangguan teknis saat menghubungi sistem pusat. Silakan coba lagi."

    async def get_analytics_trends(self) -> str:
        try:
            summaries = db_manager.get_recent_summaries(limit=20)
            if not summaries: return "Tidak ada data tiket yang cukup untuk analisis tren."
            res = await self.llm.ainvoke(f"Identifikasi 3 tren utama keluhan pelanggan dalam Bahasa Indonesia formal:\n" + "\n- ".join(summaries))
            return res.content.strip()
        except Exception: return "Analisis tren AI saat ini tidak tersedia."

    async def finalize_ticket(self, user_id: str, option: int = 1) -> str:
        messages = db_manager.get_messages(user_id)
        if not messages: return "Percakapan kosong."
        history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        try:
            if option == 1:
                res = await self.llm.ainvoke("Summarize concisely as JSON with 'summary' and 'priority' fields (Urgent, High, Medium, Low):\n" + history_text)
                import json
                data = json.loads(res.content.replace('```json','').replace('```','').strip())
                
                from app.services.sla_service import SLAService
                due_at = SLAService.calculate_due_date(data['priority'])
                
                ticket_id = db_manager.create_ticket(
                    user_id, 
                    data['summary'], 
                    history_text, 
                    priority=data['priority'],
                    due_at=due_at
                )
                return f"Tiket #{ticket_id} telah dibuat dengan prioritas {data['priority']}. Batas waktu pengerjaan: {due_at.strftime('%Y-%m-%d %H:%M')}."
            else:
                return "Sesi ditutup tanpa membuat tiket."
        except Exception as e: 
            logger.error(f"Finalize Ticket Error: {e}")
            return "Gagal membuat tiket secara otomatis. Mohon hubungi admin."

# No auto-instantiation here to avoid RuntimeWarnings during module import
rag_engine: Optional[RAGEngine] = None

def init_rag_engine() -> RAGEngine:
    global rag_engine
    rag_engine = RAGEngine()
    return rag_engine
