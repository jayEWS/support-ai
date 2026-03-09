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
    def get_least_busy_agent(tenant_id: str) -> str:
        """
        Finds the available agent with the fewest active chats, scoped by tenant.
        """
        session = db_manager.get_session()
        try:
            # Query agents who are 'available' in the specific tenant
            available_agents = session.query(Agent, AgentPresence.active_chat_count) \
                .join(AgentPresence, Agent.user_id == AgentPresence.agent_id) \
                .filter(Agent.tenant_id == tenant_id) \
                .filter(AgentPresence.status == 'available') \
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
        tenant_repo = TenantRepository(db_manager.Session)
        audit_repo = AuditRepository(db_manager.Session)

        while True:
            try:
                active_tenants = tenant_repo.list_tenants(status="active")
                
                for t_info in active_tenants:
                    tenant_id = t_info["id"]
                    with TenantContext.set_tenant_id(tenant_id):
                        session = db_manager.get_session()
                        try:
                            # Get highest priority queued ticket for THIS tenant
                            next_in_queue = session.query(TicketQueue) \
                                .join(Ticket, TicketQueue.ticket_id == Ticket.id) \
                                .filter(TicketQueue.assigned_at == None) \
                                .filter(Ticket.tenant_id == tenant_id) \
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
                
            except Exception as e:
                logger.error(f"Routing Service Error: {e}")
            finally:
                db_manager.Session.remove()
            
            await asyncio.sleep(30) # Check queue every 30 seconds

routing_service = RoutingService()
