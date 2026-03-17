from sqlalchemy import Column, Integer, Unicode, UnicodeText, DateTime, ForeignKey, Text, Float, func, Boolean, Table, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import os

Base = declarative_base()

# Determine DB type — SQLite & PostgreSQL use default schema (no "app." prefix)
# Only SQL Server uses the custom "app" schema
def get_db_type_info():
    from app.core.config import settings
    url = (settings.DATABASE_URL or "").lower()
    is_sqlite = "sqlite" in url
    is_postgres = "postgresql" in url or "postgres" in url
    is_mssql = "mssql" in url
    return is_sqlite, is_postgres, is_mssql, is_mssql

IS_SQLITE, IS_POSTGRES, IS_MSSQL, USE_APP_SCHEMA = get_db_type_info()

# ── Multi-Tenant Column Helper ────────────────────────────────────────
# When MULTI_TENANT_ENABLED=False, do NOT map the TenantID column
# (the column may not exist in the database at all).
def _check_multi_tenant():
    from app.core.config import settings
    return getattr(settings, "MULTI_TENANT_ENABLED", False)

_MULTI_TENANT = _check_multi_tenant()

def tenant_id_column():
    """Return a TenantID Column only if multi-tenancy is enabled, else None."""
    if _MULTI_TENANT:
        return Column("TenantID", Unicode(36), index=True, nullable=True)
    return None

# 1. Group-User Association (Many-to-Many)
user_roles = Table(
    "UserRoles", Base.metadata,
    Column("AgentID", Integer, ForeignKey("app.Agents.AgentID" if USE_APP_SCHEMA else "Agents.AgentID"), primary_key=True),
    Column("RoleID", Integer, ForeignKey("app.Roles.RoleID" if USE_APP_SCHEMA else "Roles.RoleID"), primary_key=True),
    **({"schema": "app"} if USE_APP_SCHEMA else {})
)

# 2. Group-Privilege Association (Many-to-Many) - groupuserprivileges
role_permissions = Table(
    "RolePermissions", Base.metadata,
    Column("RoleID", Integer, ForeignKey("app.Roles.RoleID" if USE_APP_SCHEMA else "Roles.RoleID"), primary_key=True),
    Column("PermissionID", Integer, ForeignKey("app.Permissions.PermissionID" if USE_APP_SCHEMA else "Permissions.PermissionID"), primary_key=True),
    **({"schema": "app"} if USE_APP_SCHEMA else {})
)

# 3. Individual User-Privilege Overrides (Many-to-Many) - userprivileges
user_permissions = Table(
    "UserPermissions", Base.metadata,
    Column("AgentID", Integer, ForeignKey("app.Agents.AgentID" if USE_APP_SCHEMA else "Agents.AgentID"), primary_key=True),
    Column("PermissionID", Integer, ForeignKey("app.Permissions.PermissionID" if USE_APP_SCHEMA else "Permissions.PermissionID"), primary_key=True),
    **({"schema": "app"} if USE_APP_SCHEMA else {})
)

