"""
Message Repository
===================
Portal messages, live chat sessions, and chat messages.
Extracted from DatabaseManager.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import desc
from app.repositories.base import BaseRepository
from app.models.models import Message, ChatSession, ChatMessage, User
from app.core.logging import logger


class MessageRepository(BaseRepository):
    """Manages portal messages and live chat sessions."""

    # ── Portal Messages ───────────────────────────────────────────────

    def save_message(self, user_id: str, role: str, content: str, attachments: str = None):
        """Save a portal chat message, scoped by tenant."""
        with self.session_scope() as session:
            # P1 Fix: Ensure user lookup is tenant-scoped
            q_user = session.query(User).filter_by(identifier=user_id)
            q_user = self._apply_tenant_filter(q_user, User)
            user = q_user.first()
            if not user:
                # Generate account_id to avoid UNIQUE constraint violation on SQL Server
                from app.repositories.user_repo import UserRepository
                from sqlalchemy import func as sqlfunc
                max_id = session.query(sqlfunc.max(User.account_id)).scalar()
                if max_id and max_id.startswith("EWS"):
                    try:
                        num = int(max_id[3:]) + 1
                    except ValueError:
                        num = 1
                else:
                    num = 1
                account_id = f"EWS{num}"
                
                user = User(
                    tenant_id=self.tenant_id, 
                    identifier=user_id, 
                    name=f"User {user_id[-4:]}", 
                    account_id=account_id,
                    state="idle"
                )
                session.add(user)
                session.flush()

            msg = Message(
                tenant_id=self.tenant_id, # P0 Fix
                user_id=user_id,
                role=role,
                content=content,
                attachments=attachments,
            )
            session.add(msg)

    def get_messages(self, user_id: str, limit: int = 100) -> List[dict]:
        """Get portal messages for a user, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Message).filter_by(user_id=user_id)
            q = self._apply_tenant_filter(q, Message)
            msgs = (
                q.order_by(Message.timestamp.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "attachments": m.attachments,
                    "timestamp": str(m.timestamp),
                }
                for m in msgs
            ]

    def clear_messages(self, user_id: str):
        """Clear all portal messages for a user, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Message).filter_by(user_id=user_id)
            q = self._apply_tenant_filter(q, Message)
            q.delete(synchronize_session=False)

    # ── Live Chat Sessions ────────────────────────────────────────────

    def create_chat_session(self, ticket_id: int, agent_id: str, customer_id: str) -> int:
        """Create a live chat session, scoped by tenant."""
        with self.session_scope() as session:
            cs = ChatSession(
                tenant_id=self.tenant_id, # P0 Fix
                ticket_id=ticket_id,
                agent_id=agent_id,
                customer_id=customer_id,
            )
            session.add(cs)
            session.flush()
            return cs.id

    def close_chat_session(self, session_id: int):
        """Close a live chat session, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(ChatSession).filter_by(id=session_id)
            q = self._apply_tenant_filter(q, ChatSession)
            cs = q.first()
            if cs:
                cs.ended_at = datetime.now(timezone.utc)

    def save_chat_message(
        self,
        session_id: int,
        sender_id: str,
        sender_type: str,
        content: str,
        attachment_url: str = None,
    ):
        """Save a live chat message."""
        with self.session_scope() as session:
            msg = ChatMessage(
                session_id=session_id,
                sender_id=sender_id,
                sender_type=sender_type,
                content=content,
                attachment_url=attachment_url,
            )
            session.add(msg)

    def get_chat_history(self, session_id: int, limit: int = 50) -> List[dict]:
        """Get chat history for a live session, scoped by tenant."""
        with self.session_scope() as session:
            # Filter ChatSession by tenant first to prevent leakage via session_id
            session_check = session.query(ChatSession).filter_by(id=session_id)
            session_check = self._apply_tenant_filter(session_check, ChatSession)
            if not session_check.first():
                return []

            msgs = (
                session.query(ChatMessage)
                .filter_by(session_id=session_id)
                .order_by(ChatMessage.sent_at.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "sender_type": m.sender_type,
                    "content": m.content,
                    "attachment_url": m.attachment_url,
                    "sent_at": str(m.sent_at),
                }
                for m in msgs
            ]
