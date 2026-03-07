"""
User Repository
================
Portal customer (end-user) operations, extracted from DatabaseManager.
"""

from typing import Optional, List
from app.repositories.base import BaseRepository
from app.models.models import User
from app.core.logging import logger


class UserRepository(BaseRepository):
    """Manages portal customer/user records."""

    def get_user(self, identifier: str) -> Optional[dict]:
        """Get a portal user by identifier."""
        with self.session_scope() as session:
            user = session.query(User).filter_by(identifier=identifier).first()
            if not user:
                return None
            return {
                "identifier": user.identifier,
                "account_id": user.account_id,
                "name": user.name,
                "email": user.email,
                "mobile": user.mobile,
                "company": user.company,
                "position": user.position,
                "outlet_pos": user.outlet_pos,
                "outlet_address": user.outlet_address,
                "category": user.category,
                "language": user.language,
                "state": user.state,
                "created_at": str(user.created_at) if user.created_at else None,
            }

    def get_all_users(self, page: int = 1, per_page: int = 50) -> List[dict]:
        """Get all portal users with pagination."""
        with self.session_scope() as session:
            users = (
                session.query(User)
                .order_by(User.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            return [
                {
                    "identifier": u.identifier,
                    "account_id": u.account_id,
                    "name": u.name,
                    "email": u.email,
                    "mobile": u.mobile,
                    "company": u.company,
                    "position": u.position,
                    "outlet_pos": u.outlet_pos,
                    "category": u.category,
                    "language": u.language,
                    "state": u.state,
                    "created_at": str(u.created_at) if u.created_at else None,
                }
                for u in users
            ]

    def create_or_update_user(
        self,
        identifier: str,
        name: str = None,
        company: str = None,
        position: str = None,
        outlet_pos: str = None,
        state: str = "idle",
        email: str = None,
        mobile: str = None,
        outlet_address: str = None,
        category: str = None,
        language: str = None,
    ) -> dict:
        """Create or update a portal user."""
        with self.session_scope() as session:
            user = session.query(User).filter_by(identifier=identifier).first()
            if not user:
                # Generate account_id
                account_id = self._get_next_account_id(session)
                user = User(
                    identifier=identifier,
                    account_id=account_id,
                    name=name,
                    company=company,
                    position=position,
                    outlet_pos=outlet_pos,
                    state=state,
                    email=email,
                    mobile=mobile,
                    outlet_address=outlet_address,
                    category=category,
                    language=language,
                )
                session.add(user)
                logger.info(f"New user created: {identifier} ({account_id})")
            else:
                if name is not None:
                    user.name = name
                if company is not None:
                    user.company = company
                if position is not None:
                    user.position = position
                if outlet_pos is not None:
                    user.outlet_pos = outlet_pos
                if state is not None:
                    user.state = state
                if email is not None:
                    user.email = email
                if mobile is not None:
                    user.mobile = mobile
                if outlet_address is not None:
                    user.outlet_address = outlet_address
                if category is not None:
                    user.category = category
                if language is not None:
                    user.language = language

            return self._user_to_dict(user)

    def delete_user(self, identifier: str) -> bool:
        """Delete a portal user."""
        with self.session_scope() as session:
            user = session.query(User).filter_by(identifier=identifier).first()
            if user:
                session.delete(user)
                logger.info(f"User deleted: {identifier}")
                return True
            return False

    def _get_next_account_id(self, session) -> str:
        """Generate next sequential account ID (EWS1, EWS2, ...)."""
        from sqlalchemy import func as sqlfunc
        max_id = session.query(sqlfunc.max(User.account_id)).scalar()
        if max_id and max_id.startswith("EWS"):
            try:
                num = int(max_id[3:]) + 1
            except ValueError:
                num = 1
        else:
            num = 1
        return f"EWS{num}"

    @staticmethod
    def _user_to_dict(user: User) -> dict:
        return {
            "identifier": user.identifier,
            "account_id": user.account_id,
            "name": user.name,
            "company": user.company,
            "state": user.state,
            "language": user.language,
        }
