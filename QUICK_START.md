# Quick Start: Support Portal Edgeworks

## For Developers

### Setup (5 minutes)

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   # Additional requirements for SQL Server & RAG
   pip install pyodbc rank-bm25 langchain-huggingface docx2txt
   ```

2. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your keys (OpenAI, SQL Server connection string).

3. **Start the app:**
   ```bash
   cd "support-portal-ai"
   python main.py
   ```

4. **Open browser:**
   ```
   http://localhost:8001/chat
   ```

### Test the API (Command Line)

**Check Health & RAG Status:**
```bash
curl http://localhost:8001/health
```

**Chat via API:**
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I reset my password?", "user_id": "cust_123"}'
```

---

## Code Structure

- `main.py` — FastAPI application, Lifespan handler, and API endpoints.
- `app/services/rag_engine.py` — Hybrid search (FAISS + BM25) and LLM logic.
- `app/core/database.py` — SQL Server 2025 management via SQLAlchemy.
- `app/services/websocket_manager.py` — Real-time event broadcasting.
- `templates/chat.html` — Live chat demonstration interface.

---

## Testing

### Automated Tests
We use `pytest` with `pytest-asyncio` for verification.

```bash
# Run all verified tests
python -m pytest tests/test_app.py tests/test_rag.py -v
```

### Manual Testing Checklist

- [x] RAG Engine initializes on startup (check logs)
- [x] SQL Server tables created automatically
- [x] /api/chat responds with relevant knowledge
- [x] WebSocket connects and broadcasts typing/messages
- [x] Health check shows `vector_store_ready: true`

---

## Database (SQL Server)

The app uses **SQL Server 2025**. Connection string format:
`mssql+pyodbc://sa:password@localhost:1433/DB_NAME?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=no&TrustServerCertificate=yes`

---

## Deployment

### Docker
```bash
docker-compose up --build
```

### Production
- **Server:** Gunicorn with Uvicorn workers
- **Port:** Default 8001 (configurable in main.py)
- **Log Level:** INFO (default)

---

Last Updated: 2026-02-28
