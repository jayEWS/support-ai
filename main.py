import os
import re
import json
import uuid
import asyncio
import shutil
from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from app.utils.security import safe_filename, safe_path, validate_url_or_raise, validate_knowledge_file, ALLOWED_KNOWLEDGE_EXTENSIONS
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from slowapi import Limiter  # NEW: Rate limiting
from slowapi.util import get_remote_address
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List, Annotated
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.logging import logger, set_trace_id, LogLatency
from app.core.database import db_manager

# Concurrency gate: max 10 simultaneous AI calls to avoid Vertex AI quota exhaustion
AI_SEMAPHORE = asyncio.Semaphore(10)

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
        error_msg = "PRODUCTION CONFIGURATION ERROR - Missing critical environment variables:\n" + "\n".join(missing_vars)
        logger.error(error_msg)
        # In production, we log but don't crash here to allow for recovery/debug
        logger.warning("\nWARNING: Critical variables missing. App may be unstable.")
    
    # ... (rest of validate logic) ...

validate_production_config()

# Services
from app.services.customer_service import CustomerService
from app.services.intent_service import IntentService
from app.services.rag_service import RAGService
from app.services.rag_service_v2 import RAGServiceV2
from app.services.advanced_retriever import get_rff_store
from app.services.llm_service import LLMService
from app.services.ticket_service import TicketService
from app.services.escalation_service import EscalationService
from app.services.chat_service import ChatService
from app.services.websocket_manager import manager, portal_manager
from app.webhook.whatsapp import WhatsAppWebhookService

# Background Services
from app.services.sla_service import sla_service
from app.services.routing_service import routing_service

# SaaS Infrastructure
from app.repositories.tenant_repo import TenantRepository
from app.repositories.usage_repo import UsageRepository
from app.repositories.ai_log_repo import AILogRepository
from app.services.ai_observability import AIObservabilityService
from app.middleware.tenant import TenantMiddleware
from app.middleware.usage import UsageTrackingMiddleware
from app.middleware.plan_enforcement import PlanEnforcementMiddleware
from app.routes.tenant_routes import router as tenant_router, plans_router
from app.routes.ai_tools import router as ai_tools_router
from app.routes.customer_routes import router as customer_router
from app.routes.audit_routes import router as audit_router
from app.routes.ticket_routes import router as ticket_router
from app.routes.knowledge_routes import router as knowledge_router
from app.routes.websocket_routes import router as websocket_router
from app.routes.system_routes import router as system_router
from app.routes.portal_routes import router as portal_router

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

async def get_admin_agent(agent: Annotated[dict, Depends(get_current_agent)]):
    if agent.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
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
    
    # Initialize Shopify-inspired Advanced RAG Service (V2)
    try:
        app.state.rag_service_v2 = RAGServiceV2()
        logger.info("[OK] RAGServiceV2 (Shopify-grade) initialized")
    except Exception as e:
        logger.error(f"Failed to init RAGServiceV2: {e}")
        app.state.rag_service_v2 = None
    
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
    
    # Initialize GCS Service (Phase 2)
    try:
        from app.services.gcs_service import init_gcs_service
        app.state.gcs_service = init_gcs_service()
    except Exception as e:
        logger.warning(f"GCS Service init skipped: {e}")
        app.state.gcs_service = None
    
    # Initialize ChatService with stable RAGService
    try:
        app.state.chat_service = ChatService(rag_service=app.state.rag_service)
        logger.info("[OK] ChatService standardized on stable RAGService")
    except Exception as e:
        logger.error(f"Failed to init ChatService: {e}")
        app.state.chat_service = None
    
    # RAGEngine was merged into RAGService - no longer needed here
    app.state.rag_engine = None
    
    # ── SaaS Repository Layer ──
    try:
        if db_manager:
            app.state.tenant_repo = TenantRepository(db_manager.Session)
            app.state.usage_repo = UsageRepository(db_manager.Session)
            app.state.ai_log_repo = AILogRepository(db_manager.Session)
            app.state.ai_observability = AIObservabilityService(
                ai_log_repo=app.state.ai_log_repo,
                usage_repo=app.state.usage_repo,
            )
            logger.info("SaaS repositories initialized (tenant, usage, AI observability).")
            
            # Create SaaS tables if they don't exist
            try:
                from app.models.tenant_models import Base as TenantBase
                TenantBase.metadata.create_all(db_manager.engine)
                logger.info("SaaS tables verified/created.")
            except Exception as e:
                logger.warning(f"SaaS table creation skipped: {e}")
        else:
            app.state.tenant_repo = None
            app.state.usage_repo = None
            app.state.ai_log_repo = None
            app.state.ai_observability = None
    except Exception as e:
        logger.warning(f"SaaS layer init error (non-fatal): {e}")
        app.state.tenant_repo = None
        app.state.usage_repo = None
        app.state.ai_log_repo = None
        app.state.ai_observability = None

    # 🚀 Start autonomous background workers (Powered Mode)
    try:
        asyncio.create_task(sla_service.monitor_breaches())
        asyncio.create_task(routing_service.process_queue())
        logger.info("🔥 Autonomous SLA and Routing workers activated.")
    except Exception as e:
        logger.error(f"Failed to start background workers: {e}")
    
    logger.info("All services and background workers initialized.")
    yield
    # Cleanup

