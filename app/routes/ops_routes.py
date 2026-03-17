"""
Operations Dashboard API Routes
=================================
REST API endpoints for the AI Operations Platform.

Endpoints:
    GET  /api/ops/health           — Full system health dashboard
    GET  /api/ops/health/history   — Health check history
    GET  /api/ops/incidents        — List incidents
    GET  /api/ops/incidents/{id}   — Incident detail with AI analysis
    POST /api/ops/incidents/{id}/resolve — Resolve an incident
    GET  /api/ops/twins            — All store digital twins
    GET  /api/ops/twins/{outlet_id} — Single store twin detail
    GET  /api/ops/automation/logs  — Automation action history
    POST /api/ops/automation/execute — Manually trigger an automation
    GET  /api/ops/worker/status    — Monitoring worker status
    POST /api/ops/worker/trigger   — Force a monitoring cycle
    POST /api/ops/agent/ask        — Ask the AI Support Engineer
"""

import json
from typing import Optional, Annotated
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.core.auth_deps import require_agent, require_admin


router = APIRouter(prefix="/api/ops", tags=["AI Operations"])


# ── Request/Response Schemas ─────────────────────────────────────────

class AutomationRequest(BaseModel):
    action_type: str = Field(..., description="Action to execute (e.g., retry_integration)")
    target: str = Field(..., description="Target to act on (device_id, service name)")
    context: Optional[dict] = Field(default=None, description="Additional context")

class IncidentResolveRequest(BaseModel):
    resolution_notes: str = Field(..., description="Notes on how the incident was resolved")

class AgentAskRequest(BaseModel):
    question: str = Field(..., description="Question for the AI Support Engineer")


# ── System Health ────────────────────────────────────────────────────

