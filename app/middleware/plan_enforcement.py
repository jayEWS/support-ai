"""
Plan Enforcement Middleware
=============================
Checks plan limits before allowing resource-consuming operations.
Returns 429 (Too Many Requests) when limits are exceeded.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.repositories.base import TenantContext
from app.core.logging import logger


# Endpoints that consume plan-limited resources
ENFORCED_ENDPOINTS = {
    "POST:/api/chat": "ai_messages",
    "POST:/api/portal/chat": "ai_messages",       # P0 Fix: Portal chat also consumes AI quota
    "POST:/api/portal/kb/query": "ai_messages",   # P0 Fix: KB query also consumes AI quota
    "POST:/api/knowledge/upload": "knowledge_files",
    "POST:/api/tickets": "tickets",
}


class PlanEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Enforces plan limits on resource-consuming endpoints.
    Checks before the request is processed and returns 429 if exceeded.
    """

    async def dispatch(self, request: Request, call_next):
        tenant_id = TenantContext.get()

        # Skip enforcement for default tenant (backward compat) or missing tenant
        if not tenant_id or tenant_id == "default":
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()
        key = f"{method}:{path}"

        resource = ENFORCED_ENDPOINTS.get(key)
        if resource:
            try:
                from app.repositories.usage_repo import UsageRepository
                from app.core.database import db_manager

                if db_manager:
                    usage_repo = UsageRepository(db_manager.Session)
                    check = usage_repo.check_plan_limit(tenant_id, resource)

                    if not check["allowed"]:
                        logger.warning(
                            f"Plan limit exceeded: tenant={tenant_id}, "
                            f"resource={resource}, used={check['current']}/{check['limit']}"
                        )
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": "Plan limit exceeded",
                                "resource": resource,
                                "current": check["current"],
                                "limit": check["limit"],
                                "message": f"You've reached your plan limit for {resource.replace('_', ' ')}. "
                                           f"Please upgrade your plan to continue.",
                            },
                        )
            except Exception as e:
                # Never block requests due to enforcement errors
                logger.warning(f"Plan enforcement check error: {e}")

        return await call_next(request)