app = FastAPI(title="Support Portal Edgeworks", lifespan=lifespan)

# Add CORS Middleware - MUST be configured correctly for production
# Security: reject wildcard "*" patterns — require explicit origins
_cors_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else []
if _cors_origins == ["*"]:
    logger.warning("[SECURITY] CORS ALLOWED_ORIGINS is ['*'] — this is insecure for production. Set explicit origins.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins and _cors_origins != ["*"] else ["*"],
    allow_credentials=True if _cors_origins and _cors_origins != ["*"] else False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Tenant-ID"],
)

# GZip compression for all responses > 500 bytes (saves ~70% bandwidth for HTML/JSON)
app.add_middleware(GZipMiddleware, minimum_size=500)

# ── SaaS Middleware ──
# Order matters: Tenant → Plan Enforcement → Usage Tracking
if getattr(settings, 'MULTI_TENANT_ENABLED', False):
    app.add_middleware(UsageTrackingMiddleware)
    app.add_middleware(PlanEnforcementMiddleware)
    app.add_middleware(TenantMiddleware)
    logger.info("Multi-tenant middleware enabled.")

# ── SaaS API Routes ──
app.include_router(tenant_router)
app.include_router(ai_tools_router)
app.include_router(customer_router)
app.include_router(audit_router)
app.include_router(ticket_router)
app.include_router(knowledge_router)
app.include_router(websocket_router)
app.include_router(system_router)
app.include_router(portal_router)

# Add rate limiter to app
app.state.limiter = limiter

# Setup Templates & Static Files
templates = Jinja2Templates(directory="templates")
os.makedirs(os.path.join("data", "uploads", "chat"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.path.join("data", "uploads")), name="uploads")

# ============ UI Routes ============

