"""
SaaS Multi-Tenant Models
========================
Core tenant infrastructure tables for multi-tenant SaaS architecture.
Every operational table references tenant_id for complete data isolation.
"""

from sqlalchemy import Column, Integer, Unicode, UnicodeText, DateTime, ForeignKey, Float, Boolean, func, Text, JSON
from sqlalchemy.orm import relationship
from app.models.models import Base, IS_SQLITE
from datetime import datetime


# ============ TENANT & PLAN ============

class Tenant(Base):
    """Core tenant (organization) record."""
    __tablename__ = "Tenants"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("TenantID", Unicode(36), primary_key=True)  # UUID
    name = Column("Name", Unicode(255), nullable=False)
    slug = Column("Slug", Unicode(100), unique=True, nullable=False, index=True)  # URL-safe identifier
    industry = Column("Industry", Unicode(100), nullable=True)  # Retail, F&B, ERP, etc.
    plan_id = Column("PlanID", Integer, ForeignKey("Plans.PlanID" if IS_SQLITE else "app.Plans.PlanID"), nullable=True)
    status = Column("Status", Unicode(20), default="active")  # active, suspended, trial, cancelled
    trial_ends_at = Column("TrialEndsAt", DateTime, nullable=True)
    settings_json = Column("SettingsJSON", UnicodeText, nullable=True)  # Tenant-specific config overrides
    branding_json = Column("BrandingJSON", UnicodeText, nullable=True)  # Logo, colors, etc.
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    plan = relationship("Plan", backref="tenants")
    users = relationship("TenantUser", backref="tenant", cascade="all, delete-orphan")
    subscription = relationship("Subscription", backref="tenant", uselist=False)


