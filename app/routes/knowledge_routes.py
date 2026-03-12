"""
Knowledge Base Management API Routes
====================================
Endpoints for uploading, editing, and deleting knowledge base documents.
Extracted from main.py. Fixes RAGEngine reference bugs.
Integrated Knowledge Base enhancement: rearranging elements, editing, and AI training.
"""

import os
import asyncio
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
from app.core.database import db_manager
from app.core.auth_deps import get_current_agent
from app.core.config import settings
from app.core.logging import logger
from app.utils.security import safe_filename, safe_path, validate_url_or_raise, validate_knowledge_file
from app.utils.async_db import run_sync

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])

def _require_rag(request: Request):
    rag = getattr(request.app.state, 'rag_service', None)
    if not rag:
        raise HTTPException(status_code=503, detail="RAG Service not initialized")
    return rag

@router.get("", response_model=List[dict])
async def list_knowledge(
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """List all knowledge base documents with metadata."""
    return await run_sync(db_manager.get_all_knowledge)


# Maximum file size for knowledge uploads (20 MB)
MAX_KNOWLEDGE_FILE_SIZE = 20 * 1024 * 1024
# Maximum file size for chat uploads (10 MB)
MAX_CHAT_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload_knowledge(
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)],
    files: List[UploadFile] = File(...)
):
    """Upload one or more documents to the Knowledge Base and trigger re-indexing."""
    try:
        saved_files = []
        for file in files:
            sanitized = validate_knowledge_file(file.filename)
            file_bytes = await file.read()

            # P0 Fix: Enforce file size limit to prevent resource exhaustion
            if len(file_bytes) > MAX_KNOWLEDGE_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{file.filename}' exceeds maximum size of {MAX_KNOWLEDGE_FILE_SIZE // (1024*1024)}MB"
                )

            dest_path = os.path.join(settings.KNOWLEDGE_DIR, sanitized)       
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(file_bytes)

            await run_sync(
                db_manager.save_knowledge_metadata,
                filename=sanitized,
                file_path=dest_path,
                uploaded_by=agent["user_id"],
                status="Processing"
            )
            saved_files.append(sanitized)
        rag = getattr(request.app.state, 'rag_service', None)
        if rag and hasattr(rag, 'reload_knowledge'):
            asyncio.create_task(rag.reload_knowledge())

        return {"status": "success", "files": saved_files}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Knowledge upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/paste")
