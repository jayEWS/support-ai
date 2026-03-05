"""
Repository Layer
=================
Split from monolithic DatabaseManager (1,600+ lines) into domain-specific repositories.
Each repository handles a single bounded context for better maintainability and testability.

Architecture:
    BaseRepository → provides session management & tenant scoping
    ├── TenantRepository    → Tenant CRUD, plan management
    ├── UserRepository      → Customer/portal user operations
    ├── AgentRepository     → Agent/admin user operations
    ├── TicketRepository    → Ticket lifecycle
    ├── MessageRepository   → Chat messages (portal + live)
    ├── KnowledgeRepository → Knowledge base metadata
    ├── AuthRepository      → MFA, tokens, magic links
    ├── AuditRepository     → Audit logging
    ├── UsageRepository     → Usage tracking & billing
    └── AILogRepository     → AI interaction observability

Migration Note:
    The original `db_manager` singleton in `app/core/database.py` remains as a facade
    that delegates to these repositories. This ensures backward compatibility with
    existing code while the codebase is gradually migrated.
"""

from app.repositories.base import BaseRepository, TenantContext
from app.repositories.tenant_repo import TenantRepository
from app.repositories.user_repo import UserRepository
from app.repositories.agent_repo import AgentRepository
from app.repositories.ticket_repo import TicketRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.auth_repo import AuthRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.usage_repo import UsageRepository
from app.repositories.ai_log_repo import AILogRepository

__all__ = [
    "BaseRepository",
    "TenantContext",
    "TenantRepository",
    "UserRepository",
    "AgentRepository",
    "TicketRepository",
    "MessageRepository",
    "KnowledgeRepository",
    "AuthRepository",
    "AuditRepository",
    "UsageRepository",
    "AILogRepository",
]
