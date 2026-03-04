from app.services.ticket_service import TicketService
from app.core.logging import logger
from app.schemas.schemas import TicketResponse

class EscalationService:
    @staticmethod
    async def escalate(user_id: str, reason: str, history: str, is_critical: bool = False) -> str:
        prefix = "A-" if is_critical else "B-"
        summary = f"{prefix} Escalation: {reason}"
        
        logger.info(f"Escalating request for {user_id}. Critical: {is_critical}")
        
        ticket = await TicketService.create_ticket(
            user_id=user_id,
            summary=summary,
            history=history,
            priority="Urgent" if is_critical else "High"
        )
        
        if is_critical:
            return f"Your request is urgent and has been marked as HIGH PRIORITY (Ticket #{ticket.id}). A senior specialist will contact you shortly."
        
        return f"I'm unable to fully answer your question. I've created a support ticket (#{ticket.id}) for you — our agent will handle it shortly."
