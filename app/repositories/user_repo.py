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
        """Get a portal user by identifier, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(User).filter_by(identifier=identifier)
            q = self._apply_tenant_filter(q, User)
            user = q.first()
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
        """Get all portal users with pagination, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(User)
            q = self._apply_tenant_filter(q, User)
            users = (
                q.order_by(User.created_at.desc())
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
        **kwargs
    ) -> dict:
        """Create or update a portal user, tied to current tenant."""
        with self.session_scope() as session:
            q = session.query(User).filter_by(identifier=identifier)
            q = self._apply_tenant_filter(q, User)
            user = q.first()
            
            if not user:
                user = self._create_new_user(session, identifier, **kwargs)
            else:
                self._update_user_fields(user, **kwargs)

            return self._user_to_dict(user)

    def _create_new_user(self, session, identifier: str, **kwargs) -> User:
        """Helper to create a new user record."""
        account_id = self._get_next_account_id(session)
        user = User(
            identifier=identifier,
            tenant_id=self.tenant_id,
            account_id=account_id,
        )
        self._update_user_fields(user, **kwargs)
        session.add(user)
        logger.info(f"New user created: {identifier} ({account_id}) in tenant {self.tenant_id}")
        return user

    def _update_user_fields(self, user: User, **kwargs):
        """Helper to update user model fields from kwargs."""
        field_map = {
            "name": "name", "company": "company", "position": "position",
            "outlet_pos": "outlet_pos", "state": "state", "email": "email",
            "mobile": "mobile", "outlet_address": "outlet_address",
            "category": "category", "language": "language"
        }
        for key, value in kwargs.items():
            if key in field_map and value is not None:
                setattr(user, field_map[key], value)

    def delete_user(self, identifier: str) -> bool:
        """Delete a portal user, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(User).filter_by(identifier=identifier)
            q = self._apply_tenant_filter(q, User)
            user = q.first()
            if user:
                session.delete(user)
                logger.info(f"User deleted: {identifier} from tenant {self.tenant_id}")
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
