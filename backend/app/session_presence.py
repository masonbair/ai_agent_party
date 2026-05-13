from __future__ import annotations

import asyncio
from typing import Iterable, Protocol

from app.world import PartyWorld


class SocketLike(Protocol):
    async def send_json(self, payload: dict) -> None: ...

    async def close(self) -> None: ...


class StoreLike(Protocol):
    def worlds(self) -> Iterable[PartyWorld]: ...


class SessionPresenceHub:
    """Tracks one live WebSocket per ``session_id``.

    A second ``subscribe`` for the same id evicts the prior socket
    immediately: sends ``{"type":"evicted","reason":"takeover"}``, closes
    it, and removes the participant from every world.

    A clean ``unsubscribe`` schedules ``world.leave`` after
    ``GRACE_SECONDS`` so that brief reconnects do not boot the user from
    a world they were in. A new ``subscribe`` for the same id cancels
    the pending leave.
    """

    GRACE_SECONDS: float = 3.0

    def __init__(self, store: StoreLike) -> None:
        self._store = store
        self._by_session: dict[str, SocketLike] = {}
        self._pending: list[asyncio.Task] = []
        self._pending_leaves: dict[str, asyncio.TimerHandle] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _capture_loop(self) -> None:
        if self._loop is not None:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def subscribe(self, sock: SocketLike, session_id: str) -> None:
        self._capture_loop()
        timer = self._pending_leaves.pop(session_id, None)
        if timer is not None:
            timer.cancel()
        old = self._by_session.get(session_id)
        if old is not None and old is not sock:
            self._evict(old, session_id)
        self._by_session[session_id] = sock

    def unsubscribe(self, sock: SocketLike, session_id: str) -> None:
        if self._by_session.get(session_id) is sock:
            del self._by_session[session_id]
            self._schedule_leave(session_id)

    def _schedule_leave(self, session_id: str) -> None:
        if self._loop is None:
            return
        existing = self._pending_leaves.pop(session_id, None)
        if existing is not None:
            existing.cancel()
        handle = self._loop.call_later(
            self.GRACE_SECONDS,
            self._run_leave,
            session_id,
        )
        self._pending_leaves[session_id] = handle

    def _run_leave(self, session_id: str) -> None:
        self._pending_leaves.pop(session_id, None)
        for world in self._store.worlds():
            try:
                world.leave(session_id)
            except Exception:
                pass

    def _evict(self, old: SocketLike, session_id: str) -> None:
        self._dispatch(self._send_evict_and_close(old))
        for world in self._store.worlds():
            try:
                world.leave(session_id)
            except Exception:
                pass

    async def _send_evict_and_close(self, sock: SocketLike) -> None:
        try:
            await sock.send_json({"type": "evicted", "reason": "takeover"})
        except Exception:
            pass
        try:
            await sock.close()
        except Exception:
            pass

    def _dispatch(self, coro) -> None:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None:
            self._pending.append(running.create_task(coro))
        elif self._loop is not None:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            coro.close()

    async def drain(self) -> None:
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        await asyncio.gather(*pending, return_exceptions=True)
