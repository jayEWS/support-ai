# POS AI Support — RAG Architecture & Chat Flow

## System Overview

An AI-powered customer support platform for Edgeworks POS systems, built on **Retrieval-Augmented Generation (RAG)** with hybrid search. The system handles customer queries via web portal and WhatsApp, backed by a knowledge base of POS manuals, guides, and FAQs.

```
┌─────────────────────────────────────────────────────────────┐
│                     ENTRY POINTS                            │
│                                                             │
│   Web Portal (/conversation)     WhatsApp (Meta Cloud API)  │
│         │                                │                  │
│    POST /api/chat              POST /webhook/whatsapp       │
│         │                                │                  │
│         └──────────┬─────────────────────┘                  │
│                    ▼                                        │
│            ┌──────────────┐                                 │
│            │ ChatService  │  ← Orchestrator                 │
│            └──────┬───────┘                                 │
│                   │                                         │
│     ┌─────────────┼──────────────┐                          │
│     ▼             ▼              ▼                          │
│ Onboarding    RAG Query     Escalation                      │
│   Flow         Engine        Engine                         │
│                   │                                         │
│          ┌────────┼────────┐                                │
│          ▼        ▼        ▼                                │
│       BM25     FAISS     LLM                                │
│     (keyword) (vector) (generation)                         │
│          │        │        │                                │
│          └────┬───┘        │                                │
│               ▼            │                                │
│         RRF Fusion         │                                │
│          (merge)           │                                │
│               │            │                                │
│               └─────┬──────┘                                │
│                     ▼                                       │
│              AI Response                                    │
│                     │                                       │
│         ┌───────────┼───────────┐                           │
│         ▼           ▼           ▼                           │
│   Save to DB   Return to    Escalate if                     │
│                 Customer     needed                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Entry Points

### 1.1 Web Portal (`/conversation`)

| Component | Detail |
|-----------|--------|
| **Route** | `GET /` → `index.html` (SPA, client-side routing to `/conversation`) |
| **Chat API** | `POST /api/chat` — accepts JSON or multipart/form-data (file uploads) |
| **Close API** | `POST /api/close-session` — closes chat, optionally creates ticket |
| **WebSocket** | `WS /ws/portal/{user_id}` — real-time agent replies to customer |
| **Admin WS** | `WS /ws/portal/admin/{user_id}` — admin watches/replies to customer |
| **Rate Limit** | 5 requests/minute per IP |

**Request format:**
```json
{ "message": "how to close POS?", "user_id": "628123456789" }
```

**Response format:**
```json
{
  "answer": "To close your POS shift...",
  "confidence": 0.85,
  "customer_name": "John",
  "attachment": null,
  "onboarding": false
}
```

### 1.2 WhatsApp (Meta Cloud API)

| Component | Detail |
|-----------|--------|
| **Verify** | `GET /webhook/whatsapp` — Meta webhook verification (challenge/response) |
| **Inbound** | `POST /webhook/whatsapp` — receives messages, media, status updates |
| **Outbound** | `app.adapters.whatsapp_meta.send_whatsapp_message()` |
| **Rate Limit** | 30 requests/minute |
| **Read Receipts** | Auto-sends blue ticks via `mark_message_read()` |

**WhatsApp message flow:**
```
Meta Cloud API → POST /webhook/whatsapp
  → WhatsAppWebhookService.normalize_payload()
  → mark_message_read() (blue ticks)
  → save_whatsapp_message() to DB
  → get_or_register_customer()
  → ChatService onboarding check
  → IntentService.classify() → routing
  → RAG query or escalation
  → send_whatsapp_message() back to customer
```

---

## 2. Onboarding Flow (Multi-Language)

First-time users go through a conversational onboarding before accessing AI support.

```
User sends first message
        │
        ▼
  ┌──────────────┐
  │ Detect Lang  │ ← from message content
  │ from message │
  └──────┬───────┘
         │
    ┌────┴─────┐
    │ Clear?   │
    └────┬─────┘
    yes  │  no
    │    │
    │    ▼
    │  Ask: "Select language 1/2/3"
    │    │
    │    ▼
    │  User replies (1=ID, 2=EN, 3=ZH)
    │    │
    ├────┘
    ▼
  Ask: "What is your name?"
    │
    ▼
  Ask: "What is your company/outlet?"
    │
    ▼
  State = 'complete'
  "Welcome! How can I help?"
