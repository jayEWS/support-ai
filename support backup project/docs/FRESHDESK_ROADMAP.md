# Freshdesk / Freshchat Feature Roadmap

## Overview
Transform the Support Portal AI into a full-featured support ticketing and live chat platform similar to Freshdesk/Freshchat. This roadmap prioritizes features by business impact, technical dependency order, and implementation complexity.

---

## Milestone 1: Core Ticketing & Agent Inbox (Week 1-2)
**Goal**: Agents can see, assign, and update tickets; customers see ticket status.

### Features
- **Ticket List (Agent View)**
  - List all tickets with filters (status, priority, assigned_to)
  - Search by ticket ID, customer name, or summary
  - Bulk actions (reassign, change status, close)
  - Sort by created_at, due_at (SLA), priority

- **Ticket Detail View**
  - Full conversation history (user messages + AI responses)
  - Ticket metadata: ID, customer name, company, created_at, updated_at, status, priority, assigned_to, due_at
  - Internal notes (private comments between agents)
  - Attachment preview
  - Quick actions: Resolve, Reassign, Change Priority, Snooze

- **Customer Ticket Portal**
  - View my tickets
  - See ticket status and last update
  - Add follow-up comments/attachments to ticket
  - Track SLA: show "due in X hours" or "overdue"

- **Ticket Lifecycle**
  - Statuses: Open, In Progress, Waiting on Customer, Resolved, Closed
  - Auto-create ticket when conversation ends
  - Agents can manually create tickets

### Database Schema Changes
```sql
-- Extend tickets table
ALTER TABLE tickets ADD COLUMN assigned_to TEXT;  -- agent_id (user.identifier)
ALTER TABLE tickets ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE tickets ADD COLUMN internal_notes TEXT;  -- JSON array of notes

-- New tables
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE,
    name TEXT,
    email TEXT,
    role TEXT DEFAULT 'agent',  -- 'agent', 'supervisor', 'admin'
    skills TEXT,  -- JSON: ["billing", "technical", "sales"]
    availability_status TEXT DEFAULT 'available',  -- 'available', 'busy', 'offline'
    last_activity_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    agent_id TEXT,
    content TEXT,
    is_internal BOOLEAN DEFAULT 1,  -- 1 = internal, 0 = customer-visible
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (agent_id) REFERENCES agents(user_id)
);

CREATE TABLE IF NOT EXISTS ticket_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    action TEXT,  -- 'status_change', 'assign', 'priority_change', 'note_added'
    old_value TEXT,
    new_value TEXT,
    actor_id TEXT,  -- agent or system
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
```

### API Endpoints
- `GET /api/tickets` — list with filters, pagination
- `GET /api/tickets/{id}` — ticket detail + full history
- `PATCH /api/tickets/{id}` — update status, priority, assigned_to
- `POST /api/tickets/{id}/notes` — add internal note
- `GET /api/tickets/{id}/activity` — ticket audit log
- `POST /api/tickets` — manually create ticket
- `DELETE /api/tickets/{id}` — soft delete (archive)

### UI Components
- Agent Dashboard (sidebar: ticket filters, counts)
- Ticket List Table
- Ticket Detail Panel
- Customer Portal: My Tickets page

---

## Milestone 2: Real-time Chat with WebSocket (Week 2-3)
**Goal**: Agents and customers see live typing, presence, and instant message delivery.

### Features
- **WebSocket Connection**
  - Establish WebSocket per user session (customer or agent)
  - Broadcast user typing indicators
  - Real-time message delivery (no polling)
  - Presence: show "Agent X is typing...", agent status (available/busy/offline)

- **Live Typing Indicators**
  - User types → broadcast `typing_start` event → show "Agent is typing..."
  - Stop typing for 1s → broadcast `typing_stop` event
  - Clear on message send

- **Message Delivery Confirmation**
  - Customer sends message → server broadcasts to assigned agent + UI
  - Agent sees message in real-time, shows as unread
  - Mark as read → broadcast to customer ("read at HH:MM")

