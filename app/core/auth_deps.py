"""
Shared authentication dependencies for FastAPI routes.
Extracted from main.py to allow reuse across routers (ai_tools, etc.)
"""

from fastapi import Request, HTTPException
from app.utils.auth_utils import decode_access_token
from app.core.database import db_manager
from app.core.logging import logger
from app.utils.async_db import run_sync
from typing import Annotated
from fastapi import Depends


def _extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def require_agent(request: Request) -> dict:
    """
    FastAPI dependency that validates the access token and returns agent info.
    Use as: agent: Annotated[dict, Depends(require_agent)]

    Raises HTTPException 401 if not authenticated.
    """
    token = _extract_bearer_token(request) or request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not db_manager:
        raise HTTPException(status_code=503, detail="Database unavailable")

    user_id = payload.get("sub")
    agent = await run_sync(db_manager.get_agent, user_id)
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found")

    # ✅ FIXED: Role is already fetched from DB in get_agent() (not from JWT)
    # agent["role"] is set by DatabaseManager.get_agent() from DB roles table
    
    return agent

get_current_agent = require_agent


async def require_admin(request: Request) -> dict:
    """
    FastAPI dependency that validates the agent has admin role.
    Use as: agent: Annotated[dict, Depends(require_admin)]

    Raises HTTPException 403 if not admin.
    """
    agent = await require_agent(request)
    if agent.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return agent

get_admin_agent = require_admin
