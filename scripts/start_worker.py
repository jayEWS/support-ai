"""
Knowledge Base Indexer
======================
One-shot script to scan data/knowledge/, chunk and embed every document,
then upsert all vectors into Qdrant.

Usage (on VM, with venv activated):
    python scripts/start_worker.py
    python scripts/start_worker.py --force    # re-index even already-indexed files
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import logger

# ── Supported file extensions ──────────────────────────────────────────────────
TEXT_EXTS  = {".txt", ".md", ".csv"}
PDF_EXTS   = {".pdf"}
SUPPORTED  = TEXT_EXTS | PDF_EXTS

# ── Chunking settings ──────────────────────────────────────────────────────────
CHUNK_SIZE    = 800   # characters per chunk
CHUNK_OVERLAP = 150   # overlap to preserve context across boundaries


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _chunk_text(text: str, filename: str) -> list[dict]:
    """Split *text* into overlapping chunks, returning a list of chunk dicts."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start  = 0
    idx    = 0

    while start < len(text):
        end     = min(start + CHUNK_SIZE, len(text))
        content = text[start:end].strip()

        if content:
            chunk_id = hashlib.md5(f"{filename}:{idx}:{content[:50]}".encode()).hexdigest()[:12]
            chunks.append({
                "content":     content,
                "filename":    filename,
                "chunk_index": idx,
                "chunk_id":    chunk_id,
                "source":      filename,
                "category":    _guess_category(filename),
            })
            idx += 1

        if end == len(text):
            break
        start = end - CHUNK_OVERLAP

    return chunks


def _guess_category(filename: str) -> str:
    name = filename.lower()
    if "payment" in name or "fomopay" in name or "nets" in name:
        return "payment"
    if "voucher" in name or "promo" in name or "reward" in name:
        return "voucher"
    if "inventory" in name or "stock" in name:
        return "inventory"
    if "printer" in name or "kds" in name or "kiosk" in name:
        return "hardware"
    if "tax" in name or "iras" in name or "gst" in name:
        return "compliance"
    if "xero" in name or "accounting" in name:
        return "integration"
    return "general"


def _extract_text_from_pdf(path: Path) -> str:
    """Extract raw text from a PDF using pypdf (preferred) or pdfplumber."""
    text = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
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
        pass

    logger.warning(f"[Indexer] No PDF parser available for {path.name}. "
                   "Install pypdf:  pip install pypdf")
    return ""


def _read_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="replace")
    if ext in PDF_EXTS:
        return _extract_text_from_pdf(path)
    return ""


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Main indexing routine
# ──────────────────────────────────────────────────────────────────────────────

