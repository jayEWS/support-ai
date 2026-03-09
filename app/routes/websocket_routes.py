"""
WebSocket Management API Routes
===============================
Secure real-time communication endpoints with Origin validation and Authentication.
Extracted from main.py. Fixes CSWH and Cross-Tenant leakage (P1).
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Depends
from app.core.database import db_manager
from app.core.auth_deps import decode_access_token
from app.services.websocket_manager import manager, portal_manager
from app.core.config import settings
from app.core.logging import logger
from app.utils.security import bind_user_ip

router = APIRouter(prefix="/ws", tags=["WebSocket"])

def _validate_origin(websocket: WebSocket):
    """CSWH Protection: Validate Origin header against whitelist (Security Fix)."""
    origin = websocket.headers.get("origin")
    allowed = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"]
    if "*" in allowed:
        return
    if not origin or origin not in allowed:
        logger.warning(f"WebSocket rejected: Invalid Origin {origin}")
        # WebSocket cannot raise HTTPException like normal routes - must be handled in endpoint
        return False
    return True

async def _get_ws_agent(websocket: WebSocket):
    """Extract and verify agent from query token (Security Fix C3)."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    
    # Scoped agent lookup
    agent = db_manager.get_agent(payload.get("sub"))
    if not agent:
        return None
    return agent

@router.websocket("/chat/{session_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket, 
    session_id: int, 
    user_id: str, 
    user_type: str
):
    """Secure internal chat WebSocket for agents/customers. Implements IDOR protection."""
    if not _validate_origin(websocket):
        await websocket.close(code=4003)
        return

    # 1. Authenticate Agent if user_type is agent
    agent = None
    if user_type == "agent":
        agent = await _get_ws_agent(websocket)
        if not agent:
             await websocket.close(code=4001)
             return
        user_id = agent["user_id"] # Use verified ID

    # 2. Verify Session & Tenant Isolation
    db = db_manager
    if not db:
        await websocket.close(code=1008)
        return
        
    session = db.get_chat_session(session_id)
    if not session:
        await websocket.close(code=1008)
        return
    
    # IDOR check: Is the user a participant in this session? (Security Fix)
    if user_type == "agent":
        if session["agent_id"] != user_id:
             logger.warning(f"[SECURITY] Agent {user_id} tried to access session {session_id} assigned to {session['agent_id']}")
             await websocket.close(code=4003)
             return
    elif user_type == "customer":
        if session["customer_id"] != user_id:
             logger.warning(f"[SECURITY] Customer {user_id} tried to access session {session_id} assigned to {session['customer_id']}")
             await websocket.close(code=4003)
             return
        # P1 Fix: Bind customer user_id to IP for IDOR prevention
        try:
            bind_user_ip(user_id, websocket)
        except HTTPException:
            await websocket.close(code=4003)
            return
    
    # P1 Fix: Cross-tenant IDOR check
    if agent and session.get("tenant_id") and agent.get("tenant_id") and session["tenant_id"] != agent.get("tenant_id"):
        logger.warning(f"Agent {agent['user_id']} tried to access session {session_id} in another tenant")
        await websocket.close(code=4003)
        return

    await manager.connect(session_id, user_id, user_type, websocket)
    try:
        while True:
            # We must handle the receive loop here
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "message":
                content = msg.get("content", "")[:5000]
                msg_id = db.save_chat_message(session_id, user_id, user_type, content)
                await manager.broadcast(session_id, {
                    "event": "message", 
                    "message_id": msg_id, 
                    "sender_id": user_id, 
                    "sender_type": user_type, 
                    "content": content, 
                    "sent_at": datetime.now(timezone.utc).isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    except Exception as e:
        logger.error(f"WS Chat error: {e}")
        manager.disconnect(session_id, websocket)

@router.websocket("/portal/{user_id}")
async def portal_websocket(websocket: WebSocket, user_id: str):
    """Real-time push channel for portal users. Validates origins and optional auth."""
    if not _validate_origin(websocket):
         await websocket.close(code=4003)
         return
    
    # Security: Validate user_id format to prevent abuse
    import re
    if not re.match(r'^[\w@+.\-]{1,64}$', user_id):
        await websocket.close(code=4003)
        return
    
    if len(existing) >= 5:
        logger.warning(f"[SECURITY] WebSocket flood: {user_id} already has {len(existing)} connections")
        await websocket.close(code=4008)
        return

    # P1 Fix: Bind portal user_id to IP for IDOR prevention
    try:
        bind_user_ip(user_id, websocket)
    except HTTPException:
        await websocket.close(code=4003)
        return
         
    await portal_manager.connect_user(user_id, websocket)
    heartbeat_task = None
    
    async def _heartbeat():
        try:
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"event": "ping"})
        except: pass

    heartbeat_task = asyncio.create_task(_heartbeat())
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "message":
                content = msg.get("content", "").strip()
                if content:
                    db_manager.save_message(user_id, "user", content)
                    await portal_manager.send_to_admins(user_id, {
                        "event": "message",
                        "role": "user",
                        "content": content,
                        "user_id": user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
    except WebSocketDisconnect:
        if heartbeat_task: heartbeat_task.cancel()
        portal_manager.disconnect_user(user_id, websocket)
    except Exception:
        if heartbeat_task: heartbeat_task.cancel()
        portal_manager.disconnect_user(user_id, websocket)

@router.websocket("/portal/admin/{user_id}")
async def portal_admin_websocket(websocket: WebSocket, user_id: str):
    """Admin watcher WebSocket. Enforces authentication and tenant isolation."""
    if not _validate_origin(websocket):
         await websocket.close(code=4003)
         return

    agent = await _get_ws_agent(websocket)
    if not agent:
        await websocket.close(code=4001)
        return
        
    # P1 Fix: Scoped check - can this agent watch this specific portal user?
    # Ensure customer user_id exists and matches tenant
    customer = db_manager.get_user(user_id)
    if not customer or (customer.get("tenant_id") and agent.get("tenant_id") and customer["tenant_id"] != agent.get("tenant_id")):
        logger.warning(f"Agent {agent['user_id']} tried to watch unauthorized customer {user_id}")
        await websocket.close(code=4003)
        return

    await portal_manager.connect_admin(user_id, websocket)
    agent_name = agent.get("name", "Agent")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "message":
                content = msg.get("content", "").strip()[:5000]
                if content:
                    db_manager.save_message(user_id, "assistant", content)
                    # Send to customer
                    await portal_manager.send_to_user(user_id, {
                        "event": "message",
                        "role": "assistant",
                        "content": content,
                        "sender_name": agent_name,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    # Echo back to other admin watchers
                    await portal_manager.send_to_admins(user_id, {
                        "event": "message",
                        "role": "assistant",
                        "content": content,
                        "sender_name": agent_name,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            elif msg.get("event") == "typing":
                await portal_manager.send_to_user(user_id, {
                    "event": "typing",
                    "sender_name": agent_name
                })
    except Exception:
        portal_manager.disconnect_admin(user_id, websocket)