- **Agent Presence**
  - Agents can set status: Available, Busy, In a Meeting, Offline
  - System auto-sets Offline after inactivity (5 min)
  - Show agent status next to name in UI
  - Only route chats to Available agents

### Architecture
```
Client (Customer/Agent)
    ↓ WebSocket
FastAPI WebSocket Handler
    ↓
ConnectionManager (dict of active connections by user_id)
    ↓
Message Broker (broadcast to interested parties)
    ↓
Database Logger (persist all messages + read receipts)
```

### Database Schema Changes
```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    agent_id TEXT,
    customer_id TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (agent_id) REFERENCES agents(user_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    sender_id TEXT,  -- customer or agent
    sender_type TEXT,  -- 'customer' or 'agent'
    content TEXT,
    attachment_url TEXT,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME,  -- NULL if not read
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE TABLE IF NOT EXISTS agent_presence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT UNIQUE,
    status TEXT,  -- 'available', 'busy', 'in_meeting', 'offline'
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(user_id)
);
```

### WebSocket Events
```json
{
  "typing_start": {"user_id": "...", "name": "..."},
  "typing_stop": {"user_id": "..."},
  "message": {"sender_id": "...", "content": "...", "timestamp": "..."},
  "message_read": {"session_id": "...", "message_id": "...", "read_at": "..."},
  "presence_update": {"agent_id": "...", "status": "available|busy|offline"},
  "agent_assigned": {"agent_id": "...", "agent_name": "..."},
  "session_closed": {"session_id": "..."}
}
```

### API & WebSocket Endpoints
- `WS /ws/chat/{session_id}` — join chat session (customer or agent)
- `POST /api/chat-sessions` — create new session
- `GET /api/chat-sessions/{id}/messages` — load chat history
- `PATCH /api/agents/{id}/presence` — update agent status
- `GET /api/agents/available` — list available agents

### UI Components
- Live Chat Widget (customer-facing)
- Agent Chat Panel (sidebar)
- Typing Indicator ("Agent is typing...")
- Message Read Receipts
- Agent Presence Badge

---

## ✅ Milestone 3: Multi-Agent Routing & SLA (COMPLETE)
**Goal**: Automatically route incoming chats to the best available agent; track & enforce SLAs.

### Features
- **Routing Strategies**
  - Round-robin: distribute evenly
  - Least busy: assign to agent with fewest active chats
  - Skills-based: match chat tags/category to agent skills
  - Load-aware: consider agent availability + current queue

- **SLA Management**
  - Define SLA rules: First Response Time, Resolution Time per priority
  - Example: P1 → respond in 15 min, resolve in 2 hours; P2 → 1 hour, 8 hours
  - Track actual response & resolution times
  - Alert agents when SLA breached
  - Report on SLA compliance (dashboard metric)

- **Queue Management**
  - Queue tickets awaiting assignment
  - Show queue depth (N tickets waiting)
  - Priority queue: P1 tickets served first
  - Estimated wait time (based on avg resolution time)

### Database Schema Changes
```sql
CREATE TABLE IF NOT EXISTS sla_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    priority TEXT,  -- 'P1', 'P2', 'P3', etc.
    first_response_minutes INTEGER,
    resolution_minutes INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sla_breaches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    sla_rule_id INTEGER,
    breach_type TEXT,  -- 'first_response' or 'resolution'
    breached_at DATETIME,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (sla_rule_id) REFERENCES sla_rules(id)
);

CREATE TABLE IF NOT EXISTS ticket_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER UNIQUE,
    priority INTEGER,  -- higher = more urgent
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    assigned_at DATETIME,  -- NULL until assigned
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

ALTER TABLE agents ADD COLUMN max_concurrent_chats INTEGER DEFAULT 5;
```

