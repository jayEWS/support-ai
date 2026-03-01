from datetime import datetime
from app.core.database import db_manager
from app.core.state_machine import TicketStateMachine, TicketStatus
from app.schemas.schemas import TicketResponse
from app.core.logging import logger

class TicketService:
    @staticmethod
    async def create_ticket(user_id: str, summary: str, history: str, priority: str = "Medium") -> TicketResponse:
        # Check for existing open ticket for this user (Idempotency)
        existing_tickets = db_manager.get_all_tickets(filter_type='all')
        for t in existing_tickets:
            if t['user_id'] == user_id and t['status'] not in [TicketStatus.CLOSED]:
                logger.info(f"Using existing ticket {t['id']} for user {user_id}")
                return TicketResponse(
                    id=t['id'],
                    status=t['status'],
                    summary=t['summary'],
                    created_at=datetime.fromisoformat(t['created_at']) if isinstance(t['created_at'], str) else t['created_at']
                )

        # Determine initial status from prefix
        status = TicketStateMachine.get_status_from_summary(summary)
        
        ticket_id = db_manager.create_ticket(
            user_id=user_id,
            summary=summary,
            full_history=history,
            priority=priority,
            status=status.value
        )
        
        logger.info(f"Ticket created: {ticket_id} with status {status}")
        
        return TicketResponse(
            id=ticket_id,
            status=status.value,
            summary=summary,
            created_at=datetime.utcnow()
        )

    @staticmethod
    async def update_status(ticket_id: int, next_status: TicketStatus, agent_id: str = "System"):
        ticket_data = None # Fetch ticket from DB
        # Logic to fetch current status from DB
        current_status = "PENDING_AGENT" # Placeholder
        
        new_status = TicketStateMachine.transition(ticket_id, current_status, next_status, agent_id)
        db_manager.update_ticket_status(ticket_id, new_status.value)
        return new_status
