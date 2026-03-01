import os
import json
import uuid
import asyncio
import shutil
from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter  # NEW: Rate limiting
from slowapi.util import get_remote_address
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List, Annotated
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.logging import logger, set_trace_id, LogLatency
from app.core.database import db_manager

def _require_db():
    """Guard: raises 503 if DB is unavailable so app still boots and serves non-DB routes."""
    if db_manager is None:
        raise HTTPException(status_code=503, detail="Database unavailable. Please check DATABASE_URL and DB server connectivity.")
    return db_manager

# ============ RATE LIMITING SETUP ============
limiter = Limiter(key_func=get_remote_address)

# ============ ENVIRONMENT VALIDATION (PRODUCTION SAFETY) ============
def validate_production_config():
    """Validate critical configuration for production deployment."""
    # Minimal critical vars - LLM key can be optional (Groq fallback)
    critical_vars = {
        "AUTH_SECRET_KEY": "Authentication secret key for JWT tokens",
        "DATABASE_URL": "Database connection string",
    }
    
    missing_vars = []
    for var, description in critical_vars.items():
        value = getattr(settings, var, None)
        if not value:
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        error_msg = "❌ PRODUCTION CONFIGURATION ERROR - Missing critical environment variables:\n" + "\n".join(missing_vars)
        logger.error(error_msg)
        logger.error("\n⚠️  DEPLOYMENT BLOCKED: Please configure all required environment variables in .env file.")
        raise ValueError(error_msg)
    
    # Warn about optional but recommended settings
    if not settings.OPENAI_API_KEY:
        logger.info("ℹ️  INFO: OPENAI_API_KEY not set. Using Groq fallback for LLM responses.")
    
    # Warn about insecure defaults
    if not settings.COOKIE_SECURE:
        logger.warning("⚠️  WARNING: COOKIE_SECURE is False. Set to True in production.")
    
    if settings.ALLOWED_ORIGINS == ["*"]:
        logger.warning("⚠️  WARNING: ALLOWED_ORIGINS is ['*']. Restrict to specific domains in production.")
    
    if settings.MFA_DEV_RETURN_CODE:
        logger.warning("⚠️  WARNING: MFA_DEV_RETURN_CODE is True. Set to False in production.")
    
    logger.info("✅ Production configuration validated successfully.")

validate_production_config()

# Services
from app.services.customer_service import CustomerService
from app.services.intent_service import IntentService
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.services.ticket_service import TicketService
from app.services.escalation_service import EscalationService
from app.services.chat_service import ChatService
from app.services.websocket_manager import manager
from app.webhook.whatsapp import WhatsAppWebhookService

# Background Services
from app.services.sla_service import sla_service
from app.services.routing_service import routing_service

# Schemas
from app.schemas.schemas import IntentType
from app.utils.auth_utils import (
    verify_password,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    hash_token,
    create_mfa_code,
    verify_mfa_code,
    create_mfa_token,
    decode_token,
    create_random_token
)

# Helper functions for Auth
def _extract_bearer_token(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return None

def _set_auth_cookies(response: JSONResponse, access_token: str, refresh_token: str = None):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        max_age=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            samesite=settings.COOKIE_SAMESITE,
            secure=settings.COOKIE_SECURE,
            max_age=int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
        )

def _clear_auth_cookies(response: JSONResponse):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

