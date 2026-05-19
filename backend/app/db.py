"""SQLite persistence for openParty chat (broadcast + DM).

This is the only module in the codebase that imports ``sqlite3``. All
other code talks to SQLite through the helpers here. A single connection
is created at app startup and held on ``Store``; tests pass ``":memory:"``.
"""

from __future__ import annotations

import sqlite3
from typing import Any


_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS broadcast_messages (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      party_slug   TEXT    NOT NULL,
      sender_kind  TEXT    NOT NULL,
      sender_id    TEXT    NOT NULL,
      sender_name  TEXT    NOT NULL,
      text         TEXT    NOT NULL,
      at           REAL    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_broadcast_party_at ON broadcast_messages(party_slug, at)",
    """
    CREATE TABLE IF NOT EXISTS dm_messages (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      thread_key   TEXT    NOT NULL,
      sender_kind  TEXT    NOT NULL,
      sender_id    TEXT    NOT NULL,
      sender_name  TEXT    NOT NULL,
      text         TEXT    NOT NULL,
      at           REAL    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dm_thread_at ON dm_messages(thread_key, at)",
]


def init_db(path: str) -> sqlite3.Connection:
    """Open a connection, set WAL (for file paths), and create schema.

    ``check_same_thread=False`` so the FastAPI thread pool can share one
    connection; SQLite serializes writes internally. Idempotent: callable
    multiple times safely (uses ``CREATE TABLE IF NOT EXISTS``).
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    for stmt in _SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def close_db(conn: sqlite3.Connection | None) -> None:
    if conn is not None:
        conn.close()


MAX_HISTORY_LIMIT = 200


def insert_broadcast(
    conn: sqlite3.Connection,
    *,
    party_slug: str,
    sender_kind: str,
    sender_id: str,
    sender_name: str,
    text: str,
    at: float,
) -> int:
    cur = conn.execute(
        "INSERT INTO broadcast_messages "
        "(party_slug, sender_kind, sender_id, sender_name, text, at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (party_slug, sender_kind, sender_id, sender_name, text, at),
    )
    conn.commit()
    return int(cur.lastrowid)


def query_broadcast_history(
    conn: sqlite3.Connection,
    party_slug: str,
    *,
    before_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    capped = max(1, min(int(limit), MAX_HISTORY_LIMIT))
    if before_id is None:
        rows = conn.execute(
            "SELECT id, party_slug, sender_kind, sender_id, sender_name, text, at "
            "FROM broadcast_messages WHERE party_slug = ? "
            "ORDER BY id DESC LIMIT ?",
            (party_slug, capped),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, party_slug, sender_kind, sender_id, sender_name, text, at "
            "FROM broadcast_messages WHERE party_slug = ? AND id < ? "
            "ORDER BY id DESC LIMIT ?",
            (party_slug, int(before_id), capped),
        ).fetchall()
    return [dict(r) for r in rows]