```

**States tracked in DB (`Users.state` column):**

| State | Description |
|-------|-------------|
| `new` | Never seen before — detect language |
| `asking_language` | Waiting for 1/2/3 selection |
| `asking_name` | Waiting for name input |
| `asking_company` | Waiting for company/outlet name |
| `complete` | Onboarded — proceed to RAG |

**Supported languages:**
- 🇮🇩 Bahasa Indonesia (`id`)
- 🇬🇧 English (`en`)
- 🇨🇳 Chinese / 中文 (`zh`)

**Language detection:** Keyword matching + Chinese character detection. Users can switch language mid-conversation (e.g., "can I use English?").

---

## 3. RAG Pipeline — Core AI Engine

### 3.1 Architecture

Two RAG implementations exist for different purposes:

| Component | `RAGService` | `RAGEngine` |
|-----------|-------------|-------------|
| **Purpose** | Portal chat queries | Admin KB management + WhatsApp queries |
| **Used by** | `ChatService.process_portal_message()` | Admin upload/delete/ingest APIs |
| **Search** | Hybrid (BM25 40% + Vector 60%) | Hybrid (RRF fusion) |
| **Prompt** | Dynamic confidence-based | Fixed `SUPPORT_PROMPT_TEMPLATE` |
| **Security** | Via ChatService | Built-in PII masking + jailbreak detection |

### 3.2 Knowledge Base

**Storage:** `data/knowledge/` directory (local filesystem)

**Document types supported:**
| Format | Loader |
|--------|--------|
| `.pdf` | `PyPDFLoader` |
| `.docx` | `Docx2txtLoader` |
| `.csv` | `CSVLoader` |
| `.txt`, `.md`, `.json`, `.log` | `TextLoader` (UTF-8) |
| URL | `WebBaseLoader` |

**Current knowledge base:** ~40 files including POS manuals (V3/V5), inventory guides, FAQ documents, KDS setup, retail/resto/wholesale user guides, promotion guides, and more.

**Metadata tracked per document:**
- `filename` — original file name
- `upload_date` — when uploaded (from `KnowledgeMetadata` table)
- `status` — "Indexed", "Processing", "Error: ..."
- `source_url` — if ingested from URL

### 3.3 Indexing Pipeline

```
File uploaded (or URL ingested)
        │
        ▼
  ┌──────────────────┐
  │ Document Loader  │ ← PDF/DOCX/CSV/TXT/URL
  └──────┬───────────┘
         │
         ▼
  ┌──────────────────────────────┐
  │ RecursiveCharacterTextSplitter│
  │ chunk_size=1000              │
  │ chunk_overlap=200            │
  └──────┬───────────────────────┘
         │
         ▼
  ┌──────────────────┐
  │ Metadata Enrich  │ ← filename, upload_date
  └──────┬───────────┘
         │
    ┌────┴────┐
    ▼         ▼
  FAISS     BM25
  Index    Tokenize
    │         │
    ▼         ▼
  Save to   In-memory
  disk      retriever
```

**Chunking strategy:**
- Chunk size: **1,000 characters**
- Overlap: **200 characters** (ensures context continuity at chunk boundaries)
- Splitter: `RecursiveCharacterTextSplitter` (splits on `\n\n` → `\n` → ` ` → `""`)

### 3.4 Embedding Models

Configurable via `EMBEDDINGS_TYPE` env var:

| Provider | Model | Dimension | Use Case |
|----------|-------|-----------|----------|
| **Vertex AI** (default) | `text-embedding-005` | 768 | Production (GCP) |
| OpenAI | configurable | 1536 | Alternative |
| HuggingFace | `all-MiniLM-L6-v2` | 384 | Local/offline fallback |

### 3.5 Retrieval — Hybrid Search

**Step 1: BM25 Keyword Search (40% weight)**
```
Query → tokenize → BM25Okapi.get_scores() → top-K by score
```
- Exact keyword matching
- Good for: product names, error codes, specific terms
- Library: `rank_bm25.BM25Okapi`

**Step 2: FAISS Vector Search (60% weight)**
```
Query → embed → FAISS.similarity_search() → top-K by cosine similarity
```
- Semantic meaning matching
- Good for: paraphrased questions, conceptual queries
- Library: `langchain_community.vectorstores.FAISS`

**Step 3: Reciprocal Rank Fusion (RRF)**
```python
# For each document appearing in either result list:
score = Σ (1 / (rank + k))    # k=60 (smoothing constant)