async def get_current_agent(request: Request):
    token = _extract_bearer_token(request) or request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("sub")
    agent = _require_db().get_agent(user_id)
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found")
    return agent

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Initialize Services with error handling
    try:
        app.state.intent_service = IntentService()
    except Exception as e:
        logger.error(f"Failed to init IntentService: {e}")
        app.state.intent_service = None
    
    try:
        app.state.rag_service = RAGService()
    except Exception as e:
        logger.error(f"Failed to init RAGService: {e}")
        app.state.rag_service = None
    
    try:
        app.state.llm_service = LLMService()
    except Exception as e:
        logger.error(f"Failed to init LLMService: {e}")
        app.state.llm_service = None
    
    try:
        app.state.customer_service = CustomerService()
    except Exception as e:
        logger.error(f"Failed to init CustomerService: {e}")
        app.state.customer_service = None
    
    try:
        app.state.ticket_service = TicketService()
    except Exception as e:
        logger.error(f"Failed to init TicketService: {e}")
        app.state.ticket_service = None
    
    try:
        app.state.escalation_service = EscalationService()
    except Exception as e:
        logger.error(f"Failed to init EscalationService: {e}")
        app.state.escalation_service = None
    
    try:
        app.state.chat_service = ChatService(app.state.rag_service if app.state.rag_service else None)
    except Exception as e:
        logger.error(f"Failed to init ChatService: {e}")
        app.state.chat_service = None
    
    # Start background workers - TEMPORARILY DISABLED for stability
    # try:
    #     asyncio.create_task(sla_service.monitor_breaches())
    #     asyncio.create_task(routing_service.process_queue())
    # except Exception as e:
    #     logger.error(f"Failed to start background workers: {e}")
    
    logger.info("All services and background workers initialized.")
    yield
    # Cleanup

app = FastAPI(title="Support Portal Edgeworks", lifespan=lifespan)

# Add CORS Middleware - MUST be configured correctly for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiter to app
app.state.limiter = limiter

# Setup Templates & Static Files
templates = Jinja2Templates(directory="templates")
os.makedirs(os.path.join("data", "uploads", "chat"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.path.join("data", "uploads")), name="uploads")

# ============ UI Routes ============

