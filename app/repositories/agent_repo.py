"""
Agent Repository
=================
Agent/admin user operations, extracted from DatabaseManager.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import desc
from app.repositories.base import BaseRepository, TenantContext
from app.models.models import Agent, AgentPresence, Role, Permission
from app.core.logging import logger


class AgentRepository(BaseRepository):
    """Manages agent (admin/support staff) records and RBAC."""

    def create_or_get_agent(
        self,
        user_id: str,
        name: str = None,
        email: str = None,
        department: str = "Support",
        google_id: str = None,
    ) -> dict:
        """Create a new agent or return existing, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(user_id=user_id)
            q = self._apply_tenant_filter(q, Agent)
            agent = q.first()
            if not agent:
                agent = Agent(
                    tenant_id=self.tenant_id, # P0 Fix
                    user_id=user_id,
                    name=name or user_id,
                    email=email,
                    department=department,
                    google_id=google_id,
                )
                session.add(agent)
                logger.info(f"Agent created: {user_id} in tenant {self.tenant_id}")
            return self._agent_to_dict(agent)

    def get_agent(self, user_id: str) -> Optional[dict]:
        """Get agent by username, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(user_id=user_id)
            q = self._apply_tenant_filter(q, Agent)
            agent = q.first()
            return self._agent_to_dict(agent) if agent else None

    def get_agent_by_email(self, email: str) -> Optional[dict]:
        """Get agent by email, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(email=email)
            q = self._apply_tenant_filter(q, Agent)
            agent = q.first()
            return self._agent_to_dict(agent) if agent else None

    def get_agent_by_google_id(self, google_id: str) -> Optional[dict]:
        """Get agent by Google OAuth ID, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(google_id=google_id)
            q = self._apply_tenant_filter(q, Agent)
            agent = q.first()
            return self._agent_to_dict(agent) if agent else None

    def get_all_agents(self) -> List[dict]:
        """Get all agents for current tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(is_active=True)
            q = self._apply_tenant_filter(q, Agent)
            agents = q.all()
            return [self._agent_to_dict(a) for a in agents]

    def update_agent_auth(self, user_id: str, hashed_password: str = None, google_id: str = None):
        """Update agent authentication credentials, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(user_id=user_id)
            q = self._apply_tenant_filter(q, Agent)
            agent = q.first()
            if agent:
                if hashed_password:
                    agent.hashed_password = hashed_password
                if google_id:
                    agent.google_id = google_id

    def update_agent_presence(self, agent_id: str, status: str, active_chat_count: int = None):
        """Update agent online presence, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(AgentPresence).filter_by(agent_id=agent_id)
            q = self._apply_tenant_filter(q, AgentPresence)
            presence = q.first()
            if not presence:
                presence = AgentPresence(
                    tenant_id=self.tenant_id, # P0 Fix
                    agent_id=agent_id, 
                    status=status
                )
                session.add(presence)
            else:
                presence.status = status
                if active_chat_count is not None:
                    presence.active_chat_count = active_chat_count

    def get_available_agents(self) -> List[dict]:
        """Get agents who are currently available in the current tenant."""
        with self.session_scope() as session:
            # Join with Agent to enforce tenant_id
            q = session.query(Agent, AgentPresence).outerjoin(
                AgentPresence, Agent.user_id == AgentPresence.agent_id
            ).filter(Agent.is_active == True)
            q = self._apply_tenant_filter(q, Agent)
            results = q.all()
            return [
                {
                    **self._agent_to_dict(a),
                    "presence_status": p.status if p else "offline",
                    "active_chats": p.active_chat_count if p else 0,
                }
                for a, p in results
            ]

    # ── RBAC ──────────────────────────────────────────────────────────

    def get_agent_effective_permissions(self, username: str) -> List[str]:
        """Get merged permissions from roles + direct grants, scoped by tenant."""
        with self.session_scope() as session:
            q = session.query(Agent).filter_by(user_id=username)
            q = self._apply_tenant_filter(q, Agent)
            agent = q.first()
            if not agent:
                return []
            effective = set()
            for role in agent.roles:
                for perm in role.permissions:
                    effective.add(perm.name)
            for perm in agent.direct_permissions:
                effective.add(perm.name)
            return sorted(effective)

    def assign_role_to_agent(self, username: str, role_name: str) -> bool:
        """Assign a role to an agent, scoped by tenant."""
        with self.session_scope() as session:
            q_agent = session.query(Agent).filter_by(user_id=username)
            q_agent = self._apply_tenant_filter(q_agent, Agent)
            agent = q_agent.first()
            
            q_role = session.query(Role).filter_by(name=role_name)
            q_role = self._apply_tenant_filter(q_role, Role)
            role = q_role.first()
            
            if agent and role and role not in agent.roles:
                agent.roles.append(role)
                return True
            return False

    @staticmethod
    def _agent_to_dict(agent: Agent) -> dict:
        return {
            "agent_id": agent.agent_id,
            "user_id": agent.user_id,
            "name": agent.name,
            "email": agent.email,
            "department": agent.department,
            "is_active": agent.is_active,
            "google_id": agent.google_id,
            "hashed_password": agent.hashed_password,
            "roles": [r.name for r in agent.roles] if agent.roles else [],
        }
