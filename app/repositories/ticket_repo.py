"""
Ticket Repository
==================
Ticket lifecycle operations, extracted from DatabaseManager.
"""

from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import desc
from app.repositories.base import BaseRepository
from app.models.models import Ticket, TicketQueue
from app.core.logging import logger


class TicketRepository(BaseRepository):
    """Manages ticket CRUD and queue operations."""

    def create_ticket(
        self,
        user_id: str,
        summary: str,
        full_history: str,
        priority: str = "Medium",
        due_at: datetime = None,
        status: str = "open",
    ) -> int:
        """Create a new ticket. Returns ticket_id."""
        with self.session_scope() as session:
            ticket = Ticket(
                user_id=user_id,
                summary=summary,
                full_history=full_history,
                priority=priority,
                due_at=due_at,
                status=status,
                tenant_id=self.tenant_id  # P1 Fix: Explicitly link to current tenant
            )
            session.add(ticket)
            session.flush()
            tid = ticket.id
            logger.info(f"Ticket #{tid} created for {user_id} in tenant {self.tenant_id}")
            return tid

    def get_all_tickets(self, filter_type: str = "all") -> List[dict]:
        """Get all tickets with optional status filter, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Ticket)
            q = self._apply_tenant_filter(q, Ticket) # P1 Fix: Scoping by tenant
            
            if filter_type == "open":
                q = q.filter(Ticket.status.notin_(["CLOSED"]))
            elif filter_type == "closed":
                q = q.filter_by(status="CLOSED")
                
            tickets = q.order_by(desc(Ticket.created_at)).all()
            return [self._ticket_to_dict(t) for t in tickets]

    def get_ticket(self, ticket_id: int) -> Optional[dict]:
        """Fetch a single ticket securely, scoped by tenant."""
        with self.session_scope() as session:
            query = session.query(Ticket).filter(Ticket.id == ticket_id)
            query = self._apply_tenant_filter(query, Ticket) # P1 Fix: Prevent IDOR
            ticket = query.first()
            return self._ticket_to_dict(ticket) if ticket else None

    def get_tickets_by_user(self, user_id: str, limit: int = 20) -> List[dict]:
        """Get tickets for a specific user, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Ticket).filter_by(user_id=user_id)
            q = self._apply_tenant_filter(q, Ticket) # P1 Fix
            
            tickets = (
                q.order_by(desc(Ticket.created_at))
                .limit(limit)
                .all()
            )
            return [self._ticket_to_dict(t) for t in tickets]

    def get_active_ticket_for_user(self, user_id: str) -> Optional[dict]:
        """Efficiently check if user has an open ticket (Status != CLOSED)."""
        with self.session_scope() as session:
            # Using the index 'ix_ticket_customer' implicitly via user_id filter
            q = session.query(Ticket).filter(Ticket.user_id == user_id, Ticket.status != "CLOSED")
            q = self._apply_tenant_filter(q, Ticket) # P1 Fix: Scoping
            ticket = q.order_by(desc(Ticket.created_at)).first()
            return self._ticket_to_dict(ticket) if ticket else None

    def update_ticket_status(self, ticket_id: int, status: str):
        """Update ticket status, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Ticket).filter_by(id=ticket_id)
            q = self._apply_tenant_filter(q, Ticket) # P1 Fix
            ticket = q.first()
            if ticket:
                ticket.status = status
                ticket.modified_at = datetime.now(timezone.utc)

    def update_ticket_sla(self, ticket_id: int, priority: str, due_at: datetime = None):
        """Update ticket SLA priority and due date, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Ticket).filter_by(id=ticket_id)
            q = self._apply_tenant_filter(q, Ticket) # P1 Fix
            ticket = q.first()
            if ticket:
                ticket.priority = priority
                if due_at:
                    ticket.due_at = due_at
                ticket.modified_at = datetime.now(timezone.utc)

    def get_ticket_counts(self) -> dict:
        """Get ticket counts by status, scoped by tenant."""
        with self.session_scope() as session:
            base_q = session.query(Ticket)
            base_q = self._apply_tenant_filter(base_q, Ticket) # P1 Fix
            
            total = base_q.count()
            open_count = base_q.filter(Ticket.status.notin_(["CLOSED"])).count()
            closed = base_q.filter_by(status="CLOSED").count()
            return {"total": total, "open": open_count, "closed": closed}

    def add_to_queue(self, ticket_id: int, priority_level: int = 1):
        """Add ticket to assignment queue."""
        with self.session_scope() as session:
            existing = session.query(TicketQueue).filter_by(ticket_id=ticket_id).first()
            if not existing:
                q = TicketQueue(ticket_id=ticket_id, priority_level=priority_level)
                session.add(q)

    def get_queue(self) -> List[dict]:
        """Get unassigned queue, scoped by tenant (IDOR fix)."""
        with self.session_scope() as session:
            # JOIN with Ticket to ensure the ticket belongs to this tenant
            query = (
                session.query(TicketQueue)
                .join(Ticket, Ticket.id == TicketQueue.ticket_id)
                .filter(TicketQueue.assigned_at == None)
            )
            query = self._apply_tenant_filter(query, Ticket)
            items = query \
                .order_by(TicketQueue.priority_level.desc(), TicketQueue.queued_at.asc()) \
                .all()
            return [
                {
                    "queue_id": q.id,
                    "ticket_id": q.ticket_id,
                    "priority_level": q.priority_level,
                    "queued_at": str(q.queued_at),
                }
                for q in items
            ]

    @staticmethod
    def _ticket_to_dict(t: Ticket) -> dict:
        return {
            "id": t.id,
            "user_id": t.user_id,
            "summary": t.summary,
            "status": t.status,
            "priority": t.priority,
            "category": t.category,
            "assigned_to": t.assigned_to,
            "due_at": str(t.due_at) if t.due_at else None,
            "created_at": str(t.created_at) if t.created_at else None,
            "modified_at": str(t.modified_at) if t.modified_at else None,
        }