@app.get("/", response_class=HTMLResponse)
async def portal_dashboard(request: Request):
    response = templates.TemplateResponse(request, "index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.get("/chat", response_class=HTMLResponse)
async def live_chat_demo(request: Request):
    return templates.TemplateResponse(request, "chat.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    response = templates.TemplateResponse(request, "login.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "admin.html")

@app.get("/user", response_class=HTMLResponse)
async def user_portal(request: Request):
    response = templates.TemplateResponse(request, "index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# ============ Auth APIs ============

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # Prevent brute force
async def login(request: Request):
    try:
        data = await request.json()
        email, password = data.get("email"), data.get("password")
        if not email or not email.lower().endswith("@edgeworks.com.sg"):
            raise HTTPException(status_code=403, detail="Only @edgeworks.com.sg accounts are allowed")
            
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
    except HTTPException:
        raise
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
@app.get("/api/auth/google")
@limiter.limit("30/minute")
async def google_oauth_redirect(request: Request):
    """Redirect user to Google OAuth consent screen"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    
    import urllib.parse, secrets
    state = secrets.token_urlsafe(16)
    # Store state in session cookie for CSRF protection
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
        "hd": "edgeworks.com.sg",
    }
    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    response = RedirectResponse(url=google_auth_url)
    response.set_cookie("oauth_state", state, max_age=300, httponly=True, samesite="lax")
    return response


@app.get("/api/auth/google/callback")
@limiter.limit("30/minute")
async def google_oauth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handle Google OAuth callback, exchange code for tokens, log user in"""
    import urllib.parse as _up
    import httpx as _httpx

    if error:
        return RedirectResponse(url=f"/login?error={_up.quote(error)}")

    if not code:
        return RedirectResponse(url="/login?error=missing_code")

    # Validate state for CSRF protection
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/login?error=invalid_state")

    try:
        # Exchange code for tokens
        async with _httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        if token_resp.status_code != 200:
            logger.error(f"Google token exchange failed: {token_resp.text}")
            return RedirectResponse(url="/login?error=token_exchange_failed")

        token_data = token_resp.json()
        id_token_str = token_data.get("id_token")

        # Verify the ID token with Google
        from google.oauth2 import id_token as google_id_token_lib
        from google.auth.transport import requests as google_requests
        try:
            id_info = google_id_token_lib.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception as verify_err:
            logger.error(f"Google ID token verification failed: {verify_err}")
            return RedirectResponse(url="/login?error=invalid_token")

        google_sub = id_info["sub"]
        email = id_info.get("email", "")
        if not email or not email.lower().endswith("@edgeworks.com.sg"):
            logger.warning(f"Google login domain mismatch: {email}")
            return RedirectResponse(url="/login?error=invalid_domain")
            
        name = id_info.get("name", email.split("@")[0] if email else "Agent")

        db = _require_db()
        agent = db.get_agent_by_google_id(google_sub)
        
        # Designated System Admins
        system_admins = ["support@edgeworks.com.sg", "jay@edgeworks.com.sg"]
        is_sys_admin = email.lower() in system_admins

        if not agent:
            # Check if an agent with this email already exists
            agent_data = db.get_agent_by_email(email)
            if agent_data:
                # Link existing agent
                db.update_agent_auth(agent_data["user_id"], google_id=google_sub)
                agent = db.get_agent(agent_data["user_id"])
            else:
                # STRICT: Only auto-create designate admins via Google. 
                # Others must use Magic Link (Token verification) first.
                if is_sys_admin:
                    agent = db.create_or_get_agent(
                        user_id=f"google_{uuid.uuid4().hex[:16]}",
                        name=name,
                        email=email,
                        department="Management",
                        google_id=google_sub,
                    )
                else:
                    logger.warning(f"Unauthorized Google registration attempt: {email}")
                    return RedirectResponse(url="/login?error=use_magic_link")
        else:
            db.update_agent_auth(agent["user_id"], google_id=google_sub)
            
        # Ensure System Admin role for designated emails
        if is_sys_admin:
            db.create_role("System Admin", "Full system access")
            db.assign_role_to_agent(agent["user_id"], "System Admin")
            agent = db.get_agent(agent["user_id"])

        access_token = create_access_token(data={"sub": agent["user_id"], "role": agent.get("role", "agent")})
        refresh_token = create_refresh_token()
        refresh_hash = hash_token(refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db.create_refresh_token(agent["user_id"], refresh_hash, refresh_expires, request.headers.get("user-agent"))
        db.log_action(agent["user_id"], "login_google", "agent", agent["user_id"])

        # Security Fix C9: Do NOT expose access_token in URL query string.
        # Tokens are set via secure HTTP-only cookies instead.
        qs = _up.urlencode({
            "role": agent.get("role", "agent"),
            "name": agent.get("name", agent["user_id"]),
        })
        response = RedirectResponse(url=f"/login?oauth_success=1&{qs}")
        response.delete_cookie("oauth_state")
        _set_auth_cookies(response, access_token, refresh_token)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return RedirectResponse(url="/login?error=oauth_failed")


@app.post("/api/auth/google/login")
@limiter.limit("30/minute")
async def google_login_token(request: Request):
    """Handle Google Login via ID token (from GIS/One Tap)"""
    try:
        data = await request.json()
        id_token_str = data.get("id_token")
        if not id_token_str:
            raise HTTPException(status_code=400, detail="Missing ID token")

        # Verify the ID token with Google
        from google.oauth2 import id_token as google_id_token_lib
        from google.auth.transport import requests as google_requests
        
        try:
            id_info = google_id_token_lib.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception as verify_err:
            logger.error(f"Google ID token verification failed: {verify_err}")
            raise HTTPException(status_code=401, detail="Invalid Google token")

        google_sub = id_info["sub"]
        email = id_info.get("email", "")
        if not email or not email.lower().endswith("@edgeworks.com.sg"):
            logger.warning(f"Google token domain mismatch: {email}")
            raise HTTPException(status_code=403, detail="Only @edgeworks.com.sg accounts are allowed")

        name = id_info.get("name", email.split("@")[0] if email else "Agent")

        db = _require_db()
        agent = db.get_agent_by_google_id(google_sub)

        # Designated System Admins
        system_admins = ["support@edgeworks.com.sg", "jay@edgeworks.com.sg"]
        is_sys_admin = email.lower() in system_admins

        if not agent:
            # Check if an agent with this email already exists
            agent_data = db.get_agent_by_email(email)
            if agent_data:
                # Link existing agent
                db.update_agent_auth(agent_data["user_id"], google_id=google_sub)
                agent = db.get_agent(agent_data["user_id"])
            else:
                # STRICT: Only designate admins can register via Token Login.
                # Others must use Magic Link flow first.
                if is_sys_admin:
                    agent = db.create_or_get_agent(
                        user_id=f"google_{uuid.uuid4().hex[:16]}",
                        name=name,
                        email=email,
                        department="Management",
                        google_id=google_sub,
                    )
                else:
                    raise HTTPException(status_code=403, detail="First-time registration must use Magic Link verification.")
        else:
            db.update_agent_auth(agent["user_id"], google_id=google_sub)

        # Ensure System Admin role for designated emails
        if is_sys_admin:
            db.create_role("System Admin", "Full system access")
            db.assign_role_to_agent(agent["user_id"], "System Admin")
            agent = db.get_agent(agent["user_id"])

        access_token = create_access_token(data={"sub": agent["user_id"], "role": agent.get("role", "agent")})
        refresh_token = create_refresh_token()
        refresh_hash = hash_token(refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db.create_refresh_token(agent["user_id"], refresh_hash, refresh_expires, request.headers.get("user-agent"))
        db.log_action(agent["user_id"], "login_google_token", "agent", agent["user_id"])

        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "role": agent.get("role", "agent"),
            "name": agent.get("name", agent["user_id"])
        })
        _set_auth_cookies(response, access_token, refresh_token)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google token login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during Google login")

# ============ MAGIC LINK LOGIN ============
@app.post("/api/auth/magic-link/request")
@limiter.limit("3/minute")
async def request_magic_link(request: Request, background_tasks: BackgroundTasks):
    """Request a magic link login"""
    try:
        data = await request.json()
        email = data.get("email")
        if not email or not email.lower().endswith("@edgeworks.com.sg"):
            raise HTTPException(status_code=403, detail="Only @edgeworks.com.sg accounts are allowed")
        
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
    import urllib.parse as _up
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
        
        # Redirect to login page with token in URL so JS can store it and go to /admin
        qs = _up.urlencode({
            "access_token": access_token,
            "role": agent.get("role", "agent"),
            "name": agent.get("name", agent["user_id"]),
        })
        response = RedirectResponse(url=f"/login?magic_success=1&{qs}", status_code=302)
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except HTTPException as he:
        return RedirectResponse(url=f"/login?error={_up.quote(he.detail)}", status_code=302)
    except Exception as e:
        logger.error(f"Magic link verification error: {e}")
        return RedirectResponse(url="/login?error=verification_failed", status_code=302)

# ============ Management APIs ============

# Management and System APIs moved to app/routes/ticket_routes.py and system_routes.py
# GCS and Macro APIs moved to app/routes/system_routes.py
# Public/Portal APIs moved to app/routes/portal_routes.py

# Knowledge Base and Portal APIs moved to app/routes/knowledge_routes.py and portal_routes.py

@app.post("/api/close-session")
@limiter.limit("10/minute")
async def close_session(request: Request):
    data = await request.json()
    user_id = data.get("user_id", "web_portal_user")
    option = data.get("option", "close")  # "close" | "ticket" | "ticket_and_notify"
    
    # Security: Validate user_id format
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    # Security: Validate option to prevent injection
    if option not in ("close", "ticket", "ticket_and_notify", 1, "1", 2, "2"):
        raise HTTPException(status_code=400, detail="Invalid option")
    
    # Support legacy numeric options
    if option == 1 or option == "1":
        option = "ticket_and_notify"
    elif option == 2 or option == "2":
        option = "close"
    
    result = await app.state.chat_service.close_chat(user_id, option)
    return result

# ============ WhatsApp Webhook ============

@app.get("/webhook/whatsapp")
async def whatsapp_webhook_verify(request: Request):
    """Handle Meta WhatsApp webhook verification (GET).
    Meta sends: hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info(f"✅ WhatsApp webhook verified successfully")
        return PlainTextResponse(challenge)
    
    # Fallback for health checks
    if "challenge" in params:
        return PlainTextResponse(params["challenge"])
    
    logger.warning(f"❌ WhatsApp webhook verification failed. mode={mode}, token={token}")
    return {"status": "ok", "message": "WhatsApp webhook is active"}

@app.post("/webhook/whatsapp")
@limiter.limit("30/minute")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    trace_id = set_trace_id()
    
    try:
        message = await WhatsAppWebhookService.normalize_payload(request)
    except HTTPException as e:
        # Duplicates, status updates, empty messages — return 200 so Meta doesn't retry
        logger.info(f"Webhook filtered: {e.detail}")
        return {"status": "filtered", "reason": e.detail}
    
    # Mark message as read (double blue ticks)
    try:
        from app.adapters.whatsapp_meta import mark_message_read
        await mark_message_read(message.message_id)
    except Exception:
        pass  # Non-critical
    
    # Save inbound message to DB
    db = _require_db() if db_manager else None
    if db:
        db.save_whatsapp_message(
            phone_number=message.sender,
            direction="inbound",
            content=message.text,
            external_message_id=message.message_id
        )

    customer = await app.state.customer_service.get_or_register_customer(message.sender)
    
    # Get user language for multi-language response
    chat_svc = getattr(app.state, 'chat_service', None)
    
    # Check onboarding state and handle (also detects language for complete users)
    state_info = chat_svc._get_user_state(message.sender) if chat_svc else {'state': 'complete'}
    onboarding_response = None
    if chat_svc:
        onboarding_response = chat_svc._handle_onboarding(message.sender, message.text, state_info)
    
    # Re-read language AFTER onboarding (may have been updated by language detection)
    user_lang = chat_svc.get_user_language(message.sender) if chat_svc else 'en'
    
    ticket_id = None
    if onboarding_response:
        response_text = onboarding_response
    else:
        classification = await app.state.intent_service.classify(message.text)
        
        response_text = ""
        if classification.intent == IntentType.CRITICAL:
            response_text = await app.state.escalation_service.escalate(customer.identifier, f"CRITICAL: {message.text}", message.text, True)
        elif classification.intent == IntentType.ESCALATION:
            response_text = await app.state.escalation_service.escalate(customer.identifier, f"Escalation: {message.text}", message.text)
        elif classification.intent == IntentType.DEEP_REASONING:
            response_text = await app.state.llm_service.reason(message.text)
        else: 
            rag_res = await app.state.rag_service.query(message.text, language=user_lang)
            if rag_res.confidence < 0.5:
                response_text = await app.state.escalation_service.escalate(customer.identifier, f"Low Confidence", message.text)
            else: response_text = rag_res.answer

        if customer.is_new and state_info['state'] == 'complete':
            response_text = f"{app.state.customer_service.get_personalized_greeting(customer)}\n\n{response_text}"

    # Send the reply back to WhatsApp via Meta Cloud API
    send_success = False
    try:
        from app.adapters.whatsapp_meta import send_whatsapp_message, is_meta_configured
        if is_meta_configured():
            send_success = await send_whatsapp_message(message.sender, response_text)
        else:
            logger.warning("WhatsApp Meta API not configured — reply saved locally only")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message back: {e}")

    # Save outbound message to DB
    if db:
        db.save_whatsapp_message(
            phone_number=message.sender,
            direction="outbound",
            content=response_text,
            status="sent" if send_success else "failed",
            ticket_id=ticket_id
        )

    return {"status": "success", "trace_id": trace_id, "response": response_text}

# ============ System Settings API ============

@app.get("/api/settings")
async def get_settings(agent: Annotated[dict, Depends(get_current_agent)]):
    """Get all system settings (admin only)."""
    if agent.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    db = _require_db()
    all_settings = db.get_all_settings()
    # Set defaults if not yet configured
    defaults = {
        "ticket_notify_enabled": "true",
        "ticket_notify_email": "jay@edgeworks.com.sg",
        "ticket_notify_cc": "",
        "email_provider": settings.EMAIL_PROVIDER or "gmail",
    }
    for k, v in defaults.items():
        if k not in all_settings:
            all_settings[k] = v
    return all_settings

@app.post("/api/settings")
async def save_settings(data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    """Save system settings (admin only)."""
    if agent.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    db = _require_db()
    allowed_keys = {"ticket_notify_enabled", "ticket_notify_email", "ticket_notify_cc"}
    saved = []
    for k, v in data.items():
        if k in allowed_keys:
            db.set_setting(k, str(v))
            saved.append(k)
    logger.info(f"Settings updated by {agent.get('username')}: {saved}")
    return {"status": "ok", "saved": saved}

@app.post("/api/settings/test-email")
async def test_email_notification(agent: Annotated[dict, Depends(get_current_agent)]):
    """Send a test email notification to verify email settings work."""
    if agent.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    db = _require_db()
    to_email = db.get_setting("ticket_notify_email", "jay@edgeworks.com.sg")
    try:
        success = await _send_ticket_email(
            to_email=to_email,
            ticket_id=0,
            summary="This is a test email from Edgeworks Support Portal",
            priority="Medium",
            category="Test",
            customer_name="Test User",
            customer_id="test",
            due_at_str="-",
        )
        return {"status": "sent" if success else "failed", "to": to_email}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def _send_ticket_email(
    to_email: str,
    ticket_id: int,
    summary: str,
    priority: str,
    category: str,
    customer_name: str,
    customer_id: str,
    due_at_str: str,
    cc_email: str = "",
):
    """Send ticket notification email via Gmail SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    gmail_email = settings.GMAIL_EMAIL
    gmail_password = settings.GMAIL_PASSWORD
    from_addr = settings.EMAIL_FROM_ADDRESS or gmail_email

    if not gmail_email or not gmail_password:
        logger.warning(f"[EMAIL] Gmail not configured — MOCK email to {to_email}")
        logger.info(f"[EMAIL] Ticket #{ticket_id} | {summary} | Priority: {priority}")
        return True  # Mock success so ticket creation doesn't fail

    # Build HTML email
    priority_colors = {"Urgent": "#dc2626", "High": "#ea580c", "Medium": "#2563eb", "Low": "#16a34a"}
    p_color = priority_colors.get(priority, "#2563eb")

    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1e293b; padding: 24px; border-radius: 12px 12px 0 0;">
            <h2 style="color: #fff; margin: 0; font-size: 18px;">🎫 New Support Ticket #{ticket_id}</h2>
        </div>
        <div style="background: #fff; padding: 24px; border: 1px solid #e2e8f0; border-top: none;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #64748b; font-size: 13px; width: 120px;">Customer</td>
                    <td style="padding: 8px 0; font-weight: 600;">{customer_name} ({customer_id})</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b; font-size: 13px;">Priority</td>
                    <td style="padding: 8px 0;"><span style="background: {p_color}; color: #fff; padding: 2px 10px; border-radius: 99px; font-size: 12px; font-weight: 600;">{priority}</span></td></tr>
                <tr><td style="padding: 8px 0; color: #64748b; font-size: 13px;">Category</td>
                    <td style="padding: 8px 0; font-weight: 600;">{category}</td></tr>
                <tr><td style="padding: 8px 0; color: #64748b; font-size: 13px;">Due</td>
                    <td style="padding: 8px 0; font-weight: 600;">{due_at_str}</td></tr>
            </table>
            <div style="margin-top: 16px; padding: 16px; background: #f8fafc; border-radius: 8px; border-left: 4px solid {p_color};">
                <p style="margin: 0; color: #334155; font-size: 14px; line-height: 1.6;"><strong>Summary:</strong> {summary}</p>
            </div>
            <div style="margin-top: 20px; text-align: center;">
                <a href="{settings.BASE_URL}/admin" style="display: inline-block; background: #2563eb; color: #fff; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">Open Dashboard →</a>
            </div>
        </div>
        <div style="padding: 16px; text-align: center; color: #94a3b8; font-size: 11px;">
            Edgeworks Support Portal • Automated Notification
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Ticket #{ticket_id}] {priority} — {summary[:80]}"
    msg["From"] = from_addr
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg.attach(MIMEText(html, "html"))

    recipients = [to_email]
    if cc_email:
        recipients.extend([e.strip() for e in cc_email.split(",") if e.strip()])

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _smtp_send(gmail_email, gmail_password, recipients, msg))
        logger.info(f"[EMAIL] ✅ Ticket #{ticket_id} notification sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] ❌ Failed to send ticket #{ticket_id} notification: {e}")
        return False

def _smtp_send(gmail_email, gmail_password, recipients, msg):
    """Blocking SMTP send (runs in executor)."""
    import smtplib
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_email, gmail_password)
        server.sendmail(gmail_email, recipients, msg.as_string())

