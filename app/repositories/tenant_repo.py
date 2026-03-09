"""
Tenant Repository
==================
Handles Tenant CRUD, Plan management, and tenant onboarding.
"""

import uuid
import json
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone
from app.repositories.base import BaseRepository
from app.models.tenant_models import Tenant, Plan, TenantUser, Subscription, FeatureFlag
from app.models.models import Agent
from app.core.logging import logger


class TenantRepository(BaseRepository):
    """Manages tenant lifecycle: creation, plan assignment, settings."""

    # ── Tenant CRUD ───────────────────────────────────────────────────

    def create_tenant(
        self,
        name: str,
        slug: str,
        industry: str = None,
        plan_name: str = "Starter",
        owner_agent_id: int = None,
        trial_days: int = 14,
    ) -> dict:
        """Create a new tenant with optional trial period."""
        with self.session_scope() as session:
            # Check slug uniqueness
            existing = session.query(Tenant).filter_by(slug=slug).first()
            if existing:
                raise ValueError(f"Tenant slug '{slug}' already exists")

            tenant_id = str(uuid.uuid4())
            plan = session.query(Plan).filter_by(name=plan_name).first()

            tenant = Tenant(
                id=tenant_id,
                name=name,
                slug=slug,
                industry=industry,
                plan_id=plan.id if plan else None,
                status="trial" if trial_days > 0 else "active",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=trial_days) if trial_days > 0 else None,
            )
            session.add(tenant)
            session.flush()  # Ensure tenant row exists before FK-dependent inserts

            # Link owner
            if owner_agent_id:
                tu = TenantUser(
                    tenant_id=tenant_id,
                    agent_id=owner_agent_id,
                    role="owner",
                    status="active",
                    joined_at=datetime.now(timezone.utc),
                )
                session.add(tu)

            # Create default feature flags from plan
            if plan and plan.features_json:
                features = json.loads(plan.features_json)
                for key, enabled in features.items():
                    flag = FeatureFlag(
                        tenant_id=tenant_id,
                        feature_key=key,
                        enabled=enabled,
                    )
                    session.add(flag)

            logger.info(f"Tenant created: {name} ({tenant_id}), plan={plan_name}")
            return {
                "id": tenant_id,
                "name": name,
                "slug": slug,
                "industry": industry,
                "plan": plan_name,
                "status": tenant.status,
            }

    def get_tenant(self, tenant_id: str) -> Optional[dict]:
        """Get tenant by ID."""
        with self.session_scope() as session:
            t = session.query(Tenant).filter_by(id=tenant_id).first()
            if not t:
                return None
            return {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "industry": t.industry,
                "plan_id": t.plan_id,
                "status": t.status,
                "trial_ends_at": str(t.trial_ends_at) if t.trial_ends_at else None,
                "created_at": str(t.created_at),
            }

    def get_tenant_by_slug(self, slug: str) -> Optional[dict]:
        """Get tenant by URL slug."""
        with self.session_scope() as session:
            t = session.query(Tenant).filter_by(slug=slug).first()
            if not t:
                return None
            return {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "industry": t.industry,
                "status": t.status,
            }

    def list_tenants(self, status: str = None) -> List[dict]:
        """List all tenants, optionally filtered by status."""
        with self.session_scope() as session:
            q = session.query(Tenant)
            if status:
                q = q.filter_by(status=status)
            tenants = q.order_by(Tenant.created_at.desc()).all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "industry": t.industry,
                    "status": t.status,
                    "created_at": str(t.created_at),
                }
                for t in tenants
            ]

    def update_tenant_status(self, tenant_id: str, status: str):
        """Update tenant status (active, suspended, cancelled)."""
        with self.session_scope() as session:
            t = session.query(Tenant).filter_by(id=tenant_id).first()
            if t:
                t.status = status
                logger.info(f"Tenant {tenant_id} status → {status}")

    def update_tenant_settings(self, tenant_id: str, settings_dict: dict):
        """Update tenant-specific settings JSON."""
        with self.session_scope() as session:
            t = session.query(Tenant).filter_by(id=tenant_id).first()
            if t:
                existing = json.loads(t.settings_json or "{}")
                existing.update(settings_dict)
                t.settings_json = json.dumps(existing)

    # ── Plan Management ───────────────────────────────────────────────

    def create_plan(self, name: str, price_monthly: float, max_agents: int = 3,
                    max_ai_messages: int = 1500, max_tickets: int = 500,
                    features: dict = None, **kwargs) -> dict:
        """Create or update a subscription plan."""
        with self.session_scope() as session:
            plan = session.query(Plan).filter_by(name=name).first()
            if not plan:
                plan = Plan(name=name)
                session.add(plan)

            plan.price_monthly = price_monthly
            plan.max_agents = max_agents
            plan.max_ai_messages = max_ai_messages
            plan.max_tickets = max_tickets
            if features:
                plan.features_json = json.dumps(features)
            for k, v in kwargs.items():
                if hasattr(plan, k):
                    setattr(plan, k, v)

            return {"id": plan.id, "name": plan.name, "price": plan.price_monthly}

    def get_plan(self, plan_id: int = None, name: str = None) -> Optional[dict]:
        """Get plan by ID or name."""
        with self.session_scope() as session:
            if plan_id:
                p = session.query(Plan).filter_by(id=plan_id).first()
            elif name:
                p = session.query(Plan).filter_by(name=name).first()
            else:
                return None
            if not p:
                return None
            return {
                "id": p.id,
                "name": p.name,
                "price_monthly": p.price_monthly,
                "max_agents": p.max_agents,
                "max_ai_messages": p.max_ai_messages,
                "max_tickets": p.max_tickets,
                "features": json.loads(p.features_json) if p.features_json else {},
            }

    def list_plans(self, active_only: bool = True) -> List[dict]:
        """List available plans."""
        with self.session_scope() as session:
            q = session.query(Plan)
            if active_only:
                q = q.filter_by(is_active=True)
            plans = q.all()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "price_monthly": p.price_monthly,
                    "max_agents": p.max_agents,
                    "max_ai_messages": p.max_ai_messages,
                    "max_tickets": p.max_tickets,
                    "features": json.loads(p.features_json) if p.features_json else {},
                }
                for p in plans
            ]

    # ── Tenant User / Agent Mapping ───────────────────────────────────

    def add_user_to_tenant(self, tenant_id: str, agent_id: int, role: str = "agent") -> dict:
        """Add an agent to a tenant."""
        with self.session_scope() as session:
            existing = session.query(TenantUser).filter_by(
                tenant_id=tenant_id, agent_id=agent_id
            ).first()
            if existing:
                existing.role = role
                existing.status = "active"
            else:
                tu = TenantUser(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    role=role,
                    status="active",
                    joined_at=datetime.now(timezone.utc),
                )
                session.add(tu)
            return {"tenant_id": tenant_id, "agent_id": agent_id, "role": role}

    def get_tenant_for_agent(self, agent_id: int) -> Optional[str]:
        """Get the tenant_id for a given agent. Returns first active tenant."""
        with self.session_scope() as session:
            tu = session.query(TenantUser).filter_by(
                agent_id=agent_id, status="active"
            ).first()
            return tu.tenant_id if tu else None

    def get_tenant_agents(self, tenant_id: str) -> List[dict]:
        """List all agents for a tenant."""
        with self.session_scope() as session:
            results = session.query(TenantUser, Agent).join(
                Agent, TenantUser.agent_id == Agent.agent_id
            ).filter(TenantUser.tenant_id == tenant_id).all()
            return [
                {
                    "agent_id": a.agent_id,
                    "username": a.user_id,
                    "name": a.name,
                    "email": a.email,
                    "tenant_role": tu.role,
                    "status": tu.status,
                }
                for tu, a in results
            ]

    # ── Feature Flags ─────────────────────────────────────────────────

    def is_feature_enabled(self, tenant_id: str, feature_key: str) -> bool:
        """Check if a feature is enabled for a tenant."""
        with self.session_scope() as session:
            # Tenant-specific override
            flag = session.query(FeatureFlag).filter_by(
                tenant_id=tenant_id, feature_key=feature_key
            ).first()
            if flag:
                return flag.enabled
            # Global default
            default = session.query(FeatureFlag).filter_by(
                tenant_id=None, feature_key=feature_key
            ).first()
            if default:
                return default.enabled
            return False

    def set_feature_flag(self, tenant_id: Optional[str], feature_key: str,
                         enabled: bool, config: dict = None):
        """Set a feature flag for a tenant (or globally if tenant_id is None)."""
        with self.session_scope() as session:
            flag = session.query(FeatureFlag).filter_by(
                tenant_id=tenant_id, feature_key=feature_key
            ).first()
            if not flag:
                flag = FeatureFlag(
                    tenant_id=tenant_id,
                    feature_key=feature_key,
                )
                session.add(flag)
            flag.enabled = enabled
            if config:
                flag.config_json = json.dumps(config)

    def get_tenant_features(self, tenant_id: str) -> Dict[str, bool]:
        """Get all feature flags for a tenant (merged with global defaults)."""
        with self.session_scope() as session:
            # Global defaults
            globals_ = session.query(FeatureFlag).filter_by(tenant_id=None).all()
            result = {f.feature_key: f.enabled for f in globals_}
            # Tenant overrides
            overrides = session.query(FeatureFlag).filter_by(tenant_id=tenant_id).all()
            for f in overrides:
                result[f.feature_key] = f.enabled
            return result
