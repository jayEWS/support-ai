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

SUPPORT_PROMPT_TEMPLATE = """You are a friendly and helpful Edgeworks technical support assistant. Your job is to provide accurate, clear, and easy-to-understand solutions.

Document Context (including upload dates):
{context}

User Question: {question}

Response Guidelines:
1. IDENTITY: If a new user greets you, introduce yourself and ask for their Name, WhatsApp Number, Outlet Name, and their issue.
2. PRIORITY: If there is conflicting info between documents, use the document with the LATEST DATE.
3. LANGUAGE ({target_language}): Use a friendly yet professional tone.
4. ACCURACY: Use ONLY information from the document context. Do not make things up.
5. PROACTIVE: If the issue is unclear, ask what steps have been taken or request a screenshot.
6. SOURCE: Mention the source file name at the end of your answer.
7. UNKNOWN: If the info is not found, say: "I'm sorry, this information is not yet available in our guides. Could you share your Name and Outlet? We'll connect you with a team member who can help directly."
8. FORMAT: Use bullet points or numbered steps for instructions. Make it easy to follow.

Answer (concise, clear, helpful):"""

from app.core.database import db_manager
from app.services.gcs_service import get_gcs_service

class RAGEngine:
    def __init__(self):
        self._indexing_lock = asyncio.Lock()
        self.is_indexing = False
        
        # Embeddings
        if settings.EMBEDDINGS_TYPE == "vertex":
            try:
                from langchain_google_vertexai import VertexAIEmbeddings
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
                model_name = settings.VERTEX_AI_EMBEDDINGS_MODEL or "text-embedding-005"
                if project_id:
                    logger.info(f"RAGEngine using Vertex AI Embeddings: {model_name}")
                    self.embeddings = VertexAIEmbeddings(
                        model_name=model_name,
                        project=project_id,
                        location=location,
                    )
                else:
                    logger.warning("GCP_PROJECT_ID not set for Vertex AI Embeddings in RAGEngine, falling back to local")
                    self.embeddings = None
            except Exception as e:
                logger.warning(f"Vertex AI Embeddings init failed in RAGEngine: {e}, falling back to local")
                self.embeddings = None
        elif settings.EMBEDDINGS_TYPE == "openai":
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

        self.vector_store = None
        self.all_documents = []
        self.hybrid_retriever = None
        self.llm = self._init_llm()
        
        # Start background knowledge base initialization
        self._background_tasks = set()
        task = asyncio.create_task(self._initialize_knowledge_base())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _init_llm(self):
        """Initialize LLM with provider selection: vertex > gemini > groq > openai"""
        provider = getattr(settings, 'LLM_PROVIDER', os.getenv('LLM_PROVIDER', 'openai')).lower()
        
        if provider == "vertex":
            try:
                from langchain_google_vertexai import ChatVertexAI
                project_id = settings.GCP_PROJECT_ID or os.getenv("GCP_PROJECT_ID", "")
                location = settings.VERTEX_AI_LOCATION or os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
                model_name = settings.VERTEX_AI_MODEL or os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")
                if project_id:
                    logger.info(f"RAGEngine using Vertex AI: {model_name} (project={project_id})")
                    return ChatVertexAI(
                        model_name=model_name,
                        project=project_id,
                        location=location,
                        temperature=0.1,
                        convert_system_message_to_human=True,
                    )
                else:
                    logger.warning("GCP_PROJECT_ID not set for Vertex AI in RAGEngine, falling back")
            except Exception as e:
                logger.warning(f"Vertex AI init failed in RAGEngine: {e}, falling back to Gemini")
        
        if provider in ("gemini", "vertex"):  # vertex fallback chain
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = settings.GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", "")
                if api_key:
                    logger.info(f"RAGEngine using Gemini: {settings.GEMINI_MODEL_NAME}")
                    return ChatGoogleGenerativeAI(
                        model=settings.GEMINI_MODEL_NAME,
                        google_api_key=api_key,
                        temperature=0.1,
                        convert_system_message_to_human=True,
                    )
            except Exception as e:
                logger.warning(f"Gemini init failed in RAGEngine: {e}, falling back")
        
        if provider in ("groq", "vertex", "gemini"):  # fallback chain
            try:
                from langchain_groq import ChatGroq
                groq_key = os.getenv("GROQ_API_KEY", "")
                if groq_key:
                    logger.info(f"RAGEngine using Groq: {settings.MODEL_NAME}")
                    return ChatGroq(
                        model=settings.MODEL_NAME,
                        api_key=groq_key,
                        temperature=0.1,
                    )
            except Exception as e:
                logger.warning(f"Groq init failed in RAGEngine: {e}, falling back to OpenAI")
        
        logger.info(f"RAGEngine using OpenAI: {settings.MODEL_NAME}")
        return ChatOpenAI(
            model_name=settings.MODEL_NAME, 
            temperature=0.1, 
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.AI_BASE_URL
        )

    async def _initialize_knowledge_base(self):
        try:
            if os.path.exists(settings.DB_DIR) and os.path.exists(os.path.join(settings.DB_DIR, "index.faiss")) and self.embeddings:
                logger.info("[OK] Loading existing Knowledge Base (FAISS)...")
                try:
                    self.vector_store = FAISS.load_local(settings.DB_DIR, self.embeddings, allow_dangerous_deserialization=True)
                except Exception as e:
                    logger.error(f"Error loading FAISS, will re-index: {e}")
                    self.vector_store = None
                # Still run ingestion to populate BM25/all_documents with fresh dates
                await self.ingest_documents()
            else:
                logger.info("[INIT] No index found. Starting initial ingestion...")
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
            logger.info(f"[OK] Re-indexing complete: {len(self.all_documents)} chunks with dates.")
            
            # Phase 2: Sync knowledge files to GCS (non-blocking, best-effort)
            try:
                gcs = get_gcs_service()
                if gcs.enabled:
                    results = gcs.sync_local_to_gcs(settings.KNOWLEDGE_DIR)
                    synced = sum(1 for v in results.values() if v != "FAILED" and not v.startswith("_"))
                    logger.info(f"[GCS] Post-ingest sync: {synced} files synced to GCS")
            except Exception as gcs_err:
                logger.warning(f"[GCS] Post-ingest sync failed (non-critical): {gcs_err}")
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
            
            db_manager.save_knowledge_metadata(filename=filename, file_path=file_path, uploaded_by=uploaded_by, status="Processing", source_url=url)
            
            # Phase 2: Upload to GCS
            try:
                gcs = get_gcs_service()
                if gcs.enabled:
                    await gcs.async_upload_file(file_path, filename)
            except Exception as gcs_err:
                logger.warning(f"[GCS] URL ingest sync failed (non-critical): {gcs_err}")
            
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
            
            # Phase 2: Delete from GCS too
            try:
                gcs = get_gcs_service()
                if gcs.enabled:
                    gcs.delete_file(filename)
            except Exception as gcs_err:
                logger.warning(f"[GCS] Delete sync failed for {filename}: {gcs_err}")
            
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
        
        # Phase 2: Batch delete from GCS
        try:
            gcs = get_gcs_service()
            if gcs.enabled:
                gcs.delete_files(filenames)
        except Exception as gcs_err:
            logger.warning(f"[GCS] Batch delete sync failed: {gcs_err}")
        
        task = asyncio.create_task(self.ingest_documents())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        if errors: raise ValueError(f"Errors: {', '.join(errors)}")

    async def ask(self, query: str, user_id: str = "default", language: str = 'en') -> str:
        """Enterprise query flow with Version Awareness."""
        if SecurityEngine.check_jailbreak(query):
            return "Sorry, our system detected an unauthorized activity."
        
        masked_query = SecurityEngine.mask_pii(query)
        # db_manager.save_message(user_id, "user", masked_query) # Handled by callers now

        if not self.vector_store and not self.hybrid_retriever:
            return "The system is currently processing data. Please wait a moment."

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
            return "The information was not found sufficiently in our knowledge base. Please wait a moment while we connect you with our product specialist."

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
            return "A technical error occurred while connecting to the central system. Please try again."

    async def get_analytics_trends(self) -> str:
        try:
            summaries = db_manager.get_recent_summaries(limit=20)
            if not summaries: return "Not enough ticket data for trend analysis."
            res = await self.llm.ainvoke(f"Identify the top 3 customer complaint trends in English:\n" + "\n- ".join(summaries))
            return res.content.strip()
        except Exception: return "AI trend analysis is currently unavailable."

    async def finalize_ticket(self, user_id: str, option: int = 1) -> str:
        messages = db_manager.get_messages(user_id)
        if not messages: return "Conversation is empty."
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
                return f"Ticket #{ticket_id} has been created with priority {data['priority']}. Deadline: {due_at.strftime('%Y-%m-%d %H:%M')}."
            else:
                return "Session closed without creating a ticket."
        except Exception as e: 
            logger.error(f"Finalize Ticket Error: {e}")
            return "Failed to create ticket automatically. Please contact admin."

# No auto-instantiation here to avoid RuntimeWarnings during module import
rag_engine: Optional[RAGEngine] = None

def init_rag_engine() -> RAGEngine:
    global rag_engine
    rag_engine = RAGEngine()
    return rag_engine