@router.get("/health")
async def get_system_health(agent: Annotated[dict, Depends(require_agent)]):
    """
    Full system health dashboard — runs all health checks in real-time.
    Returns infrastructure status, device overview, and aggregate scores.
    """
    from app.monitoring.health_checks import run_all_checks

    results = await run_all_checks()

    # Categorize results
    infra = {}
    devices = []
    for r in results:
        data = r.to_dict()
        if r.outlet_id is not None:
            devices.append(data)
        else:
            infra[r.target] = data

    # Aggregate
    total_checks = len(results)
    healthy = sum(1 for r in results if r.status.value == "healthy")
    degraded = sum(1 for r in results if r.status.value == "degraded")
    critical = sum(1 for r in results if r.status.value in ("critical", "unreachable"))

    if critical > 0:
        overall = "critical"
    elif degraded > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall_status": overall,
        "summary": {
            "total_checks": total_checks,
            "healthy": healthy,
            "degraded": degraded,
            "critical": critical,
        },
        "infrastructure": infra,
        "devices": devices[:50],  # Cap for API response size
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/history")
async def get_health_history(
    agent: Annotated[dict, Depends(require_agent)],
    target: Optional[str] = None,
    target_type: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Health check history for trending / charts."""
    from app.core.database import db_manager
    from app.models.ops_models import HealthCheck

    if not db_manager:
        raise HTTPException(status_code=503, detail="Database unavailable")

    session = db_manager.get_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = session.query(HealthCheck).filter(HealthCheck.checked_at >= cutoff)

        if target:
            query = query.filter(HealthCheck.target == target)
        if target_type:
            query = query.filter(HealthCheck.target_type == target_type)

        results = query.order_by(HealthCheck.checked_at.desc()).limit(limit).all()

        return {
            "count": len(results),
            "time_range_hours": hours,
            "data": [
                {
                    "id": r.id,
                    "target": r.target,
                    "target_type": r.target_type,
                    "status": r.status,
                    "latency_ms": r.latency_ms,
                    "details": json.loads(r.details) if r.details else None,
                    "outlet_id": r.outlet_id,
                    "checked_at": r.checked_at.isoformat() if r.checked_at else None,
                }
                for r in results
            ],
        }
    finally:
        db_manager.Session.remove()


# ── Incidents ────────────────────────────────────────────────────────

@router.get("/incidents")
async def list_incidents(
    agent: Annotated[dict, Depends(require_agent)],
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    hours: int = Query(default=72, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List detected incidents with filters."""
    from app.core.database import db_manager
    from app.models.ops_models import Incident

    if not db_manager:
        raise HTTPException(status_code=503, detail="Database unavailable")

    session = db_manager.get_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = session.query(Incident).filter(Incident.created_at >= cutoff)

        if status:
            query = query.filter(Incident.status == status)
        if severity:
            query = query.filter(Incident.severity == severity)
        if category:
            query = query.filter(Incident.category == category)

        results = query.order_by(Incident.created_at.desc()).limit(limit).all()

        return {
            "count": len(results),
            "data": [
                {
                    "id": r.id,
                    "title": r.title,
                    "severity": r.severity,
                    "status": r.status,
                    "category": r.category,
                    "source": r.source,
                    "outlet_id": r.outlet_id,
                    "device_id": r.device_id,
                    "root_cause": r.root_cause,
                    "recommended_fix": r.recommended_fix,
                    "automation_action": r.automation_action,
                    "ai_confidence": r.ai_confidence,
                    "resolved_by": r.resolved_by,
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in results
            ],
        }
    finally:
        db_manager.Session.remove()


@router.get("/incidents/{incident_id}")
async def get_incident_detail(
    incident_id: int,
    agent: Annotated[dict, Depends(require_agent)],
):
    """Get full incident detail including AI analysis and investigation log."""
    from app.core.database import db_manager
    from app.models.ops_models import Incident, AutomationLog

    if not db_manager:
        raise HTTPException(status_code=503, detail="Database unavailable")

    session = db_manager.get_session()
    try:
        incident = session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Get related automation logs
        auto_logs = session.query(AutomationLog).filter_by(
            incident_id=incident_id
        ).order_by(AutomationLog.executed_at.desc()).all()

        return {
            "id": incident.id,
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity,
            "status": incident.status,
            "category": incident.category,
            "source": incident.source,
            "outlet_id": incident.outlet_id,
            "device_id": incident.device_id,
            "root_cause": incident.root_cause,
            "evidence": json.loads(incident.evidence) if incident.evidence else None,
            "recommended_fix": incident.recommended_fix,
            "automation_action": incident.automation_action,
            "ai_confidence": incident.ai_confidence,
            "investigation_log": json.loads(incident.investigation_log) if incident.investigation_log else None,
            "resolved_by": incident.resolved_by,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "resolution_notes": incident.resolution_notes,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
            "automation_logs": [
                {
                    "id": al.id,
                    "action_type": al.action_type,
                    "target": al.target,
                    "result": al.result,
                    "result_details": al.result_details,
                    "executed_by": al.executed_by,
                    "executed_at": al.executed_at.isoformat() if al.executed_at else None,
                }
                for al in auto_logs
            ],
        }
    finally:
        db_manager.Session.remove()


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: int,
    request: IncidentResolveRequest,
    agent: Annotated[dict, Depends(require_agent)],
):
    """Manually resolve an incident."""
    from app.core.database import db_manager
    from app.models.ops_models import Incident

    if not db_manager:
        raise HTTPException(status_code=503, detail="Database unavailable")

    session = db_manager.get_session()
    try:
        incident = session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        incident.status = "resolved"
        incident.resolved_by = agent.get("user_id", "unknown")
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolution_notes = request.resolution_notes
        session.commit()

        return {"status": "resolved", "incident_id": incident_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to resolve incident: {str(e)}")
    finally:
        db_manager.Session.remove()


# ── Digital Twins ────────────────────────────────────────────────────

@router.get("/twins")
async def list_store_twins(agent: Annotated[dict, Depends(require_agent)]):
    """Get summary of all store digital twins."""
    from app.digital_twin.twin_manager import TwinManager
    tm = TwinManager()
    twins = await tm.get_all_twins()
    return {"count": len(twins), "stores": twins}


@router.get("/twins/{outlet_id}")
async def get_store_twin(
    outlet_id: int,
    agent: Annotated[dict, Depends(require_agent)],
):
    """Get detailed digital twin for a specific store."""
    from app.digital_twin.twin_manager import TwinManager
    tm = TwinManager()
    twin = await tm.get_store_twin(outlet_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"No twin found for outlet {outlet_id}")
    return twin


# ── Automation ───────────────────────────────────────────────────────

@router.get("/automation/logs")
async def list_automation_logs(
    agent: Annotated[dict, Depends(require_agent)],
    action_type: Optional[str] = None,
    result: Optional[str] = None,
    hours: int = Query(default=72, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get automation action history."""
    from app.core.database import db_manager
    from app.models.ops_models import AutomationLog

    if not db_manager:
        raise HTTPException(status_code=503, detail="Database unavailable")

    session = db_manager.get_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = session.query(AutomationLog).filter(AutomationLog.executed_at >= cutoff)

        if action_type:
            query = query.filter(AutomationLog.action_type == action_type)
        if result:
            query = query.filter(AutomationLog.result == result)

        results = query.order_by(AutomationLog.executed_at.desc()).limit(limit).all()

        return {
            "count": len(results),
            "data": [
                {
                    "id": al.id,
                    "incident_id": al.incident_id,
                    "action_type": al.action_type,
                    "target": al.target,
                    "result": al.result,
                    "result_details": al.result_details,
                    "executed_by": al.executed_by,
                    "executed_at": al.executed_at.isoformat() if al.executed_at else None,
                }
                for al in results
            ],
        }
    finally:
        db_manager.Session.remove()


@router.post("/automation/execute")
async def execute_automation(
    request: AutomationRequest,
    agent: Annotated[dict, Depends(require_admin)],
):
    """Manually trigger an automation action (admin only)."""
    from app.automation.engine import automation_engine

    result = await automation_engine.execute(
        incident_id=None,
        action_type=request.action_type,
        target=request.target,
        context=request.context,
        executed_by=f"agent:{agent.get('user_id', 'unknown')}",
    )

    return result


# ── Monitoring Worker ────────────────────────────────────────────────

@router.get("/worker/status")
async def get_worker_status(agent: Annotated[dict, Depends(require_agent)]):
    """Get the monitoring worker's current status."""
    from app.monitoring.worker import monitoring_worker
    return monitoring_worker.get_status()


@router.post("/worker/trigger")
async def trigger_monitoring_cycle(agent: Annotated[dict, Depends(require_admin)]):
    """Manually trigger a monitoring cycle (admin only)."""
    from app.monitoring.worker import monitoring_worker

    if not monitoring_worker.running:
        return {"status": "error", "message": "Monitoring worker is not running"}

    # Run cycle in background
    import asyncio
    asyncio.create_task(monitoring_worker._run_cycle())

    return {
        "status": "triggered",
        "message": "Monitoring cycle triggered in background",
        "cycle_count": monitoring_worker.cycle_count + 1,
    }


# ── AI Support Engineer ─────────────────────────────────────────────

@router.post("/agent/ask")
async def ask_support_agent(
    request: AgentAskRequest,
    agent: Annotated[dict, Depends(require_agent)],
):
    """
    Ask the AI Support Engineer a question.
    The agent will gather relevant system data and provide an actionable answer.
    """
    from app.agents.support_agent import SupportEngineerAgent

    engineer = SupportEngineerAgent()
    result = await engineer.ask(request.question)
    return result


# ── Dashboard Summary ────────────────────────────────────────────────

@router.get("/dashboard")
async def get_ops_dashboard(agent: Annotated[dict, Depends(require_agent)]):
    """
    Aggregated dashboard data — combines health, incidents, twins, and automation
    into a single API call for the frontend dashboard.
    """
    from app.core.database import db_manager
    from app.models.ops_models import Incident, AutomationLog, HealthCheck
    from app.monitoring.worker import monitoring_worker
    from app.digital_twin.twin_manager import TwinManager
    from sqlalchemy import func as sqlfunc

    result = {
        "worker": monitoring_worker.get_status(),
        "incidents": {"open": 0, "resolved_24h": 0, "by_severity": {}},
        "automation": {"total_24h": 0, "success_24h": 0, "failed_24h": 0},
        "stores": [],
    }

    if not db_manager:
        return result

    session = db_manager.get_session()
    try:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        # Incident stats
        open_count = session.query(sqlfunc.count(Incident.id)).filter(
            Incident.status.notin_(["resolved"])
        ).scalar() or 0

        resolved_24h = session.query(sqlfunc.count(Incident.id)).filter(
            Incident.status == "resolved",
            Incident.resolved_at >= day_ago,
        ).scalar() or 0

        severity_counts = session.query(
            Incident.severity, sqlfunc.count(Incident.id)
        ).filter(
            Incident.status.notin_(["resolved"])
        ).group_by(Incident.severity).all()

        result["incidents"] = {
            "open": open_count,
            "resolved_24h": resolved_24h,
            "by_severity": {s: c for s, c in severity_counts},
        }

        # Automation stats
        auto_total = session.query(sqlfunc.count(AutomationLog.id)).filter(
            AutomationLog.executed_at >= day_ago
        ).scalar() or 0

        auto_success = session.query(sqlfunc.count(AutomationLog.id)).filter(
            AutomationLog.executed_at >= day_ago,
            AutomationLog.result == "success",
        ).scalar() or 0

        auto_failed = session.query(sqlfunc.count(AutomationLog.id)).filter(
            AutomationLog.executed_at >= day_ago,
            AutomationLog.result == "failed",
        ).scalar() or 0

        result["automation"] = {
            "total_24h": auto_total,
            "success_24h": auto_success,
            "failed_24h": auto_failed,
        }

        # Store twins summary
        tm = TwinManager()
        result["stores"] = await tm.get_all_twins()

    except Exception as e:
        logger.error(f"[OpsRoute] Dashboard query error: {e}")
    finally:
        db_manager.Session.remove()

    return result
