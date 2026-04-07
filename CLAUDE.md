# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent healthcare system built on a RAG (Retrieval-Augmented Generation) pipeline. Ingests medical documents (PDFs, MSD articles), chunks and embeds them, stores vectors in Qdrant, and uses LangGraph + Groq LLM to answer user queries via a Flask web app. The system operates in two modes: **Patient Mode** (medical Q&A, intake forms, document analysis) and **Doctor Practice Mode** (simulated patient encounters for clinical training).

## Architecture

### Data Layer

1. **Data collection & preprocessing** (`data_collection/scripts/`) — Scrapes MSD articles, extracts/cleans PDF text, chunks with LangChain `RecursiveCharacterTextSplitter` (3000 chars, 250 overlap), outputs to `data_collection/processed/`.

2. **Vector DB ingestion** (`db/ingestion.py`) — Embeds chunks with BGE and PubMedBERT models (sentence-transformers), upserts into Qdrant collection `medical_chunks_hybrid_fast` with cosine similarity. Batch size 100.

### Agent Layer

3. **LangGraph orchestrator** (`pipeline/main.py`) — A `StateGraph` that routes patient-mode messages through: intent classification → retrieval → LLM generation → response formatting. Uses `AgentState` TypedDict for state. Doctor mode bypasses this graph entirely.

4. **LLM generation** (`pipeline/generator.py`) — Uses Groq API (`llama-3.3-70b-versatile`) via `langchain-groq`. Formats retrieved chunks into context, applies a medical system prompt (plain language, source attribution, disclaimer, emergency detection), returns grounded answers.

5. **Patient intake agent** (`pipeline/agents/intake_agent.py`) — Multi-step conversational intake that collects chief complaint, symptoms, medications, allergies, conditions, family history, and lifestyle. Runs emergency checks at every step. Outputs a structured JSON intake form.

6. **Simulated patient agent** (`pipeline/agents/patient_sim_agent.py`) — Doctor Practice Mode agent. Dynamically generates patient cases from Qdrant medical chunks via Groq LLM. Role-plays as the patient, gates information behind doctor actions (history-taking, exam, labs), evaluates submitted diagnoses with multi-dimensional scoring, generates quizzes, and checks differential hypotheses.

### Serving Layer

7. **Flask backend** (`app.py`) — Serves the frontend, exposes all API routes. Uses in-memory dicts for session state (`uploaded_docs`, `intake_sessions`, `doctor_sessions`).

8. **Frontend** (`frontend/`) — Vanilla HTML/JS/CSS. `app.js` manages chat state in localStorage, renders messages/sources, handles mode switching between patient and doctor modes.

`archive/` contains legacy code — not active, kept for reference only.

## Commands

```bash
# Start Qdrant (required before running the app)
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.2.0

# Ingest data into Qdrant (one-time, after Qdrant is running)
python db/ingestion.py

# Run the Flask web app (serves frontend + API on port 5000)
python app.py

# Test Qdrant connection with dummy vectors
python db/test_qdrant.py

# Run retriever standalone (interactive query prompt)
python pipeline/retriever.py
```

## Key Configuration

- Qdrant: `localhost:6333`, collection name `medical_chunks_hybrid_fast`
- Embedding models: `BAAI/bge-small-en-v1.5` and PubMedBERT (must be consistent between ingestion and retrieval)
- LLM: Groq API with `llama-3.3-70b-versatile` — requires `GROQ_API_KEY` in `.env`
- Flask app: port 5000, serves static files from `frontend/`
- Chunked data source: `data_collection/processed/clean_chunks.json`

## Dependencies

Core packages: `flask`, `sentence-transformers`, `qdrant-client`, `langchain`, `langchain-groq`, `langgraph`, `langchain-text-splitters`, `groq`, `pypdf`, `pandas`, `python-dotenv`, `resend`.

`.env` file (gitignored) must contain:
```
GROQ_API_KEY=gsk_...
```

## API Endpoints

| Method | Route | Mode | Purpose |
|--------|-------|------|---------|
| GET | `/api/health` | Both | Health check |
| POST | `/api/chat` | Patient | Send message, get RAG-powered answer + sources |
| POST | `/api/upload` | Patient | Upload medical document (PDF, TXT, DOCX, images) |
| POST | `/api/intake` | Patient | Multi-turn patient intake conversation |
| GET | `/api/intake/<id>/download` | Patient | Download completed intake form as text |
| GET | `/api/intake/<id>/json` | Patient | Get completed intake form as JSON |
| POST | `/api/pre_medical` | Patient | Process and email pre-medical form |
| POST | `/api/doctor/session` | Doctor | Start new case (generates patient from Qdrant chunks) |
| POST | `/api/doctor/chat` | Doctor | Send doctor message, get simulated patient response |
| POST | `/api/doctor/quiz` | Doctor | Generate MCQs from active case |
| POST | `/api/doctor/differential` | Doctor | Check differential hypotheses against case |

