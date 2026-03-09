# 🚀 Edgeworks AI Support Portal: Technical Architecture

## 1. Executive Overview
The **Edgeworks AI Support Portal** is a scalable, enterprise-grade, Multi-Tenant SaaS platform built to automate Tier-1 and Tier-2 POS technical support. By combining a **Hybrid RAG (Retrieval-Augmented Generation) Pipeline**, **Real-Time WebSockets**, and **Agentic Tool Execution**, the system aims to automatically resolve 80-90% of common POS support requests (e.g., sync issues, printer failures, voucher errors) while securely escalating complex issues to human agents.

## 2. Core Technology Stack
| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI (Python 3.11)** | High-performance asynchronous API layer. |
| **Relational Database** | **SQL Server / PostgreSQL** | Core operational state (transactions, tickets, users). Managed via **SQLAlchemy (ORM)** and **Alembic** (migrations). |
| **AI / LLM Engine** | **Vertex AI / OpenAI** | Powers intent detection, reasoning, and conversational responses (`gpt-4o-mini` or `gemini`). |
| **Vector Database** | **FAISS (Local)** | High-speed semantic vector search for knowledge retrieval. |
| **Real-Time Comms** | **WebSockets + Redis** | Enables live multi-agent chat and dynamic UI updates across multiple horizontal server instances. |
| **Deployment** | **Docker + Gunicorn** | Containerized execution environment running Uvicorn asynchronous workers. |
| **External Integrations** | **Meta WhatsApp Business API** | Omnichannel ticket ingestion and automated remote replies. |

## 3. High-Level Architecture Pipelines

### A. The Hybrid RAG Engine (`AdvancedRetriever`)
To prevent "hallucinations" (the AI guessing answers), the system uses a highly accurate Hybrid RAG pipeline:
1.  **Ingestion & Chunking:** PDFs, text files, and logs are ingested, chunked by `RecursiveCharacterTextSplitter`, and converted to embeddings via `SentenceTransformers` (`all-MiniLM-L6-v2`).
2.  **Hybrid Retrieval:** When a user asks a question (e.g., "My printer won't print"), the system searches the FAISS Vector DB **and** performs BM25 exact-keyword matching.
3.  **Cross-Encoder Reranking:** The top 20 candidate documents are re-scored, and only the mathematically highest-scoring top 5 are injected into the LLM's context window.

### B. Agentic Tool Execution
The AI is not just a chatbot; it operates as an active troubleshooter. Based on intents (`pos_guardian`, `heart_guardian`, etc.), the AI can trigger predefined backend tools:
*   **Database Tool (`api/ai/db_query`):** Secure, read-only verification of transaction statuses, inventory logs, and POS device connections.
*   **Voucher Tool (`api/ai/check_voucher`):** Validates expiry dates and campaign rules in real-time if a customer reports a redemption error.
*   **Diagnostic Tools:** Gathers real system state before suggesting manual workflows.

### C. Self-Learning & Data Pipeline
*   **Interaction Logging:** Every AI resolution, whether successful or escalated, is permanently stored in the `AIInteraction` SQL table.
*   **PII Scrubber:** A critical security guardrail located at `app/utils/pii_scrubber.py`. Before *any* AI transcript is saved to the database, it is aggressively scanned via Regex. Credit cards, NRICs (Singapore standard), phone numbers, and API keys are redacted (e.g., `[REDACTED_CARD]`).
*   **Knowledge Extraction:** Human-resolved tickets are analyzed by a background job (`KnowledgeExtractor`) to dynamically generate new Knowledge Base embeddings, ensuring the AI continuously gets smarter.

## 4. Production & Security Enhancements
Following a comprehensive 18-Phase Engineering Audit, several critical enterprise features were implemented to ensure the system survives high-traffic loads:
1.  **Asynchronous Pool Unblocking (`run_sync`)**
    *   *Problem:* Synchronous SQLAlchemy database calls were blocking FastAPI's async event loop.
    *   *Solution:* Integrated `run_in_executor` wraps around critical paths (like Auth Dependencies and Portal Message fetching) to prevent blocking the async loop. 
2.  **Schema Versioning (`Alembic`)**
    *   Migrated from raw `metadata.create_all()` to robust, sequential Alembic migrations, permanently stamping the database baseline to safely apply future schema changes via code automatically seamlessly.
3.  **Horizontal WebSocket Scaling (Redis Enforcement)**
    *   Added startup guards in `gunicorn_conf.py` that loudly enforce Redis clustering if `workers > 1`, preventing WebSocket silent broadcast failures where Agent A cannot see Customer B typing.
4.  **IP-Bin-Binding (IDOR Protection)**
    *   Chat sessions dynamically bind to the initiating client's IP, preventing API tampering where users attempt to fetch historical chats of arbitrary `user_id`s.

## 5. Omnichannel Workflow Integration
The backend serves two distinct frontlines simultaneously:
1.  **Web Portal (`portal_routes.py`):** Anonymous tracking via local state, connecting directly to the RAG pipeline or opening WebSockets to human agents.
2.  **WhatsApp Webhook (`whatsapp.py`):** Passes messages from Meta directly into the async task queue, generating a `Ticket` or maintaining context in an existing AI dialogue loop. Upon AI failure, the loop is broken, and a human agent is pinged via the Admin Dashboard.
