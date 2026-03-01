from app.core.database import db_manager
from app.models.models import Ticket, Agent, AgentPresence, TicketQueue
from app.core.logging import logger
import asyncio
from datetime import datetime

class RoutingService:
    @staticmethod
    def get_least_busy_agent() -> str:
        """
        Finds the available agent with the fewest active chats.
        """
        session = db_manager.get_session()
        try:
            # Query agents who are 'available'
            available_agents = session.query(Agent, AgentPresence.active_chat_count) \
                .join(AgentPresence, Agent.user_id == AgentPresence.agent_id) \
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
        while True:
            try:
                session = db_manager.get_session()
                # Get next ticket in queue (highest priority first)
                next_in_queue = session.query(TicketQueue) \
                    .filter(TicketQueue.assigned_at == None) \
                    .order_by(TicketQueue.priority_level.desc(), TicketQueue.queued_at.asc()) \
                    .first()

                if next_in_queue:
                    agent_id = RoutingService.get_least_busy_agent()
                    if agent_id:
                        # Assign ticket
                        ticket = session.query(Ticket).get(next_in_queue.ticket_id)
                        if ticket:
                            ticket.assigned_to = agent_id
                            next_in_queue.assigned_at = datetime.now()
                            
                            # Increment agent chat count
                            presence = session.query(AgentPresence).filter_by(agent_id=agent_id).first()
                            if presence:
                                presence.active_chat_count += 1
                                if presence.active_chat_count >= 5: # Max load
                                    presence.status = 'busy'
                            
                            logger.info(f"Routed Ticket #{ticket.id} to Agent {agent_id}")
                            
                            t_id = ticket.id
                            db_manager.log_action("System", "auto_assign", "ticket", str(t_id), f"Assigned to {agent_id}")
                            session.commit()
                
            except Exception as e:
                logger.error(f"Routing Service Error: {e}")
            finally:
                db_manager.Session.remove()
            
            await asyncio.sleep(30) # Check queue every 30 seconds

routing_service = RoutingService()
