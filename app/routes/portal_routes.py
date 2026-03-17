"""
Public Portal API Routes
========================
Endpoints for the customer-facing chat portal (KB query, direct chat, RFF).
Extracted from main.py. High throughput, rate-limited.
"""

import json
import re
import os
import hashlib
import asyncio
from typing import Annotated, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Response, Form, UploadFile, File
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.database import db_manager
from app.core.auth_deps import decode_access_token
from app.core.config import settings
from app.core.logging import logger
from app.utils.security import bind_user_ip
from app.utils.async_db import run_sync
from app.utils.file_handler import save_upload
from app.services.websocket_manager import portal_manager
from app.services.guardrail_service import guardrail_service
from datetime import datetime, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/api/portal", tags=["Portal"])

# --- Security: Rate limiter for public endpoints ---
limiter = Limiter(key_func=get_remote_address)

# --- Security: AI Semaphore to prevent LLM quota exhaustion ---
AI_SEMAPHORE = asyncio.Semaphore(10) # Max 10 concurrent AI queries

# --- Security: Max query length to prevent prompt injection / abuse ---
MAX_PORTAL_QUERY_LENGTH = 500

def _god_mode_key(user_id: str) -> str:
    return f"god_mode:{user_id}"

def _require_rag(request: Request):
    rag = getattr(request.app.state, 'rag_service', None)
    if not rag:
        raise HTTPException(status_code=503, detail="RAG Service unavailable")
    return rag


# --- Pre-Chat Registration ---
class RegisterRequest(BaseModel):
    user_id: str
    name: str
    company: str
    outlet: str
    mobile: str
    email: str
    language: str = "en"

