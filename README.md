# SenAI Agentic CRM Intelligence Platform

Production-oriented take-home implementation: real-time email ingestion, multi-layer intelligence (heuristics → LLM → sentiment), RAG-grounded autonomous agent, web reputation cache, and a three-view React dashboard.

## Quick Start

```powershell
# Backend
cd backend
pip install -r requirements.txt
python scripts/seed_db.py          # load 60 emails + knowledge base
python -m uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

- **API docs**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/health  

Optional: set `OPENAI_API_KEY` in `.env` for live LLM classification (otherwise rule-based engine handles all assessment scenarios deterministically).

## What This System Does

### 1. Email Ingestion & Streaming (`POST /api/ingest`)
- Validates JSON schema (sender, `message_id`, `thread_id`, timestamps)
- **Deduplicates** on `message_id` (idempotent re-delivery)
- **Thread linking** — creates or updates `threads`, handles out-of-order timestamps
- **Heuristic priority** on ingest (spam, security, legal, urgency keywords)
- Sanitizes empty/HTML-only bodies; truncates bodies >10,000 chars
- `POST /api/stream/start?rate=1` replays `data/email-data-advanced.json`

### 2. Multi-Layer Intelligence

| Layer | Speed | Role |
|-------|-------|------|
| **L1 Heuristics** | <10ms | Spam, internal routing, security queue, urgency scoring |
| **L2 LLM** | ~100ms–2s | Full-thread + RAG classification, structured JSON, entity extraction |
| **L3 Sentiment** | async | Per-sender moving average; 3+ consecutive negative → escalation alert |

**Conflicting signals** (e.g. love product + want refund): `Mixed` sentiment, confidence capped below 0.70 → mandatory human review. Documented in README and `app/services/llm.py`.

### 3. RAG Pipeline (`GET /rag/search`)
- Knowledge base: `knowledge/*.md` (pricing, refunds, SLA, GDPR, FAQ)
- Chunked + hash embeddings (swap for OpenAI/pgvector in production)
- Top-3 chunks injected into classifier and agent

### 4. Autonomous Agent (`POST /agent/dry-run/{email_id}`)
Multi-step **Thought → Action → Observation** trace. Scenario handlers:

| Scenario | Message | Behavior |
|----------|---------|----------|
| GDPR Art. 20 | `msg_052` | Legal flag, 30-day acknowledgement, compliance ticket — **not** generic auto-reply |
| Ransomware | `msg_038` | Critical security escalate, **never** auto-reply |
| Chatbot misinformation | `msg_056` | RAG refund policy, empathetic draft, escalate liability |
| Reputation crisis | `msg_033` | Web intel (G2/Trustpilot), retention brief, escalate |
| Alice pro-rata | `msg_041` | Full thread + NPO pricing from RAG |

### 5. Web Intelligence (`GET /intelligence/reputation`)
Cached public reputation (G2/Trustpilot mock) with TTL; triggered on review-threat emails.

### 6. Dashboard (React)
- **Mission Control** — tabs, badges, search, thread grouping, bulk spam, WebSocket/polling
- **Thread Workspace** — timeline, entities, contact card, agent trace, RAG panel, web intel
- **Analytics** — sentiment line, category pie, response heatmap, at-risk panel, agent KPIs

## Stack Justification

- **FastAPI** — async I/O, automatic OpenAPI, Python AI ecosystem
- **SQLAlchemy 2 + SQLite** — zero-config assessment run; Postgres + pgvector for production scale
- **React + Vite + Recharts** — fast dashboard with real-time UX
- **Rule + optional OpenAI** — reliable eval scenarios without API key; upgrade path clear

## API Endpoints

All errors: `{ "error_code", "message", "details" }`. Full spec at `/docs`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ingest` | Ingest email → job_id |
| GET | `/api/status/{job_id}` | Processing status |
| GET | `/dashboard/stats` | Pending, Replied, Escalated, Critical, Spam |
| GET | `/threads/{contact_email}` | Full threads + actions + agent logs |
| GET | `/emails` | Inbox list with filters |
| POST | `/respond/{email_id}` | Send reply |
| POST | `/agent/dry-run/{email_id}` | Agent trace without execution |
| GET | `/analytics/sentiment-trend` | Time-series sentiment |
| GET | `/analytics/category-breakdown` | Category distribution |
| GET | `/rag/search` | Debug RAG retrieval |
| GET | `/intelligence/reputation` | Public reputation cache |
| GET | `/audit/{entity_type}/{entity_id}` | Audit trail |

## How to Run

**Requires:** Python 3.11+, Node.js 18+. Optional: `OPENAI_API_KEY` in `backend/.env` (copy from `.env.example`).

**Terminal 1 — API**
```powershell
cd backend
pip install -r requirements.txt
python scripts/seed_db.py
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Dashboard**
```powershell
cd frontend
npm install
npm run dev
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Start the **backend first**, then the frontend. Run `seed_db.py` once to load emails before using the inbox or analytics.
