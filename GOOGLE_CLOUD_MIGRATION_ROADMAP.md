# 🚀 Google Cloud Migration Roadmap
## Support Portal AI — FAISS/OpenAI → Vertex AI Search + Gemini

> **Domain**: https://support-edgeworks.duckdns.org/
> **Repo**: `pt-ewopos-solusi-indonesia/support-ai-ews`
> **Date**: March 2026
> **Target UAT**: 20 March 2026
> **Timeline**: 3 Mar → 20 Mar (17 working days)

---

## 📊 Current Architecture (Before)

```
┌──────────────────────────────────────────────────────────────┐
│                    CURRENT STACK (v2.1)                       │
├──────────────────────────────────────────────────────────────┤
│  LLM Provider  │  Groq (llama-3.3-70b) via LangChain        │
│  Embeddings    │  Local HuggingFace (all-MiniLM-L6-v2)       │
│  Vector DB     │  FAISS (local file-based)                   │
│  Keyword Search│  BM25Okapi (in-memory)                      │
│  Fusion        │  Reciprocal Rank Fusion (custom)            │
│  Database      │  Supabase PostgreSQL                        │
│  Hosting       │  GCP VM (Docker) + DuckDNS                  │
│  Auth          │  JWT + Google OAuth + Magic Link             │
└──────────────────────────────────────────────────────────────┘

Files yang akan dimodifikasi:
├── app/core/config.py          ← Tambah Google Cloud settings
├── app/services/rag_service.py ← Ganti FAISS → Vertex AI Search
├── app/services/rag_engine.py  ← Ganti FAISS + LLM → Vertex AI + Gemini
├── app/services/llm_service.py ← Ganti ChatOpenAI → Gemini
├── requirements.txt            ← Tambah google-cloud deps
└── .env                        ← Tambah GCP credentials
```

---

## 🎯 Target Architecture (After)

```
┌──────────────────────────────────────────────────────────────┐
│                 TARGET STACK (v3.0 - Google Cloud)            │
├──────────────────────────────────────────────────────────────┤
│  LLM Provider  │  Google Gemini 2.0 Flash / 1.5 Pro         │
│  Embeddings    │  Google Vertex AI Embeddings                │
│  Search/RAG    │  Vertex AI Search (Discovery Engine)        │
│  Keyword Search│  Built into Vertex AI Search                │
│  Database      │  Supabase PostgreSQL (unchanged)            │
│  Storage       │  Google Cloud Storage (knowledge docs)      │
│  Hosting       │  GCP VM (Docker) + DuckDNS (unchanged)     │
│  Auth          │  Unchanged (JWT + Google OAuth)              │
│  Fallback      │  Groq llama / OpenAI (failover)             │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 Phase Plan (4 Phases)

### ═══════════════════════════════════════════
### PHASE 1: Gemini LLM Integration (Day 1-2)
### ═══════════════════════════════════════════

**Goal**: Ganti otak AI dari Groq/OpenAI ke Google Gemini, tanpa mengubah RAG pipeline.

**Kenapa duluan?** Paling mudah, paling cepat, dan langsung terasa efeknya.

#### Tasks:
- [ ] 1.1 Tambah `google-genai` ke `requirements.txt`
- [ ] 1.2 Tambah config `GOOGLE_GEMINI_API_KEY` dan `LLM_PROVIDER=gemini` ke `config.py`
- [ ] 1.3 Buat adapter `GeminiLLM` yang kompatibel dengan LangChain di `llm_service.py`
- [ ] 1.4 Update `rag_service.py` → `_get_llm()` method, tambah `gemini` case
- [ ] 1.5 Update `rag_engine.py` → `self.llm` initialization, tambah Gemini option
- [ ] 1.6 Test PoC: script terpisah `scripts/test_gemini.py`
- [ ] 1.7 Update `.env` di VM: `LLM_PROVIDER=gemini`
- [ ] 1.8 Deploy & verify

#### Files Modified:
```
config.py         +6 lines (GOOGLE_GEMINI_API_KEY, LLM_PROVIDER options)
llm_service.py    +20 lines (Gemini adapter)
rag_service.py    +15 lines (Gemini in _get_llm)
rag_engine.py     +15 lines (Gemini LLM init)
requirements.txt  +2 lines (google-genai, langchain-google-genai)
.env              +2 lines
```

#### Risk: LOW — Fallback ke Groq/OpenAI tetap tersedia

---

### ═══════════════════════════════════════════════════
### PHASE 2: Google Cloud Storage for Knowledge (Day 2-3)
### ═══════════════════════════════════════════════════

**Goal**: Upload dokumen knowledge ke Google Cloud Storage (GCS) — siap untuk Vertex AI Search.

**Kenapa?** Vertex AI Search butuh dokumen di GCS, bukan file lokal.

#### Tasks:
- [ ] 2.1 Buat GCS bucket: `gs://support-edgeworks-knowledge`
- [ ] 2.2 Tambah `google-cloud-storage` ke `requirements.txt`
- [ ] 2.3 Buat `app/services/gcs_service.py` — upload/delete/list knowledge files
- [ ] 2.4 Update `rag_engine.py` → saat file di-upload, sync ke GCS juga
- [ ] 2.5 Upload existing knowledge files ke GCS
- [ ] 2.6 Config: `GCS_BUCKET_NAME` di `.env`

