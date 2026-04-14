"""
Simple SQLite-backed user authentication.
Uses werkzeug password hashing (ships with Flask).
"""

import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            messages TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def create_user(username: str, email: str, password: str) -> dict | None:
    """Create a new user. Returns user dict or None if username/email taken."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username.strip(), email.strip().lower(), generate_password_hash(password)),
        )
        conn.commit()
        user = conn.execute(
            "SELECT id, username, email FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        return dict(user)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict or None."""
    conn = _get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    conn.close()
    if user and check_password_hash(user["password_hash"], password):
        return {"id": user["id"], "username": user["username"], "email": user["email"]}
    return None


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    user = conn.execute(
        "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(user) if user else None


# -- Conversation persistence per user --

def save_conversation(user_id: int, convo_id: str, title: str, messages: str):
    """Upsert a conversation for the given user."""
    conn = _get_conn()
    conn.execute("""
        INSERT INTO conversations (id, user_id, title, messages, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            messages = excluded.messages,
            updated_at = CURRENT_TIMESTAMP
    """, (convo_id, user_id, title, messages))
    conn.commit()
    conn.close()


def get_conversations(user_id: int) -> list[dict]:
    """Return all conversations for a user, newest first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, messages, created_at, updated_at FROM conversations "
        "WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_conversation(user_id: int, convo_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (convo_id, user_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0
