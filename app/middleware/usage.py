"""
Usage Tracking Middleware
==========================
Automatically tracks API usage per tenant for billing and plan enforcement.
Runs after request completion to log resource consumption.
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.repositories.base import TenantContext
from app.core.logging import logger


# Map API paths to trackable resource types
TRACKED_ENDPOINTS = {
    "/api/chat": "ai_messages",
    "/api/knowledge/upload": "knowledge_files",
    "/webhook/whatsapp": "whatsapp_messages",
}


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """
    Tracks API usage per tenant per request.
    Increments counters in UsageTracking table after successful requests.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        # Only track on success
        if response.status_code < 400:
            tenant_id = TenantContext.get()
            if tenant_id and tenant_id != "default":
                path = request.url.path
                method = request.method.upper()

                resource = self._get_tracked_resource(path, method)
                if resource:
                    try:
                        # Lazy import to avoid circular dependency
                        from app.repositories.usage_repo import UsageRepository
                        from app.core.database import db_manager

                        if db_manager:
                            usage_repo = UsageRepository(db_manager.Session)
                            usage_repo.increment_usage(tenant_id, resource)
                            latency = int((time.time() - start_time) * 1000)
                            logger.debug(
                                f"Usage tracked: tenant={tenant_id}, resource={resource}, latency={latency}ms"
                            )
                    except Exception as e:
                        # Never block requests for usage tracking failures
                        logger.warning(f"Usage tracking error: {e}")

        return response

    @staticmethod
    def _get_tracked_resource(path: str, method: str) -> str:
        """Determine which resource type this request consumes."""
        # Only track POST/PUT methods that create resources
        if method not in ("POST", "PUT"):
            return None

        for endpoint, resource in TRACKED_ENDPOINTS.items():
            if path.startswith(endpoint):
                return resource

        # Track ticket creation
        if path == "/api/tickets" and method == "POST":
            return "tickets_created"

        return None
