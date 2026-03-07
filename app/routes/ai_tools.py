from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional, Dict, List, Any, Annotated
from pydantic import BaseModel
from app.core.database import db_manager
from app.core.logging import logger
from app.core.config import settings
from app.core.auth_deps import require_agent, require_admin
from app.models.models import AIInteraction
from sqlalchemy import func, desc
from app.repositories.voucher_repo import VoucherRepository
from app.schemas.schemas import (
    DBQueryRequest,
    CheckVoucherRequest,
    RedeemVoucherRequest,
    DeviceCheckRequest,
    LogSearchRequest
)

router = APIRouter(prefix="/api/ai", tags=["AI Tools"])

# --- Request Schemas ---

class FeedbackRequest(BaseModel):
    is_correct: bool
    correction: Optional[str] = None

# --- Metrics Endpoints ---
# Security Fix C1: ALL endpoints now require authentication

@router.get("/metrics")
async def get_ai_metrics(agent: Annotated[dict, Depends(require_agent)]):
    """Enterprise AI Performance Summary. Requires authenticated agent."""
    session = db_manager.get_session()
    try:
        # Total interactions
        total = session.query(func.count(AIInteraction.id)).scalar() or 0
        
        # Resolution Rate (Simple Mock: % of interactions with confidence > 0.7)
        resolved = session.query(func.count(AIInteraction.id)).filter(AIInteraction.confidence > 0.7).scalar() or 0
        resolution_rate = (resolved / total * 100) if total > 0 else 0
        
        # Average Confidence
        avg_conf = session.query(func.avg(AIInteraction.confidence)).scalar() or 0
        
        return {
            "total_interactions": total,
            "resolution_rate": round(resolution_rate, 1),
            "average_confidence": round(float(avg_conf), 2),
            "hallucination_reports": 0,
            "top_categories": ["Printer", "Login", "Payment"]
        }
    finally:
        db_manager.Session.remove()

@router.get("/interactions")
async def list_ai_interactions(agent: Annotated[dict, Depends(require_agent)], limit: int = 50):
    """Recent AI Interactions for human review. Requires authenticated agent."""
    # Security: Cap limit to prevent data dump
    limit = min(limit, 100)
    session = db_manager.get_session()
    try:
        results = session.query(AIInteraction).order_by(desc(AIInteraction.created_at)).limit(limit).all()
        return [{
            "id": r.id,
            "query": r.query,
            "response": r.response,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat(),
            "status": r.resolution_status
        } for r in results]
    finally:
        db_manager.Session.remove()

@router.post("/interactions/{interaction_id}/feedback")
async def submit_ai_feedback(interaction_id: int, req: FeedbackRequest, agent: Annotated[dict, Depends(require_agent)]):
    """Allows human agents to correct or confirm AI answers (Self-Learning). Requires authenticated agent."""
    session = db_manager.get_session()
    try:
        log = session.get(AIInteraction, interaction_id)
        if not log:
            raise HTTPException(status_code=404, detail="Interaction not found")
        
        log.resolution_status = "solved" if req.is_correct else "correction_needed"
        log.human_correction = req.correction
        session.commit()
        return {"status": "success"}
    finally:
        db_manager.Session.remove()

# --- Tool Endpoints --- (Rest of existing tools)
# Security Fix C1: db_query now requires ADMIN role — this is the most sensitive endpoint

@router.post("/db_query")
async def tool_db_query(req: DBQueryRequest, agent: Annotated[dict, Depends(require_admin)]):
    """
    Tool for AI to query internal database tables safely.
    Requires ADMIN authentication.
    Tables: tickets, users, messages, audit_logs
    """
    try:
        # Security: Cap limit to prevent massive data dumps
        safe_limit = min(req.limit, 100)
        results = db_manager.execute_safe_query(
            table_name=req.table_name,
            filters=req.filters,
            limit=safe_limit
        )
        return {"status": "success", "count": len(results), "data": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"AI DB Query failed: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

@router.post("/check_voucher")
async def tool_check_voucher(
    req: CheckVoucherRequest,
    agent: Annotated[dict, Depends(require_agent)]
):
    """
    Tool to validate loyalty vouchers against the production POS database.
    Requires authenticated agent.
    """
    repo = VoucherRepository(db_manager.Session)
    try:
        result = repo.check_voucher_validity(req.voucher_code)
        return result
    except Exception as e:
        logger.error(f"Voucher check failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to check voucher status")


@router.post("/redeem_voucher")
async def tool_redeem_voucher(
    req: RedeemVoucherRequest,
    agent: Annotated[dict, Depends(require_agent)]
):
    """
    Redeem a loyalty voucher for the current transaction.
    P0 FIX: Implements row-level locking (with_for_update) to prevent double-spending.
    Requires authenticated agent.
    """
    repo = VoucherRepository(db_manager.Session)
    try:
        # P0 Fix: Row-level locking logic is within the repository
        result = repo.redeem_voucher(req.voucher_code, agent_id=agent.get("user_id", "ai_agent"))
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voucher redemption failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to redeem voucher")

@router.post("/device_check")
async def tool_device_check(
    req: DeviceCheckRequest,
    agent: Annotated[dict, Depends(require_agent)]
):
    """
    Tool to check POS hardware status.
    (Mock implementation)
    """
    # Simulate device check
    status = "online"
    health = "good"
    details = {}
    
    if "err" in req.device_id.lower():
        status = "offline"
        health = "critical"
        details = {"last_heartbeat": "2 hours ago", "error_code": "NET_TIMEOUT"}
    elif "warn" in req.device_id.lower():
        status = "online"
        health = "warning"
        details = {"paper_level": "low", "cpu_load": "90%"}
        
    return {
        "device_id": req.device_id,
        "type": req.device_type,
        "status": status,
        "health": health,
        "details": details
    }

@router.post("/log_search")
async def tool_log_search(
    req: LogSearchRequest,
    agent: Annotated[dict, Depends(require_agent)]
):
    """
    Tool to search device logs for errors.
    """
    # Mock logs
    logs = []
    if "err" in req.device_id.lower():
        logs.append(f"[ERROR] {req.minutes_ago - 5} mins ago: Connection timeout to payment gateway")
        logs.append(f"[WARN] {req.minutes_ago - 10} mins ago: High latency detected")
    
    return {
        "device_id": req.device_id,
        "found_logs": len(logs),
        "logs": logs
    }
