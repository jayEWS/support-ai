"""
Audit Repository
=================
Audit logging operations, extracted from DatabaseManager.
"""

from typing import List
from sqlalchemy import desc
from app.repositories.base import BaseRepository
from app.models.models import AuditLog
from app.core.logging import logger


class AuditRepository(BaseRepository):
    """Manages audit trail records."""

    def log_action(
        self,
        agent_id: str,
        action: str,
        target_type: str,
        target_id: str,
        details: str = None,
    ):
        """Log an auditable action."""
        with self.session_scope() as session:
            log = AuditLog(
                agent_id=agent_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
            session.add(log)

    def get_audit_logs(self, page: int = 1, per_page: int = 50) -> List[dict]:
        """Get recent audit logs with pagination."""
        with self.session_scope() as session:
            logs = (
                session.query(AuditLog)
                .order_by(AuditLog.timestamp.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            return [
                {
                    "id": l.id,
                    "agent_id": l.agent_id,
                    "action": l.action,
                    "target_type": l.target_type,
                    "target_id": l.target_id,
                    "details": l.details,
                    "timestamp": str(l.timestamp),
                }
                for l in logs
            ]
