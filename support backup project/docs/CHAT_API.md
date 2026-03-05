# Real-time Chat API Documentation

## Overview
The Support Portal AI now includes real-time chat capabilities powered by WebSocket. Agents and customers can communicate with instant message delivery, typing indicators, and read receipts.

## REST API Endpoints

### Chat Sessions

#### Create Chat Session
```http
POST /api/chat-sessions
Content-Type: application/json

{
  "ticket_id": 1,
  "customer_id": "web_portal_user",
  "agent_id": "optional_agent_id"
}
```

**Response:**
```json
{
  "session_id": 123,
  "agent_id": "agent_john"
}
```

**Notes:**
- If `agent_id` is omitted, the system automatically assigns the least-busy available agent.
- Returns 503 if no agents are available.

---

#### Get Chat Session
```http
GET /api/chat-sessions/{session_id}
```

**Response:**
```json
{
  "id": 123,
  "ticket_id": 1,
  "agent_id": "agent_john",
  "customer_id": "web_portal_user",
  "started_at": "2026-02-26T23:30:00.000Z",
  "ended_at": null
}
```

---

#### Get Chat History
```http
GET /api/chat-sessions/{session_id}/messages?limit=50
```

**Response:**
```json
{
  "session_id": 123,
  "messages": [
    {
      "id": 1,
      "session_id": 123,
      "sender_id": "web_portal_user",
      "sender_type": "customer",
      "content": "Hello, I need help with my account",
      "attachment_url": null,
      "sent_at": "2026-02-26T23:30:15.000Z",
      "read_at": "2026-02-26T23:30:20.000Z"
    },
    {
      "id": 2,
      "session_id": 123,
      "sender_id": "agent_john",
      "sender_type": "agent",
      "content": "Hi! I'm happy to assist. What's the issue?",
      "attachment_url": null,
      "sent_at": "2026-02-26T23:30:25.000Z",
      "read_at": null
    }
  ]
}
```

---

#### Close Chat Session
```http
POST /api/chat-sessions/{session_id}/close
```

**Response:**
```json
{
  "status": "closed"
}
```

**Notes:**
- Automatically decrements agent's active chat count.
- Updates agent status to "available" if no other active chats.

---

### Agent Management

#### Get All Agents
```http
GET /api/agents
X-API-Key: your_api_key
```

**Response:**
```json
{
  "agents": [
    {
      "id": 1,
      "user_id": "agent_john",
      "name": "John Smith",
      "email": "john@company.com",
      "role": "agent",
      "skills": "[\"billing\", \"technical\"]",
      "availability_status": "available",
      "max_concurrent_chats": 5,
      "active_chat_count": 2,
      "last_activity_at": "2026-02-26T23:30:00.000Z"
    }
  ]
}
```

---

#### Get Available Agents
```http
GET /api/agents/available
```

**Response:**
```json
{
  "agents": [
    {
      "user_id": "agent_john",
      "name": "John Smith",
      "availability_status": "available",
      "active_chat_count": 2,
      "max_concurrent_chats": 5
    }
  ]
}
```

**Notes:**
- Returns agents with status "available" and active chat count below their max.
- Sorted by least busy first.

---

#### Update Agent Presence
```http
PATCH /api/agents/{agent_id}/presence
X-API-Key: your_api_key
Content-Type: application/json

{
  "status": "available"
}
```

**Valid Status Values:**
- `available` — Agent is ready to accept chats
- `busy` — Agent is in a chat or meeting
- `in_meeting` — Agent is in a meeting
- `offline` — Agent is not working

**Response:**
```json
{
  "status": "updated",
  "agent_id": "agent_john",
  "presence": "available"
}
```

**Notes:**
- Broadcasts presence update to all active chat sessions.
- Automatically managed when agent chats increase/decrease.

---

## WebSocket API

### Connect to Chat
```
WS /ws/chat/{session_id}?user_id={user_id}&user_type={user_type}

user_type: "agent" or "customer"
```

**Example JavaScript:**
```javascript
const ws = new WebSocket(
  `ws://localhost:8000/ws/chat/123?user_id=customer_1&user_type=customer`
);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message);
};
```

---

### WebSocket Events

#### Connection Established
```json
{
  "event": "session_started",
  "session_id": 123,
  "agent_id": "agent_john",
  "customer_id": "customer_1",
  "participants": {
    "agent_id": "agent_john",
    "customer_id": "customer_1"
  }
}
```

---

#### Send Message
**Client sends:**
```json
{
  "event": "message",
  "content": "How can I reset my password?",
  "attachment_url": null
}
```

**Server broadcasts to all participants:**
```json
{
  "event": "message",
  "message_id": 42,
  "sender_id": "customer_1",
  "sender_type": "customer",
  "content": "How can I reset my password?",
  "attachment_url": null,
  "sent_at": "2026-02-26T23:30:15.000Z"
}
```

---

#### Typing Start
**Client sends:**
```json
{
  "event": "typing_start",
  "name": "John"
}
```

**Server broadcasts:**
```json
{
  "event": "typing_start",
  "user_id": "customer_1",
  "user_name": "John",
  "timestamp": null
}
```

**UI Behavior:** Display "John is typing..." indicator

---

#### Typing Stop
**Client sends:**
```json
{
  "event": "typing_stop"
}
```

**Server broadcasts:**
```json
{
  "event": "typing_stop",
  "user_id": "customer_1",
  "timestamp": null
}
```

**UI Behavior:** Hide typing indicator

---

#### Message Read Receipt
**Client sends:**
```json
{
  "event": "message_read",
  "message_id": 42
}
```

**Server broadcasts:**
```json
{
  "event": "message_read",
  "message_id": 42,
  "read_at": "2026-02-26T23:30:20.000Z"
}
```

**UI Behavior:** Show "✓✓" (read indicator) next to message

---

#### Presence Update (Broadcast only)
```json
{
  "event": "presence_update",
  "agent_id": "agent_john",
  "status": "available",
  "active_chat_count": 2,
  "timestamp": null
}
```

**UI Behavior:** Update agent status badge (green dot for available, red for offline)

---

#### User Joined
```json
{
  "event": "user_joined",
  "user_id": "customer_1",
  "user_type": "customer",
  "timestamp": null
}
```

---

## Usage Examples

### Python Client Example

```python
import asyncio
import websockets
import json

