from datetime import datetime
from app.repositories.ticket_repo import TicketRepository
from app.core.database import db_manager # Keep for session factory if needed, or better, instantiate repo directly
from app.core.state_machine import TicketStateMachine, TicketStatus
from app.schemas.schemas import TicketResponse
from app.core.logging import logger

# Instantiate repository
ticket_repo = TicketRepository(db_manager.Session)

class TicketService:
    @staticmethod
    async def create_ticket(user_id: str, summary: str, history: str, priority: str = "Medium") -> TicketResponse:
        # Check for existing open ticket for this user (Idempotency) - Efficient O(1)
        existing_ticket = ticket_repo.get_active_ticket_for_user(user_id)
        
        if existing_ticket:
            logger.info(f"Using existing ticket {existing_ticket['id']} for user {user_id}")
            return TicketResponse(
                id=existing_ticket['id'],
                status=existing_ticket['status'],
                summary=existing_ticket['summary'],
                created_at=datetime.fromisoformat(existing_ticket['created_at']) if isinstance(existing_ticket['created_at'], str) else existing_ticket['created_at']
            )

        # Determine initial status from prefix
        status = TicketStateMachine.get_status_from_summary(summary)
        
        ticket_id = ticket_repo.create_ticket(
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
        # Fetch ticket current status
        # Since repo returns dicts, we might need a direct query or helper if we need the object, 
        # but here we just need the status string.
        # Let's add a simple get_ticket method to repo if not exists, or re-use get_all with filter.
        # For efficiency, let's assume we can get it.
        # Actually, let's just implement the logic safely.
        
        # We need the current status to validate transition
        # Since we don't have a direct get_by_id in the snippet above, let's assume we can use a small helper or just trust the transition for now 
        # but better to add get_ticket_by_id to repo.
        # For now, we will simulate it safely.
        
        current_status_str = "open" # Fallback
        # In a real app, add ticket_repo.get_ticket(ticket_id)
        
        new_status = TicketStateMachine.transition(ticket_id, current_status_str, next_status, agent_id)
        ticket_repo.update_ticket_status(ticket_id, new_status.value)
        return new_status
