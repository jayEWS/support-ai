"""
Tenant API Routes
==================
API endpoints for tenant management, plan listing, and SaaS administration.
Mounted as a sub-router in main.py.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from app.core.logging import logger

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


# ── Schemas ───────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9\-]+$")
    industry: Optional[str] = None
    plan_name: str = "Starter"

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None

class FeatureFlagUpdate(BaseModel):
    feature_key: str
    enabled: bool
    config: Optional[dict] = None


# ── Helper to get repos ──────────────────────────────────────────────

def _get_tenant_repo(request: Request):
    """Get TenantRepository from app state."""
    repo = getattr(request.app.state, "tenant_repo", None)
    if not repo:
        raise HTTPException(status_code=503, detail="Tenant service not initialized")
    return repo

def _get_usage_repo(request: Request):
    """Get UsageRepository from app state."""
    repo = getattr(request.app.state, "usage_repo", None)
    if not repo:
        raise HTTPException(status_code=503, detail="Usage service not initialized")
    return repo

def _get_ai_log_repo(request: Request):
    """Get AILogRepository from app state."""
    repo = getattr(request.app.state, "ai_log_repo", None)
    if not repo:
        raise HTTPException(status_code=503, detail="AI observability not initialized")
    return repo


# ── Tenant CRUD ───────────────────────────────────────────────────────

@router.post("/register")
async def register_tenant(body: TenantCreate, request: Request):
    """Self-serve tenant registration (public endpoint)."""
    repo = _get_tenant_repo(request)
    try:
        result = repo.create_tenant(
            name=body.name,
            slug=body.slug,
            industry=body.industry,
            plan_name=body.plan_name,
        )
        return {"status": "success", "tenant": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
async def list_tenants(request: Request, status: Optional[str] = None):
    """List all tenants (admin only)."""
    repo = _get_tenant_repo(request)
    return {"tenants": repo.list_tenants(status=status)}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, request: Request):
    """Get tenant details."""
    repo = _get_tenant_repo(request)
    tenant = repo.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, body: TenantUpdate, request: Request):
    """Update tenant details."""
    repo = _get_tenant_repo(request)
    if body.status:
        repo.update_tenant_status(tenant_id, body.status)
    if body.name or body.industry:
        settings_update = {}
        if body.name:
            settings_update["name"] = body.name
        if body.industry:
            settings_update["industry"] = body.industry
        repo.update_tenant_settings(tenant_id, settings_update)
    return {"status": "updated"}


# ── Tenant Agents ─────────────────────────────────────────────────────

@router.get("/{tenant_id}/agents")
async def list_tenant_agents(tenant_id: str, request: Request):
    """List agents for a tenant."""
    repo = _get_tenant_repo(request)
    return {"agents": repo.get_tenant_agents(tenant_id)}


# ── Feature Flags ─────────────────────────────────────────────────────

@router.get("/{tenant_id}/features")
async def get_features(tenant_id: str, request: Request):
    """Get all feature flags for a tenant."""
    repo = _get_tenant_repo(request)
    return {"features": repo.get_tenant_features(tenant_id)}


@router.post("/{tenant_id}/features")
async def set_feature(tenant_id: str, body: FeatureFlagUpdate, request: Request):
    """Set a feature flag for a tenant."""
    repo = _get_tenant_repo(request)
    repo.set_feature_flag(tenant_id, body.feature_key, body.enabled, body.config)
    return {"status": "updated", "feature": body.feature_key, "enabled": body.enabled}


# ── Usage & Billing ───────────────────────────────────────────────────

@router.get("/{tenant_id}/usage")
async def get_usage(tenant_id: str, request: Request):
    """Get current usage for a tenant."""
    repo = _get_usage_repo(request)
    return repo.get_current_usage(tenant_id)


@router.get("/{tenant_id}/usage/history")
async def get_usage_history(tenant_id: str, request: Request, months: int = 6):
    """Get usage history."""
    repo = _get_usage_repo(request)
    return {"history": repo.get_usage_history(tenant_id, months=months)}


@router.get("/{tenant_id}/usage/limits")
async def check_limits(tenant_id: str, request: Request, resource: str = "ai_messages"):
    """Check plan limit for a resource."""
    repo = _get_usage_repo(request)
    return repo.check_plan_limit(tenant_id, resource)


# ── AI Observability ──────────────────────────────────────────────────

@router.get("/{tenant_id}/ai/metrics")
async def get_ai_metrics(tenant_id: str, request: Request, days: int = 30):
    """Get AI quality metrics for a tenant."""
    repo = _get_ai_log_repo(request)
    return repo.get_ai_metrics(tenant_id, days=days)


@router.get("/{tenant_id}/ai/interactions")
async def get_ai_interactions(tenant_id: str, request: Request, limit: int = 20):
    """Get recent AI interactions."""
    repo = _get_ai_log_repo(request)
    return {"interactions": repo.get_recent_interactions(tenant_id, limit=limit)}


@router.get("/{tenant_id}/ai/low-confidence")
async def get_low_confidence(tenant_id: str, request: Request, threshold: float = 0.5):
    """Get low-confidence AI interactions (quality monitoring)."""
    repo = _get_ai_log_repo(request)
    return {"interactions": repo.get_low_confidence_interactions(tenant_id, threshold=threshold)}


# ── Plans (Public) ────────────────────────────────────────────────────

plans_router = APIRouter(prefix="/api/plans", tags=["Plans"])


@plans_router.get("/")
async def list_plans(request: Request):
    """List available subscription plans (public)."""
    repo = _get_tenant_repo(request)
    return {"plans": repo.list_plans()}


@plans_router.get("/{plan_id}")
async def get_plan(plan_id: int, request: Request):
    """Get plan details."""
    repo = _get_tenant_repo(request)
    plan = repo.get_plan(plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
