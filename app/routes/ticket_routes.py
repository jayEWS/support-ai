"""
Ticket Management API Routes
============================
Endpoints for ticket lifecycle, extracted from main.py.
Implements tenant-level isolation to prevent cross-tenant IDOR (P1).
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from app.core.database import db_manager
from app.core.auth_deps import get_current_agent
from app.repositories.ticket_repo import TicketRepository
from app.services.knowledge_extractor import KnowledgeExtractor
from app.core.logging import logger

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

def _get_repo():
    if db_manager is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return TicketRepository(db_manager.Session)

@router.get("", response_model=List[dict])
async def get_tickets(
    agent: Annotated[dict, Depends(get_current_agent)], 
    filter: str = 'all'
):
    """List tickets for the current tenant. Scoped automatically by TicketRepository."""
    repo = _get_repo()
    return repo.get_all_tickets(filter_type=filter)

@router.get("/counts")
async def get_ticket_counts(agent: Annotated[dict, Depends(get_current_agent)]):
    """Aggregate ticket counts for the current tenant dashboard."""
    repo = _get_repo()
    return repo.get_ticket_counts()

@router.get("/{ticket_id}")
async def get_ticket_details(
    ticket_id: int, 
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Fetch single ticket details with IDOR protection."""
    repo = _get_repo()
    ticket = repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or access denied")
    return ticket

@router.get("/{ticket_id}/history")
async def get_ticket_history(
    ticket_id: int, 
    agent: Annotated[dict, Depends(get_current_agent)]
):
    """Retrieve unified interaction history for a ticket."""
    repo = _get_repo()
    # Verify access first
    ticket = repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    # DatabaseManager still holds the unified history logic for now
    history = db_manager.get_unified_history(None, ticket_id)
    return {"history": history}

@router.patch("/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: int, 
    data: dict, 
    request: Request,
    agent: Annotated[dict, Depends(get_current_agent)], 
    background_tasks: BackgroundTasks
):
    """Update ticket status and trigger Knowledge Extraction if resolved."""
    status = data.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="Status is required")
        
    repo = _get_repo()
    ticket = repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    repo.update_ticket_status(ticket_id, status)
    
    # Self-Learning AI: Extract knowledge if resolved/closed
    if status.lower() in ("resolved", "closed"):
        rag = getattr(request.app.state, 'rag_service', None)
        if rag:
            extractor = KnowledgeExtractor(rag)
            background_tasks.add_task(extractor.extract_from_ticket, ticket_id)
            logger.info(f"Knowledge extraction queued for resolved ticket {ticket_id}")
            
    return {"status": "success", "ticket_id": ticket_id, "new_status": status}