# BM25 results contribute 40% weight
# Vector results contribute 60% weight
# Documents appearing in BOTH lists get boosted
```

```
  BM25 Results          Vector Results
  ┌──────────┐          ┌──────────┐
  │ Doc A (1)│          │ Doc C (1)│
  │ Doc B (2)│          │ Doc A (2)│  ← Doc A in both!
  │ Doc D (3)│          │ Doc E (3)│
  └──────────┘          └──────────┘
        │                     │
        └──────┬──────────────┘
               ▼
         RRF Merge
        ┌──────────┐
        │ Doc A ★★ │  ← boosted (in both lists)
        │ Doc C ★  │
        │ Doc B    │
        │ Doc E    │
        │ Doc D    │
        └──────────┘
```

### 3.6 Confidence Scoring

```python
confidence = |query_words ∩ context_words| / |query_words|
```

Word-overlap based (simple but effective). Determines prompt strategy:

| Confidence | Strategy |
|------------|----------|
| ≥ 0.5 | **Grounded prompt** — "Answer based ONLY on documents" |
| < 0.5 | **General prompt** — "Try context, fall back to general knowledge" |
| < 0.05 | **Bail out** — "Information not found, connecting you with specialist" |

### 3.7 LLM Generation

**Provider chain (with automatic fallback):**
```
Vertex AI (Gemini 2.5 Flash)
    ↓ fails
Google Gemini API
    ↓ fails
Groq (Llama/Mixtral)
    ↓ fails
Ollama (local)
    ↓ fails
OpenAI (GPT)
```

Configured via `LLM_PROVIDER` env var. Temperature: `0.1` (deterministic).

**Prompt template structure:**
```
System: You are a friendly Edgeworks technical support assistant.

Document Context (with upload dates):
--- SOURCE: closing_v5.txt | UPLOADED: 2026-02-01 ---
[chunk content]

--- SOURCE: Equip_FAQ.txt | UPLOADED: 2026-01-15 ---
[chunk content]

Question: {user_question}

Instructions:
1. Use ONLY information from documents
2. Answer in {user_language}
3. Use bullet points / numbered steps
4. Mention source file name
5. If info not found, offer to connect with team
```

**Version awareness:** Documents include upload dates so the LLM prioritizes the **latest version** when conflicting information exists.

---

## 4. Post-RAG Processing

### 4.1 Greeting Detection (Short-circuit)

Messages like "hi", "hello", "halo" bypass retrieval entirely:
```
Short message + greeting keyword detected
    → Direct LLM response (no document search)
    → "Hello! I'm the Edgeworks AI assistant. How can I help?"
```

### 4.2 Recurring Issue Detection

On the **first message** of each session:
```
Query keywords ← current message
Past tickets   ← last 10 tickets for this user

if keyword_overlap ≥ 2:
    prepend "📋 Similar issue found in Ticket #42..."
```

### 4.3 Escalation Detection

AI responses are scanned for escalation trigger phrases:
```python
triggers = [
    "hubungkan dengan tim",
    "menghubungkan anda dengan spesialis",
    "hubungkan dengan spesialis",
    "tim yang bisa bantu"
]
```

If triggered:
```
Create support ticket
    │
    ├── Agent available? → Create live chat session
    │                       → WebSocket connection
    │                       → response: { live_session_started: true }
    │
    └── No agent? → Add to ticket queue
                    → response: { status: "queued" }
