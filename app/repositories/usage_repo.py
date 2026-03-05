"""
Usage Repository
=================
Usage tracking and billing enforcement for SaaS plans.
"""

import json
from typing import Optional, Dict
from datetime import datetime
from app.repositories.base import BaseRepository
from app.models.tenant_models import UsageTracking, Subscription, Plan, Tenant
from app.core.logging import logger


class UsageRepository(BaseRepository):
    """Tracks per-tenant usage for billing and plan enforcement."""

    def get_current_usage(self, tenant_id: str) -> dict:
        """Get current month's usage for a tenant."""
        period = datetime.utcnow().strftime("%Y-%m")
        with self.session_scope() as session:
            usage = session.query(UsageTracking).filter_by(
                tenant_id=tenant_id, period=period
            ).first()
            if not usage:
                return {
                    "tenant_id": tenant_id,
                    "period": period,
                    "ai_messages_used": 0,
                    "tickets_created": 0,
                    "active_agents": 0,
                    "storage_used_mb": 0.0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }
            return {
                "tenant_id": tenant_id,
                "period": period,
                "ai_messages_used": usage.ai_messages_used,
                "tickets_created": usage.tickets_created,
                "active_agents": usage.active_agents,
                "storage_used_mb": usage.storage_used_mb,
                "total_tokens": usage.total_tokens,
                "total_cost_usd": usage.total_cost_usd,
                "whatsapp_messages": usage.whatsapp_messages,
                "knowledge_files": usage.knowledge_files,
            }

    def increment_usage(self, tenant_id: str, field: str, amount: int = 1):
        """Increment a usage counter for the current period."""
        period = datetime.utcnow().strftime("%Y-%m")
        with self.session_scope() as session:
            usage = session.query(UsageTracking).filter_by(
                tenant_id=tenant_id, period=period
            ).first()
            if not usage:
                usage = UsageTracking(
                    tenant_id=tenant_id,
                    period=period,
                )
                session.add(usage)
                session.flush()

            current = getattr(usage, field, 0) or 0
            setattr(usage, field, current + amount)

    def add_token_usage(self, tenant_id: str, tokens: int, cost_usd: float = 0.0):
        """Add token and cost usage for AI interactions."""
        period = datetime.utcnow().strftime("%Y-%m")
        with self.session_scope() as session:
            usage = session.query(UsageTracking).filter_by(
                tenant_id=tenant_id, period=period
            ).first()
            if not usage:
                usage = UsageTracking(tenant_id=tenant_id, period=period)
                session.add(usage)
                session.flush()

            usage.total_tokens = (usage.total_tokens or 0) + tokens
            usage.total_cost_usd = (usage.total_cost_usd or 0) + cost_usd

    def check_plan_limit(self, tenant_id: str, resource: str) -> Dict:
        """
        Check if a tenant has exceeded their plan limit for a resource.
        Returns: {"allowed": bool, "current": int, "limit": int, "remaining": int}
        """
        with self.session_scope() as session:
            # Get tenant's plan
            tenant = session.query(Tenant).filter_by(id=tenant_id).first()
            if not tenant or not tenant.plan_id:
                return {"allowed": True, "current": 0, "limit": -1, "remaining": -1}

            plan = session.query(Plan).filter_by(id=tenant.plan_id).first()
            if not plan:
                return {"allowed": True, "current": 0, "limit": -1, "remaining": -1}

            # Map resource to plan limit and usage field
            resource_map = {
                "ai_messages": ("max_ai_messages", "ai_messages_used"),
                "tickets": ("max_tickets", "tickets_created"),
                "agents": ("max_agents", "active_agents"),
                "knowledge_files": ("max_knowledge_files", "knowledge_files"),
            }

            if resource not in resource_map:
                return {"allowed": True, "current": 0, "limit": -1, "remaining": -1}

            limit_field, usage_field = resource_map[resource]
            limit_value = getattr(plan, limit_field, -1) or -1

            if limit_value == -1:  # Unlimited
                return {"allowed": True, "current": 0, "limit": -1, "remaining": -1}

            # Get current usage
            period = datetime.utcnow().strftime("%Y-%m")
            usage = session.query(UsageTracking).filter_by(
                tenant_id=tenant_id, period=period
            ).first()
            current = getattr(usage, usage_field, 0) if usage else 0

            remaining = max(0, limit_value - current)
            return {
                "allowed": current < limit_value,
                "current": current,
                "limit": limit_value,
                "remaining": remaining,
            }

    def get_usage_history(self, tenant_id: str, months: int = 6) -> list:
        """Get usage history for the last N months."""
        with self.session_scope() as session:
            usages = (
                session.query(UsageTracking)
                .filter_by(tenant_id=tenant_id)
                .order_by(UsageTracking.period.desc())
                .limit(months)
                .all()
            )
            return [
                {
                    "period": u.period,
                    "ai_messages_used": u.ai_messages_used,
                    "tickets_created": u.tickets_created,
                    "total_tokens": u.total_tokens,
                    "total_cost_usd": u.total_cost_usd,
                }
                for u in usages
            ]
