"""Server-side action queue with asyncio-based scheduling.

Each principal can have at most MAX_PENDING_PER_PRINCIPAL queued entries.
Entries are keyed by a UUID hex queue_id and stored in-memory.  When an
entry's scheduled time arrives, its asyncio.Task fires _act_dispatch and
then self-removes from the registry.

On application shutdown, all outstanding tasks are cancelled.

Implementation note
-------------------
We use ``asyncio.create_task`` (not FastAPI's ``BackgroundTasks``) because we
need ``start_at`` deferred execution and per-ID cancellation.  The task
lifecycle (creation → sleep → run → self-cleanup) is managed entirely inside
``ActionQueueStore``.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import threading
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app.action_dispatch import Action, DispatchContext

MAX_PENDING_PER_PRINCIPAL = 3


@dataclass
class QueueEntry:
    queue_id: str
    slug: str
    principal_id: str
    actions: list[Action]
    scheduled_for: float  # epoch seconds
    task: asyncio.Task | None = field(default=None, repr=False)
    timer: threading.Timer | None = field(default=None, repr=False)
    cancelled: bool = False


class ActionQueueStore:
    """In-memory store of pending action queue entries.

    All public methods are safe to call from sync route handlers.
    ``schedule`` creates an asyncio Task via ``asyncio.create_task`` and
    requires a running event loop (FastAPI's own loop is used in production;
    the TestClient's anyio portal provides it in tests).
    """

    def __init__(self) -> None:
        self._by_id: dict[str, QueueEntry] = {}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_for(self, principal_id: str, slug: str) -> list[dict]:
        """Return summary dicts for all pending entries owned by principal."""
        return [
            {
                "queue_id": e.queue_id,
                "scheduled_for": dt.datetime.fromtimestamp(
                    e.scheduled_for, tz=dt.timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "action_count": len(e.actions),
            }
            for e in self._by_id.values()
            if e.principal_id == principal_id and e.slug == slug
            and not e.cancelled
        ]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def _pending_count(self, principal_id: str) -> int:
        return sum(
            1 for e in self._by_id.values()
            if e.principal_id == principal_id and not e.cancelled
        )

    def schedule(
        self,
        *,
        ctx: DispatchContext,
        actions: list[Action],
        start_at: dt.datetime | None,
        runner: Callable[[DispatchContext, list[Action]], Awaitable[list[dict]]],
    ) -> tuple[str, float]:
        """Schedule actions for execution at start_at (or immediately if None).

        Returns (queue_id, epoch_seconds_scheduled_for).
        Raises QueueLimitError if the principal already has MAX_PENDING_PER_PRINCIPAL
        entries.
        """
        if self._pending_count(ctx.principal_id) >= MAX_PENDING_PER_PRINCIPAL:
            raise QueueLimitError()

        # Use timezone-aware now() to avoid local-time vs UTC mismatch.
        _utc = dt.timezone.utc
        when = (
            start_at.timestamp()
            if start_at is not None
            else dt.datetime.now(_utc).timestamp()
        )
        qid = uuid.uuid4().hex
        entry = QueueEntry(
            queue_id=qid,
            slug=ctx.slug,
            principal_id=ctx.principal_id,
            actions=actions,
            scheduled_for=when,
        )
        self._by_id[qid] = entry

        # Capture the running event loop now (we're inside an async route
        # handler, so get_event_loop() returns the current loop).
        loop = asyncio.get_event_loop()
        store = self

        def _fire() -> None:
            """Called from the timer thread; submits the async work to the loop."""
            e = store._by_id.get(qid)
            if e is None or e.cancelled:
                return

            async def _run() -> None:
                try:
                    await runner(ctx, actions)
                finally:
                    store._by_id.pop(qid, None)

            asyncio.run_coroutine_threadsafe(_run(), loop)

        delay = max(0.0, when - dt.datetime.now(_utc).timestamp())
        if delay <= 0:
            # Immediate: schedule via the loop rather than a zero-second timer
            # so we don't block the route handler.
            async def _run_now() -> None:
                e = store._by_id.get(qid)
                if e is None or e.cancelled:
                    return
                try:
                    await runner(ctx, actions)
                finally:
                    store._by_id.pop(qid, None)

            entry.task = asyncio.ensure_future(_run_now())
        else:
            t = threading.Timer(delay, _fire)
            t.daemon = True
            t.start()
            entry.timer = t

        return qid, when

    def cancel(self, queue_id: str, principal_id: str) -> bool:
        """Cancel a pending queue entry.

        Returns True on success, False if queue_id not found.
        Raises NotOwnerError if the entry belongs to a different principal.
        """
        entry = self._by_id.get(queue_id)
        if entry is None:
            return False
        if entry.principal_id != principal_id:
            raise NotOwnerError()
        entry.cancelled = True
        if entry.task is not None:
            entry.task.cancel()
        if entry.timer is not None:
            entry.timer.cancel()
        self._by_id.pop(queue_id, None)
        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Cancel all outstanding tasks and timers on application shutdown."""
        for entry in list(self._by_id.values()):
            entry.cancelled = True
            if entry.task is not None:
                entry.task.cancel()
            if entry.timer is not None:
                entry.timer.cancel()
        self._by_id.clear()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class QueueLimitError(Exception):
    """Raised when a principal exceeds MAX_PENDING_PER_PRINCIPAL."""


class NotOwnerError(Exception):
    """Raised when a principal tries to cancel another's queue entry."""