```

### 4.4 Language-Aware Responses

The LLM receives language-specific instructions:
- `id` → "Jawab dalam Bahasa Indonesia. Gunakan nada santai tapi profesional."
- `en` → "Answer in English. Use a friendly and professional tone."
- `zh` → "请用中文回答。使用友好且专业的语气。"

Language is auto-detected from message content and can be switched mid-conversation.

---

## 5. Chat Session Lifecycle

```
┌──────────────────────────────────────────────────┐
│                 CHAT LIFECYCLE                    │
│                                                  │
│  New User ──→ Onboarding ──→ AI Conversation     │
│                                    │              │
│                              ┌─────┴─────┐       │
│                              ▼           ▼       │
│                          Resolved    Unresolved   │
│                              │           │       │
│                              ▼           ▼       │
│                       Close Chat    Create Ticket │
│                       (option=      (option=      │
│                        "close")     "ticket")     │
│                              │           │       │
│                              ▼           ▼       │
│                        LLM Summary   LLM Summary  │
│                        + closed      + priority    │
│                        ticket        + SLA due     │
│                              │      + email notify │
│                              │           │        │
│                              └─────┬─────┘        │
│                                    ▼              │
│                            Clear messages         │
│                            (fresh start)          │
└──────────────────────────────────────────────────┘
```

### Close Options

| Option | Behavior |
|--------|----------|
| `close` | AI resolved. LLM summarizes → creates **closed** ticket for history → clears messages |
| `ticket` | Unresolved. LLM summarizes + determines priority/category → creates **open** ticket with SLA deadline |
| `ticket_and_notify` | Same as `ticket` + sends ticket details to user + email notification to support team |

**SLA due dates (from `SLARules` table):**

| Priority | Default Resolution Time |
|----------|------------------------|
| Urgent | 1 hour |
| High | 4 hours |
| Medium | 24 hours |
| Low | 48 hours |

---

## 6. Security Layer

### 6.1 PII Masking (Pre-RAG)

Applied before sending to LLM:
```
Email:  user@email.com     → [EMAIL_MASKED]
Phone:  +6281234567890     → [PHONE_MASKED]
Card:   4111111111111111   → [CARD_MASKED]
```

### 6.2 Jailbreak Detection

Blocked patterns:
- "ignore all previous instructions"
- "system prompt"
- "developer mode"

Response: `"Sorry, our system detected an unauthorized activity."`

### 6.3 Input Sanitization

All AI responses pass through surrogate character stripping to prevent UTF-8 encoding errors:
```python
text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
```

---

## 7. Real-Time Communication (WebSocket)

### 7.1 Portal WebSocket

```
Customer Browser                      Admin Dashboard
      │                                     │
  WS /ws/portal/{user_id}          WS /ws/portal/admin/{user_id}
      │                                     │
      └──────── PortalManager ──────────────┘
                     │
              ┌──────┴──────┐
              │  Message    │
              │  Broadcast  │
              └─────────────┘
```

**Events:**
| Event | Direction | Purpose |
|-------|-----------|---------|
| `message` | Customer → Admin | Customer sends message |
| `message` | Admin → Customer | Agent replies |
| `typing` | Customer → Admin | Typing indicator |

### 7.2 Live Chat WebSocket

```
WS /ws/chat/{session_id}?user_id=X&user_type=agent|customer
```

For escalated sessions — both agent and customer connect to the same session. Messages broadcast to all participants.

---

## 8. Data Flow Diagram

```
                    ┌─────────────┐
                    │  Knowledge  │
                    │    Files    │
                    │ (PDF/TXT/  │
                    │  DOCX/CSV) │
                    └──────┬──────┘
                           │ upload/ingest
                           ▼
                    ┌──────────────┐
                    │  RAGEngine   │
                    │ (indexing)   │
                    └──────┬───────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐ ┌──────────┐
              │  FAISS   │ │   BM25   │
              │  Index   │ │  Index   │
              │ (disk)   │ │ (memory) │
              └──────────┘ └──────────┘
                    │             │
                    └──────┬──────┘
                           │ query time
                           ▼
User ──→ ChatService ──→ RAGService
              │              │
              │         Hybrid Search
              │         + RRF Fusion
              │         + LLM Generation
              │              │
              │              ▼
              │         AI Response
              │              │
              ├──── Save to PortalMessages
              ├──── Save to WhatsAppMessages (if WA)
              ├──── Check escalation triggers
              └──── Return to user
                         │
                    ┌────┴────┐
                    ▼         ▼
              Web Portal  WhatsApp
              (JSON)     (Meta API)