### Routing Algorithm
```python
def route_chat(ticket: Ticket):
    # 1. Get available agents (status='available')
    available = get_available_agents()
    
    # 2. Filter by skills match if ticket has category
    if ticket.category:
        available = [a for a in available if ticket.category in a.skills]
    
    # 3. Get least busy agent
    agent = min(available, key=lambda a: a.active_chat_count)
    
    # 4. Assign & start session
    assign_to_agent(ticket, agent)
    return agent
```

### API Endpoints
- `POST /api/sla-rules` — create/update SLA rule
- `GET /api/sla-rules` — list all rules
- `GET /api/queue` — view ticket queue
- `POST /api/routing/assign-next` — trigger manual routing
- `GET /api/sla-metrics` — SLA compliance report

### UI Components
- Queue Dashboard (agents see their queue count)
- SLA Timer on ticket detail (red if breached)
- Routing Settings (admin config)

---

## Milestone 4: Agent Dashboard & Macros (Week 4)
**Goal**: Agents work efficiently with canned responses, saved searches, and insights.

### Features
- **Agent Dashboard**
  - Today's stats: chats handled, avg resolution time, SLA compliance
  - My queue: tickets assigned to me
  - Recent activity feed
  - Performance trends (daily, weekly)

- **Canned Responses (Macros)**
  - Save frequently used responses
  - Categorize by topic
  - Use variables: {{customer_name}}, {{ticket_id}}, {{product}}
  - Share macros with team
  - Usage metrics (which macros used most)

- **Saved Searches**
  - Save filter combinations for quick access
  - E.g., "My P1s", "Unresolved billing issues", "Waiting on customer"
  - One-click apply

- **Performance Analytics**
  - CSAT score (customer satisfaction survey after ticket close)
  - Response time distribution
  - Resolution rate
  - Tickets reopened rate

### Database Schema Changes
```sql
CREATE TABLE IF NOT EXISTS macros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    content TEXT,  -- supports {{variables}}
    category TEXT,
    created_by TEXT,  -- agent_id
    is_shared BOOLEAN DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES agents(user_id)
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT,
    name TEXT,
    filters JSON,  -- {"status": "open", "priority": "P1"}
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(user_id)
);

CREATE TABLE IF NOT EXISTS csat_surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    rating INTEGER,  -- 1-5
    feedback TEXT,
    submitted_at DATETIME,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
```

### API Endpoints
- `GET /api/agent-dashboard` — agent dashboard metrics
- `POST /api/macros` — create macro
- `GET /api/macros` — list macros (personal + shared)
- `POST /api/saved-searches` — save search
- `GET /api/performance` — agent performance metrics
- `POST /api/csat/{ticket_id}` — submit CSAT survey

### UI Components
- Agent Dashboard landing page
- Macro Library modal
- Macro inserter (suggestions while typing)
- Performance Chart

---

## Milestone 5: Integrations & Channels (Week 5)
**Goal**: Unified inbox: WhatsApp, Email, Slack, SMS via single support platform.

### Supported Channels
1. **WhatsApp** (via Bird/MessageBird or Twilio)
2. [x] **Email** (IMAP/SMTP or Mailgun/SendGrid)
3. **Slack** (direct DM or mention bot)
4. **SMS** (Twilio)
5. **Web Chat** (widget on customer website)

### Architecture
```
Incoming Message (WhatsApp/Email/Slack)
    ↓
Normalize to Unified Format
    ↓
Create/Update Ticket
    ↓
Route to Agent
    ↓
Agent Replies
    ↓
Send Back on Original Channel
```

### Database Schema Changes
```sql
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,  -- 'whatsapp', 'email', 'slack', 'sms', 'web'
    is_enabled BOOLEAN DEFAULT 1,
    config JSON,  -- provider-specific config (API keys, channel IDs, etc.)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_channel_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    channel_name TEXT,
    external_id TEXT,  -- message ID on external platform (WhatsApp msg ID, email ID, etc.)
    FOREIGN KEY (message_id) REFERENCES chat_messages(id)
);
```