async def chat_example():
    # 1. Create session
    import requests
    resp = requests.post("http://localhost:8000/api/chat-sessions", json={
        "ticket_id": 1,
        "customer_id": "python_client"
    })
    session_id = resp.json()["session_id"]
    
    # 2. Connect WebSocket
    async with websockets.connect(
        f"ws://localhost:8000/ws/chat/{session_id}?user_id=python_client&user_type=customer"
    ) as ws:
        # 3. Send message
        await ws.send(json.dumps({
            "event": "message",
            "content": "Hello, I need help!"
        }))
        
        # 4. Listen for responses
        async for message in ws:
            data = json.loads(message)
            print(f"Received: {data}")
            
            if data.get("event") == "message" and data.get("sender_type") == "agent":
                # Mark as read
                await ws.send(json.dumps({
                    "event": "message_read",
                    "message_id": data["message_id"]
                }))

asyncio.run(chat_example())
```

### JavaScript Client Example (Frontend)

```javascript
// Demo available at /chat endpoint
// See templates/chat.html for complete implementation
```

---

## Database Schema

### Chat Sessions Table
```sql
CREATE TABLE chat_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id INTEGER,
  agent_id TEXT,
  customer_id TEXT,
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME,
  FOREIGN KEY (ticket_id) REFERENCES tickets(id),
  FOREIGN KEY (agent_id) REFERENCES agents(user_id)
);
```

### Chat Messages Table
```sql
CREATE TABLE chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER,
  sender_id TEXT,
  sender_type TEXT,  -- 'customer' or 'agent'
  content TEXT,
  attachment_url TEXT,
  sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  read_at DATETIME,
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
```

### Agents Table
```sql
CREATE TABLE agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT UNIQUE,
  name TEXT,
  email TEXT,
  role TEXT DEFAULT 'agent',  -- 'agent', 'supervisor', 'admin'
  skills TEXT,  -- JSON array
  availability_status TEXT DEFAULT 'available',
  max_concurrent_chats INTEGER DEFAULT 5,
  last_activity_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Agent Presence Table
```sql
CREATE TABLE agent_presence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT UNIQUE,
  status TEXT DEFAULT 'available',
  active_chat_count INTEGER DEFAULT 0,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (agent_id) REFERENCES agents(user_id)
);
```

---

## Error Handling

### Common Errors

#### Session Not Found (404)
```json
{
  "error": "Session not found"
}
```

#### No Agents Available (503)
```json
{
  "error": "No agents available"
}
```

#### WebSocket Disconnection (Code 1008)
- **Session not found**: `reason: "Session not found"`
- Connection closed cleanly, client may reconnect

---

## Performance & Scaling Notes

### Connection Management
- Each WebSocket connection holds in-memory reference in `ConnectionManager`
- Graceful cleanup on disconnect
- Scales to ~1000s of concurrent connections per instance

### Message Persistence
- All messages stored in SQLite `chat_messages` table
- Read receipts tracked in `read_at` column
- Query history anytime for audit/analytics

### Agent Presence
- In-memory tracking in `ConnectionManager`
- Persisted in `agent_presence` table
- Broadcast to all active sessions (slight latency acceptable for UX)

### Recommended Production Setup
- Deploy with Redis for distributed session state (across multiple app instances)
- Use message queue (RabbitMQ, Redis Streams) for scaling WebSocket broadcasts
- Implement rate limiting on message endpoints
- Set idle timeout on WebSocket connections (e.g., 5 minutes)

---

## Testing

### Test Connection
```bash
# Start app
python main.py

# Open browser
http://localhost:8000/chat

# Or use curl + websocat
# websocat ws://localhost:8000/ws/chat/1?user_id=test_user&user_type=customer
```

### Load Testing
```bash
# Example with Apache Bench for REST endpoints
ab -n 100 -c 10 http://localhost:8000/api/agents/available

# WebSocket load testing requires specialized tools (e.g., k6, Artillery)
```

---

## Roadmap

**Completed (Milestone 2):**
- ✅ WebSocket real-time messaging
- ✅ Typing indicators
- ✅ Read receipts
- ✅ Agent presence tracking
- ✅ Automatic agent assignment

**Next (Milestone 3):**
- Multi-agent routing with SLA
- Queue management
- Escalations & supervisor handoff

**Coming (Milestone 4+):**
- Canned responses / macros
- Chat transcripts & export
- Voice/video call integration
- AI-powered chat suggestions