async def paste_knowledge(
    request: Request,
    background_tasks: BackgroundTasks,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Save pasted text directly as a .txt knowledge document."""
    data = await request.json()
    title: str = data.get("title", "").strip()
    content: str = data.get("content", "").strip()
    overwrite: bool = data.get("overwrite", False)

    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not content or len(content) < 10:
        raise HTTPException(status_code=400, detail="Content is too short (minimum 10 characters)")

    # Sanitise title → filename
    sanitized_title = safe_filename(title if title.endswith(".txt") else f"{title}.txt")
    dest_path = safe_path(settings.KNOWLEDGE_DIR, sanitized_title)

    if os.path.exists(dest_path) and not overwrite:
        return JSONResponse(
            status_code=409,
            content={
                "error": "exists",
                "message": f'"{sanitized_title}" already exists. Overwrite?',
                "filename": sanitized_title
            }
        )

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)

    await run_sync(
        db_manager.save_knowledge_metadata,
        filename=sanitized_title,
        file_path=dest_path,
        uploaded_by=agent["user_id"],
        status="Processing"
    )

    rag = _require_rag(request)
    background_tasks.add_task(rag.reload_knowledge)

    return {"status": "success", "filename": sanitized_title, "size": len(content)}


@router.post("/reindex")
async def reindex_knowledge(
    request: Request,
    background_tasks: BackgroundTasks,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Trigger a full re-index of the Knowledge Base into the vector store."""
    rag = _require_rag(request)
    rag_v2 = getattr(request.app.state, 'rag_service_v2', None)

    background_tasks.add_task(rag.reload_knowledge)
    if rag_v2 and hasattr(rag_v2, 'reload_knowledge'):
        background_tasks.add_task(rag_v2.reload_knowledge)

    return {"status": "success", "message": "Re-indexing queued. The AI knowledge base will update shortly."}


@router.get("/stats")
async def get_knowledge_stats(
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Knowledge base performance & file metrics."""
    db = db_manager
    all_kb = await run_sync(db.get_all_knowledge)
    rag_svc = getattr(request.app.state, 'rag_service', None)
    rag_v2 = getattr(request.app.state, 'rag_service_v2', None)
    
    total_files = len(all_kb)
    indexed_count = sum(1 for k in all_kb if k.get('status') == 'Indexed')
    total_chunks = len(rag_svc.all_documents) if rag_svc and hasattr(rag_svc, 'all_documents') and rag_svc.all_documents else 0
    has_vector_store = bool(rag_svc and getattr(rag_svc, 'vector_store', None) and getattr(rag_svc.vector_store, 'client', None))
    last_upload = all_kb[0]['upload_date'] if all_kb and all_kb[0].get('upload_date') else None
    
    return {
        "total_files": total_files,
        "indexed_files": indexed_count,
        "total_chunks": total_chunks,
        "vector_store_ready": has_vector_store,
        "last_upload": last_upload,
        "rag_v2": {
            "active": bool(rag_v2 and getattr(rag_v2, 'vector_store', None)),
            "total_chunks": len(rag_v2.all_documents) if rag_v2 and hasattr(rag_v2, 'all_documents') and rag_v2.all_documents else 0,
            "engine": "shopify_advanced_rag"
        }
    }

@router.post("/ingest-url")
async def ingest_knowledge_from_url(
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Ingest knowledge base from URL (Admin Only)."""
    data = await request.json()
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    validate_url_or_raise(url)
    rag = _require_rag(request)
    
    # RAGService now handles the ingestion logic directly
    filename = await rag.ingest_from_url(url, uploaded_by=agent["user_id"])
    return {"status": "success", "filename": filename, "message": f"Content from {url} ingested"}

@router.delete("/{filename}")
async def delete_knowledge(
    filename: str,
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Delete a document from KB."""
    rag = _require_rag(request)
    # The original rag_eng reference in main.py was a bug, we use rag_service 
    await run_sync(rag.delete_knowledge_document, filename)
    return {"status": "success", "message": f"Deleted {filename}"}
@router.post("/batch-delete")
async def batch_delete_knowledge(
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Delete multiple documents from KB."""
    data = await request.json()
    filenames = data.get("filenames", [])
    if not filenames:
        raise HTTPException(status_code=400, detail="No filenames provided")  

    rag = _require_rag(request)
    await run_sync(rag.delete_knowledge_documents, filenames)
    return {"status": "success", "message": f"Deleted {len(filenames)} files"}
@router.get("/{filename}/content")
async def get_knowledge_content(
    filename: str, 
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Get raw content of a text-based document for editing (Objective: KB Enrichment)."""
    sanitized = safe_filename(filename)
    file_path = safe_path(settings.KNOWLEDGE_DIR, sanitized)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    if not sanitized.lower().endswith(('.txt', '.md', '.text', '.json', '.csv', '.log')):
        raise HTTPException(status_code=400, detail="Only text-based files can be viewed/edited")
    
    # Limit size for editing
    stats = os.stat(file_path)
    if stats.st_size > 5 * 1024 * 1024:
         raise HTTPException(status_code=400, detail="File is too large to edit in browser")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"filename": sanitized, "content": content}

@router.post("/{filename}/update")
async def update_knowledge_content(
    filename: str, 
    request: Request,
    background_tasks: BackgroundTasks,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Update file content and trigger AI re-indexing (Objective: KB Enrichment)."""
    data = await request.json()
    content = data.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="Content is required")
        
    sanitized = safe_filename(filename)
    file_path = safe_path(settings.KNOWLEDGE_DIR, sanitized)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    # Save content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Update DB status
    await run_sync(db_manager.update_knowledge_status, sanitized, 'Processing')

    # Background task to re-index (AI Training feature)
    rag = _require_rag(request)
    background_tasks.add_task(rag.reload_knowledge)
    
    return {"status": "success", "message": "File updated and queued for re-indexing (AI Learning)"}