### API Endpoints
- `POST /webhook/whatsapp` — already exists, keep + enhance
- `POST /webhook/email` — Mailgun/SendGrid webhook
- `POST /webhook/slack` — Slack Event API
- `GET /api/channels` — list enabled channels
- `POST /api/channels/{name}/config` — admin configure channel

### Implementation Priority
1. **Email** (most critical for traditional support)
2. **Slack** (internal team collab)
3. **SMS** (Twilio integration)
4. [x] **Improve WhatsApp** (add media support, button templates)

---

## Milestone 6: Scale & Production Hardening (Week 5-6)
**Goal**: Prepare for production: persistence, observability, security, horizontal scaling.

### Features
- **Database Migrations**
  - Use Alembic for schema versioning
  - Support zero-downtime migrations
  - Rollback capability

- **Vector Store Scaling**
  - Migrate FAISS to Pinecone or Milvus for distributed search
  - Implement multi-tenant namespace isolation

- **Session Persistence**
  - Redis for WebSocket session state (survives server restart)
  - Chat history sync across multiple app instances

- **Monitoring & Observability**
  - Structured logging (JSON format)
  - Prometheus metrics (request latency, queue depth, SLA breaches, agent availability)
  - Sentry for error tracking
  - Health checks: DB, vector store, message broker readiness

- **Security Hardening**
  - RBAC: admin, supervisor, agent, customer roles
  - Rate limiting per user/IP
  - API key rotation
  - SSL/TLS enforced in Docker Compose
  - Secrets manager integration (AWS Secrets Manager, HashiCorp Vault)

- **Backup & Disaster Recovery**
  - Daily SQLite exports to S3
  - Vector index snapshots
  - Restore runbook

### Database Schema Changes
```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT UNIQUE,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE agents ADD COLUMN role_permissions TEXT;  -- JSON: ["view_all_tickets", "manage_agents"]
```

### Infrastructure
```yaml
# docker-compose.yml additions
services:
  app:
    # ... existing config ...
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
  vector-db:  # Milvus or Pinecone
    image: milvusdb/milvus:latest
```

### Deployment Checklist
- [ ] SSL certificates (Let's Encrypt)
- [ ] Reverse proxy (Nginx)
- [ ] Database backup schedule
- [ ] Monitoring alerts (SLA breaches, errors, uptime)
- [ ] Load testing (concurrent agents, chats)
- [ ] Documentation (API, deployment, runbooks)

---

## Implementation Order & Dependencies

```
Milestone 1: Core Ticketing
    ↓ (needs agent model)
Milestone 2: Real-time Chat
    ↓ (needs routing logic)
Milestone 3: Multi-Agent Routing
    ↓ (needs dashboards)
Milestone 4: Agent Dashboards
    ↓ (enables multi-channel)
Milestone 5: Integrations
    ↓ (production prep)
Milestone 6: Scale & Hardening
```

## Effort Estimation
- Milestone 1: 40 hours (DB, APIs, basic UI)
- Milestone 2: 35 hours (WebSocket, real-time, presence)
- Milestone 3: 25 hours (routing algo, SLA tracking)
- Milestone 4: 20 hours (dashboards, macros)
- Milestone 5: 50 hours (multiple integrations, webhooks)
- Milestone 6: 30 hours (infra, monitoring, security)

**Total: ~200 hours** (5-6 weeks full-time or 3-4 months part-time)

---

## Quick Start: First Week Tasks
1. ✅ Database schema: agents, tickets enhancements, ticket_notes
2. ✅ API: GET /tickets, PATCH /tickets/{id}, POST /notes
3. ✅ UI: Agent dashboard, ticket list, detail view
4. ✅ WebSocket foundation: connection manager, basic event broadcasting

**Goal**: By end of Week 1, agents can see and update tickets in real-time with live chat.
