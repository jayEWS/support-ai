from sqlalchemy import Column, Integer, Unicode, UnicodeText, DateTime, ForeignKey, Text, Float, func, Boolean, Table
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import os

Base = declarative_base()

# Determine if we're using SQLite (which doesn't support schemas)
IS_SQLITE = "sqlite" in os.environ.get("DATABASE_URL", "").lower()

# 1. Group-User Association (Many-to-Many)
user_roles = Table(
    "UserRoles", Base.metadata,
    Column("AgentID", Integer, ForeignKey("Agents.AgentID" if IS_SQLITE else "app.Agents.AgentID"), primary_key=True),
    Column("RoleID", Integer, ForeignKey("Roles.RoleID" if IS_SQLITE else "app.Roles.RoleID"), primary_key=True),
    **({"schema": "app"} if not IS_SQLITE else {})
)

# 2. Group-Privilege Association (Many-to-Many) - groupuserprivileges
role_permissions = Table(
    "RolePermissions", Base.metadata,
    Column("RoleID", Integer, ForeignKey("Roles.RoleID" if IS_SQLITE else "app.Roles.RoleID"), primary_key=True),
    Column("PermissionID", Integer, ForeignKey("Permissions.PermissionID" if IS_SQLITE else "app.Permissions.PermissionID"), primary_key=True),
    **({"schema": "app"} if not IS_SQLITE else {})
)

# 3. Individual User-Privilege Overrides (Many-to-Many) - userprivileges
user_permissions = Table(
    "UserPermissions", Base.metadata,
    Column("AgentID", Integer, ForeignKey("Agents.AgentID" if IS_SQLITE else "app.Agents.AgentID"), primary_key=True),
    Column("PermissionID", Integer, ForeignKey("Permissions.PermissionID" if IS_SQLITE else "app.Permissions.PermissionID"), primary_key=True),
    **({"schema": "app"} if not IS_SQLITE else {})
)

