"""
Auth Repository
================
MFA challenges, refresh tokens, magic links.
Extracted from DatabaseManager.
"""

from typing import Optional
from datetime import datetime, timezone
from app.repositories.base import BaseRepository
from app.models.models import AuthMFAChallenge, AuthRefreshToken, AuthMagicLink, Agent
from app.core.logging import logger


class AuthRepository(BaseRepository):
    """Manages authentication tokens and MFA challenges."""

    # ── MFA ───────────────────────────────────────────────────────────

    def create_mfa_challenge(self, user_id: str, code_hash: str, expires_at: datetime) -> int:
        """Create an MFA challenge. Returns challenge_id."""
        with self.session_scope() as session:
            challenge = AuthMFAChallenge(
                user_id=user_id,
                code_hash=code_hash,
                expires_at=expires_at,
            )
            session.add(challenge)
            session.flush()
            return challenge.id

    def get_mfa_challenge(self, challenge_id: int) -> Optional[dict]:
        """Get MFA challenge by ID."""
        with self.session_scope() as session:
            c = session.query(AuthMFAChallenge).filter_by(id=challenge_id).first()
            if not c:
                return None
            return {
                "id": c.id,
                "user_id": c.user_id,
                "code_hash": c.code_hash,
                "expires_at": c.expires_at,
                "attempts": c.attempts,
            }

    def get_latest_mfa_challenge(self, user_id: str) -> Optional[dict]:
        """Get the most recent MFA challenge for a user."""
        with self.session_scope() as session:
            c = (
                session.query(AuthMFAChallenge)
                .filter_by(user_id=user_id)
                .order_by(AuthMFAChallenge.created_at.desc())
                .first()
            )
            if not c:
                return None
            return {
                "id": c.id,
                "user_id": c.user_id,
                "code_hash": c.code_hash,
                "expires_at": c.expires_at,
                "attempts": c.attempts,
                "created_at": c.created_at,
            }

    def increment_mfa_attempts(self, challenge_id: int):
        """Increment MFA attempt counter."""
        with self.session_scope() as session:
            c = session.query(AuthMFAChallenge).filter_by(id=challenge_id).first()
            if c:
                c.attempts = (c.attempts or 0) + 1

    def delete_mfa_challenge(self, challenge_id: int):
        """Delete an MFA challenge."""
        with self.session_scope() as session:
            c = session.query(AuthMFAChallenge).filter_by(id=challenge_id).first()
            if c:
                session.delete(c)

    # ── Refresh Tokens ────────────────────────────────────────────────

    def create_refresh_token(self, user_id: str, token_hash: str, expires_at: datetime, user_agent: str = None):
        """Store a refresh token."""
        with self.session_scope() as session:
            rt = AuthRefreshToken(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                user_agent=user_agent,
            )
            session.add(rt)

    def get_refresh_token(self, token_hash: str) -> Optional[dict]:
        """Get refresh token by hash."""
        with self.session_scope() as session:
            rt = session.query(AuthRefreshToken).filter_by(token_hash=token_hash).first()
            if not rt:
                return None
            return {
                "id": rt.id,
                "user_id": rt.user_id,
                "token_hash": rt.token_hash,
                "expires_at": rt.expires_at,
                "revoked_at": rt.revoked_at,
            }

    def revoke_refresh_token(self, token_hash: str):
        """Revoke a refresh token."""
        with self.session_scope() as session:
            rt = session.query(AuthRefreshToken).filter_by(token_hash=token_hash).first()
            if rt:
                rt.revoked_at = datetime.now(timezone.utc)

    # ── Magic Links ───────────────────────────────────────────────────

    def create_magic_link(self, email: str, token_hash: str, expires_at: datetime) -> int:
        """Create a magic link. Returns link_id."""
        with self.session_scope() as session:
            # Look up agent by email
            agent = session.query(Agent).filter_by(email=email).first()
            if not agent:
                raise ValueError(f"No agent found with email: {email}")

            link = AuthMagicLink(
                user_id=agent.user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            session.add(link)
            session.flush()
            return link.id

    def get_magic_link(self, email: str, token_hash: str) -> Optional[dict]:
        """Get magic link by email and token hash."""
        with self.session_scope() as session:
            agent = session.query(Agent).filter_by(email=email).first()
            if not agent:
                return None
            link = session.query(AuthMagicLink).filter_by(
                user_id=agent.user_id, token_hash=token_hash
            ).first()
            if not link:
                return None
            return {
                "id": link.id,
                "user_id": link.user_id,
                "token_hash": link.token_hash,
                "expires_at": link.expires_at,
            }

    def delete_magic_link(self, link_id: int):
        """Delete a magic link."""
        with self.session_scope() as session:
            link = session.query(AuthMagicLink).filter_by(id=link_id).first()
            if link:
                session.delete(link)
