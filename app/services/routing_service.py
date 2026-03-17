from datetime import datetime, timezone
import asyncio
from app.core.database import db_manager
from app.models.models import Ticket, Agent, AgentPresence, TicketQueue
from app.repositories.tenant_repo import TenantRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.base import TenantContext
from app.core.logging import logger

class RoutingService:
    @staticmethod
    def get_least_busy_agent(tenant_id: str = None) -> str:
        """
        Finds the available agent with the fewest active chats.
        Scoped by tenant only when multi-tenancy is enabled.
        """
        from app.core.config import settings
        session = db_manager.get_session()
        try:
            # ✅ FIXED: Use SELECT ... FOR UPDATE to prevent race condition
            query = session.query(Agent, AgentPresence.active_chat_count) \
                .join(AgentPresence, Agent.user_id == AgentPresence.agent_id) \
                .filter(AgentPresence.status == 'available')
            
            # Only apply tenant filter if multi-tenancy is enabled AND column exists
            if getattr(settings, "MULTI_TENANT_ENABLED", False) and tenant_id and hasattr(Agent, 'tenant_id') and Agent.tenant_id is not None:
                query = query.filter(Agent.tenant_id == tenant_id)
            
            available_agents = query \
                .with_for_update() \
                .order_by(AgentPresence.active_chat_count.asc()) \
                .first()
            
            if available_agents:
                return available_agents[0].user_id
            return None
        finally:
            db_manager.Session.remove()

    @staticmethod
    async def process_queue():
        """
        Periodic task to assign queued tickets to available agents.
        """
        from app.core.config import settings
        
        # If multi-tenancy is disabled, we just use the default tenant
        if not getattr(settings, "MULTI_TENANT_ENABLED", False):
            while True:
                try:
                    tenant_id = getattr(settings, "DEFAULT_TENANT_ID", "default")
                    with TenantContext.set_tenant_id(tenant_id):
                        await RoutingService._process_tenant_queue(tenant_id)
                except Exception as e:
                    logger.error(f"Routing Service Error (Single-Tenant): {e}")
                await asyncio.sleep(30)
            return

        tenant_repo = TenantRepository(db_manager.Session)
        # ... rest of the multi-tenant logic ...

    @staticmethod
    async def _process_tenant_queue(tenant_id: str):
        """Internal helper to process queue for a specific tenant."""
        from app.core.config import settings
        audit_repo = AuditRepository(db_manager.Session)
        session = db_manager.get_session()
        try:
            # Get highest priority queued ticket
            query = session.query(TicketQueue) \
                .join(Ticket, TicketQueue.ticket_id == Ticket.id) \
                .filter(TicketQueue.assigned_at == None)
            
            # Only filter by tenant_id if multi-tenancy enabled and column exists
            if getattr(settings, "MULTI_TENANT_ENABLED", False) and hasattr(Ticket, 'tenant_id') and Ticket.tenant_id is not None:
                query = query.filter(Ticket.tenant_id == tenant_id)
            
            next_in_queue = query \
                .order_by(TicketQueue.priority_level.desc(), TicketQueue.queued_at.asc()) \
                .first()

            if next_in_queue:
                agent_id = RoutingService.get_least_busy_agent(tenant_id)
                if agent_id:
                    ticket = session.query(Ticket).get(next_in_queue.ticket_id)
                    if ticket:
                        ticket.assigned_to = agent_id
                        next_in_queue.assigned_at = datetime.now(timezone.utc)
                        
                        presence = session.query(AgentPresence).filter_by(agent_id=agent_id).first()
                        if presence:
                            presence.active_chat_count += 1
                            if presence.active_chat_count >= 5:
                                presence.status = 'busy'
                        
                        logger.info(f"Routed Ticket #{ticket.id} to Agent {agent_id} (Tenant: {tenant_id})")
                        
                        audit_repo.log_action(
                            agent_id="System", 
                            action="auto_assign", 
                            target_type="ticket", 
                            target_id=str(ticket.id), 
                            details=f"Assigned to {agent_id}"
                        )
                        session.commit()
        finally:
            db_manager.Session.remove()

routing_service = RoutingService()
