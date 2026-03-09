# MASTER SYSTEM AUDIT REPORT
**Date:** 2026-03-09
**Auditor:** Gemini CLI (Master System Auditor)
**Target:** `support-portal-edgeworks`

## EXECUTIVE SUMMARY
The system is a sophisticated FastAPI-based support portal with RAG capabilities, featuring a clean Layered Architecture. However, **critical deployment blockers** and **multi-tenancy risks** were identified.

**Verdict:** ⚠️ **HIGH RISK** (Due to deployment failure & tenant isolation gaps)

### 🚨 CRITICAL ACTIONS (P0)
1.  **Deployment Failure:** The `Dockerfile` is missing the `msodbcsql18` driver required for SQL Server connection. **Deployment will fail immediately.**
2.  **Multi-Tenant Leak:** The `TenantMiddleware` falls back to a default tenant (`'default'`) if resolution fails. In a production SaaS environment, this defaults unauthenticated or malformed requests to a shared bucket, potentially leaking "default" data.

---

## DETAILED FINDINGS (19-PHASE AUDIT)

### PHASE 1: SYSTEM DISCOVERY
*   **Stack:** FastAPI, SQLAlchemy, Vertex AI/Gemini, FAISS.
*   **Database:** SQL Server (Target), SQLite (Local).
*   **Missing Component:** `ODBC Driver 18 for SQL Server` is NOT installed in `Dockerfile` or `deploy_prod.sh`.

### PHASE 2: ARCHITECTURE QUALITY
*   **Strengths:** Clear separation of concerns (Routes -> Services -> Repositories).
*   **Weaknesses:** 
    *   **God Class Risk:** `app/services/advanced_retriever.py` (783 lines) and `app/services/query_engine.py` centralize excessive logic, making testing and maintenance difficult.
    *   **Circular Dependencies:** None detected in critical paths.

### PHASE 3: SECURITY PENETRATION
*   **Auth:** JWT with expiration checks (`ACCESS_TOKEN_EXPIRE_MINUTES = 60`).
*   **IDOR Risk:** High. The `DEFAULT_TENANT_ID` fallback in `app/middleware/tenant.py` creates a "catch-all" tenant. If a user forgets a header, they land in 'default' context.
*   **Secrets:** `Settings` class validates secret strength in production mode.

### PHASE 4: API CONTRACT
*   **Consistency:** Endpoints generally follow RESTful patterns.
*   **Versioning:** No explicit API versioning (e.g., `/v1/`) seen in route prefixes, though structure allows for it.

### PHASE 5: DATABASE FORENSIC
*   **Isolation:** `BaseRepository` uses `TenantContext` for automatic filtering.
*   **Risk:** Relies on developer discipline to use `BaseRepository` methods. Raw SQL queries (if any) would bypass tenant filters.

### PHASE 6: CONCURRENCY & DATA INTEGRITY
*   **Transactions:** `session_scope` context manager ensures atomic commits.
*   **Race Conditions:** No explicit row-locking (`with_for_update`) observed in critical stock/voucher decrements.

### PHASE 7: POS FINANCIAL INTEGRITY
*   **Applicability:** Limited (Support Portal).
*   **Audit:** Ticket state transitions managed via `state_machine.py`.

### PHASE 8: SAAS MULTI-TENANT SAFETY
*   **Implementation:** `TenantMiddleware` + `ContextVars`.
*   **Critical Flaw:** The fallback to `default` tenant in `TenantMiddleware` is dangerous for a strict SaaS app. It should 403 Forbidden if tenant cannot be resolved in production.

### PHASE 9: EVENT & QUEUE RELIABILITY
*   **Background Tasks:** Uses FastAPI `BackgroundTasks`.
*   **Risk:** In-memory queue. If container restarts, pending tasks (emails, vector indexing) are lost. Redis is configured but usage needs verification for reliable queuing.

### PHASE 10: AI SAFETY AUDIT
*   **Protection:** `guardrail_service.py` exists to filter inputs/outputs.
*   **RAG Poisoning:** Document ingestion (`knowledge_repo.py`) needs strict validation of uploaded files (PDF/Text) to prevent prompt injection via data.

### PHASE 11: OBSERVABILITY
*   **Logging:** `ai_observability.py` tracks token usage and costs.
*   **Health:** `/health` endpoint exists and is checked in Docker.

### PHASE 12: DEVOPS & DEPLOYMENT
*   **Container:** Uses non-root user (`appuser`). Good security practice.
*   **Missing Driver:** **P0 Fix Required** for SQL Server support.

### PHASE 13-16: SCALING & SIMULATION
*   **Bottleneck:** FAISS index is loaded in memory. `preload` in Gunicorn helps, but large knowledge bases will exhaust RAM. Vector DB (Pinecone/Weaviate) recommended for scaling.

### PHASE 17: FINAL VERDICT
**HIGH RISK.** The system is architecturally sound but operationally immature (missing drivers, risky defaults).

### PHASE 18: EXECUTIVE FIX ROADMAP
1.  **P0:** Install `msodbcsql18` in Dockerfile. (Auditor will perform this).
2.  **P1:** Disable `DEFAULT_TENANT_ID` fallback in Production.
3.  **P2:** Refactor `AdvancedRetriever`.

### PHASE 19: RED TEAM CONCLUSION
"I would attack this system by omitting the `X-Tenant-ID` header to see if I can access 'default' tenant data, or by uploading a malicious PDF to poison the RAG context."
