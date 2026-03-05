"""
Models Package
================
SQLAlchemy ORM models for the Support Portal.

- models.py: Core operational tables (Agent, User, Ticket, Message, etc.)
- tenant_models.py: SaaS multi-tenant tables (Tenant, Plan, Subscription, etc.)
"""

from app.models.models import Base
from app.models.tenant_models import (
    Tenant, Plan, TenantUser,
    AIInteractionLog, UsageTracking,
    Subscription, Invoice,
    FeatureFlag, KnowledgeCollection,
)