class Permission(Base):
    __tablename__ = "Permissions"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("PermissionID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True) # e.g., 'knowledge.upload'
    category = Column("Category", Unicode(50), default="General") # e.g., 'System', 'Chat', 'KB'
    description = Column("Description", Unicode(255))

class Role(Base):
    __tablename__ = "Roles"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("RoleID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True) # Group Name
    description = Column("Description", Unicode(255))
    is_active = Column("IsActive", Boolean, default=True)
    
    permissions = relationship("Permission", secondary=role_permissions, backref="roles")

class Agent(Base):
    """The User Master (usermst) Table"""
    __tablename__ = "Agents"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    agent_id = Column("AgentID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), unique=True, index=True)
    name = Column("FullName", Unicode(255))
    email = Column("Email", Unicode(255), unique=True)
    department = Column("Department", Unicode(50), default="Support")
    hashed_password = Column("HashedPassword", UnicodeText)
    google_id = Column("GoogleID", Unicode(100), unique=True, index=True)
    is_active = Column("IsActive", Boolean, default=True)
    created_at = Column("CreatedDate", DateTime, server_default=func.now())
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, backref="agents")
    direct_permissions = relationship("Permission", secondary=user_permissions, backref="agents_with_direct_access")

class AuthMFAChallenge(Base):
    __tablename__ = "AuthMFAChallenges"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("ChallengeID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), index=True)
    code_hash = Column("CodeHash", Unicode(128))
    expires_at = Column("ExpiresAt", DateTime)
    attempts = Column("Attempts", Integer, default=0)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())

class AuthRefreshToken(Base):
    __tablename__ = "AuthRefreshTokens"
    __table_args__ = (
        Index("ix_refreshtoken_user_active", "Username", "RevokedAt"),  # Fast active-token lookup
        {"schema": "app"} if USE_APP_SCHEMA else {}
    )
    tenant_id = tenant_id_column()
    id = Column("TokenID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), index=True)
    token_hash = Column("TokenHash", Unicode(128), unique=True, index=True)
    expires_at = Column("ExpiresAt", DateTime)
    revoked_at = Column("RevokedAt", DateTime)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    user_agent = Column("UserAgent", Unicode(255))

class AuthMagicLink(Base):
    __tablename__ = "AuthMagicLinks"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("LinkID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), index=True)
    token_hash = Column("TokenHash", Unicode(128), unique=True, index=True)
    expires_at = Column("ExpiresAt", DateTime)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())

class Outlet(Base):
    __tablename__ = "outlets"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("OutletID", Integer, primary_key=True)
    name = Column("OutletName", Unicode(100))
    location = Column("Location", Unicode(255))
    timezone = Column("Timezone", Unicode(50), default="Asia/Singapore")
    pos_version = Column("POSVersion", Unicode(20))
    tenant_id = tenant_id_column()

class POSDevice(Base):
    __tablename__ = "pos_devices"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("DeviceID", Unicode(50), primary_key=True)
    outlet_id = Column("OutletID", Integer, ForeignKey("app.outlets.OutletID" if USE_APP_SCHEMA else "outlets.OutletID"))
    device_type = Column("DeviceType", Unicode(50)) # pos_terminal, printer, scanner, payment_terminal
    device_name = Column("DeviceName", Unicode(100))
    status = Column("Status", Unicode(20), default="online")
    last_seen = Column("LastSeen", DateTime, server_default=func.now())
    ip_address = Column("IPAddress", Unicode(45))
    tenant_id = tenant_id_column()

class POSTransaction(Base):
    __tablename__ = "pos_transactions"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("TransactionID", Unicode(50), primary_key=True)
    outlet_id = Column("OutletID", Integer, ForeignKey("app.outlets.OutletID" if USE_APP_SCHEMA else "outlets.OutletID"))
    device_id = Column("DeviceID", Unicode(50), ForeignKey("app.pos_devices.DeviceID" if USE_APP_SCHEMA else "pos_devices.DeviceID"))
    timestamp = Column("TransactionTime", DateTime, server_default=func.now())
    total_amount = Column("TotalAmount", Float)
    tax_amount = Column("TaxAmount", Float)
    payment_method = Column("PaymentMethod", Unicode(50))
    status = Column("Status", Unicode(20)) # completed, failed, void
    tenant_id = tenant_id_column()

class Voucher(Base):
    __tablename__ = "vouchers"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    code = Column("VoucherCode", Unicode(50), primary_key=True)
    campaign_id = Column("CampaignID", Unicode(50))
    status = Column("Status", Unicode(20), default="active") # active, expired, redeemed
    expiry_date = Column("ExpiryDate", DateTime)
    usage_limit = Column("UsageLimit", Integer, default=1)
    usage_count = Column("UsageCount", Integer, default=0)
    tenant_id = tenant_id_column()

class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("MembershipID", Unicode(50), primary_key=True)
    customer_name = Column("CustomerName", Unicode(100))
    points_balance = Column("PointsBalance", Integer, default=0)
    tier = Column("Tier", Unicode(20), default="Bronze")
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    tenant_id = tenant_id_column()

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("ItemID", Unicode(50), primary_key=True)
    name = Column("ItemName", Unicode(100))
    category = Column("Category", Unicode(50))
    price = Column("Price", Float)
    status = Column("Status", Unicode(20), default="active")
    tenant_id = tenant_id_column()

class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("InteractionID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("UserID", Unicode(50))
    query = Column("UserQuery", Text)
    response = Column("AIResponse", Text)
    retrieved_docs = Column("RetrievedDocs", Text) # JSON list
    tools_used = Column("ToolsUsed", Text) # JSON list
    confidence = Column("Confidence", Float)
    resolution_status = Column("ResolutionStatus", Unicode(20), default="pending") # solved, escalated, correction_needed
    human_correction = Column("HumanCorrection", Text, nullable=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    tenant_id = tenant_id_column()

class POSIssue(Base):
    """Knowledge Base entry for an AI Support issue (as defined in knowledge_base_schema.md)"""
    __tablename__ = "pos_issues"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    id = Column("IssueID", Integer, primary_key=True, autoincrement=True)
    problem_id = Column("ProblemID", Unicode(50), unique=True, index=True) # e.g., POS_SYNC_001
    problem_name = Column("ProblemName", Unicode(255))
    category = Column("Category", Unicode(100))
    priority = Column("Priority", Unicode(50), default="medium")
    affected_system = Column("AffectedSystem", Text)  # JSON/CSV
    symptoms = Column("Symptoms", Text)
    root_causes = Column("RootCauses", Text)
    diagnostic_steps = Column("DiagnosticSteps", Text)
    fix_steps = Column("FixSteps", Text)
    automation_tools = Column("AutomationTools", Text) # JSON list
    verification_steps = Column("VerificationSteps", Text)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())
    tenant_id = tenant_id_column()

class User(Base):
    __tablename__ = "Users"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    identifier = Column("UserID", Unicode(100), primary_key=True)
    account_id = Column("AccountID", Unicode(20), index=True, nullable=True)  # EWS1, EWS2, ...
    name = Column("DisplayName", Unicode(255))
    email = Column("Email", Unicode(255), nullable=True)
    mobile = Column("Mobile", Unicode(50), nullable=True)
    company = Column("Company", Unicode(255))
    position = Column("Position", Unicode(100)) # NEW: Cashier, SPV, Manager, etc.
    outlet_pos = Column("OutletPOS", Unicode(100)) # NEW: Outlet name or ID
    outlet_address = Column("OutletAddress", Unicode(500), nullable=True)
    category = Column("Category", Unicode(50), nullable=True)  # Retail / FNB
    language = Column("Language", Unicode(10), nullable=True)  # id, en, zh
    state = Column("CurrentState", Unicode(20), default="idle")
    created_at = Column("CreatedDate", DateTime, server_default=func.now())

class Message(Base):
    __tablename__ = "PortalMessages"
    __table_args__ = (
        Index("ix_msg_user_time", "UserID", "Timestamp"),      # Fast chat history
        Index("ix_msg_user_role", "UserID", "Role"),            # Fast role-filtered queries
        {"schema": "app"} if USE_APP_SCHEMA else {}
    )
    tenant_id = tenant_id_column()
    id = Column("MessageID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("UserID", Unicode(100), ForeignKey("app.Users.UserID" if USE_APP_SCHEMA else "Users.UserID"), index=True)
    role = Column("Role", Unicode(20))
    content = Column("Content", UnicodeText)
    attachments = Column("Attachments", UnicodeText)
    timestamp = Column("Timestamp", DateTime, server_default=func.now())

class Ticket(Base):
    __tablename__ = "Tickets"
    __table_args__ = (
        Index("ix_ticket_status_created", "Status", "CreatedDate"),      # Inbox filtering
        Index("ix_ticket_status_assigned", "Status", "AssignedToAgent"),  # Unassigned queries
        Index("ix_ticket_customer", "CustomerID", "CreatedDate"),         # Customer ticket history
        Index("ix_ticket_due_status", "DueAt", "Status"),                 # SLA/overdue checks
        {"schema": "app"} if USE_APP_SCHEMA else {}
    )
    tenant_id = tenant_id_column()
    id = Column("TicketID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("CustomerID", Unicode(100), ForeignKey("app.Users.UserID" if USE_APP_SCHEMA else "Users.UserID"), index=True)
    summary = Column("Summary", UnicodeText)
    full_history = Column("FullHistory", UnicodeText)
    status = Column("Status", Unicode(20), default="open", index=True)
    priority = Column("Priority", Unicode(20), default="Medium")
    category = Column("TicketType", Unicode(50), default="Support")
    assigned_to = Column("AssignedToAgent", Unicode(100), ForeignKey("app.Agents.Username" if USE_APP_SCHEMA else "Agents.Username"))
    due_at = Column("DueAt", DateTime)
    created_at = Column("CreatedDate", DateTime, server_default=func.now())
    modified_at = Column("ModifiedDate", DateTime, server_default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "AuditLogs"
    __table_args__ = (
        Index("ix_audit_time", "LogDate"),         # Fast recent-first queries
        Index("ix_audit_agent", "AgentID"),         # Per-agent audit trail
        {"schema": "app"} if USE_APP_SCHEMA else {}
    )
    tenant_id = tenant_id_column()
    id = Column("LogID", Integer, primary_key=True, autoincrement=True)
    agent_id = Column("AgentID", Unicode(100))
    action = Column("Action", Unicode(100))
    target_type = Column("TargetType", Unicode(50))
    target_id = Column("TargetID", Unicode(100))
    details = Column("Details", UnicodeText)
    timestamp = Column("LogDate", DateTime, server_default=func.now())

class KnowledgeMetadata(Base):
    __tablename__ = "KnowledgeMetadata"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("KnowledgeID", Integer, primary_key=True, autoincrement=True)
    filename = Column("Filename", Unicode(255), unique=True)
    file_path = Column("FilePath", Unicode(512))
    upload_date = Column("UploadDate", DateTime, server_default=func.now())
    uploaded_by = Column("UploadedBy", Unicode(100), ForeignKey("app.Agents.Username" if USE_APP_SCHEMA else "Agents.Username"))
    status = Column("Status", Unicode(50), default="Processing") # Processing, Indexed, Error
    source_url = Column("SourceURL", Unicode(1024), nullable=True)  # URL source for crawled docs

class Macro(Base):
    __tablename__ = "Macros"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("MacroID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True)
    content = Column("Content", UnicodeText)
    category = Column("Category", Unicode(50), default="General")
    created_at = Column("CreatedDate", DateTime, server_default=func.now())

class AgentPresence(Base):
    __tablename__ = "AgentPresence"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("PresenceID", Integer, primary_key=True, autoincrement=True)
    agent_id = Column("Username", Unicode(100), ForeignKey("app.Agents.Username" if USE_APP_SCHEMA else "Agents.Username"), unique=True)
    status = Column("Status", Unicode(20), default="available")
    active_chat_count = Column("ActiveChatCount", Integer, default=0)
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

class CSATSurvey(Base):
    __tablename__ = "CSATSurveys"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("SurveyID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID" if USE_APP_SCHEMA else "Tickets.TicketID"), unique=True)
    rating = Column("Rating", Integer)
    feedback = Column("Feedback", UnicodeText)
    submitted_at = Column("SubmittedAt", DateTime, server_default=func.now())

class ChatSession(Base):
    __tablename__ = "ChatSessions"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("SessionID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID" if USE_APP_SCHEMA else "Tickets.TicketID"))
    agent_id = Column("AgentID", Unicode(100), ForeignKey("app.Agents.Username" if USE_APP_SCHEMA else "Agents.Username"))
    customer_id = Column("CustomerID", Unicode(100))
    started_at = Column("StartedAt", DateTime, server_default=func.now())
    ended_at = Column("EndedAt", DateTime)

class ChatMessage(Base):
    __tablename__ = "ChatMessages"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("ChatMessageID", Integer, primary_key=True, autoincrement=True)
    session_id = Column("SessionID", Integer, ForeignKey("app.ChatSessions.SessionID" if USE_APP_SCHEMA else "ChatSessions.SessionID"))
    sender_id = Column("SenderID", Unicode(100))
    sender_type = Column("SenderType", Unicode(20))
    content = Column("Content", UnicodeText)
    attachment_url = Column("AttachmentURL", UnicodeText)
    sent_at = Column("SentAt", DateTime, server_default=func.now())

class SLARule(Base):
    __tablename__ = "SLARules"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("RuleID", Integer, primary_key=True, autoincrement=True)
    name = Column("RuleName", Unicode(100))
    priority = Column("Priority", Unicode(20), unique=True)
    first_response_minutes = Column("FirstResponseMinutes", Integer)
    resolution_minutes = Column("ResolutionMinutes", Integer)
    created_at = Column("CreatedDate", DateTime, server_default=func.now())

class TicketQueue(Base):
    __tablename__ = "TicketQueue"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    id = Column("QueueID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID" if USE_APP_SCHEMA else "Tickets.TicketID"), unique=True)
    priority_level = Column("PriorityLevel", Integer, default=1)
    queued_at = Column("QueuedAt", DateTime, server_default=func.now())
    assigned_at = Column("AssignedAt", DateTime)

# ============ WhatsApp Messages ============

class WhatsAppMessage(Base):
    """Stores all WhatsApp messages (inbound + outbound) for visibility in admin dashboard."""
    __tablename__ = "WhatsAppMessages"
    __table_args__ = (
        Index("ix_wa_phone_created", "PhoneNumber", "CreatedAt"),   # Conversation thread
        Index("ix_wa_phone_direction", "PhoneNumber", "Direction"),  # Inbound/outbound filter
        Index("ix_wa_ticket", "TicketID"),                           # Linked ticket lookup
        {"schema": "app"} if USE_APP_SCHEMA else {}
    )
    tenant_id = tenant_id_column()
    id = Column("MessageID", Integer, primary_key=True, autoincrement=True)
    external_message_id = Column("ExternalMessageID", Unicode(255), unique=True, nullable=True)
    phone_number = Column("PhoneNumber", Unicode(20), index=True, nullable=False)
    direction = Column("Direction", Unicode(10), nullable=False)  # 'inbound' or 'outbound'
    content = Column("Content", UnicodeText)
    message_type = Column("MessageType", Unicode(20), default="text")
    status = Column("Status", Unicode(20), default="received")
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID" if USE_APP_SCHEMA else "Tickets.TicketID"), nullable=True)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())

class SystemSetting(Base):
    """Key-value store for system settings (e.g. ticket notification email)."""
    __tablename__ = "SystemSettings"
    __table_args__ = {"schema": "app"} if USE_APP_SCHEMA else {}
    tenant_id = tenant_id_column()
    key = Column("SettingKey", Unicode(100), primary_key=True)
    value = Column("SettingValue", UnicodeText, nullable=True)
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())
