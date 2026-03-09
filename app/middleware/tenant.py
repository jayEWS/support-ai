"""
Tenant Middleware
==================
Extracts tenant context from the request (header, subdomain, or JWT claim)
and sets it in the thread-safe TenantContext for downstream use.

Resolution Order:
1. X-Tenant-ID header (for API calls)
2. JWT claim "tenant_id" (from authenticated sessions)
3. Subdomain (e.g., acme.support.edgeworks.co.id)
4. Default tenant (for backward compatibility during migration)
"""

import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.repositories.base import TenantContext
from app.core.logging import logger
from app.core.config import settings


# Routes that don't require tenant context
TENANT_EXEMPT_PATHS = {
    "/health",
    "/login",
    "/docs",
    "/openapi.json",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/google",
    "/api/auth/google/callback",
    "/api/auth/google/login",
    "/api/auth/magic-link/request",
    "/api/auth/magic-link/verify",
    "/api/plans",  # Public plan listing
    "/api/tenants/register",  # Self-serve signup
    "/webhook/whatsapp",
}

# Default tenant ID for backward compatibility (single-tenant mode)
DEFAULT_TENANT_ID = getattr(settings, "DEFAULT_TENANT_ID", "default")


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extracts tenant_id from request and sets TenantContext.
    
    In single-tenant mode (migration period), uses DEFAULT_TENANT_ID.
    In multi-tenant mode, requires explicit tenant identification.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Skip tenant resolution for exempt paths
        if self._is_exempt(path):
            TenantContext.set(DEFAULT_TENANT_ID)
            response = await call_next(request)
            TenantContext.clear()
            return response

        # Skip for static files and uploads
        if path.startswith("/uploads/") or path.startswith("/static/"):
            TenantContext.set(DEFAULT_TENANT_ID)
            response = await call_next(request)
            TenantContext.clear()
            return response

        # Resolve tenant
        tenant_id = self._resolve_tenant(request)

        if not tenant_id:
            # In multi-tenant mode, we MUST resolve a tenant unless the path is exempt.
            # Falling back to 'default' in production SaaS is a security risk.
            if settings.MULTI_TENANT_ENABLED:
                logger.warning(f"Tenant resolution failed for {path}. Rejecting request.")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Tenant identification required (X-Tenant-ID header or valid session)."}
                )
            
            # During migration or single-tenant mode: fall back to default tenant
            tenant_id = DEFAULT_TENANT_ID
            logger.debug(f"No tenant resolved for {path}, using default: {DEFAULT_TENANT_ID}")

        TenantContext.set(tenant_id)

        try:
            response = await call_next(request)
            # Add tenant_id to response headers for debugging
            response.headers["X-Tenant-ID"] = tenant_id
            return response
        finally:
            TenantContext.clear()

    def _resolve_tenant(self, request: Request) -> str:
        """Resolve tenant_id from multiple sources."""
        
        # 1. Explicit header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_id

        # 2. JWT claim (from auth middleware)
        # The auth system should inject tenant_id into request.state
        if hasattr(request.state, "tenant_id"):
            return request.state.tenant_id

        # 3. Subdomain extraction (e.g., acme.support.edgeworks.co.id)
        host = request.headers.get("host", "")
        tenant_from_subdomain = self._extract_subdomain_tenant(host)
        if tenant_from_subdomain:
            return tenant_from_subdomain

        # 4. Query parameter (for portal widget embedding)
        tenant_id = request.query_params.get("tenant_id")
        if tenant_id:
            return tenant_id

        return None

    @staticmethod
    def _extract_subdomain_tenant(host: str) -> str:
        """
        Extract tenant slug from subdomain.
        e.g., 'acme.support.edgeworks.co.id' → 'acme'
        """
        if not host:
            return None
        # Remove port
        host = host.split(":")[0]
        # Known base domains
        base_domains = [
            "support.edgeworks.co.id",
            "localhost",
            "127.0.0.1",
        ]
        for base in base_domains:
            if host.endswith(base) and host != base:
                subdomain = host[: -(len(base) + 1)]  # Remove .base
                if subdomain and subdomain != "www":
                    return subdomain
        return None

    @staticmethod
    def _is_exempt(path: str) -> bool:
        """Check if path is exempt from tenant requirement."""
        # Exact match
        if path in TENANT_EXEMPT_PATHS:
            return True
        # Prefix match for page routes
        if path in ("/", "/chat", "/admin", "/user"):
            return True
        # Catch-all HTML pages
        if not path.startswith("/api/") and not path.startswith("/webhook/") and not path.startswith("/ws/"):
            return True
        return False
