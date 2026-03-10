# Edgeworks AI Support Portal - AI Developer Instructions

Welcome to the Edgeworks AI Support Portal! This is a high-performance, Multi-Tenant SaaS platform providing Tier-1/Tier-2 POS technical support using a Hybrid RAG pipeline, WebSockets, and AI Agents.

## 🏛 Big Picture & Architecture
- **Framework & Runtime:** FastAPI (Python 3.11). Deployed via Docker + Gunicorn (Uvicorn workers).
- **Relational DB:** SQL Server / PostgreSQL managed via **SQLAlchemy (ORM)** and **Alembic** for migrations.
- **AI Core:** Vertex AI / OpenAI coupled with a local **FAISS** vector database. We use a **Hybrid RAG Engine** (FAISS + BM25 exact matching + Cross-Encoder reranking) for highly accurate context injection.
- **Real-Time Comms:** WebSockets combined with Redis. Redis clustering is strictly enforced for horizontal scaling if workers > 1.
- **Tenancy:** Omnichannel system. Always ensure all database queries and interactions strictly scope data to the current tenant to prevent IDOR vulnerabilities.

## 💻 Developer Workflows & Commands
- **Database Migrations:** Never use raw `metadata.create_all()`. Always use **Alembic**.
  - Generate: `alembic revision --autogenerate -m "description"`
  - Apply: `alembic upgrade head`
- **Starting the Server:** Primarily run via `docker-compose up` (or `docker-compose -f docker-compose.prod.yml` for prod). For local testing, use a standard `uvicorn main:app --reload` with `.venv` activated.
- **Testing:** Tests are located in `tests/` (e.g., `test_rag.py`, `stress_test.py`). Use `pytest` for running suites.

## ⚙️ Core Conventions & Defensive Patterns
- **Non-Blocking Async DB Calls:** Because SQLAlchemy calls can be synchronous and block FastAPI's event loop, wrap critical DB paths in the `run_sync` wrapper (`app.utils.async_db.run_sync`).
  - *Example Pattern:* `await run_sync(sync_db_function, session, arg1)`
- **Active PII Scrubbing:** Before *any* AI transcript is persisted to the database (e.g., `AIInteraction` table), it MUST pass through `app/utils/pii_scrubber.py` to redact sensitive info (CCs, NRICs, phone numbers).
- **Concurrency Guards:** We use `AI_SEMAPHORE = asyncio.Semaphore(10)` (in `main.py`) to gate simultaneous AI calls to prevent Vertex AI quota exhaustion under heavy load. Use similarly strict rate limits (`slowapi`) and semaphores for external integrations.

## 📁 Key Directories
- `app/core/`: Engine room (database connection, config, auth dependencies, middleware).
- `app/services/`: Deep business logic, RAG pipelines (`advanced_retriever.py`), AI interactions (`llm_service.py`), and guardrails.
- `app/repositories/`: Data Access Interfaces handling CRUD boundaries. Keeps `routes/` clean.
- `app/routes/`: FastAPI routers separating `portal_routes.py` (web frontend), `system_routes.py`, and `websocket_routes.py`.