---

## Dual-Mode Agent System — Implementation Reference

The system has two fully isolated operating modes sharing the same Flask backend and Qdrant data.

| | **Patient Mode** | **Doctor Practice Mode** |
|---|---|---|
| **User** | Patient seeking information | Doctor/trainee practicing diagnosis |
| **Agent role** | Medical information assistant | Simulated patient with hidden diagnosis |
| **Data source** | Qdrant `medical_chunks_hybrid_fast` | Same collection, but used to synthesize cases |
| **Right panel** | Document upload & analysis | Case card, differential builder, quiz, evaluation |
| **LLM calls** | LangGraph pipeline via `pipeline/main.py` | Direct Groq calls in `patient_sim_agent.py` |

### Phase A: Mode Switching Infrastructure (implemented)

**What it does:** Adds a toggle button in the frontend header that flips between patient and doctor modes. Applies a `body.doctor-mode` CSS class for palette shift, swaps the right panel (document upload vs. case/quiz panel), and clears the conversation on switch.

**Files edited:**
- `frontend/index.html` — Added `#doctorModeToggle` button in `.chat-header-actions`, added full `<aside class="doctor-panel">` markup
- `frontend/app.js` — Added `appMode` to state, `toggleDoctorMode()` and `applyMode()` functions, routes `handleSend()` to `handleDoctorSend()` when in doctor mode
- `frontend/styles.css` — `.doctor-toggle-btn`, `.doctor-mode-active`, `body.doctor-mode` palette overrides, `.doctor-panel` layout
- `pipeline/main.py` — Added `app_mode: str` field to `AgentState` TypedDict (informational only; doctor mode doesn't use the LangGraph graph)

**Key decision:** Doctor mode does NOT route through the LangGraph `StateGraph`. It calls `run_patient_sim()` directly from `app.py`, keeping the existing patient pipeline untouched.

### Phase B + F: Dynamic Case Generation (implemented, merged)

**What it does:** Instead of static case JSON files, cases are generated dynamically each session. `generate_case_from_chunks()` picks a random seed query (e.g., "chest pain shortness of breath cardiac"), retrieves top medical chunks from Qdrant, and sends them to Groq LLM with a prompt to synthesize a realistic clinical case with hidden diagnosis. Falls back to a hardcoded migraine case if Qdrant or Groq is unavailable.

**Files created:**
- `pipeline/agents/patient_sim_agent.py` — Contains `SEED_QUERIES` list, `generate_case_from_chunks()`, `_llm_call()` helper, static fallback case

**No new dependencies.** Uses existing `pipeline/retriever.py` for Qdrant access and `groq` package for LLM calls.

**Case JSON structure produced:**
```python
{
    "chief_complaint": "...",
    "background": "...",
    "symptom_details": "...",
    "exam_findings": "...",
    "lab_results": "...",
    "diagnosis": "...",          # hidden from doctor
    "key_findings": ["..."],     # hidden until evaluation
    "differential": ["..."],     # hidden until evaluation
    "difficulty": "beginner|intermediate|advanced"
}
```

### Phase C: Simulated Patient Agent (implemented)

**What it does:** The LLM role-plays as the generated patient. An action classifier (keyword-based) categorizes each doctor message into: `ask_history`, `order_exam`, `order_labs`, `submit_diagnosis`, or `request_hint`. The patient only reveals exam findings when the doctor explicitly examines, and lab results only when tests are ordered. Session state tracks `revealed` sections, `turns` count, and `tests_ordered`.

**Files created/edited:**
- `pipeline/agents/patient_sim_agent.py` — `run_patient_sim(session, doctor_message)` function, `_classify_action()`, `new_session(case)` helper
- `app.py` — Added `doctor_sessions = {}` in-memory store, `POST /api/doctor/session` and `POST /api/doctor/chat` endpoints

**Information gating rules:**

| Doctor action | Keyword triggers | What gets revealed |
|---|---|---|
| Ask history | "history", "medications", "allergies" | `background` field |
| Order exam | "examine", "vitals", "auscultate" | `exam_findings` field |
| Order labs | "lab", "blood", "x-ray", "CBC", "imaging" | `lab_results` field |
| Submit diagnosis | "diagnosis is", "I think this is", "my assessment" | Triggers evaluation |
| Request hint | "hint", "clue", "help me" | Brief nudge from LLM |

### Phase D: Doctor-Mode Right Panel UI (implemented)

**What it does:** When in doctor mode, the right panel shows a case card with difficulty badge and chief complaint, progress dots (Hx/PE/Dx that light up as the doctor reveals information), and four tabs: Actions (quick-action chips + submit diagnosis), Differential (hypothesis builder with add/remove/check), Quiz (LLM-generated MCQs), and Results (evaluation card, locked until diagnosis submitted).

**Files edited:**
- `frontend/index.html` — Full doctor panel markup: `#caseCard`, `#caseProgress` with `.progress-dot` spans, `.doctor-tabs` with four `.doctor-tab` buttons, four `.doctor-tab-content` divs (`#tabActions`, `#tabDifferential`, `#tabQuiz`, `#tabTeaching`)
- `frontend/app.js` — `switchDoctorTab()`, `loadNewCase()`, `renderCaseCard()`, `updateProgressDots()`, `addDifferentialHypothesis()`, `renderDifferentialList()`, `checkDifferentialHypotheses()`, `loadQuiz()`, `selectQuizOption()`, `renderEvaluationCard()`
- `frontend/styles.css` — All doctor panel element styles: `.doctor-tabs`, `.doctor-tab`, `.doctor-tab-content`, `.diff-input-row`, `.diff-item`, `.diff-correct/.diff-plausible/.diff-unlikely`, `.diff-badge`, `.quiz-question`, `.quiz-option`, `.quiz-correct/.quiz-wrong`, `.quiz-explanation`, `.case-progress`, `.progress-dot`, `.eval-scores`, `.eval-grade`, `.eval-warn`, `.tab-desc`

**API endpoints added to `app.py`:**
- `POST /api/doctor/quiz` — Calls `generate_quiz(case)` which asks LLM to produce 3 MCQs from the case data
- `POST /api/doctor/differential` — Calls `check_differential(case, hypotheses)` which compares doctor's hypotheses against case diagnosis/differential via keyword matching

### Phase E: Diagnosis Evaluation & Scoring (implemented)

**What it does:** When the doctor submits a diagnosis (via chat message or "Submit Diagnosis" button), `_evaluate_diagnosis()` runs. It first tries an LLM-judged evaluation (Groq) that scores reasoning quality (1-5), efficiency (1-5), premature closure detection, key findings identified vs. missed, and overall grade (A-F). Falls back to keyword matching if LLM is unavailable.

**Files edited:**
- `pipeline/agents/patient_sim_agent.py` — `_evaluate_diagnosis(session, submitted_diagnosis)` with `EVAL_PROMPT`, JSON parsing of LLM response, keyword-match fallback
- `frontend/app.js` — `renderEvaluationCard(evaluation)` shows pass/fail banner, grade, star-based scores, strengths/improvements lists, identified/missed findings, full differential reveal
- `frontend/styles.css` — `.evaluation-card`, `.eval-header`, `.eval-correct/.eval-incorrect`, `.eval-body`, `.eval-scores`, `.eval-score-item`, `.eval-warn`, `.eval-grade`

**Evaluation output structure:**
```python
{
    "diagnosis_correct": bool,
    "correct_diagnosis": "...",
    "overall_grade": "A" | "B" | "C" | "D" | "F",
    "reasoning_quality": 1-5,
    "efficiency_score": 1-5,
    "premature_closure": bool,
    "key_findings_identified": ["..."],
    "missed_findings": ["..."],
    "strengths": ["..."],
    "improvements": ["..."],
    "full_differential": ["..."]
}
```

---

## Design Principles

1. **Every answer is source-grounded.** The LLM cites retrieved chunks. No hallucinated medical advice.
2. **Emergency detection is non-negotiable.** Runs on every user message in patient mode. False positives > false negatives.
3. **The system is an information tool, not a doctor.** Every response includes a disclaimer.
4. **Graceful degradation.** If Groq or Qdrant is unavailable, falls back to chunk concatenation (patient mode) or a static case (doctor mode). Never shows a blank error.
5. **The two modes are fully isolated.** Doctor-mode state (`doctor_sessions`) never leaks into patient-mode state. Doctor mode bypasses LangGraph entirely.
6. **Cases are dynamically generated.** No static case files — every session synthesizes a fresh case from the existing Qdrant medical corpus via LLM.
7. **Scoring is formative, not punitive.** Feedback focuses on reasoning process. A wrong diagnosis with excellent reasoning scores better than a lucky guess.