# ============ WhatsApp API (Admin Dashboard) ============

@app.get("/api/whatsapp/conversations")
async def get_whatsapp_conversations(
    agent: Annotated[dict, Depends(get_current_agent)],
    search: str = None, page: int = 1, per_page: int = 50
):
    """Get WhatsApp conversations grouped by phone number."""
    return _require_db().get_whatsapp_conversations(search=search, page=page, per_page=per_page)

@app.get("/api/whatsapp/messages/{phone_number:path}")
async def get_whatsapp_messages(
    phone_number: str,
    agent: Annotated[dict, Depends(get_current_agent)],
    page: int = 1, per_page: int = 100
):
    """Get message thread for a specific phone number."""
    return _require_db().get_whatsapp_messages(phone_number=phone_number, page=page, per_page=per_page)

@app.get("/api/whatsapp/stats")
async def get_whatsapp_stats(agent: Annotated[dict, Depends(get_current_agent)]):
    """Get WhatsApp messaging statistics."""
    return _require_db().get_whatsapp_stats()

@app.get("/api/whatsapp/config-status")
async def get_whatsapp_config_status(agent: Annotated[dict, Depends(get_current_agent)]):
    """Check if WhatsApp Meta API is configured and test mode status."""
    from app.adapters.whatsapp_meta import is_meta_configured
    configured = is_meta_configured()
    test_mode = settings.WHATSAPP_TEST_MODE
    return {
        "configured": configured,
        "test_mode": test_mode,
        "provider": "meta_cloud_api",
        "note": "Test Mode ON — messages processed locally without Meta API." if test_mode and not configured else (
            "Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env to enable sending." if not configured else "Meta WhatsApp Cloud API is active."
        )
    }

