"""
Base Repository
================
Provides session management, tenant scoping, and common patterns
shared across all domain repositories.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, TypeVar, Type, List
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T")

# ── Tenant Context (Thread-Safe) ──────────────────────────────────────
# This ContextVar holds the current tenant_id for the request lifecycle.
# Set by TenantMiddleware, read by repositories for automatic scoping.
_current_tenant: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)


class TenantContext:
    """Thread-safe tenant context for request-scoped tenant isolation."""

    @staticmethod
    def set(tenant_id: str):
        _current_tenant.set(tenant_id)

    @staticmethod
    def get() -> Optional[str]:
        return _current_tenant.get()

    @staticmethod
    def require() -> str:
        """Get tenant_id or raise if not set (for tenant-scoped operations)."""
        tid = _current_tenant.get()
        if not tid:
            raise ValueError("Tenant context not set. Ensure TenantMiddleware is active.")
        return tid

    @staticmethod
    def clear():
        _current_tenant.set(None)


class BaseRepository:
    """
    Base class for all domain repositories.
    
    Provides:
    - Managed session via context manager
    - Automatic tenant scoping helpers
    - Common CRUD patterns
    """

    def __init__(self, session_factory: scoped_session):
        self._Session = session_factory

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self._Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self._Session.remove()

    def get_session(self) -> Session:
        """Get a raw session (for backward compatibility). Caller must handle cleanup."""
        return self._Session()

    @property
    def tenant_id(self) -> Optional[str]:
        """Current tenant from context."""
        return TenantContext.get()

    def require_tenant(self) -> str:
        """Require tenant_id or raise."""
        return TenantContext.require()

    def _apply_tenant_filter(self, query, model_class, tenant_id: str = None):
        """Apply tenant_id filter if the model has a TenantID column."""
        tid = tenant_id or self.tenant_id
        if tid and hasattr(model_class, "tenant_id"):
            return query.filter(model_class.tenant_id == tid)
        # P0 Safety: Warn if multi-tenant is enabled but no tenant context is set
        if hasattr(model_class, "tenant_id") and not tid:
            from app.core.config import settings as _settings
            if getattr(_settings, 'MULTI_TENANT_ENABLED', False):
                logger.warning(
                    f"[SECURITY] No tenant context for {model_class.__name__} query. "
                    f"Data may leak across tenants. Set TenantContext before querying."
                )
        return query