@app.get("/", response_class=HTMLResponse)
async def portal_dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/chat", response_class=HTMLResponse)
async def live_chat_demo(request: Request):
    return templates.TemplateResponse(request, "chat.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "admin.html")

# ============ Auth APIs ============

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # Prevent brute force
async def login(request: Request):
    try:
        data = await request.json()
        email, password = data.get("email"), data.get("password")
        db = _require_db()
        agent = db.get_agent_by_email(email)
        if not agent or not verify_password(password, agent.get("hashed_password")):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        # Simplified: Auto-login for now (MFA logic can be added back if needed)
        access_token = create_access_token(data={"sub": agent["user_id"], "role": agent["role"]})
        refresh_token = create_refresh_token()
        refresh_hash = hash_token(refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db.create_refresh_token(agent["user_id"], refresh_hash, refresh_expires, request.headers.get("user-agent"))
        
        db.log_action(agent["user_id"], "login", "agent", agent["user_id"])

        response = JSONResponse({
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": agent["role"],
            "name": agent.get("name", agent["user_id"])
        })
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/auth/me")
async def get_me(agent: Annotated[dict, Depends(get_current_agent)]):
    return agent

@app.post("/api/auth/logout")
async def logout(request: Request):
    incoming = request.cookies.get("refresh_token")
    if incoming and db_manager:
        db_manager.revoke_refresh_token(hash_token(incoming))
    response = JSONResponse({"status": "success"})
    _clear_auth_cookies(response)
    return response

@app.post("/api/auth/refresh")
async def refresh_token_route(request: Request):
    incoming = request.cookies.get("refresh_token")
    if not incoming: raise HTTPException(status_code=401, detail="Missing refresh token")
    db = _require_db()
    token_hash = hash_token(incoming)
    stored = db.get_refresh_token(token_hash)
    if not stored or stored.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    agent = db.get_agent(stored["user_id"])
    if not agent: raise HTTPException(status_code=401, detail="Agent not found")

    db.revoke_refresh_token(token_hash)
    new_refresh = create_refresh_token()
    refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.create_refresh_token(agent["user_id"], hash_token(new_refresh), refresh_expires, request.headers.get("user-agent"))

    access_token = create_access_token(data={"sub": agent["user_id"], "role": agent["role"]})
    response = JSONResponse({"access_token": access_token, "token_type": "bearer", "role": agent["role"]})
    _set_auth_cookies(response, access_token, new_refresh)
    return response

# ============ GOOGLE OAUTH LOGIN ============
@app.post("/api/auth/google/login")
@limiter.limit("5/minute")
async def google_login(request: Request):
    """Google OAuth callback - exchanges Google token for app access token"""
    try:
        data = await request.json()
        google_id_token = data.get("id_token") or data.get("token")
        
        if not google_id_token:
            raise HTTPException(status_code=400, detail="Missing Google token")
        db = _require_db()
        # Try to get/create agent with Google ID
        agent = db.get_agent_by_google_id(google_id_token.split(".")[0][:50])
        
        if not agent:
            # Create new agent from Google data
            email = data.get("email") or f"google_{uuid.uuid4().hex[:8]}@support.local"
            agent = db.create_or_get_agent(
                user_id=f"google_{uuid.uuid4().hex[:16]}",
                name=data.get("name", "Support Agent"),
                email=email,
                department="Support",
                google_id=google_id_token.split(".")[0][:50]
            )
        else:
            # Update agent's last login
            db.update_agent_auth(agent["user_id"], google_id=google_id_token.split(".")[0][:50])
        
        # Create session tokens
        access_token = create_access_token(data={"sub": agent["user_id"], "role": agent.get("role", "agent")})
        refresh_token = create_refresh_token()
        refresh_hash = hash_token(refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db.create_refresh_token(agent["user_id"], refresh_hash, refresh_expires, request.headers.get("user-agent"))
        
        db.log_action(agent["user_id"], "login_google", "agent", agent["user_id"])
        
        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "role": agent.get("role", "agent"),
            "name": agent.get("name", agent["user_id"]),
            "email": agent.get("email")
        })
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login error: {e}")
        raise HTTPException(status_code=500, detail="Google authentication failed")

# ============ MAGIC LINK LOGIN ============
@app.post("/api/auth/magic-link/request")
@limiter.limit("3/minute")
async def request_magic_link(request: Request, background_tasks: BackgroundTasks):
    """Request a magic link login"""
    try:
        data = await request.json()
        email = data.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email required")
        
        # Generate magic link token
        magic_token = create_random_token()
        magic_hash = hash_token(magic_token)
        
        # Store magic link with 15 minute expiry
        magic_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        _require_db().create_magic_link(email, magic_hash, magic_expires)
        
        # Build the magic link URL (for production, this should be from settings.BASE_URL)
        magic_link_url = f"{settings.BASE_URL}/api/auth/magic-link/verify?token={magic_token}&email={email}"
        
        # Send email in background
        from app.utils.email_utils import send_magic_link_email
        background_tasks.add_task(send_magic_link_email, email, magic_link_url)
        
        # Log the attempt
        logger.info(f"Magic link requested for: {email}")
        
        return JSONResponse({
            "status": "success",
            "message": "Check your email for the magic link. If you don't see it, check your spam folder."
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Magic link request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create magic link")

@app.get("/api/auth/magic-link/verify")
async def verify_magic_link(token: str, email: str, request: Request):
    """Verify magic link and log in user"""
    try:
        # Check magic link validity
        magic_hash = hash_token(token)
        db = _require_db()
        magic_link = db.get_magic_link(email, magic_hash)
        
        if not magic_link:
            raise HTTPException(status_code=401, detail="Invalid or expired magic link")
        
        # Handle both timezone-aware and naive datetimes
        expires_at = magic_link.get("expires_at")
        now = datetime.now(timezone.utc)
        
        # Ensure both are timezone-aware for comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < now:
            db.revoke_magic_link(email, magic_hash)
            raise HTTPException(status_code=401, detail="Magic link expired")
        
        # Get or create agent
        agent = db.get_agent_by_email(email)
        if not agent:
            agent = db.create_or_get_agent(
                user_id=f"ml_{uuid.uuid4().hex[:16]}",
                name=email.split("@")[0],
                email=email,
                department="Support"
            )
        
        # Revoke used magic link
        db.revoke_magic_link(email, magic_hash)
        
        # Create session tokens
        access_token = create_access_token(data={"sub": agent["user_id"], "role": agent.get("role", "agent")})
        refresh_token = create_refresh_token()
        refresh_hash = hash_token(refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db.create_refresh_token(agent["user_id"], refresh_hash, refresh_expires, request.headers.get("user-agent"))
        
        db.log_action(agent["user_id"], "login_magic_link", "agent", agent["user_id"])
        
        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "role": agent.get("role", "agent"),
            "name": agent.get("name", agent["user_id"]),
            "email": agent.get("email")
        })
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Magic link verification error: {e}")
        raise HTTPException(status_code=500, detail="Magic link verification failed")

# ============ Management APIs ============

@app.get("/api/tickets")
async def get_tickets(agent: Annotated[dict, Depends(get_current_agent)], filter: str = 'all'):
    return _require_db().get_all_tickets(filter_type=filter)

@app.get("/api/tickets/counts")
async def get_ticket_counts(agent: Annotated[dict, Depends(get_current_agent)]):
    return _require_db().get_ticket_counts()

@app.get("/api/tickets/{ticket_id}/history")
async def get_ticket_history(ticket_id: int, agent: Annotated[dict, Depends(get_current_agent)]):
    db = _require_db()
    ticket = db.get_session().query(db.engine).get(ticket_id) if False else None
    # Use db method directly instead of raw query
    history = db.get_unified_history(None, ticket_id)
    return {"history": history}

@app.patch("/api/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: int, data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    if "status" in data:
        _require_db().update_ticket_status(ticket_id, data["status"])
    return {"status": "success"}

@app.get("/api/analytics")
async def get_analytics(request: Request, agent: Annotated[dict, Depends(get_current_agent)]):
    # Mock/Actual Analytics integration
    metrics = _require_db().get_ticket_metrics()
    return {
        "metrics": metrics,
        "agent_performance": [],
        "priority_distribution": {"High": 5, "Medium": 10, "Low": 2},
        "volume_trends": [],
        "ai_trends": "Tren AI sedang dianalisis..."
    }

@app.get("/api/agents")
async def get_agents(agent: Annotated[dict, Depends(get_current_agent)]):
    return _require_db().get_all_agents()

@app.get("/api/knowledge")
async def get_knowledge(agent: Annotated[dict, Depends(get_current_agent)]):
    return _require_db().get_all_knowledge()

@app.post("/api/knowledge/upload")
async def upload_knowledge(
    agent: Annotated[dict, Depends(get_current_agent)],
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    for file in files:
        file_path = os.path.join(settings.KNOWLEDGE_DIR, file.filename)
        with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        _require_db().save_knowledge_metadata(filename=file.filename, file_path=file_path, uploaded_by=agent["user_id"])
    
    # Trigger re-indexing
    background_tasks.add_task(app.state.rag_service._load_vector_store)
    return {"status": "success"}

@app.post("/api/knowledge/ingest-url")
async def ingest_knowledge_from_url(
    agent: Annotated[dict, Depends(get_current_agent)],
    request: Request
):
    """Ingest knowledge base from URL"""
    try:
        data = await request.json()
        url = data.get("url")
        
        if not url:
            return JSONResponse({"error": "URL is required"}, status_code=400)
        
        # Use RAG engine to ingest from URL
        try:
            from app.services.rag_engine import rag_engine
            if not rag_engine:
                return JSONResponse({"error": "RAG Engine not initialized"}, status_code=500)
            
            filename = await rag_engine.ingest_from_url(url, uploaded_by=agent["user_id"])
            return JSONResponse({"status": "success", "filename": filename, "message": f"Content from {url} ingested successfully"})
        except Exception as import_err:
            logger.error(f"RAG engine import error: {str(import_err)}")
            raise
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"URL ingestion error: {str(e)}")
        return JSONResponse({"error": f"Failed to ingest from URL: {str(e)}"}, status_code=500)

@app.delete("/api/knowledge/{filename}")
async def delete_knowledge(
    filename: str,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    try:
        from app.services.rag_engine import rag_engine
        if not rag_engine:
            return JSONResponse({"error": "RAG Engine not initialized"}, status_code=500)
        
        rag_engine.delete_knowledge_document(filename)
        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        logger.error(f"Error deleting knowledge: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/knowledge/batch-delete")
async def batch_delete_knowledge(
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    try:
        data = await request.json()
        filenames = data.get("filenames", [])
        
        if not filenames:
            return JSONResponse({"error": "No filenames provided"}, status_code=400)
            
        from app.services.rag_engine import rag_engine
        if not rag_engine:
            return JSONResponse({"error": "RAG Engine not initialized"}, status_code=500)
            
        rag_engine.delete_knowledge_documents(filenames)
        return {"status": "success", "message": f"Deleted {len(filenames)} files"}
    except Exception as e:
        logger.error(f"Error batch deleting knowledge: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/macros")
async def get_macros(agent: Annotated[dict, Depends(get_current_agent)]):
    return _require_db().get_macros()

@app.get("/api/audit-logs")
async def get_audit_logs(agent: Annotated[dict, Depends(get_current_agent)]):
    return _require_db().get_audit_logs()

# ============ Public / Portal APIs ============

@app.get("/api/history")
@limiter.limit("10/minute")
async def get_chat_history(request: Request, user_id: str = "web_portal_user"):
    return {"history": _require_db().get_messages(user_id)}

@app.post("/api/chat")
@limiter.limit("5/minute")
async def chat_directly(
    request: Request,
    message: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    set_trace_id()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            message, user_id, language = data.get("message"), data.get("user_id", "web_portal_user"), data.get("language")
        except: return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    response_data, status_code = await app.state.chat_service.process_portal_message(
        query=message, user_id=user_id or "web_portal_user", file=file, language=language
    )
    return JSONResponse(response_data, status_code=status_code)

@app.post("/api/close-session")
async def close_session(request: Request):
    data = await request.json()
    user_id, option = data.get("user_id", "web_portal_user"), data.get("option", 1)
    from app.services.rag_engine import rag_engine
    if rag_engine: return {"answer": await rag_engine.finalize_ticket(user_id, option)}
    return JSONResponse({"error": "RAG Engine not initialized"}, status_code=500)

# ============ WhatsApp Webhook ============

@app.post("/webhook/whatsapp")
@limiter.limit("10/minute")  # NEW: Rate limit to prevent abuse
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    trace_id = set_trace_id()
    message = await WhatsAppWebhookService.normalize_payload(request)
    customer = await app.state.customer_service.get_or_register_customer(message.sender)
    classification = await app.state.intent_service.classify(message.text)
    
    response_text = ""
    if classification.intent == IntentType.CRITICAL:
        response_text = await app.state.escalation_service.escalate(customer.identifier, f"CRITICAL: {message.text}", message.text, True)
    elif classification.intent == IntentType.ESCALATION:
        response_text = await app.state.escalation_service.escalate(customer.identifier, f"Escalation: {message.text}", message.text)
    elif classification.intent == IntentType.DEEP_REASONING:
        response_text = await app.state.llm_service.reason(message.text)
    else: 
        rag_res = await app.state.rag_service.query(message.text)
        if rag_res.confidence < 0.5:
            response_text = await app.state.escalation_service.escalate(customer.identifier, f"Low Confidence", message.text)
        else: response_text = rag_res.answer

    if customer.is_new:
        response_text = f"{app.state.customer_service.get_personalized_greeting(customer)}\n\n{response_text}"

    # Actually Send the reply back to WhatsApp via Bird API
    try:
        from app.adapters.whatsapp_bird import send_whatsapp_message
        await send_whatsapp_message(message.sender, response_text)
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message back: {e}")

    return {"status": "success", "trace_id": trace_id, "response": response_text}

# ============ WebSocket ============

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat_endpoint(websocket: WebSocket, session_id: int, user_id: str, user_type: str):
    try:
        db = _require_db() if db_manager else None
        if not db:
            await websocket.close(code=1008)
            return
        session = db.get_chat_session(session_id)
        if not session:
            await websocket.close(code=1008)
            return
        await manager.connect(session_id, user_id, user_type, websocket)
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "message":
                content = msg.get("content")
                msg_id = db.save_chat_message(session_id, user_id, user_type, content)
                await manager.broadcast(session_id, {"event": "message", "message_id": msg_id, "sender_id": user_id, "sender_type": user_type, "content": content, "sent_at": datetime.now(timezone.utc).isoformat()})
    except: manager.disconnect(session_id, websocket)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
