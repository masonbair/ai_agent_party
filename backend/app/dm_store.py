"""In-memory DM message store.

This module is a deliberate shim — Phase 6a's SQLite-backed ``db`` module
ships ``insert_dm``, ``query_thread_history``, and ``list_threads_for``
with identical signatures, and the post-merge follow-up swaps this
module's import for theirs in ``app.dm`` and the DM routes.

Each row is a plain dict with the same shape Phase 6a's
``dm_messages`` table will produce.
"""

from __future__ import annotations

import itertools
from typing import Any


class DmStore:
    """Append-only list of DM rows + an id counter.

    A dedicated class (rather than module-level globals) keeps tests and
    application instances isolated.
    """

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._next_id = itertools.count(1)

    def next_id(self) -> int:
        return next(self._next_id)


def insert_dm(
    store: DmStore,
    *,
    thread_key: str,
    sender_kind: str,
    sender_id: str,
    sender_name: str,
    text: str,
    at: float,
) -> int:
    mid = store.next_id()
    store.rows.append(
        {
            "id": mid,
            "thread_key": thread_key,
            "sender_kind": sender_kind,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
            "at": at,
        }
    )
    return mid


def query_thread_history(
    store: DmStore,
    *,
    thread_key: str,
    before_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Newest-first, cursor-paged. ``before_id`` is exclusive."""
    matching = [r for r in store.rows if r["thread_key"] == thread_key]
    if before_id is not None:
        matching = [r for r in matching if r["id"] < before_id]
    matching.sort(key=lambda r: r["id"], reverse=True)
    return matching[:limit]


def list_threads_for(
    store: DmStore, *, principal_key: str
) -> list[dict[str, Any]]:
    """Return one summary per thread the principal participates in.

    Sorted newest-first by ``last_at``. A principal is in a thread if
    their ``principal_key`` is one of the two parts of ``thread_key``.
    """
    by_thread: dict[str, dict[str, Any]] = {}
    for row in store.rows:
        parts = row["thread_key"].split("|", 1)
        if principal_key not in parts:
            continue
        existing = by_thread.get(row["thread_key"])
        if existing is None or row["at"] > existing["last_at"]:
            other = parts[0] if parts[1] == principal_key else parts[1]
            by_thread[row["thread_key"]] = {
                "thread_key": row["thread_key"],
                "other_principal_key": other,
                "last_at": row["at"],
                "last_text": row["text"],
                "last_sender_kind": row["sender_kind"],
                "last_sender_id": row["sender_id"],
                "last_sender_name": row["sender_name"],
                "last_message_id": row["id"],
            }
    return sorted(by_thread.values(), key=lambda t: t["last_at"], reverse=True)