#### Files Modified:
```
NEW: app/services/gcs_service.py  (GCS upload/delete helper)
rag_engine.py                     +10 lines (auto-sync to GCS)
config.py                         +3 lines (GCS config)
requirements.txt                  +1 line
.env                              +2 lines
```

#### Risk: LOW — Tidak mengubah flow RAG yang sudah ada

---

### ══════════════════════════════════════════════════════════
### PHASE 3: Vertex AI Search Integration (Day 3-5) ⭐ CRITICAL
### ══════════════════════════════════════════════════════════

**Goal**: Ganti FAISS + BM25 → Vertex AI Search (Discovery Engine) sebagai mesin retrieval utama.

**Ini upgrade terbesar** — search quality akan setara Google Search.

#### Tasks:
- [ ] 3.1 Create Vertex AI Search Data Store di GCP Console
  - Type: Unstructured Documents
  - Source: GCS bucket dari Phase 2
- [ ] 3.2 Create Vertex AI Search App (Search Engine)
- [ ] 3.3 Tambah `google-cloud-discoveryengine` ke `requirements.txt`
- [ ] 3.4 Buat `app/services/vertex_search_service.py`:
  - `search(query) → List[Document]` — call Vertex AI Search API
  - `get_answer(query) → str` — optional: use built-in answer generation
- [ ] 3.5 Update `rag_service.py`:
  - Tambah `RETRIEVAL_ENGINE` config (`vertex_ai` | `faiss` | `hybrid_local`)
  - Jika `vertex_ai`: panggil Vertex Search API
  - Jika `faiss`: fallback ke FAISS (existing code)
- [ ] 3.6 Update `rag_engine.py`:
  - Method `ask()` — gunakan Vertex AI Search untuk retrieval
  - Keep FAISS sebagai fallback
- [ ] 3.7 Update `rag_engine.py` → `ingest_documents()`:
  - Setelah upload ke GCS (Phase 2), trigger Vertex re-index
- [ ] 3.8 Buat `scripts/test_vertex_search.py` — PoC script
- [ ] 3.9 Deploy & run A/B test (FAISS vs Vertex side by side)

#### Architecture Change:
```
BEFORE:
  User Query → BM25 + FAISS → RRF → LLM → Answer

AFTER:
  User Query → Vertex AI Search API → Top Documents → Gemini → Answer
              (fallback) → FAISS + BM25 → RRF → LLM → Answer
```

#### Files Modified:
```
NEW: app/services/vertex_search_service.py  (Vertex AI Search client)
rag_service.py    ~30 lines changed (add vertex_ai retrieval path)
rag_engine.py     ~40 lines changed (vertex search in ask(), ingest sync)
config.py         +6 lines (VERTEX_*, RETRIEVAL_ENGINE)
requirements.txt  +1 line
.env              +4 lines
```

#### Risk: MEDIUM — Butuh setup di GCP Console, API mungkin perlu fine-tuning

---

### ══════════════════════════════════════════════════════════
### PHASE 4: Vertex AI Embeddings + Full Cleanup (Day 5-7)
### ══════════════════════════════════════════════════════════

**Goal**: Ganti HuggingFace local embeddings → Vertex AI Embeddings, dan cleanup kode legacy.

