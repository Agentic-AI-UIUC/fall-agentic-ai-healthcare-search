import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent / "app.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    with _conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                sources TEXT,
                emergency INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
            CREATE TABLE IF NOT EXISTS intake_sessions (
                id TEXT PRIMARY KEY,
                step TEXT,
                form TEXT,
                messages TEXT,
                complete INTEGER DEFAULT 0,
                emergency INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS uploaded_documents (
                id TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                patient_email TEXT NOT NULL,
                reason TEXT,
                preferred_date TEXT,
                preferred_time TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending','confirmed','cancelled')),
                intake_session_id TEXT,
                created_at TEXT NOT NULL
            );
        """)


def save_message(session_id, role, message, sources=None, emergency=False):
    """Save one chat turn. Returns the new row id."""
    msg_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, session_id, role, message, sources, emergency, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (msg_id, session_id, role, message,
             json.dumps(sources or []), int(emergency), _now()),
        )
    return msg_id


def get_conversation(session_id):
    """Return all messages for a session, oldest first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id=? ORDER BY created_at, rowid",
            (session_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"]) if d["sources"] else []
        result.append(d)
    return result


def save_intake_session(session_id, session_dict):
    """Upsert intake session state."""
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO intake_sessions "
            "(id, step, form, messages, complete, emergency, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                session_id,
                session_dict.get("step"),
                json.dumps(session_dict.get("form")),
                json.dumps(session_dict.get("messages", [])),
                int(bool(session_dict.get("complete", False))),
                int(bool(session_dict.get("emergency", False))),
                _now(),
            ),
        )


def load_intake_session(session_id):
    """Load an intake session. Returns None if not found."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM intake_sessions WHERE id=?", (session_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["form"] = json.loads(d["form"]) if d["form"] else None
    d["messages"] = json.loads(d["messages"]) if d["messages"] else []
    d["complete"] = bool(d["complete"])
    d["emergency"] = bool(d["emergency"])
    return d


def save_document(doc_id, original_name, stored_name, path):
    """Persist uploaded document metadata."""
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO uploaded_documents "
            "(id, original_name, stored_name, path, uploaded_at) VALUES (?,?,?,?,?)",
            (doc_id, original_name, stored_name, path, _now()),
        )


def get_document(doc_id):
    """Return document metadata dict or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM uploaded_documents WHERE id=?", (doc_id,)
        ).fetchone()
    return dict(row) if row else None


def create_appointment(patient_name, email, reason, date, time, intake_session_id=None):
    """Create a new appointment. Returns the appointment id."""
    appt_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO appointments "
            "(id, patient_name, patient_email, reason, preferred_date, preferred_time, "
            "status, intake_session_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (appt_id, patient_name, email, reason, date, time,
             "pending", intake_session_id, _now()),
        )
    return appt_id


def get_appointments():
    """Return all appointments, newest first."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_appointment(appt_id):
    """Return one appointment dict or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE id=?", (appt_id,)
        ).fetchone()
    return dict(row) if row else None


def update_appointment_status(appt_id, status):
    """Update appointment status. Returns True if found, False if not found."""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE appointments SET status=? WHERE id=?", (status, appt_id)
        )
    return cur.rowcount > 0