```

---

## 9. Database Tables (Chat-Related)

| Table | Purpose |
|-------|---------|
| `Users` | Customer profiles (name, company, language, onboarding state) |
| `PortalMessages` | Chat history (user_id, role, content, attachments, timestamp) |
| `WhatsAppMessages` | WhatsApp message log (phone, direction, content, external_id) |
| `Tickets` | Support tickets (summary, priority, status, due_at, assigned_agent) |
| `ChatSessions` | Live chat sessions (ticket_id, agent_id, customer_id) |
| `ChatMessages` | Live chat messages within sessions |
| `KnowledgeMetadata` | KB file tracking (filename, upload_date, status, source_url) |
| `AIInteractionLogs` | AI observability (tokens, confidence, latency, escalation flag) |
| `SLARules` | SLA configuration per priority level |
| `TicketQueue` | Queued tickets waiting for agent assignment |

---

## 10. Intent Classification (WhatsApp)

WhatsApp messages go through LLM-based intent classification before processing:

| Intent | Description | Action |
|--------|-------------|--------|
| `simple` | General questions, greetings | RAG query |
| `deep_reasoning` | Complex technical issues | RAG query (detailed) |
| `escalation` | User asks for human agent | Create ticket + assign agent |
| `ticket_update` | Status inquiry on existing ticket | Lookup ticket |
| `critical` | System failure, security, business loss | Urgent ticket + alert |

---

## 11. Observability

### AI Interaction Logging
Every AI query logs:
- `tokens_used` — LLM token consumption
- `confidence_score` — retrieval confidence
- `escalation_flag` — whether escalated
- `latency_ms` — end-to-end response time
- `model_used` — which LLM provider answered

### Langfuse Integration (Optional)
If `LANGFUSE_PUBLIC_KEY` is set, traces are sent to Langfuse for:
- Query analysis
- Retrieval quality monitoring
- Response quality tracking

### Application Logging
Structured logging with `LogLatency` context manager for performance tracking of:
- `chat_service.process_portal_message`
- `rag_service.query`
- `intent_service.classify`

---

## 12. Infrastructure

| Component | Technology |
|-----------|------------|
| **Runtime** | Python 3.11 + FastAPI + Gunicorn (Uvicorn worker) |
| **Database** | Neon PostgreSQL 17.8 (Singapore, free tier) |
| **Vector Store** | FAISS (local disk at `data/db_storage/`) |
| **Embeddings** | Vertex AI `text-embedding-005` |
| **LLM** | Vertex AI Gemini 2.5 Flash (with Groq/OpenAI fallback) |
| **Deployment** | GCP VM (`asia-southeast1`) + Docker |
| **WhatsApp** | Meta Cloud API (direct integration) |
| **File Storage** | Local filesystem (GCS optional) |
| **Rate Limiting** | SlowAPI (in-memory) |

---

## 13. Configuration Reference

| Env Variable | Purpose | Default |
|-------------|---------|---------|
| `LLM_PROVIDER` | LLM provider selection | `vertex` |
| `EMBEDDINGS_TYPE` | Embedding model provider | `vertex` |
| `GCP_PROJECT_ID` | Google Cloud project | — |
| `VERTEX_AI_MODEL` | LLM model name | `gemini-2.5-flash` |
| `VERTEX_AI_EMBEDDINGS_MODEL` | Embedding model | `text-embedding-005` |
| `VERTEX_AI_LOCATION` | GCP region | `asia-southeast1` |
| `GOOGLE_GEMINI_API_KEY` | Gemini API key (fallback) | — |
| `GROQ_API_KEY` | Groq API key (fallback) | — |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | — |
| `DATABASE_URL` | PostgreSQL connection string | — |
| `WHATSAPP_TOKEN` | Meta WhatsApp access token | — |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token | — |
| `WHATSAPP_PHONE_ID` | WhatsApp phone number ID | — |
| `LANGFUSE_PUBLIC_KEY` | Langfuse observability (optional) | — |
| `TEMPERATURE` | LLM temperature | `0.1` |

---

*Architecture document for POS AI Support RAG system. Last updated: March 2026.*
