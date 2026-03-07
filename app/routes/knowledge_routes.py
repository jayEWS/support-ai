"""
Knowledge Base Management API Routes
====================================
Endpoints for uploading, editing, and deleting knowledge base documents.
Extracted from main.py. Fixes RAGEngine reference bugs.
Integrated Knowledge Base enhancement: rearranging elements, editing, and AI training.
"""

import os
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
from app.core.database import db_manager
from app.core.auth_deps import get_current_agent
from app.core.config import settings
from app.core.logging import logger
from app.utils.security import safe_filename, safe_path, validate_url_or_raise

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])

def _require_rag(request: Request):
    rag = getattr(request.app.state, 'rag_service', None)
    if not rag:
        raise HTTPException(status_code=503, detail="RAG Service not initialized")
    return rag

@router.get("/stats")
async def get_knowledge_stats(
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Knowledge base performance & file metrics."""
    db = db_manager
    all_kb = db.get_all_knowledge()
    rag_svc = _require_rag(request)
    rag_v2 = getattr(request.app.state, 'rag_service_v2', None)
    
    total_files = len(all_kb)
    indexed_count = sum(1 for k in all_kb if k.get('status') == 'Indexed')
    total_chunks = len(rag_svc.all_documents) if rag_svc and rag_svc.all_documents else 0
    has_vector_store = bool(rag_svc and rag_svc.vector_store)
    last_upload = all_kb[0]['upload_date'] if all_kb and all_kb[0].get('upload_date') else None
    
    return {
        "total_files": total_files,
        "indexed_files": indexed_count,
        "total_chunks": total_chunks,
        "vector_store_ready": has_vector_store,
        "last_upload": last_upload,
        "rag_v2": {
            "active": bool(rag_v2 and rag_v2.vector_store),
            "total_chunks": len(rag_v2.all_documents) if rag_v2 and rag_v2.all_documents else 0,
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
    rag.delete_knowledge_document(filename)
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
    rag.delete_knowledge_documents(filenames)
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
    db_manager.update_knowledge_status(sanitized, 'Processing')
    
    # Background task to re-index (AI Training feature)
    rag = _require_rag(request)
    background_tasks.add_task(rag.reload_knowledge)
    
    return {"status": "success", "message": "File updated and queued for re-indexing (AI Learning)"}
