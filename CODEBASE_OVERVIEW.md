# Codebase Overview: Agentic AI Healthcare Search

Multi-agent healthcare system on a RAG pipeline. Two operating modes: **Patient Mode** (medical Q&A, intake, document analysis) and **Doctor Practice Mode** (simulated patient encounters for clinical training).

---

## Project Structure

```
fall-agentic-ai-healthcare-search/
├── app.py                        # Flask backend — all API routes
├── frontend/                     # Vanilla HTML/JS/CSS
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── pipeline/                     # Agent + RAG logic
│   ├── main.py                   # LangGraph StateGraph orchestrator (patient mode)
│   ├── retriever.py              # Qdrant vector search
│   ├── generator.py              # Groq LLM generation
│   ├── prompts.py                # Prompt templates
│   ├── email_sender.py           # Resend email integration
│   └── agents/
│       ├── intake_agent.py       # Multi-step patient intake conversation
│       ├── patient_sim_agent.py  # Doctor Practice Mode simulated patient
│       └── scheduling_agent.py   # [PLANNED] Appointment booking tool
├── db/
│   ├── ingestion.py              # Embed + upsert chunks into Qdrant
│   ├── test_qdrant.py            # Qdrant connectivity test
│   └── database.py               # [PLANNED] SQLite persistence layer
├── data_collection/
│   ├── scripts/                  # PDF extraction, MSD scraping, KB building
│   ├── sources/                  # Raw PDFs and MSD data
│   └── processed/                # clean_chunks.json (~111K chunks)
├── uploads/                      # Uploaded patient documents (files on disk)
├── intake_forms/                 # Legacy intake JSON files (moving to SQLite)
├── docs/superpowers/specs/       # Design specs
└── archive/                      # Legacy code — not active
```

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| PDF extraction + MSD scraping | ✅ Done | 111K+ chunks in Qdrant |
| Qdrant vector DB | ✅ Done | `medical_chunks_hybrid_fast`, cosine similarity |
| LangGraph orchestrator | ✅ Done | `pipeline/main.py` — intent → retrieval → generation |
| Groq LLM generation | ✅ Done | `llama-3.3-70b-versatile` via langchain-groq |
| Patient intake agent | ✅ Done | Multi-step, emergency detection, PDF export |
| Doctor Practice Mode | ✅ Done | Dynamic case gen, evaluation, quiz, differential |
| Flask backend + frontend | ✅ Done | Patient + Doctor modes, mode switching |
| **SQLite persistence** | 🔲 Planned | Replace in-memory dicts — see design spec |
| **Appointment scheduling** | 🔲 Planned | LLM tool + post-intake UI + API endpoints |

---

## Technology Stack

| Category | Technology |
|----------|------------|
| Vector DB | Qdrant (Docker, `localhost:6333`) |
| Embeddings | `BAAI/bge-small-en-v1.5` + PubMedBERT (sentence-transformers) |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Orchestration | LangGraph `StateGraph` |
| Web framework | Flask |
| Frontend | Vanilla HTML/JS/CSS |
| Email | Resend API |
| Persistence | SQLite (planned — currently in-memory dicts) |

---

## Key Configuration

- Qdrant: `localhost:6333`, collection `medical_chunks_hybrid_fast`
- LLM: `GROQ_API_KEY` in `.env`
- Flask: port 5000
- Chunked data: `data_collection/processed/clean_chunks.json`

---

## API Endpoints

| Method | Route | Mode | Purpose |
|--------|-------|------|---------|
| GET | `/api/health` | Both | Health check |
| POST | `/api/chat` | Patient | RAG-powered Q&A |
| POST | `/api/upload` | Patient | Upload document |
| POST | `/api/intake` | Patient | Multi-turn intake conversation |
| GET | `/api/intake/<id>/download` | Patient | Download intake PDF |
| GET | `/api/intake/<id>/json` | Patient | Get intake JSON |
| POST | `/api/intake/<id>/email` | Patient | Email intake to doctor |
| POST | `/api/pre_medical` | Patient | Process + email pre-medical form |
| POST | `/api/doctor/session` | Doctor | Start new case |
| POST | `/api/doctor/chat` | Doctor | Simulated patient response |
| POST | `/api/doctor/quiz` | Doctor | Generate MCQs |
| POST | `/api/doctor/differential` | Doctor | Check differential hypotheses |
| POST | `/api/appointments` | Patient | Book appointment *(planned)* |
| GET | `/api/appointments` | Patient | List appointments *(planned)* |
| GET | `/api/appointments/<id>` | Patient | Get appointment *(planned)* |
| PATCH | `/api/appointments/<id>` | Patient | Update status *(planned)* |

---

## Dual-Mode System

| | Patient Mode | Doctor Practice Mode |
|---|---|---|
| User | Patient seeking info | Doctor/trainee practicing diagnosis |
| Agent | Medical Q&A assistant | Simulated patient (hidden diagnosis) |
| State | `uploaded_docs`, `intake_sessions` | `doctor_sessions` (in-memory, resets per case) |
| LLM calls | LangGraph pipeline | Direct Groq calls in `patient_sim_agent.py` |
| Right panel | Upload + intake | Case card, differential, quiz, evaluation |

---

## Session State (current — pre-persistence)

```python
# app.py — all lost on server restart
uploaded_docs = {}      # doc_id -> metadata dict
intake_sessions = {}    # session_id -> session dict
doctor_sessions = {}    # session_id -> {case, messages, session_complete}
```

After persistence work: `uploaded_docs` and `intake_sessions` move to SQLite. `doctor_sessions` stays in-memory intentionally.

---

## Commands

```bash
# Start Qdrant
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.2.0

# Ingest data (one-time)
python db/ingestion.py

# Run app
python app.py

# Test Qdrant
python db/test_qdrant.py
```

---

## Design Specs

- `docs/superpowers/specs/2026-04-13-persistence-scheduling-design.md` — SQLite persistence + appointment scheduling
