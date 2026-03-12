# Edgeworks AI Support Portal

Multi-tenant SaaS platform providing Tier-1/Tier-2 POS technical support using a Hybrid RAG pipeline, WebSockets, and AI Agents.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Runtime** | Python 3.11 |
| **Framework** | FastAPI 0.111 + Gunicorn/Uvicorn |
| **Database** | SQL Server 2025 (prod) via SQLAlchemy 2.0 + Alembic |
| **Vector DB** | Qdrant (self-hosted) |
| **LLM** | Vertex AI / Gemini / Groq / OpenAI (fallback chain) |
| **Embeddings** | Vertex AI `text-embedding-005` / HuggingFace `all-MiniLM-L6-v2` |
| **Reranker** | Cross-Encoder `ms-marco-MiniLM-L-6-v2` |
| **Search** | Hybrid — BM25 (Okapi) + Vector Similarity + RRF Score Fusion |
| **Cache** | Redis (session, WS pub/sub, rate-limit) |
| **Real-Time** | WebSockets + Redis Pub/Sub |
| **Auth** | JWT + RBAC + MFA (TOTP) |
| **Observability** | Prometheus + structured JSON logging |
| **Channels** | Web Portal, WhatsApp (Meta Cloud API) |
| **Deployment** | GCP VM (`asia-southeast1`) + systemd + Nginx |

## Architecture

```
Customer ──► Nginx (443) ──► Gunicorn :8001 ──► FastAPI
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼              ▼
              WebSocket      REST API      WhatsApp Webhook
                    │             │              │
                    └─────────────┼──────────────┘
                                  ▼
                         ┌─── Chat Service ───┐
                         │  Onboarding FSM    │
                         │  Intent Detection  │
                         │  Guardrail I/O     │
                         └────────┬───────────┘
                                  ▼
                    ┌──── RAG Pipeline ────────┐
                    │  Query Expansion         │
                    │  BM25 + Vector Search    │
                    │  RRF Score Fusion        │
                    │  Cross-Encoder Rerank    │
                    │  Parent-Doc Enrichment   │
                    │  Confidence Calibration  │
                    │  RFF (Feedback Boost)    │
                    └────────┬────────────────┘
                             ▼
                    LLM (Vertex/Gemini/Groq/OpenAI)
                             │
                    ┌────────▼────────────────┐
                    │  PII Scrubbing          │
                    │  Output Guardrails      │
                    │  Self-Learning Logger   │
                    └─────────────────────────┘
```

## RAG Pipeline (Hybrid Retrieval)

1. **Multi-Query Retrieval** — Original + expanded + HyDE + sub-queries
2. **BM25 Okapi** — Stopword-filtered keyword matching
3. **Vector Search** — Qdrant cosine similarity (768d embeddings)
4. **Reciprocal Rank Fusion** — Weighted score merging across methods
5. **Cross-Encoder Reranking** — `ms-marco-MiniLM-L-6-v2` (optional, env-gated)
6. **Parent-Doc Enrichment** — Adjacent chunk merging for context continuity
7. **RFF Boost** — User feedback (👍/👎) adjusts future chunk rankings
8. **Confidence Calibration** — 6-signal scoring (rerank, coverage, gap, diversity, RFF)

## Key Directories

```
app/
├── core/          Config, DB engine, auth, middleware, Redis, state machine
├── middleware/     Tenant isolation, plan enforcement, usage metering
├── models/         SQLAlchemy ORM models (multi-tenant)
├── repositories/   Data access layer (CRUD, tenant-scoped)
├── routes/         FastAPI routers (portal, system, WS, tickets, KB)
├── schemas/        Pydantic request/response schemas
├── services/       Business logic: RAG, LLM, chat, escalation, guardrails
├── utils/          PII scrubber, file handler, security helpers
└── webhook/        WhatsApp inbound handler
```

## Quick Start

```bash
# 1. Clone & venv
git clone https://github.com/jayEWS/support-ai.git
cd support-ai
python -m venv .venv && source .venv/bin/activate

# 2. Install deps
pip install -r requirements.txt

# 3. Configure
cp .env.example .env   # Edit with your DB, LLM keys, Redis URL

# 4. Migrate DB
alembic upgrade head

# 5. Run
uvicorn main:app --reload --port 8001
```

## Production Deployment (GCP VM)

See [DEPLOYMENT_GCP_VM.md](DEPLOYMENT_GCP_VM.md) for full guide.

```bash
# Service management
sudo systemctl restart support-ai
sudo systemctl status support-ai
journalctl -u support-ai -f
```

## Security Features

- **Multi-Tenant Isolation** — All queries scoped by `tenant_id` via `TenantContext`
- **Input/Output Guardrails** — Blocks prompt injection, PII leakage, off-topic abuse
- **PII Scrubbing** — CC numbers, NRICs, phone numbers redacted before DB persistence
- **RBAC** — Role-based access (Super Admin → Admin → Agent → Viewer)
- **Rate Limiting** — SlowAPI per-endpoint + AI Semaphore (max 10 concurrent LLM calls)
- **WhatsApp Signature Validation** — Fail-closed HMAC-SHA256 verification

## License

Proprietary — Edgeworks Solutions Pte Ltd