class Permission(Base):
    __tablename__ = "Permissions"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}
    id = Column("PermissionID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True) # e.g., 'knowledge.upload'
    category = Column("Category", Unicode(50), default="General") # e.g., 'System', 'Chat', 'KB'
    description = Column("Description", Unicode(255))

class Role(Base):
    __tablename__ = "Roles"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}
    id = Column("RoleID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True) # Group Name
    description = Column("Description", Unicode(255))
    is_active = Column("IsActive", Boolean, default=True)
    
    permissions = relationship("Permission", secondary=role_permissions, backref="roles")

class Agent(Base):
    """The User Master (usermst) Table"""
    """The User Master (usermst) Table"""
    __tablename__ = "Agents"
    __table_args__ = {"schema": "app"} if not IS_SQLITE else {}
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
    __table_args__ = {"schema": "app"}
    id = Column("ChallengeID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), index=True)
    code_hash = Column("CodeHash", Unicode(128))
    expires_at = Column("ExpiresAt", DateTime)
    attempts = Column("Attempts", Integer, default=0)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())

class AuthRefreshToken(Base):
    __tablename__ = "AuthRefreshTokens"
    __table_args__ = {"schema": "app"}
    id = Column("TokenID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), index=True)
    token_hash = Column("TokenHash", Unicode(128), unique=True, index=True)
    expires_at = Column("ExpiresAt", DateTime)
    revoked_at = Column("RevokedAt", DateTime)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())
    user_agent = Column("UserAgent", Unicode(255))

class AuthMagicLink(Base):
    __tablename__ = "AuthMagicLinks"
    __table_args__ = {"schema": "app"}
    id = Column("LinkID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("Username", Unicode(100), index=True)
    token_hash = Column("TokenHash", Unicode(128), unique=True, index=True)
    expires_at = Column("ExpiresAt", DateTime)
    created_at = Column("CreatedAt", DateTime, server_default=func.now())

# ... (rest of the models for Ticket, User, Message, etc. remain the same)

class User(Base):
    __tablename__ = "Users"
    __table_args__ = {"schema": "app"}
    identifier = Column("UserID", Unicode(100), primary_key=True)
    account_id = Column("AccountID", Unicode(20), unique=True, nullable=True)  # EWS1, EWS2, ...
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
    __table_args__ = {"schema": "app"}
    id = Column("MessageID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("UserID", Unicode(100), ForeignKey("app.Users.UserID"))
    role = Column("Role", Unicode(20))
    content = Column("Content", UnicodeText)
    attachments = Column("Attachments", UnicodeText)
    timestamp = Column("Timestamp", DateTime, server_default=func.now())

class Ticket(Base):
    __tablename__ = "Tickets"
    __table_args__ = {"schema": "app"}
    id = Column("TicketID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("CustomerID", Unicode(100), ForeignKey("app.Users.UserID"))
    summary = Column("Summary", UnicodeText)
    full_history = Column("FullHistory", UnicodeText)
    status = Column("Status", Unicode(20), default="open")
    priority = Column("Priority", Unicode(20), default="Medium")
    category = Column("TicketType", Unicode(50), default="Support") # NEW: Category/Issue Type
    assigned_to = Column("AssignedToAgent", Unicode(100), ForeignKey("app.Agents.Username"))
    asana_task_id = Column("AsanaTaskID", Unicode(100))
    due_at = Column("DueAt", DateTime)
    created_at = Column("CreatedDate", DateTime, server_default=func.now())
    modified_at = Column("ModifiedDate", DateTime, server_default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "AuditLogs"
    __table_args__ = {"schema": "app"}
    id = Column("LogID", Integer, primary_key=True, autoincrement=True)
    agent_id = Column("AgentID", Unicode(100))
    action = Column("Action", Unicode(100))
    target_type = Column("TargetType", Unicode(50))
    target_id = Column("TargetID", Unicode(100))
    details = Column("Details", UnicodeText)
    timestamp = Column("LogDate", DateTime, server_default=func.now())

class KnowledgeMetadata(Base):
    __tablename__ = "KnowledgeMetadata"
    __table_args__ = {"schema": "app"}
    id = Column("KnowledgeID", Integer, primary_key=True, autoincrement=True)
    filename = Column("Filename", Unicode(255), unique=True)
    file_path = Column("FilePath", Unicode(512))
    upload_date = Column("UploadDate", DateTime, server_default=func.now())
    uploaded_by = Column("UploadedBy", Unicode(100), ForeignKey("app.Agents.Username"))
    status = Column("Status", Unicode(50), default="Processing") # Processing, Indexed, Error
    source_url = Column("SourceURL", Unicode(1024), nullable=True)  # URL source for crawled docs

class Macro(Base):
    __tablename__ = "Macros"
    __table_args__ = {"schema": "app"}
    id = Column("MacroID", Integer, primary_key=True, autoincrement=True)
    name = Column("Name", Unicode(100), unique=True)
    content = Column("Content", UnicodeText)
    category = Column("Category", Unicode(50), default="General")
    created_at = Column("CreatedDate", DateTime, server_default=func.now())

class AgentPresence(Base):
    __tablename__ = "AgentPresence"
    __table_args__ = {"schema": "app"}
    id = Column("PresenceID", Integer, primary_key=True, autoincrement=True)
    agent_id = Column("Username", Unicode(100), ForeignKey("app.Agents.Username"), unique=True)
    status = Column("Status", Unicode(20), default="available")
    active_chat_count = Column("ActiveChatCount", Integer, default=0)
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

class CSATSurvey(Base):
    __tablename__ = "CSATSurveys"
    __table_args__ = {"schema": "app"}
    id = Column("SurveyID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID"), unique=True)
    rating = Column("Rating", Integer)
    feedback = Column("Feedback", UnicodeText)
    submitted_at = Column("SubmittedAt", DateTime, server_default=func.now())

class ChatSession(Base):
    __tablename__ = "ChatSessions"
    __table_args__ = {"schema": "app"}
    id = Column("SessionID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID"))
    agent_id = Column("AgentID", Unicode(100), ForeignKey("app.Agents.Username"))
    customer_id = Column("CustomerID", Unicode(100))
    started_at = Column("StartedAt", DateTime, server_default=func.now())
    ended_at = Column("EndedAt", DateTime)

class ChatMessage(Base):
    __tablename__ = "ChatMessages"
    __table_args__ = {"schema": "app"}
    id = Column("ChatMessageID", Integer, primary_key=True, autoincrement=True)
    session_id = Column("SessionID", Integer, ForeignKey("app.ChatSessions.SessionID"))
    sender_id = Column("SenderID", Unicode(100))
    sender_type = Column("SenderType", Unicode(20))
    content = Column("Content", UnicodeText)
    attachment_url = Column("AttachmentURL", UnicodeText)
    sent_at = Column("SentAt", DateTime, server_default=func.now())

class SLARule(Base):
    __tablename__ = "SLARules"
    __table_args__ = {"schema": "app"}
    id = Column("RuleID", Integer, primary_key=True, autoincrement=True)
    name = Column("RuleName", Unicode(100))
    priority = Column("Priority", Unicode(20), unique=True)
    first_response_minutes = Column("FirstResponseMinutes", Integer)
    resolution_minutes = Column("ResolutionMinutes", Integer)
    created_at = Column("CreatedDate", DateTime, server_default=func.now())

class TicketQueue(Base):
    __tablename__ = "TicketQueue"
    __table_args__ = {"schema": "app"}
    id = Column("QueueID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("app.Tickets.TicketID"), unique=True)
    priority_level = Column("PriorityLevel", Integer, default=1)
    queued_at = Column("QueuedAt", DateTime, server_default=func.now())
    assigned_at = Column("AssignedAt", DateTime)

# ============ WhatsApp Messages ============

class WhatsAppMessage(Base):
    """Stores all WhatsApp messages (inbound + outbound) for visibility in admin dashboard."""
    __tablename__ = "WhatsAppMessages"
    __table_args__ = {"schema": "app"}
    id = Column("MessageID", Integer, primary_key=True, autoincrement=True)
    bird_message_id = Column("BirdMessageID", Unicode(255), unique=True, nullable=True)
    phone_number = Column("PhoneNumber", Unicode(20), index=True)  # e.g. +6281229009543
    direction = Column("Direction", Unicode(10))  # 'inbound' or 'outbound'
    content = Column("Content", UnicodeText)
    message_type = Column("MessageType", Unicode(20), default="text")  # text, image, audio, etc.
    status = Column("Status", Unicode(20), default="received")  # received, sent, failed
    ticket_id = Column("TicketID", Integer, nullable=True)  # Link to ticket if created
    created_at = Column("CreatedAt", DateTime, server_default=func.now())

# ============ Freshdesk Historical Data ============

class SystemSetting(Base):
    """Key-value store for system settings (e.g. ticket notification email)."""
    __tablename__ = "SystemSettings"
    __table_args__ = {"schema": "app"}
    key = Column("SettingKey", Unicode(100), primary_key=True)
    value = Column("SettingValue", UnicodeText, nullable=True)
    updated_at = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

class FreshdeskContact(Base):
    """Imported customer contacts from Freshdesk ticket exports."""
    __tablename__ = "FreshdeskContacts"
    __table_args__ = {"schema": "app"}
    id = Column("ContactID", Integer, primary_key=True, autoincrement=True)
    freshdesk_id = Column("FreshdeskContactID", Unicode(255), unique=True, index=True)  # Contact ID from export
    full_name = Column("FullName", Unicode(255))
    email = Column("Email", Unicode(255))
    work_phone = Column("WorkPhone", Unicode(50))
    mobile_phone = Column("MobilePhone", Unicode(50))
    company_name = Column("CompanyName", Unicode(255))
    industry = Column("Industry", Unicode(100))
    timezone = Column("Timezone", Unicode(50))
    language = Column("Language", Unicode(10))
    account_tier = Column("AccountTier", Unicode(50))
    health_score = Column("HealthScore", Unicode(50))
    total_tickets = Column("TotalTickets", Integer, default=0)
    # Link to internal User table (if mapped)
    internal_user_id = Column("InternalUserID", Unicode(100), ForeignKey("app.Users.UserID"), nullable=True)
    created_at = Column("CreatedDate", DateTime, server_default=func.now())

class FreshdeskTicket(Base):
    """Imported historical tickets from Freshdesk exports."""
    __tablename__ = "FreshdeskTickets"
    __table_args__ = {"schema": "app"}
    id = Column("RecordID", Integer, primary_key=True, autoincrement=True)
    ticket_id = Column("FreshdeskTicketID", Integer, unique=True, index=True)
    subject = Column("Subject", UnicodeText)
    status = Column("Status", Unicode(30))
    priority = Column("Priority", Unicode(20))
    source = Column("Source", Unicode(30))
    ticket_type = Column("TicketType", Unicode(100))
    agent = Column("Agent", Unicode(100))
    group_name = Column("GroupName", Unicode(100))
    tags = Column("Tags", UnicodeText)
    summary = Column("Summary", UnicodeText)
    product = Column("Product", Unicode(100))
    # Contact reference
    contact_id = Column("ContactRef", Unicode(255), ForeignKey("app.FreshdeskContacts.FreshdeskContactID"), nullable=True)
    # Timestamps
    created_time = Column("CreatedTime", DateTime)
    due_by_time = Column("DueByTime", DateTime)
    resolved_time = Column("ResolvedTime", DateTime)
    closed_time = Column("ClosedTime", DateTime)
    last_update_time = Column("LastUpdateTime", DateTime)
    initial_response_time = Column("InitialResponseTime", DateTime)
    # Metrics
    first_response_hrs = Column("FirstResponseHrs", Unicode(30))
    resolution_hrs = Column("ResolutionHrs", Unicode(30))
    agent_interactions = Column("AgentInteractions", Integer, default=0)
    customer_interactions = Column("CustomerInteractions", Integer, default=0)
    resolution_status = Column("ResolutionStatus", Unicode(30))  # Within SLA / SLA Violated
    first_response_status = Column("FirstResponseStatus", Unicode(30))
    survey_results = Column("SurveyResults", Unicode(50))
    csat_score = Column("CSATScore", Unicode(50))
    imported_at = Column("ImportedAt", DateTime, server_default=func.now())
