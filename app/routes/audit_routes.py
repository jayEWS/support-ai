"""
Audit Logging API Routes
=========================
Endpoints for retrieving system audit trails.
Extracted from main.py for architectural modularity.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db_manager
from app.core.auth_deps import require_admin
from app.core.logging import logger

router = APIRouter(prefix="/api/audit-logs", tags=["Audit"])


def _require_db():
    if db_manager is None:
        raise HTTPException(
            status_code=503, 
            detail="Database unavailable. Please check DATABASE_URL and DB server connectivity."
        )
    return db_manager


@router.get("")
async def get_audit_logs(
    agent: Annotated[dict, Depends(require_admin)],
    page: int = 1,
    per_page: int = 50
):
    """Retrieve system audit logs with pagination (Admin Only)."""
    return _require_db().get_audit_logs(page=page, per_page=per_page)