@router.post("/register")
@limiter.limit("10/minute")
async def register_portal_user(request: Request, body: RegisterRequest):
    """
    Register or update a portal customer before starting chat.
    Collects: name, company, outlet, mobile (WhatsApp), email, language.
    Saves to DB and marks onboarding complete so backend skips onboarding flow.
    """
    import re as _re
    # Validate user_id
    if not _re.match(r'^[\w@+.\-]{1,64}$', body.user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    
    # Validate required fields
    if not body.name or len(body.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name is required (min 2 chars)")
    if not body.company or len(body.company.strip()) < 2:
        raise HTTPException(status_code=400, detail="Company name is required")
    if not body.outlet or len(body.outlet.strip()) < 2:
        raise HTTPException(status_code=400, detail="Outlet name is required")
    if not body.mobile or not _re.match(r'^[+]?[\d\s\-]{8,15}$', body.mobile.strip()):
        raise HTTPException(status_code=400, detail="Valid WhatsApp number is required")
    if not body.email or '@' not in body.email:
        raise HTTPException(status_code=400, detail="Valid email address is required")
    
    lang = body.language if body.language in ('en', 'id', 'zh') else 'en'
    
    try:
        # Save customer data to DB with state='complete' to skip backend onboarding
        await run_sync(
            db_manager.create_or_update_user,
            body.user_id,
            name=body.name.strip().title(),
            company=body.company.strip(),
            outlet_pos=body.outlet.strip(),
            mobile=_re.sub(r'[\s\-]+', '', body.mobile.strip()),
            email=body.email.strip().lower(),
            language=lang,
            state='complete'
        )
        
        # Generate welcome message in selected language
        name = body.name.strip().title()
        welcome_messages = {
            'en': f"Hi {name}! 👋 Welcome to Edgeworks Support.\nYour details have been saved. How can we help you today? 😊",
            'id': f"Halo {name}! 👋 Selamat datang di Edgeworks Support.\nData Anda sudah tersimpan. Ada yang bisa kami bantu hari ini? 😊",
            'zh': f"{name} 您好！👋 欢迎来到 Edgeworks Support。\n您的信息已保存。请问今天有什么可以帮您的？😊"
        }
        
        logger.info(f"Portal customer registered: {body.user_id} ({name}, {body.company}, {body.outlet})")
        
        return {
            "status": "registered",
            "welcome_message": welcome_messages.get(lang, welcome_messages['en']),
            "user_id": body.user_id
        }
    except Exception as e:
        logger.error(f"Portal registration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/kb/query")
@limiter.limit("20/minute")
async def portal_kb_query(request: Request):
    """Knowledge base query with RAG. Agent sources removed for portal users."""
    try:
        # Detect if caller is an authenticated agent
        is_agent = False
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_access_token(token)
            if payload and await run_sync(db_manager.get_agent, payload.get("sub")):
                is_agent = True
        
        data = await request.json()
        query = data.get("query", "").strip()[:500]
        language = data.get("language", "en")
        
        if not query:
            return JSONResponse({"error": "Query is required"}, status_code=400)

        # P0 Fix: Validate input against prompt injection before sending to RAG
        if not guardrail_service.validate_input(query):
            return JSONResponse(
                {"answer": "I'm sorry, I couldn't process that request. Could you rephrase your question?", "confidence": 0, "sources": []},
                status_code=200
            )

        rag = _require_rag(request)
        rag_v2 = getattr(request.app.state, 'rag_service_v2', None)
        
        async with AI_SEMAPHORE:
            # Use V2 if available, else V1
            if rag_v2: 
                result = await rag_v2.query(text=query, threshold=0.3, language=language)
            else: 
                result = await rag.query(text=query, threshold=0.4, language=language)
        
        answer = result.answer
        # P1 Fix: Sanitize AI output (PII masking, hallucination detection)
        answer = guardrail_service.validate_output(answer)
        if not is_agent:
            # P1 Fix: Rigorous anonymization for public portal
            answer = re.sub(r"Internal[\s:]*", "", answer, flags=re.IGNORECASE)
            answer = re.sub(r"\([\s,]*Sources?:?[^)]*\)", "", answer, flags=re.IGNORECASE)
            answer = re.sub(r"\*?\*?Sources?:?\*?\*?\s*.*?(?=\n|$)", "", answer, flags=re.IGNORECASE)
            answer = re.sub(r"\[\d+\]", "", answer)
            answer = re.sub(r"[\w_-]+\.(txt|pdf|docx|md|csv|log)", "", answer, flags=re.IGNORECASE)
            answer = answer.strip()

        return {
            "answer": answer,
            "confidence": result.confidence,
            "sources": result.source_documents if is_agent else [],
        }
    except Exception as e:
        logger.error(f"Portal KB query failed: {e}")
        return JSONResponse({"error": "Failed to query knowledge"}, status_code=500)

@router.post("/chat")
@limiter.limit("10/minute")
async def portal_chat(
    request: Request,
    message: Optional[str] = Form(None),
    user_id: Optional[str] = Form("web_portal_user"),
    language: Optional[str] = Form("en"),
    file: Optional[UploadFile] = File(None)
):
    """Direct portal chat with Level-1 AI agent."""
    try:
        # Security: Bind user_id to IP to prevent IDOR enumeration
        bind_user_ip(user_id, request)
        
        chat_service = getattr(request.app.state, 'chat_service', None)
        if not chat_service:
            raise HTTPException(status_code=503, detail="Chat service unavailable")

        god_mode_enabled = (await run_sync(db_manager.get_setting, _god_mode_key(user_id), "0")) == "1"

        if god_mode_enabled:
            attachment_meta = None
            if file:
                file_bytes = await file.read()
                attachment_meta = save_upload(file_bytes, file.filename, destination="chat")

            if not message and attachment_meta:
                message = f"[Uploaded {attachment_meta['category']}: {attachment_meta['original_name']}]"

            if not message:
                raise HTTPException(status_code=400, detail="Message or file is required")

            await run_sync(
                db_manager.save_message,
                user_id,
                "user",
                message,
                None if not attachment_meta else json.dumps([attachment_meta])
            )

            await portal_manager.send_to_admins(user_id, {
                "event": "message",
                "role": "user",
                "content": message,
                "user_id": user_id,
                "god_mode": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            return {
                "answer": "✅ Received. A human resolver is handling your case now.",
                "god_mode": True,
                "resolver": "human"
            }
            
        async with AI_SEMAPHORE:
            response_data, status_code = await chat_service.process_portal_message(
                query=message, user_id=user_id, file=file, language=language
            )
            
        # Unicode sanitization
        safe_json = json.dumps(response_data, ensure_ascii=False, default=str).encode('utf-8', errors='replace').decode('utf-8')
        return Response(content=safe_json, status_code=status_code, media_type="application/json")
    except Exception as e:
        logger.error(f"Portal chat error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"}
        )

@router.get("/history")
@limiter.limit("30/minute")
async def get_chat_history(request: Request, user_id: str = "web_portal_user", ticket_id: Optional[int] = None):
    """Retrieve chat history for a portal user. IDOR protected by IP binding."""
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    # Security: Bind user_id to the IP that first used it
    bind_user_ip(user_id, request)
    
    db = db_manager
    if ticket_id:
        return {"history": await run_sync(db.get_unified_history, user_id, ticket_id)}
    return {"history": await run_sync(db.get_messages, user_id)}

@router.get("/history/sessions")
@limiter.limit("30/minute")
async def get_history_sessions(request: Request, user_id: str = "web_portal_user"):
    """Return ticket-based sessions for user's history view."""
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    # Security: Bind user_id to the IP that first used it
    bind_user_ip(user_id, request)
    
    db = db_manager
    tickets = await run_sync(db.get_tickets_by_user, user_id, 50)
    return {
        "sessions": [{
            "session_id": f"ticket_{t['id']}",
            "ticket_id": t["id"],
            "summary": t.get("summary", "Support request"),
            "status": t.get("status", "open"),
            "timestamp": t.get("created_at", ""),
            "agent_name": t.get("assigned_to") or "AI Assistant"
        } for t in tickets]
    }

@router.post("/recording/upload")
async def upload_portal_recording(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form("web_portal_user")
):
    """Secure screen recording upload from portal. Enforces file type and size limits."""
    # Security: File extension whitelist
    allowed = [".webm", ".mp4", ".mov"]
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Invalid video format")
        
    # Security: Size check
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (50MB)")
        
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
        
    from app.utils.file_handler import save_upload
    metadata = save_upload(file_bytes, f"portal_{user_id}{ext}", destination="chat")
    
    await run_sync(db_manager.save_message, user_id, "user", f"📹 Screen Recording: {metadata['url']}")
    return {"status": "ok", "url": metadata["url"], "filename": metadata.get("filename", "")}


@router.post("/recording/analyze")
async def analyze_portal_recording(request: Request):
    """
    AI-powered screen recording analysis.
    Extracts key frames and uses Llama 4 Scout Vision to explain
    what's on screen — POS menus, functions, errors, workflow steps.
    """
    data = await request.json()
    video_url = data.get("video_url", "").strip()
    question = data.get("question", "").strip()

    if not video_url:
        raise HTTPException(status_code=400, detail="Missing video_url")

    # Security: only allow local upload paths
    if not video_url.startswith("/uploads/chat/"):
        raise HTTPException(status_code=400, detail="Invalid video path")

    # Sanitize filename
    filename = video_url.split("/")[-1]
    if not re.match(r'^[\w.\-]+\.(webm|mp4|mov)$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    video_path = os.path.join("data", "uploads", "chat", filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    async with AI_SEMAPHORE:
        from app.services.video_analysis_service import analyze_video
        result = await analyze_video(video_path, user_question=question)

    return {
        "analysis": result["analysis"],
        "frames_analyzed": result["frames_analyzed"],
        "error": result.get("error", False)
    }

class CloseSessionRequest(BaseModel):
    user_id: str
    option: str = "close"

@router.post("/session/close")
async def close_portal_session(request: Request, body: CloseSessionRequest):
    """Close a chat session and optionally create a ticket."""
    user_id = body.user_id
    option = body.option
    
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    chat_service = getattr(request.app.state, 'chat_service', None)
    if not chat_service:
        raise HTTPException(status_code=503, detail="Service unavailable")

    result = await chat_service.close_chat(user_id, option)
    return result
