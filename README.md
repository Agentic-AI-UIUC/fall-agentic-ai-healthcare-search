# Agentic AI Healthcare Search

A multi-agent medical assistant built on top of a RAG pipeline. It is **two products in one app**:

1. **Patient Mode** — a source-grounded medical Q&A chatbot with conversational intake, document upload, and an automated pipeline that emails a clinical-grade pre-consultation summary to the patient's doctor.
2. **Doctor Practice Mode** — a clinical training simulator where med students interview an LLM that role-plays a patient, then submit a diagnosis and get scored on reasoning, efficiency, and premature closure.

Both modes share the same Qdrant medical knowledge base, the same Groq LLM, and a SQLite-backed auth layer that ties conversations and intake history to a real user account.

---

## Table of Contents
- [System at a Glance](#system-at-a-glance)
- [How a Patient Question Flows](#how-a-patient-question-flows)
- [Conversational Intake → Email-to-Doctor](#conversational-intake--email-to-doctor)
- [Doctor Practice Mode](#doctor-practice-mode)
- [Auth & Persistence](#auth--persistence)
- [Project Layout](#project-layout)
- [Setup](#setup)
- [API Reference](#api-reference)
- [Design Principles](#design-principles)

---

## System at a Glance

```mermaid
flowchart TB
    user(["User<br/>(Patient or Med Student)"])

    subgraph FE["Frontend — vanilla HTML/JS/CSS"]
        login["Login / Signup"]
        modeSwitch{{"Mode Toggle<br/>Patient ↔ Doctor"}}
        chat["Chat UI"]
        panel["Right Panel<br/>(upload / case card)"]
    end

    subgraph BE["Flask Backend (app.py)"]
        auth["Auth Routes<br/>session cookie"]
        chatAPI["/api/chat"]
        intakeAPI["/api/intake"]
        emailAPI["/api/pre_medical"]
        docAPI["/api/doctor/*"]
    end

    subgraph Agents["Agent Layer"]
        rag["LangGraph<br/>RAG Pipeline"]
        intake["Intake Agent"]
        sim["Patient Sim Agent"]
        mailer["Email Sender"]
    end

    subgraph Stores["Stores"]
        qdrant[("Qdrant<br/>medical_chunks")]
        sqlite[("SQLite<br/>users + convos")]
        forms[("intake_forms/<br/>JSON files")]
    end

    groq[["Groq LLM<br/>llama-3.3-70b"]]
    gmail[["Gmail / Resend SMTP"]]

    user --> FE
    FE --> BE
    auth --> sqlite
    chatAPI --> rag --> qdrant
    rag --> groq
    intakeAPI --> intake --> groq
    intake --> forms
    emailAPI --> mailer --> gmail
    docAPI --> sim --> qdrant
    sim --> groq
    chatAPI -.reads.-> forms
```

The backend is a thin Flask shell. **All intelligence lives in the agent layer**, which is what makes this system "agentic" rather than just a chatbot:

| Agent | Lives in | What it does |
|---|---|---|
| **RAG agent** | `pipeline/main.py` | LangGraph state machine: classify intent → rewrite query → retrieve → generate → format |
| **Intake agent** | `pipeline/agents/intake_agent.py` | Multi-turn conversational form-filler with emergency detection at every step |
| **Patient simulator** | `pipeline/agents/patient_sim_agent.py` | Generates a hidden case, role-plays the patient, gates info, scores the diagnosis |
| **Email agent** | `pipeline/email_sender.py` | LLM formats raw form data into a clinical document, then dispatches via Gmail/Resend |

---

## How a Patient Question Flows

When a logged-in patient sends a chat message, the LangGraph orchestrator routes it through this state machine:

```mermaid
flowchart LR
    in([User message]) --> classify["classify_intent<br/>question / greeting / document"]
    classify -->|greeting| greet["handle_greeting"]
    classify -->|question| rewrite["rewrite_query<br/>layman → clinical terms<br/>+ extract source filter"]
    rewrite --> retrieve["retrieve<br/>top-k chunks from Qdrant"]
    retrieve --> generate["generate<br/>Groq LLM with<br/>medical system prompt"]
    generate --> emergency{{"emergency<br/>keyword scan"}}
    emergency --> format["format_response<br/>build source cards"]
    greet --> format
    format --> out([Answer + sources + flag])
```

Two non-obvious things this does:

- **Query rewriting before retrieval.** "My belly hurts" gets rewritten to clinical vocabulary the corpus actually uses (e.g., "abdominal pain epigastric"), which dramatically improves chunk quality.
- **Intake-aware generation.** If the user has a saved intake form (`intake_forms/user_<id>.json`), it's loaded and passed into the prompt so the LLM personalizes the answer to that patient's history.

---

## Conversational Intake → Email-to-Doctor

The intake system is a **stateful conversational agent**, not a static form. It walks the patient through 9 steps, runs an emergency check on every reply, and produces a structured JSON form that downstream agents consume.

```mermaid
flowchart TB
    start([Patient clicks 'Start Intake']) --> step1[Chief Complaint]
    step1 --> step2[Demographics]
    step2 --> step3[Emergency Contact + PCP]
    step3 --> step4[Medical History]
    step4 --> step5[Family History]
    step5 --> step6[Lifestyle & Habits]
    step6 --> step7[Activity & Physical]
    step7 --> step8[Medications]
    step8 --> step9[Objectives]
    step9 --> review[Review & Confirm]
    review --> save[(Save to<br/>intake_forms/<br/>session_id.json<br/>+ user_id.json)]

    step1 -.->|emergency<br/>keyword hit| er[["911 / ER banner<br/>shown immediately"]]
    step2 -.-> er
    step3 -.-> er
    step4 -.-> er
    step5 -.-> er
    step6 -.-> er
    step7 -.-> er
    step8 -.-> er

    save --> outputs{Outputs}
    outputs --> pdf["PDF download<br/>/api/intake/&lt;id&gt;/download"]
    outputs --> json["JSON export<br/>/api/intake/&lt;id&gt;/json"]
    outputs --> email["Email to doctor<br/>/api/intake/&lt;id&gt;/email"]
    outputs --> ctx["Auto-loaded as<br/>chat context"]
```

The richer **pre-medical questionnaire** (`/api/pre_medical`) is a separate longer form covering insurance, immunizations, ROS, and specialty-specific questions. It's piped through an LLM-powered formatter before being mailed:

```mermaid
sequenceDiagram
    participant P as Patient
    participant FE as Frontend
    participant API as /api/pre_medical
    participant LLM as Groq LLM
    participant Mail as Email Sender
    participant Doc as Doctor's Inbox

    P->>FE: Fills 10-section questionnaire
    FE->>API: POST raw form JSON
    API->>LLM: "Format this clinically,<br/>do not drop any data"
    LLM-->>API: Clean clinical document
    API->>Mail: send_email(doctor, subject, body)
    Mail->>Mail: Try Gmail SMTP →<br/>Resend → simulation
    Mail->>Doc: Pre-Consultation Patient Info
    Mail-->>FE: success / error
```

The cascading transport (`Gmail SMTP → Resend → console simulation`) means the system always **degrades gracefully**: a developer with no email credentials still sees the rendered email in their terminal instead of a 500 error.

---

## Doctor Practice Mode

This is the multi-agent half of the system. A med student toggles "Doctor Mode" and gets a fresh patient simulation generated **on demand** from the same Qdrant corpus that powers patient Q&A — no static case files, no canned scripts.

```mermaid
flowchart TB
    start([Doctor clicks 'New Case']) --> seed["Pick random seed query<br/>(e.g. 'chest pain cardiac')"]
    seed --> chunks["Retrieve top-k chunks<br/>from Qdrant"]
    chunks --> gen["LLM synthesizes case<br/>with HIDDEN diagnosis"]
    gen --> case[("Case JSON<br/>chief complaint<br/>background<br/>exam findings<br/>labs<br/>diagnosis 🔒<br/>differential 🔒")]

    case --> chat[Doctor Chat Loop]

    chat --> classify{Action classifier}
    classify -->|"ask history"| revealHx[Reveal background]
    classify -->|"examine / vitals"| revealEx[Reveal exam findings]
    classify -->|"order labs"| revealLab[Reveal lab results]
    classify -->|"hint"| hint[LLM nudge]
    classify -->|"diagnosis is X"| evaluate

    revealHx --> chat
    revealEx --> chat
    revealLab --> chat
    hint --> chat

    evaluate["Evaluate diagnosis<br/>(LLM-judged)"] --> scores[("Grade A-F<br/>reasoning 1-5<br/>efficiency 1-5<br/>premature closure<br/>missed findings")]
```

The right-side panel mirrors a real clinical workflow:

| Tab | What it does |
|---|---|
| **Actions** | Quick-action chips ("Take history", "Auscultate lungs", "Order CBC") and a "Submit Diagnosis" button |
| **Differential** | Build a hypothesis list, click "Check" — each gets marked correct / plausible / unlikely against the hidden case |
| **Quiz** | Generates 3 LLM-written MCQs grounded in the active case |
| **Results** | Locked until diagnosis is submitted — then reveals scores, missed findings, and the full differential |

**Why this matters:** the same Qdrant chunks that ground a patient's question are reused as clinical seed material for the simulator. One corpus, two completely different agentic behaviors.

---

## Auth & Persistence

Recently added — gated chat and intake behind a real user account so conversations and intake history persist across sessions.

```mermaid
flowchart LR
    visitor([Visitor]) --> gate{Has session cookie?}
    gate -->|no| auth["Login / Signup<br/>werkzeug password hash"]
    auth --> sqlite[("users.db<br/>users + conversations")]
    auth --> sess[Flask session cookie]
    gate -->|yes| app[Full app access]
    sess --> app

    app --> chat["/api/chat"]
    app --> intake["/api/intake"]

    chat -.user_id.-> ctx["Load intake_forms/<br/>user_&lt;id&gt;.json<br/>as chat context"]
    intake -.user_id.-> save["Save form to<br/>user_&lt;id&gt;.json"]

    app --> convos["/api/conversations<br/>list / save / delete"]
    convos --> sqlite
```

Auth is intentionally minimal: SQLite, Werkzeug password hashing, server-side session cookie. No JWTs, no OAuth — keeps the prototype simple while still scoping all per-user data correctly.

---

## Project Layout

```
.
├── app.py                         # Flask entrypoint — routes only, no business logic
├── db/
│   ├── auth.py                    # SQLite users + conversations
│   ├── ingestion.py               # Embed chunks → Qdrant
│   └── test_qdrant.py
├── pipeline/
│   ├── main.py                    # LangGraph RAG state machine
│   ├── retriever.py               # Qdrant query
│   ├── generator.py               # Groq prompt + medical system prompt
│   ├── prompts.py                 # All prompt templates
│   ├── email_sender.py            # Gmail → Resend → simulation cascade
│   └── agents/
│       ├── intake_agent.py        # Conversational intake state machine
│       └── patient_sim_agent.py   # Doctor-mode case gen + sim + scoring
├── data_collection/scripts/       # MSD scrapers + chunker (one-time)
├── frontend/                      # Vanilla HTML / JS / CSS
│   ├── index.html
│   ├── app.js                     # Mode switching, chat state, doctor panel
│   └── styles.css
├── intake_forms/                  # Saved intake JSON, keyed by session and user
├── uploads/                       # Patient document uploads
└── archive/                       # Legacy code — reference only
```

---

## Setup

**Prerequisites:** Docker, Python 3.10+, a Groq API key.

```bash
# 1. Start Qdrant
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.2.0

# 2. Install deps
pip install -r requirements.txt

# 3. Add credentials to .env
#    GROQ_API_KEY=gsk_...
#    SECRET_KEY=<flask-session-secret>
#    GMAIL_USER=...           # optional, for real email
#    GMAIL_APP_PASSWORD=...   # optional
#    RESEND_API_KEY=...       # optional fallback

# 4. Ingest medical chunks (one-time, after Qdrant is up)
python db/ingestion.py

# 5. Run the app
python app.py
# → http://localhost:5000
```

Without email credentials, sends print to your terminal instead — the app still works end-to-end.

---

## API Reference

### Auth
| Method | Route | Purpose |
|---|---|---|
| POST | `/api/auth/signup` | Create account, returns user + sets session cookie |
| POST | `/api/auth/login` | Authenticate, sets session cookie |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/auth/me` | Current user (or null) |

### Patient Mode
| Method | Route | Purpose |
|---|---|---|
| POST | `/api/chat` | RAG chat (intake-aware if user has a saved form) |
| POST | `/api/upload` | Upload PDF/TXT/DOCX/image |
| POST | `/api/intake` | Multi-turn intake conversation |
| GET | `/api/intake/<id>/download` | Intake form as PDF |
| GET | `/api/intake/<id>/json` | Intake form as JSON |
| POST | `/api/intake/<id>/email` | Email completed intake to doctor |
| POST | `/api/pre_medical` | Process and email full pre-consultation form |
| GET/POST/DELETE | `/api/conversations[/id]` | Per-user conversation persistence |

### Doctor Practice Mode
| Method | Route | Purpose |
|---|---|---|
| POST | `/api/doctor/session` | Generate a fresh case, return session id + greeting |
| POST | `/api/doctor/chat` | Doctor message → simulated patient response (+ evaluation if diagnosis submitted) |
| POST | `/api/doctor/quiz` | Generate 3 MCQs from the active case |
| POST | `/api/doctor/differential` | Score the doctor's hypothesis list against the hidden case |

### Health
| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |

---

## Design Principles

1. **Every patient answer is source-grounded.** The LLM is never asked to recall medical facts — it summarizes retrieved chunks and cites them. Sources are always returned to the UI.
2. **Emergency detection is non-negotiable.** Runs on every patient message and at every intake step. False positives are preferred to false negatives.
3. **The two modes are fully isolated.** Doctor sessions never touch patient state. Doctor mode bypasses the LangGraph pipeline entirely.
4. **Cases are dynamic.** No static case files. Every doctor session synthesizes a fresh patient from the existing medical corpus, so the trainee can't memorize the answers.
5. **Graceful degradation everywhere.** No Groq → chunk concatenation. No Qdrant → static fallback case. No SMTP → console simulation. The app never shows a blank error.
6. **Scoring is formative.** A wrong diagnosis with strong reasoning scores better than a lucky guess. Feedback names what was missed, not just whether the answer was right.
7. **The system is an information tool, not a doctor.** Every response carries a disclaimer, and emergency triggers always defer to 911 / ER.