class Plan(Base):
    """Subscription plan definitions."""
    __tablename__ = "Plans"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("PlanID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True, nullable=False)  # Starter, Growth, Enterprise
    price_monthly = Column("PriceMonthly", Float, default=0.0)
    price_yearly = Column("PriceYearly", Float, nullable=True)
    max_agents = Column("MaxAgents", Integer, default=3)
    max_ai_messages = Column("MaxAIMessages", Integer, default=1500)  # per month
    max_tickets = Column("MaxTickets", Integer, default=500)  # per month
    max_knowledge_files = Column("MaxKnowledgeFiles", Integer, default=50)
    max_storage_mb = Column("MaxStorageMB", Integer, default=500)
    features_json = Column("FeaturesJSON", UnicodeText, nullable=True)  # {"sla_engine": true, "whatsapp": false, ...}
    is_active = Column("IsActive", Boolean, default=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())


class TenantUser(Base):
    """Maps agents/users to tenants with tenant-scoped roles."""
    __tablename__ = "TenantUsers"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("TenantUserID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=False, index=True)
    agent_id = Column("AgentID", Integer, ForeignKey("Agents.AgentID" if IS_SQLITE else "app.Agents.AgentID"), nullable=False)
    role = Column("Role", Unicode(50), default="agent")  # owner, admin, agent, viewer
    status = Column("Status", Unicode(20), default="active")  # active, invited, disabled
    invited_at = Column("InvitedAt", DateTime, nullable=True)
    joined_at = Column("JoinedAt", DateTime, nullable=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())


# ============ AI OBSERVABILITY ============

class AIInteractionLog(Base):
    """Tracks every AI interaction for quality monitoring, billing, and observability."""
    __tablename__ = "AIInteractionLogs"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("InteractionID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=False, index=True)
    user_id = Column("UserID", Unicode(100), nullable=True)  # Portal customer
    ticket_id = Column("TicketID", Integer, nullable=True)
    query = Column("Query", UnicodeText, nullable=True)
    response = Column("Response", UnicodeText, nullable=True)
    tokens_input = Column("TokensInput", Integer, default=0)
    tokens_output = Column("TokensOutput", Integer, default=0)
    tokens_total = Column("TokensTotal", Integer, default=0)
    confidence_score = Column("ConfidenceScore", Float, nullable=True)
    escalation_flag = Column("EscalationFlag", Boolean, default=False)
    hallucination_flag = Column("HallucinationFlag", Boolean, default=False)
    retrieval_method = Column("RetrievalMethod", Unicode(50), nullable=True)  # bm25, vector, hybrid
    latency_ms = Column("LatencyMs", Integer, nullable=True)
    cost_usd = Column("CostUSD", Float, nullable=True)  # Estimated cost per response
    model_name = Column("ModelName", Unicode(100), nullable=True)
    language = Column("Language", Unicode(10), nullable=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())


# ============ USAGE TRACKING ============

class UsageTracking(Base):
    """Aggregated usage metrics per tenant per period for billing enforcement."""
    __tablename__ = "UsageTracking"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("UsageID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=False, index=True)
    period = Column("Period", Unicode(7), nullable=False)  # YYYY-MM format
    ai_messages_used = Column("AIMessagesUsed", Integer, default=0)
    tickets_created = Column("TicketsCreated", Integer, default=0)
    active_agents = Column("ActiveAgents", Integer, default=0)
    storage_used_mb = Column("StorageUsedMB", Float, default=0.0)
    total_tokens = Column("TotalTokens", Integer, default=0)
    total_cost_usd = Column("TotalCostUSD", Float, default=0.0)
    whatsapp_messages = Column("WhatsAppMessages", Integer, default=0)
    knowledge_files = Column("KnowledgeFiles", Integer, default=0)
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())


# ============ BILLING / SUBSCRIPTION ============

class Subscription(Base):
    """Active subscription for a tenant."""
    __tablename__ = "Subscriptions"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("SubscriptionID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=False, unique=True, index=True)
    plan_id = Column("PlanID", Integer, ForeignKey("Plans.PlanID" if IS_SQLITE else "app.Plans.PlanID"), nullable=False)
    status = Column("Status", Unicode(20), default="active")  # active, past_due, cancelled, trialing
    billing_cycle = Column("BillingCycle", Unicode(10), default="monthly")  # monthly, yearly
    current_period_start = Column("CurrentPeriodStart", DateTime, nullable=True)
    current_period_end = Column("CurrentPeriodEnd", DateTime, nullable=True)
    stripe_subscription_id = Column("StripeSubscriptionID", Unicode(255), nullable=True)
    stripe_customer_id = Column("StripeCustomerID", Unicode(255), nullable=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

    plan = relationship("Plan")


class Invoice(Base):
    """Invoice records (placeholder for Stripe integration)."""
    __tablename__ = "Invoices"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("InvoiceID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=False, index=True)
    subscription_id = Column("SubscriptionID", Integer, ForeignKey("Subscriptions.SubscriptionID" if IS_SQLITE else "app.Subscriptions.SubscriptionID"), nullable=True)
    amount = Column("Amount", Float, nullable=False)
    currency = Column("Currency", Unicode(3), default="USD")
    status = Column("Status", Unicode(20), default="draft")  # draft, sent, paid, overdue, void
    stripe_invoice_id = Column("StripeInvoiceID", Unicode(255), nullable=True)
    period_start = Column("PeriodStart", DateTime, nullable=True)
    period_end = Column("PeriodEnd", DateTime, nullable=True)
    paid_at = Column("PaidAt", DateTime, nullable=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())


# ============ FEATURE FLAGS ============

class FeatureFlag(Base):
    """Per-tenant feature toggle system."""
    __tablename__ = "FeatureFlags"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("FlagID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=True, index=True)  # NULL = global default
    feature_key = Column("FeatureKey", Unicode(100), nullable=False, index=True)  # e.g., "sla_engine", "whatsapp", "ai_dashboard"
    enabled = Column("Enabled", Boolean, default=False)
    config_json = Column("ConfigJSON", UnicodeText, nullable=True)  # Per-feature configuration
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())


# ============ KNOWLEDGE COLLECTION (TENANT-SCOPED) ============

class KnowledgeCollection(Base):
    """Tenant-isolated knowledge base collections."""
    __tablename__ = "KnowledgeCollections"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}

    id = Column("CollectionID", Integer, primary_key=True, autoincrement=True)
    tenant_id = Column("TenantID", Unicode(36), ForeignKey("Tenants.TenantID" if IS_SQLITE else "app.Tenants.TenantID"), nullable=False, index=True)
    name = Column("Name", Unicode(255), nullable=False)
    description = Column("Description", UnicodeText, nullable=True)
    vector_index_path = Column("VectorIndexPath", Unicode(512), nullable=True)  # Path to tenant's FAISS index
    document_count = Column("DocumentCount", Integer, default=0)
    status = Column("Status", Unicode(20), default="active")  # active, building, error
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())