#### Tasks:
- [ ] 4.1 Tambah `langchain-google-vertexai` ke requirements
- [ ] 4.2 Update `config.py`: `EMBEDDINGS_TYPE=vertex_ai` option
- [ ] 4.3 Update `rag_service.py` → `_init_embeddings()`: Vertex AI case
- [ ] 4.4 Update `rag_engine.py` → embeddings init: Vertex AI case
- [ ] 4.5 Re-index semua knowledge documents with new embeddings
- [ ] 4.6 Performance benchmark: local vs Vertex AI embeddings
- [ ] 4.7 Cleanup: remove HuggingFace model download from Docker image (saves ~500MB)
- [ ] 4.8 Update `Dockerfile` — lighter image
- [ ] 4.9 Final integration test
- [ ] 4.10 Update docs

#### Files Modified:
```
rag_service.py    +10 lines (vertex_ai embeddings init)
rag_engine.py     +10 lines (vertex_ai embeddings init)
config.py         +2 lines
requirements.txt  +1 line, -2 lines (remove sentence-transformers if desired)
Dockerfile        optimized (smaller image)
```

#### Risk: LOW — embeddings are swappable, fallback exists

---

## 🔧 Environment Variables (Final State)

```env
# ============ LLM Provider ============
LLM_PROVIDER=gemini                    # gemini | groq | openai | ollama
GOOGLE_GEMINI_API_KEY=AIza...          # from https://aistudio.google.com/
GROQ_API_KEY=gsk_...                   # fallback

# ============ Google Cloud ============
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GCP_PROJECT_ID=tcare-edgeworks
GCS_BUCKET_NAME=support-edgeworks-knowledge

# ============ Vertex AI Search ============
VERTEX_SEARCH_ENGINE_ID=your-engine-id
VERTEX_SEARCH_LOCATION=global
RETRIEVAL_ENGINE=vertex_ai             # vertex_ai | faiss | hybrid_local

# ============ Embeddings ============
EMBEDDINGS_TYPE=vertex_ai              # vertex_ai | local | openai

# ============ (existing vars unchanged) ============
DATABASE_URL=postgresql+psycopg2://...
AUTH_SECRET_KEY=...
BASE_URL=https://support-edgeworks.duckdns.org
```

---

## 📊 Impact Analysis

| Metric | Before (FAISS) | After (Vertex AI) |
|--------|---------------|-------------------|
| **Search Quality** | Good (local embedding) | Excellent (Google-grade) |
| **Embedding Model** | all-MiniLM-L6-v2 (22M params) | Vertex AI (proprietary, enterprise) |
| **Index Update** | Manual re-index (minutes) | Auto-sync from GCS (seconds) |
| **Scalability** | Single machine | Unlimited (Google infra) |
| **Multi-language** | Limited | Native multi-language |
| **LLM Context** | 8K tokens (Groq/llama) | 1M+ tokens (Gemini 1.5 Pro) |
| **LLM Cost** | Free tier (Groq) | Free tier available (Gemini Flash) |
| **Docker Image Size** | ~2.5GB (HuggingFace models) | ~800MB (API-only) |
| **Cold Start** | 30-60s (model loading) | 2-3s (no local models) |

---

## 🔗 Alignment with Global Category Leader Strategy

Dari `Global_Category_Leader_Internal_Spinoff_Summary.md`:

| Strategy Goal | How This Migration Helps |
|---------------|------------------------|
| **Year 1: Productization** | Vertex AI Search = enterprise-ready API-based RAG |
| **Year 2: 40-60% Auto-Resolution** | Gemini 1.5 Pro context window = better answers = higher auto-resolution |
| **Year 3: Multi-Region SaaS** | Google Cloud = built-in multi-region, no FAISS file sync needed |
| **Intelligence Core** | Vertex AI Search = world-class retrieval, Gemini = world-class reasoning |
| **Competitive Moat** | POS data + Google AI = unbeatable combination |
| **Category Narrative** | "AI-powered control tower" backed by Google's search infrastructure |

---

## ⚡ Quick Start — Phase 1 Right Now

Siap mulai? Katakan **"mulai phase 1"** dan saya akan:
1. Install `google-genai` + `langchain-google-genai`
2. Add Gemini adapter ke LLM service
3. Buat test script
4. Update config

> **Prerequisite**: Anda perlu API Key dari https://aistudio.google.com/ (gratis, 60 req/min)
