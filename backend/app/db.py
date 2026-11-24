"""
db.py
-----
All SQLite access lives here. We use Python's built-in `sqlite3` module (no ORM)
so the data layer is small and easy to read.

The table schema is exactly the one given in the assignment. History survives
container restarts because the .db file lives on a mounted Docker volume (/data).
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from . import config


def _db_path() -> str:
    """Convert the DATABASE_URL into a plain filesystem path for sqlite3."""
    url = config.DATABASE_URL
    # Strip the "sqlite:///" prefix. A 4th leading slash (sqlite:////data/app.db)
    # leaves "/data/app.db" (absolute); 3 slashes leave a relative path.
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url  # already a bare path


def _connect() -> sqlite3.Connection:
    """Open a new connection. Rows come back as dict-like objects."""
    path = _db_path()
    # Make sure the folder (e.g. /data) exists before opening the file.
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the messages table on startup if it isn't there yet."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,     -- 'user' or 'assistant'
                content     TEXT NOT NULL,
                metadata    TEXT,              -- JSON string, assistant messages only
                created_at  TEXT NOT NULL      -- server time, ISO-8601
            );
            """
        )
        # An index on session_id keeps history lookups fast as the table grows.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);"
        )


def _now_iso() -> str:
    """Current server time as an ISO-8601 string (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> None:
    """Append one message to a session's history."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                json.dumps(metadata) if metadata is not None else None,
                _now_iso(),
            ),
        )


def get_history(session_id: str) -> list[dict]:
    """
    Return the raw stored rows for a session, oldest first.
    Each row is a dict: {role, content, metadata(dict|None)}.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    history = []
    for row in rows:
        history.append(
            {
                "role": row["role"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            }
        )
    return history


def session_exists(session_id: str) -> bool:
    """True if we have stored at least one message for this session."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
    return row is not None


def clear_all() -> None:
    """Wipe every message. Only used by the test suite between tests."""
    with _connect() as conn:
        conn.execute("DELETE FROM messages")
