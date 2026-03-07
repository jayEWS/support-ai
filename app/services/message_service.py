from app.services.rag_service import RAGService
from app.core.database import db_manager

# Note: Using a localized RAGService if not provided by app state
_rag_service = RAGService()

async def process_incoming_message(text: str, user_id: str):
    """
    Processes incoming portal messages using the unified RAGService.
    This is a compatibility layer for legacy message processing.
    """
    response = await _rag_service.query(text)
    return response.answer
