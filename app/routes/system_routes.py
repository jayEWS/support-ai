"""
System and Management API Routes
================================
Endpoints for settings, macros, and miscellaneous system tools.
Extracted from main.py. High security (Admin Only) for settings.
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form, UploadFile, File, BackgroundTasks
from app.core.database import db_manager
from app.core.auth_deps import get_current_agent
from app.core.config import settings
from app.core.logging import logger
import re

router = APIRouter(prefix="/api/system", tags=["System"])

def _get_db():
    if db_manager is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db_manager

@router.get("/settings")
async def get_settings(agent: Annotated[dict, Depends(get_current_agent)]):
    """Get all system settings (admin only)."""
    if agent.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    db = _get_db()
    all_settings = db.get_all_settings()
    # Set defaults if not yet configured
    defaults = {
        "ticket_notify_enabled": "true",
        "ticket_notify_email": "jay@edgeworks.com.sg",
        "ticket_notify_cc": "",
    }
    for k, v in defaults.items():
        if k not in all_settings:
            all_settings[k] = v
    return all_settings

@router.post("/settings")
async def save_settings(data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    """Save system settings (admin only)."""
    if agent.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    db = _get_db()
    allowed_keys = {"ticket_notify_enabled", "ticket_notify_email", "ticket_notify_cc"}
    saved = []
    for k, v in data.items():
        if k in allowed_keys:
            db.set_setting(k, str(v))
            saved.append(k)
    logger.info(f"Settings updated by {agent.get('username')}: {saved}")
    return {"status": "ok", "saved": saved}

@router.post("/recording/upload")
async def upload_recording(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    agent: Annotated[dict, Depends(get_current_agent)] = None # Optional auth for recording?
):
    """Handle screen recording uploads from the portal."""
    sanitized_name = f"rec_{user_id}_{file.filename}"
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    from app.utils.file_handler import save_upload
    metadata = save_upload(file_bytes, sanitized_name, destination="chat")
    
    db = _get_db()
    db.save_message(user_id=user_id, role="user", content=f"📹 Screen Recording: {metadata['url']}")
    
    return {"status": "ok", "url": metadata["url"], "filename": metadata["stored_name"]}

@router.get("/macros")
async def list_macros(agent: Annotated[dict, Depends(get_current_agent)]):
    """List helper macros for ticket replies."""
    db = _get_db()
    return db.get_all_macros()

@router.get("/analytics")
async def get_analytics(agent: Annotated[dict, Depends(get_current_agent)]):
    """Get system-wide ticket analytics and AI performance."""
    db = _get_db()
    metrics = db.get_ticket_metrics()
    return {
        "metrics": metrics,
        "priority_distribution": {"High": 5, "Medium": 10, "Low": 2},
        "volume_trends": [],
        "ai_trends": "AI performance is optimal based on recent interactions."
    }

@router.get("/agents")
async def get_agents(agent: Annotated[dict, Depends(get_current_agent)]):
    """List all agents in the system."""
    db = _get_db()
    return db.get_all_agents()

@router.get("/roles")
async def get_roles(agent: Annotated[dict, Depends(get_current_agent)]):
    """List all available roles and permissions."""
    db = _get_db()
    return db.get_all_roles()

@router.get("/gcs/status")
async def gcs_status(agent: Annotated[dict, Depends(get_current_agent)]):
    """Check Cloud Storage integration status."""
    try:
        from app.services.gcs_service import get_gcs_service
        gcs = get_gcs_service()
        return gcs.get_status()
    except Exception as e:
        return {"enabled": False, "error": str(e)}

@router.post("/gcs/sync")
async def gcs_sync(agent: Annotated[dict, Depends(get_current_agent)]):
    """Batch sync local files to GCS."""
    try:
        from app.services.gcs_service import get_gcs_service
        gcs = get_gcs_service()
        if not gcs.enabled:
            raise HTTPException(status_code=400, detail="GCS is not enabled")
        results = await gcs.async_sync_local_to_gcs()
        return {"status": "success", "results": results}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"GCS sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/livechat/{user_id}/messages")
async def get_livechat_messages(user_id: str, agent: Annotated[dict, Depends(get_current_agent)]):
    """Get messages for a live chat session."""
    db = _get_db()
    return {"messages": db.get_messages(user_id), "user_id": user_id}

@router.post("/livechat/{user_id}/reply")
async def livechat_agent_reply(user_id: str, request: Request, agent: Annotated[dict, Depends(get_current_agent)]):
    """Send agent reply via WebSocket."""
    data = await request.json()
    content = data.get("message", "").strip()
    if not content: raise HTTPException(status_code=400, detail="Empty message")
    
    db = _get_db()
    db.save_message(user_id, "assistant", content)
    
    from app.services.websocket_manager import portal_manager
    await portal_manager.send_to_user(user_id, {
        "event": "message",
        "role": "assistant",
        "content": content,
        "sender_name": agent.get("name", "Agent"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return {"status": "sent"}