@app.post("/api/whatsapp/test-mode")
async def toggle_whatsapp_test_mode(data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    """Toggle WhatsApp test mode (admin only). Requires API_SECRET_KEY for security."""
    secret = data.get("secret", "")
    if secret != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    enabled = data.get("enabled", True)
    settings.WHATSAPP_TEST_MODE = bool(enabled)
    logger.info(f"WhatsApp test mode {'ENABLED' if settings.WHATSAPP_TEST_MODE else 'DISABLED'} by {agent.get('username', 'unknown')}")
    return {"test_mode": settings.WHATSAPP_TEST_MODE}

@app.post("/api/whatsapp/simulate")
async def simulate_whatsapp_inbound(data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    """Simulate an inbound WhatsApp message (test mode only). 
    This processes the message through the full AI pipeline and saves both inbound + AI response."""
    if not settings.WHATSAPP_TEST_MODE:
        raise HTTPException(status_code=403, detail="Test mode is disabled. Enable it in Settings first.")
    
    phone = data.get("phone_number", "").strip()
    message_text = data.get("message", "").strip()
    if not phone or not message_text:
        raise HTTPException(status_code=400, detail="phone_number and message are required")
    
    # Normalize phone
    if not phone.startswith("+"):
        phone = f"+{phone}"
    
    db = _require_db()
    
    # Save the simulated inbound message
    db.save_whatsapp_message(
        phone_number=phone,
        direction="inbound",
        content=message_text,
        external_message_id=f"test_{int(__import__('time').time()*1000)}"
    )
    
    # Process through AI pipeline
    try:
        customer = await app.state.customer_service.get_or_register_customer(phone)
        
        # Get user language for multi-language response
        chat_svc = getattr(app.state, 'chat_service', None)
        
        # Check onboarding state and handle (also detects language for complete users)
        state_info = chat_svc._get_user_state(phone) if chat_svc else {'state': 'complete'}
        onboarding_response = None
        if chat_svc:
            onboarding_response = chat_svc._handle_onboarding(phone, message_text, state_info)
        
        # Re-read language AFTER onboarding (may have been updated by language detection)
        user_lang = chat_svc.get_user_language(phone) if chat_svc else 'en'
        
        if onboarding_response:
            response_text = onboarding_response
        else:
            classification = await app.state.intent_service.classify(message_text)
            
            response_text = ""
            if classification.intent == IntentType.CRITICAL:
                response_text = await app.state.escalation_service.escalate(customer.identifier, f"CRITICAL: {message_text}", message_text, True)
            elif classification.intent == IntentType.ESCALATION:
                response_text = await app.state.escalation_service.escalate(customer.identifier, f"Escalation: {message_text}", message_text)
            elif classification.intent == IntentType.DEEP_REASONING:
                response_text = await app.state.llm_service.reason(message_text)
            else:
                rag_res = await app.state.rag_service.query(message_text, language=user_lang)
                if rag_res.confidence < 0.5:
                    response_text = await app.state.escalation_service.escalate(customer.identifier, f"Low Confidence", message_text)
                else:
                    response_text = rag_res.answer
            
            if customer.is_new and state_info['state'] == 'complete':
                response_text = f"{app.state.customer_service.get_personalized_greeting(customer)}\n\n{response_text}"
        
        # Save AI response
        db.save_whatsapp_message(
            phone_number=phone,
            direction="outbound",
            content=response_text,
            status="sent"
        )
        
        return {"status": "success", "inbound": message_text, "ai_response": response_text, "phone": phone}
    except Exception as e:
        logger.error(f"Simulate AI processing failed: {e}")
        return {"status": "partial", "inbound": message_text, "ai_response": f"[AI Error] {str(e)}", "phone": phone}

@app.post("/api/whatsapp/send")
async def send_whatsapp_reply(data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    """Agent sends a manual WhatsApp reply to a customer."""
    phone = data.get("phone_number")
    message = data.get("message", "").strip()
    if not phone or not message:
        raise HTTPException(status_code=400, detail="phone_number and message are required")

    from app.adapters.whatsapp_meta import send_whatsapp_message, is_meta_configured
    meta_ready = is_meta_configured()
    test_mode = settings.WHATSAPP_TEST_MODE
    send_success = False
    if meta_ready:
        send_success = await send_whatsapp_message(phone, message)
    elif test_mode:
        send_success = True  # In test mode, treat as successfully sent locally

    # Always save the message locally so it appears in the admin chat UI
    db = _require_db()
    if send_success:
        status = "sent"
    elif test_mode:
        status = "sent"
    elif not meta_ready:
        status = "pending"
    else:
        status = "failed"
    msg_id = db.save_whatsapp_message(
        phone_number=phone,
        direction="outbound",
        content=message,
        status=status
    )

    if meta_ready and not send_success:
        raise HTTPException(status_code=502, detail="Failed to send via Meta WhatsApp API")
    return {"status": status, "message_id": msg_id, "test_mode": test_mode}

@app.post("/api/whatsapp/convert-ticket")
async def convert_whatsapp_to_ticket(data: dict, agent: Annotated[dict, Depends(get_current_agent)]):
    """Convert a WhatsApp conversation into a support ticket."""
    phone = data.get("phone_number")
    title = data.get("title", "WhatsApp Conversation")
    priority = data.get("priority", "Medium")
    if not phone:
        raise HTTPException(status_code=400, detail="phone_number is required")

    db = _require_db()
    # Get conversation history for transcript
    conv_data = db.get_whatsapp_messages(phone_number=phone, per_page=500)
    messages = conv_data.get("messages", [])
    transcript = "\n".join([
        f"[{m['direction'].upper()}] {m['created_at'] or ''}: {m['content']}"
        for m in messages
    ])

    # Create ticket
    from app.services.ticket_service import TicketService
    ticket = await TicketService.create_ticket(
        user_id=phone,
        summary=f"[WhatsApp] {title}",
        history=transcript,
        priority=priority
    )

    # Link all messages to the new ticket
    db.link_whatsapp_messages_to_ticket(phone, ticket.id)

    # Notify customer via Meta WhatsApp API
    try:
        from app.adapters.whatsapp_meta import send_whatsapp_message, is_meta_configured
        notify_msg = f"Hi Kak! Percakapan ini sudah dibuatkan tiket support #{ticket.id}. Tim kami akan follow up segera. Terima kasih! 🙏"
        notify_success = False
        if is_meta_configured():
            notify_success = await send_whatsapp_message(phone, notify_msg)
        db.save_whatsapp_message(
            phone_number=phone, direction="outbound",
            content=f"[System] Ticket #{ticket.id} created. Team will follow up.",
            ticket_id=ticket.id, status="sent" if notify_success else "pending"
        )
    except Exception as e:
        logger.warning(f"Failed to notify customer about ticket: {e}")

    return {"status": "success", "ticket_id": ticket.id, "summary": ticket.summary}


# WebSockets moved to app/routes/websocket_routes.py


@app.get("/health")
async def health():
    health_data = {"status": "ok"}
    
    # Database connection check
    try:
        if db_manager:
            from sqlalchemy import text as sa_text
            session = db_manager.get_session()
            session.execute(sa_text("SELECT 1"))
            db_manager.Session.remove()
            health_data["database"] = "connected"
        else:
            health_data["database"] = "unavailable"
    except Exception as e:
        health_data["database"] = f"error: {str(e)[:50]}"
    
    # Active connections
    from app.services.websocket_manager import portal_manager
    health_data["active_ws_users"] = len(portal_manager.connections)
    
    # Phase 2: Include GCS status
    try:
        from app.services.gcs_service import get_gcs_service
        gcs = get_gcs_service()
        health_data["gcs"] = {"enabled": gcs.enabled, "bucket": settings.GCS_BUCKET_NAME if gcs.enabled else None}
    except Exception:
        health_data["gcs"] = {"enabled": False}
    
    # SaaS status
    health_data["saas"] = {
        "multi_tenant": getattr(settings, "MULTI_TENANT_ENABLED", False),
        "plan_enforcement": getattr(settings, "PLAN_ENFORCEMENT_ENABLED", False),
        "ai_observability": getattr(settings, "AI_OBSERVABILITY_ENABLED", True),
        "repositories": {
            "tenant": app.state.tenant_repo is not None if hasattr(app.state, "tenant_repo") else False,
            "usage": app.state.usage_repo is not None if hasattr(app.state, "usage_repo") else False,
            "ai_log": app.state.ai_log_repo is not None if hasattr(app.state, "ai_log_repo") else False,
        }
    }
    
    return health_data

# ============ SPA Catch-all (MUST be last route) ============
@app.get("/{tab:path}", response_class=HTMLResponse)
async def admin_spa(request: Request, tab: str):
    admin_tabs = {
        "overview", "inbox", "team", "tickets", "whatsapp",
        "macros", "knowledge", "customers", "settings",
        "audit", "usermst", "groupperms", "privsetup", "livechat"
    }
    user_tabs = {
        "conversation", "history", "historydetail", "kb"
    }
    root = tab.split("/")[0]
    if root in admin_tabs:
        return templates.TemplateResponse(request, "admin.html")
    if root in user_tabs:
        response = templates.TemplateResponse(request, "index.html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    return HTMLResponse(status_code=404, content="Not Found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
