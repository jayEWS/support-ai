"""
Message Repository
===================
Portal messages, live chat sessions, and chat messages.
Extracted from DatabaseManager.
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import desc
from app.repositories.base import BaseRepository
from app.models.models import Message, ChatSession, ChatMessage, User
from app.core.logging import logger


class MessageRepository(BaseRepository):
    """Manages portal messages and live chat sessions."""

    # ── Portal Messages ───────────────────────────────────────────────

    def save_message(self, user_id: str, role: str, content: str, attachments: str = None):
        """Save a portal chat message."""
        with self.session_scope() as session:
            # Ensure user exists
            user = session.query(User).filter_by(identifier=user_id).first()
            if not user:
                user = User(identifier=user_id, name=f"User {user_id[-4:]}", state="idle")
                session.add(user)
                session.flush()

            msg = Message(
                user_id=user_id,
                role=role,
                content=content,
                attachments=attachments,
            )
            session.add(msg)

    def get_messages(self, user_id: str, limit: int = 100) -> List[dict]:
        """Get portal messages for a user."""
        with self.session_scope() as session:
            msgs = (
                session.query(Message)
                .filter_by(user_id=user_id)
                .order_by(Message.timestamp.asc())
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
        """Clear all portal messages for a user."""
        with self.session_scope() as session:
            session.query(Message).filter_by(user_id=user_id).delete()

    # ── Live Chat Sessions ────────────────────────────────────────────

    def create_chat_session(self, ticket_id: int, agent_id: str, customer_id: str) -> int:
        """Create a live chat session. Returns session_id."""
        with self.session_scope() as session:
            cs = ChatSession(
                ticket_id=ticket_id,
                agent_id=agent_id,
                customer_id=customer_id,
            )
            session.add(cs)
            session.flush()
            return cs.id

    def close_chat_session(self, session_id: int):
        """Close a live chat session."""
        with self.session_scope() as session:
            cs = session.query(ChatSession).filter_by(id=session_id).first()
            if cs:
                cs.ended_at = datetime.utcnow()

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
        """Get chat history for a live session."""
        with self.session_scope() as session:
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
