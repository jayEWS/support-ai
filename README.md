# 🚀 Edgeworks AI Support Portal

**Enterprise-grade AI customer support platform** powering Tier-1/Tier-2 POS technical support — built for Edgeworks Solutions Pte Ltd.

> 🌏 **Deployed on Singapore PC** — accessible by colleagues anywhere, anytime via Cloudflare Tunnel.  
> 💰 **$0/month running cost** — Groq AI (free), Neon PostgreSQL (free), Cloudflare Tunnel (free).

---

## ⚡ Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| **Runtime** | Python 3.11 + FastAPI | Free |
| **AI Engine** | Groq Llama-3.3 70B Versatile | Free (API) |
| **Database** | Neon Cloud PostgreSQL (Singapore region) | Free tier |
| **Vector DB** | Qdrant (local file-based) | Free |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` (local) | Free |
| **Search** | Hybrid RAG — BM25 + Vector + RRF Fusion | Free |
| **Auth** | Google OAuth 2.0 + JWT + MFA | Free |
| **Channels** | Web Portal, WhatsApp (Meta Cloud API) | Free |
| **Tunnel** | Cloudflare Tunnel (public HTTPS) | Free |
| **Hosting** | Singapore Office PC (Windows) | $0 |

---

## 🏗️ Architecture

```
Internet (Colleagues, Customers)
        │
        ▼
  Cloudflare Tunnel (HTTPS)
        │
        ▼
  Singapore PC (:8001)
  ┌─────────────────────────────────────────┐
  │  FastAPI + Uvicorn                      │
  │  ┌───────────────────────────────────┐  │
  │  │  Web Portal    Admin Dashboard    │  │
  │  │  WhatsApp WH   WebSocket Chat     │  │
  │  └────────────┬──────────────────────┘  │
  │               ▼                         │
  │  ┌──── Chat Service ────────────────┐   │
  │  │  Onboarding FSM                  │   │
  │  │  Intent Detection                │   │
  │  │  Input/Output Guardrails         │   │
  │  └────────────┬─────────────────────┘   │
  │               ▼                         │
  │  ┌──── RAG Pipeline (Multi-Query) ──┐   │
  │  │  Query Expansion                 │   │
  │  │  BM25 + Vector Search            │   │
  │  │  RRF Score Fusion                │   │
  │  │  Cross-Encoder Rerank (optional) │   │
  │  │  Confidence Calibration          │   │
  │  └────────────┬─────────────────────┘   │
  │               ▼                         │
  │  Groq API (Llama-3.3 70B)              │
  └─────────────────────────────────────────┘
        │                    │
        ▼                    ▼
  Neon PostgreSQL      Qdrant (Local)
  (Cloud - SG)         (File Storage)
```

---

## 📁 Project Structure

```
support-ai/
├── main.py                 # FastAPI app + auth routes + lifespan
├── app/
│   ├── core/               # Config, database, auth, middleware, Redis
│   ├── models/             # SQLAlchemy ORM models
│   ├── repositories/       # Data access layer (CRUD)
│   ├── routes/             # API routers (portal, tickets, knowledge, etc.)
│   ├── schemas/            # Pydantic request/response models
│   ├── services/           # Business logic: RAG, LLM, chat, escalation
│   ├── utils/              # Security, PII scrubbing, file handling
│   └── webhook/            # WhatsApp inbound handler
├── data/
│   ├── knowledge/          # Knowledge base documents (.pdf, .txt, .md)
│   ├── qdrant_storage/     # Qdrant vector index (auto-generated)
│   └── uploads/            # User file uploads
├── templates/              # HTML templates (portal, admin, login)
├── scripts/                # DB seeding & maintenance scripts
├── migrations/             # Alembic migration files
├── tests/                  # Test suite
├── DEPLOYMENT_SG_PC.md     # 📋 Step-by-step deployment guide
├── SECURITY_AUDIT_REPORT.md
└── NYALAKAN_SERVER.bat     # One-click server start (Windows)
```

---

## 🔑 Key Features

### 🤖 AI-Powered Support
- **Multi-Query RAG** — generates sub-queries for comprehensive document retrieval
- **Hybrid Search** — BM25 keyword + vector similarity + RRF score fusion
- **Auto-Escalation** — low-confidence answers routed to human agents
- **Self-Learning** — human corrections feed back into knowledge base

### 💬 Communication Channels
- **Web Portal** — customer-facing chat with AI agent
- **Admin Dashboard** — ticket management, live chat, analytics
- **WhatsApp** — Meta Cloud API integration (optional)

### 🔒 Security
- **Google OAuth 2.0** — SSO for all agents (`@edgeworks.com.sg`)
- **JWT + RBAC** — role-based access (Admin / Agent)
- **Input/Output Guardrails** — prompt injection detection, PII scrubbing
- **Rate Limiting** — per-endpoint + AI concurrency semaphore

### 📊 Operations
- **Ticket System** — create, assign, escalate, SLA monitoring
- **Knowledge Management** — upload PDF/TXT/MD, auto-index into RAG
- **Customer Database** — CRM with outlet, position, contact info
- **Audit Logs** — full trail of all agent/system actions

---

## 🚀 Quick Start (Development)

```powershell
# 1. Clone
git clone https://github.com/jayEWS/support-ai.git
cd support-ai

# 2. Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Create .env file (see .env.example or DEPLOYMENT_SG_PC.md)

# 5. Run server
uvicorn main:app --host 0.0.0.0 --port 8001

# 6. Open browser
# http://localhost:8001
```

---

## 🌐 Production Deployment

See **[DEPLOYMENT_SG_PC.md](DEPLOYMENT_SG_PC.md)** for the complete step-by-step guide to deploy on the Singapore PC with Cloudflare Tunnel.

**TL;DR:**
1. `git clone` on SG PC
2. Create `.env` with Neon DB + Groq API key
3. Install `cloudflared` and create tunnel
4. Double-click `NYALAKAN_SERVER.bat`
5. Colleagues access via `https://your-domain.trycloudflare.com`

---

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Neon PostgreSQL connection string |
| `GROQ_API_KEY` | ✅ | Groq API key (free from console.groq.com) |
| `LLM_PROVIDER` | ✅ | Set to `groq` |
| `MODEL_NAME` | ❌ | Default: `llama-3.3-70b-versatile` |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | ❌ | Default: `http://localhost:8001/api/auth/google/callback` |
| `AUTH_SECRET_KEY` | ❌ | Auto-generated if missing (set for production) |
| `PORT` | ❌ | Default: `8001` |

---

## 📞 Support & Maintenance

- **Sync from Indo PC**: `git push` → SG PC: `git pull` → restart server
- **Database**: Neon Cloud — zero maintenance, auto-backups
- **AI Model**: Groq free tier — 30 req/min, 14,400 req/day
- **Updates**: Edit `.env` to switch AI providers without code changes

---

## 📄 License

Proprietary — **Edgeworks Solutions Pte Ltd** © 2026
