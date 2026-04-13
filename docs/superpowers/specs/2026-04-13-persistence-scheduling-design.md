# Persistence + Appointment Scheduling — Design Spec

**Date:** 2026-04-13  
**Status:** Approved

---

## Overview

Two related features sharing the same foundational work:

1. **Persistence** — replace all in-memory Python dicts with SQLite so data survives server restarts
2. **Appointment Scheduling** — patients can book appointments via chat or after completing intake; stored in the same SQLite DB

---

## Decisions Made

| Question | Decision | Reason |
|---|---|---|
| DB technology | SQLite via `sqlite3` (no ORM) | Zero new deps, fits existing `db/` module pattern, single file, prototype-appropriate |
| What to persist | Patient chat, intake sessions, uploaded doc metadata | Doctor sessions stay in-memory — they reset per case intentionally |
| Auth | Skip — anonymous sessions with UUIDs | Demo context, ships faster, can layer on later |
| Scheduling integration | End of intake (offer_scheduling flag) + mid-chat LLM tool | Both reinforce agentic demo |
| Scheduling backend | `pipeline/agents/scheduling_agent.py` | Mirrors existing agent module pattern |

---

## Architecture

### New File: `db/database.py`

Single module owning all SQLite access. No ORM — raw `sqlite3`.

**Responsibilities:**
- `init_db()` — create all tables if not exist; called once at app startup
- Grouped functions per domain (conversations, intake, documents, appointments)

**DB file location:** `db/app.db`

### Modified: `app.py`

- Remove `uploaded_docs`, `intake_sessions` in-memory dicts
- `doctor_sessions` stays in-memory (intentional)
- Replace every dict read/write with corresponding `db/database.py` call
- Call `init_db()` at startup
- Remove `_save_intake_form()` helper (DB replaces `intake_forms/` JSON files)
- Add 4 new appointment API endpoints

### New File: `pipeline/agents/scheduling_agent.py`

Single function `book_appointment(...)` — validates, writes to DB, returns confirmation dict.

### Modified: `pipeline/main.py`

Add `schedule_appointment` as a LangGraph tool. Intent classifier routes "book/schedule/appointment" phrases to this tool instead of RAG retrieval.

### Modified: `pipeline/agents/intake_agent.py`

When `complete=True`, add `"offer_scheduling": True` to the returned session dict.

### Frontend

- Scheduling card in right panel appears when `offer_scheduling: true` in intake response
- Fields: name, email, reason for visit, preferred date, preferred time
- On submit → `POST /api/appointments`
- Confirmation shown in chat + right panel
- "Book Appointment" button also available in patient mode header for mid-session use

---

## Database Schema

```sql
-- Patient chat history
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user' | 'assistant'
    message TEXT NOT NULL,
    sources TEXT,                 -- JSON array
    emergency INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Intake sessions
CREATE TABLE IF NOT EXISTS intake_sessions (
    id TEXT PRIMARY KEY,
    step TEXT,
    form TEXT,                    -- JSON blob of completed form
    messages TEXT,                -- JSON blob of message history
    complete INTEGER DEFAULT 0,
    emergency INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Uploaded document metadata
CREATE TABLE IF NOT EXISTS uploaded_documents (
    id TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL
);

-- Appointments
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_name TEXT NOT NULL,
    patient_email TEXT NOT NULL,
    reason TEXT,
    preferred_date TEXT,          -- ISO date string YYYY-MM-DD
    preferred_time TEXT,          -- e.g. '10:00 AM'
    status TEXT DEFAULT 'pending', -- 'pending' | 'confirmed' | 'cancelled'
    intake_session_id TEXT,       -- nullable FK to intake_sessions.id
    created_at TEXT NOT NULL
);
```

---

## API — `db/database.py` Interface

```python
# Startup
init_db() -> None

# Conversations
save_message(session_id, role, message, sources, emergency) -> str  # returns id
get_conversation(session_id) -> list[dict]

# Intake
save_intake_session(session_id, session_dict) -> None
load_intake_session(session_id) -> dict | None

# Documents
save_document(doc_id, original_name, stored_name, path) -> None
get_document(doc_id) -> dict | None

# Appointments
create_appointment(patient_name, email, reason, date, time, intake_session_id=None) -> str  # returns id
get_appointments() -> list[dict]
get_appointment(id) -> dict | None
update_appointment_status(id, status) -> None
```

---

## New Flask Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/appointments` | Book appointment (from UI form or LLM tool) |
| GET | `/api/appointments` | List all appointments |
| GET | `/api/appointments/<id>` | Get single appointment |
| PATCH | `/api/appointments/<id>` | Update status (confirm/cancel) |

---

## Naming Note

`/api/chat` accepts `conversation_id` from the frontend (stored in localStorage). This maps directly to `session_id` in the `conversations` table — no rename needed, just pass it through as-is when calling `save_message()`.

---

## LLM Tool Integration

Intent triggers (keyword-based, same pattern as `_classify_action` in patient_sim_agent):
- "book", "appointment", "schedule", "see a doctor", "make an appointment", "visit"

When triggered: agent calls `book_appointment()` tool, collects name/email/reason/date/time from conversation context or asks patient for missing fields, confirms booking in chat response.

---

## Intake → Scheduling Handoff

`run_intake_step()` returns `offer_scheduling: True` when `complete=True`.

Frontend handling:
```javascript
if (data.intake_complete && data.offer_scheduling) {
    showSchedulingCard();  // renders form in right panel
}
```

---

## Files Changed / Created

| File | Action |
|------|--------|
| `db/database.py` | **Create** — all SQLite logic |
| `db/app.db` | Auto-created by `init_db()` at first run |
| `pipeline/agents/scheduling_agent.py` | **Create** — `book_appointment()` tool |
| `pipeline/main.py` | **Modify** — add scheduling tool to LangGraph agent |
| `pipeline/agents/intake_agent.py` | **Modify** — add `offer_scheduling: True` on complete |
| `app.py` | **Modify** — replace in-memory dicts, add appointment endpoints, call `init_db()` |
| `frontend/index.html` | **Modify** — add scheduling card markup |
| `frontend/app.js` | **Modify** — add scheduling card logic, `POST /api/appointments` |
| `frontend/styles.css` | **Modify** — scheduling card styles |

---

## What Stays the Same

- `doctor_sessions` — in-memory, intentional
- `uploads/` directory — files still saved to disk; only metadata moves to DB
- `intake_forms/` directory — can be kept for backwards compat or removed
- All existing API routes — no breaking changes

---

## Out of Scope

- User authentication / login
- Google Calendar / external calendar sync
- Admin UI for managing appointments
- Email confirmation of appointments (can add later via existing `email_sender.py`)
