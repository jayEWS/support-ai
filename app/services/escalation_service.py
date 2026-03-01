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
            return f"Permintaan Anda bersifat mendesak dan telah kami tandai sebagai PRIORITAS TINGGI (Tiket #{ticket.id}). Spesialis senior akan segera menghubungi Anda."
        
        return f"Maaf, saya tidak dapat menjawab pertanyaan tersebut secara memadai. Saya telah membuatkan tiket bantuan (#{ticket.id}) untuk Anda dan akan segera ditangani oleh agen kami."
