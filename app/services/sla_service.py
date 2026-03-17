from datetime import datetime, timedelta, timezone
import asyncio
from app.core.database import db_manager
from app.models.models import Ticket, SLARule
from app.repositories.audit_repo import AuditRepository
from app.repositories.base import TenantContext
from app.core.logging import logger

class SLAService:
    @staticmethod
    def calculate_due_date(priority: str, tenant_id: str = None) -> datetime:
        """
        Calculates the due date based on SLA rules.
        """
        from app.core.config import settings
        session = db_manager.get_session()
        try:
            q = session.query(SLARule).filter_by(priority=priority)
            # Only filter by tenant if multi-tenancy enabled and column exists
            if tenant_id and getattr(settings, "MULTI_TENANT_ENABLED", False) and hasattr(SLARule, 'tenant_id') and SLARule.tenant_id is not None:
                q = q.filter_by(tenant_id=tenant_id)
            rule = q.first()
            if rule:
                minutes = rule.resolution_minutes
            else:
                # Fallbacks
                fallbacks = {
                    "Urgent": 60,
                    "High": 240,
                    "Medium": 1440,
                    "Low": 2880
                }
                minutes = fallbacks.get(priority, 1440)
            
            return datetime.now(timezone.utc) + timedelta(minutes=minutes)
        finally:
            db_manager.Session.remove()

    @staticmethod
    async def monitor_breaches():
        """
        Periodic task to check for overdue tickets and log breaches.
        """
        from app.core.config import settings
        
        while True:
            try:
                session = db_manager.get_session()
                now = datetime.now(timezone.utc)
                
                # Monitor all overdue tickets across all tenants
                overdue_tickets = session.query(Ticket).filter(
                    Ticket.status.in_(['open', 'pending']),
                    Ticket.due_at < now
                ).all()

                audit_repo = AuditRepository(db_manager.Session)

                for ticket in overdue_tickets:
                    # Resolve tenant_id: use ticket's tenant_id (if column exists) OR the default
                    tenant_id = getattr(ticket, 'tenant_id', None) or getattr(settings, "DEFAULT_TENANT_ID", "default")
                    
                    # Securely associate breach with the correct tenant
                    with TenantContext.set_tenant_id(tenant_id):
                        logger.warning(f"SLA BREACH: Ticket #{ticket.id} is overdue!")
                        
                        audit_repo.log_action(
                            agent_id="System", 
                            action="sla_breach", 
                            target_type="ticket", 
                            target_id=str(ticket.id), 
                            details=f"Ticket overdue. Priority: {ticket.priority}, Due was: {ticket.due_at}"
                        )
                
                session.commit()
            except Exception as e:
                logger.error(f"SLA Monitor Error: {e}")
            finally:
                db_manager.Session.remove()
            
            await asyncio.sleep(300) # Check every 5 minutes

sla_service = SLAService()
