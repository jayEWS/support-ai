"""
Live Chat Management API Routes
===============================
Endpoints for agent-to-customer live chat interactions.
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.database import db_manager
from app.core.auth_deps import get_current_agent
from app.services.websocket_manager import portal_manager
from app.core.logging import logger
from datetime import datetime, timezone

router = APIRouter(prefix="/api/livechat", tags=["Live Chat"])

@router.get("/sessions")
async def get_active_sessions(
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """
    List active portal chat users for the admin dashboard.
    Combines DB state with real-time online status.
    """
    try:
        # Get chats that have messages in DB (not yet closed/cleared)
        chats = db_manager.get_active_portal_chats()
        
        # Add real-time online status from portal_manager
        online_users = portal_manager.get_online_users()
        
        for chat in chats:
            chat["is_online"] = chat["user_id"] in online_users
            
        return chats
    except Exception as e:
        logger.error(f"Error fetching livechat sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")

@router.get("/{user_id}/messages")
async def get_session_messages(
    user_id: str,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Fetch interaction history for a specific portal user."""
    try:
        messages = db_manager.get_messages(user_id)
        context = db_manager.get_customer_context(user_id)
        
        return {
            "messages": messages,
            "context": context,
            "is_online": portal_manager.is_user_online(user_id)
        }
    except Exception as e:
        logger.error(f"Error fetching messages for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")

@router.post("/{user_id}/reply")
async def agent_reply(
    user_id: str,
    data: dict,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Send an agent reply to a portal customer."""
    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content required")
        
    try:
        # 1. Save to DB
        db_manager.save_message(user_id, "assistant", content)
        
        # 2. Push via WebSocket to customer
        agent_name = agent.get("name", "Agent")
        payload = {
            "event": "message",
            "role": "assistant",
            "content": content,
            "sender_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await portal_manager.send_to_user(user_id, payload)
        
        # 3. Echo to other admin watchers
        await portal_manager.send_to_admins(user_id, payload)
        
        return {"status": "success", "user_id": user_id}
    except Exception as e:
        logger.error(f"Error sending agent reply to {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send reply")

@router.post("/{user_id}/close")
async def close_live_session(
    user_id: str,
    data: dict,
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Close the portal chat session and optionally create a ticket."""
    option = data.get("option", "close") # "close" | "ticket" | "ticket_and_notify"
    
    chat_svc = getattr(request.app.state, 'chat_service', None)
    if not chat_svc:
         raise HTTPException(status_code=503, detail="Chat service unavailable")
         
    try:
        result = await chat_svc.close_chat(user_id, option)
        
        # Notify customer session is closed
        await portal_manager.send_to_user(user_id, {
            "event": "session_closed",
            "reason": "agent_closed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return result
    except Exception as e:
        logger.error(f"Error closing session for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
