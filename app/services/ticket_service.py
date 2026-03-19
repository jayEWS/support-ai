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
                assigned_to=existing_ticket.get('assigned_to'),
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
        
        # Auto-assign to the agent with the fewest open tickets (load balancing)
        assigned_agent = ticket_repo.assign_to_least_loaded_agent(ticket_id)
        
        logger.info(f"Ticket created: {ticket_id} with status {status}, assigned to: {assigned_agent or 'unassigned'}")
        
        return TicketResponse(
            id=ticket_id,
            status=status.value,
            summary=summary,
            assigned_to=assigned_agent,
            created_at=datetime.utcnow()
        )

    @staticmethod
    async def update_status(ticket_id: int, next_status: TicketStatus, agent_id: str = "System"):
        # Fetch ticket current status from database
        ticket = ticket_repo.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")
        
        current_status_str = ticket.get("status", "PENDING_AGENT")
        
        new_status = TicketStateMachine.transition(ticket_id, current_status_str, next_status, agent_id)
        ticket_repo.update_ticket_status(ticket_id, new_status.value)
        return new_status