def run_indexing(force: bool = False):
    knowledge_dir = Path(settings.KNOWLEDGE_DIR)
    if not knowledge_dir.exists():
        logger.error(f"[Indexer] Knowledge dir not found: {knowledge_dir.resolve()}")
        sys.exit(1)

    # ── Connect to Qdrant ─────────────────────────────────────────────────────
    from app.services.qdrant_store import get_qdrant_store
    store = get_qdrant_store()

    if store.client is None:
        logger.error("[Indexer] Cannot connect to Qdrant. "
                     "Is it running?  sudo systemctl status qdrant")
        sys.exit(1)

    info = store.get_collection_info()
    logger.info(f"[Indexer] Qdrant collection '{store.collection_name}' — "
                f"{info.get('points_count', 0)} existing vectors")

    # ── Load embeddings model ─────────────────────────────────────────────────
    logger.info(f"[Indexer] Loading embeddings model: {settings.EMBEDDINGS_MODEL_NAME}")
    try:
        if settings.EMBEDDINGS_TYPE == "openai" and settings.OPENAI_API_KEY:
            from langchain_openai import OpenAIEmbeddings
            embed_model = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
            embed_dim   = 1536
        else:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
            except ImportError:
                from langchain_community.embeddings import HuggingFaceEmbeddings
            embed_model = HuggingFaceEmbeddings(model_name=settings.EMBEDDINGS_MODEL_NAME)
            embed_dim   = 384  # all-MiniLM-L6-v2

        # Patch collection vector size if it differs (happens on provider switch)
        if info.get("points_count", 0) == 0 and store.vector_size != embed_dim:
            logger.info(f"[Indexer] Re-creating collection with vector size {embed_dim}")
            store.vector_size = embed_dim
            store.client.delete_collection(store.collection_name)
            store._ensure_collection()

        store.vector_size = embed_dim
        logger.info(f"[Indexer] Embeddings ready (dim={embed_dim})")
    except Exception as e:
        logger.error(f"[Indexer] Failed to load embeddings: {e}")
        sys.exit(1)

    # ── Track processed files via a simple hash cache ────────────────────────
    cache_path = Path("data") / ".indexer_cache.txt"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    processed: dict[str, str] = {}  # filename → md5

    if cache_path.exists() and not force:
        for line in cache_path.read_text().splitlines():
            parts = line.split("||", 1)
            if len(parts) == 2:
                processed[parts[0]] = parts[1]

    # ── Discover files ────────────────────────────────────────────────────────
    files = sorted(
        p for p in knowledge_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )

    logger.info(f"[Indexer] Found {len(files)} supported file(s) in {knowledge_dir}")

    total_chunks   = 0
    indexed_files  = 0
    skipped_files  = 0
    failed_files   = 0

    for path in files:
        name   = path.name
        fhash  = _file_hash(path)

        if not force and processed.get(name) == fhash:
            logger.debug(f"[Indexer] SKIP (unchanged): {name}")
            skipped_files += 1
            continue

        logger.info(f"[Indexer] Processing: {name}")

        try:
            raw_text = _read_file(path)
            if not raw_text.strip():
                logger.warning(f"[Indexer] No text extracted from {name}, skipping.")
                failed_files += 1
                continue

            chunks = _chunk_text(raw_text, name)
            if not chunks:
                logger.warning(f"[Indexer] No chunks for {name}, skipping.")
                failed_files += 1
                continue

            # Embed in batches of 64
            BATCH = 64
            for i in range(0, len(chunks), BATCH):
                batch    = chunks[i : i + BATCH]
                texts    = [c["content"] for c in batch]
                vectors  = embed_model.embed_documents(texts)

                # Build LangChain-like Document objects for QdrantVectorStore.add_documents
                class _Doc:
                    def __init__(self, content, meta):
                        self.page_content = content
                        self.metadata     = meta

                docs = [_Doc(c["content"], {
                    "filename":    c["filename"],
                    "chunk_index": c["chunk_index"],
                    "chunk_id":    c["chunk_id"],
                    "source":      c["source"],
                    "category":    c["category"],
                }) for c in batch]

                store.add_documents(docs, vectors)

            total_chunks += len(chunks)
            indexed_files += 1
            processed[name] = fhash
            logger.info(f"[Indexer]   ✓  {name}  →  {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"[Indexer] Failed to index {name}: {e}")
            failed_files += 1

    # ── Save hash cache ───────────────────────────────────────────────────────
    cache_path.write_text("\n".join(f"{k}||{v}" for k, v in processed.items()))

    # ── Summary ───────────────────────────────────────────────────────────────
    info_after = store.get_collection_info()
    logger.info("=" * 60)
    logger.info(f"[Indexer] DONE — "
                f"indexed={indexed_files}, skipped={skipped_files}, "
                f"failed={failed_files}, chunks_added={total_chunks}")
    logger.info(f"[Indexer] Qdrant total vectors: {info_after.get('points_count', '?')}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index knowledge base into Qdrant")
    parser.add_argument("--force", action="store_true",
                        help="Re-index all files, ignoring the change cache")
    args = parser.parse_args()
    run_indexing(force=args.force)