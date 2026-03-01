from datetime import datetime, timedelta
from app.core.database import db_manager
from app.models.models import Ticket, SLARule
from app.core.logging import logger
import asyncio

class SLAService:
    @staticmethod
    def calculate_due_date(priority: str) -> datetime:
        """
        Calculates the due date based on SLA rules in the database.
        Default fallbacks if no rule exists.
        """
        session = db_manager.get_session()
        try:
            rule = session.query(SLARule).filter_by(priority=priority).first()
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
            
            return datetime.now() + timedelta(minutes=minutes)
        finally:
            db_manager.Session.remove()

    @staticmethod
    async def monitor_breaches():
        """
        Periodic task to check for overdue tickets and log breaches.
        """
        while True:
            try:
                session = db_manager.get_session()
                # Fetch only needed fields to avoid detachment issues or refresh later
                overdue_tickets = session.query(Ticket).filter(
                    Ticket.status.in_(['open', 'pending']),
                    Ticket.due_at < datetime.now()
                ).all()

                for ticket in overdue_tickets:
                    # Capture data before any potential session removal or refresh
                    t_id = ticket.id
                    t_priority = ticket.priority
                    t_due_at = ticket.due_at
                    
                    logger.warning(f"SLA BREACH: Ticket #{t_id} is overdue! (Priority: {t_priority})")
                    
                    # log_action creates its own session, which is fine if we use local variables here
                    db_manager.log_action(
                        "System", 
                        "sla_breach", 
                        "ticket", 
                        str(t_id), 
                        f"Ticket overdue. Due was: {t_due_at}"
                    )
                
                session.commit()
            except Exception as e:
                logger.error(f"SLA Monitor Error: {e}")
            finally:
                db_manager.Session.remove()
            
            await asyncio.sleep(300) # Check every 5 minutes

sla_service = SLAService()
