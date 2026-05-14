"""Per-party realtime fan-out: listens to a PartyWorld's event stream and
broadcasts each event to every subscribed socket.

The hub is transport-agnostic: subscribers only need ``send_json`` and
``close`` coroutines, which lets the route layer pass a real FastAPI
``WebSocket`` and tests pass an in-memory fake.

World events are emitted synchronously by ``PartyWorld`` (which may be
running in a worker thread when called from a sync FastAPI route via
``TestClient``). To bridge into the asyncio world reliably we capture
the event loop the hub was first observed on (when ``subscribe`` is
called from an async context) and dispatch via either ``create_task``
(same-thread) or ``run_coroutine_threadsafe`` (cross-thread).
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from app.events import Event
from app.world import PartyWorld


class SocketLike(Protocol):
    async def send_json(self, payload: dict) -> None: ...

    async def close(self) -> None: ...


def _serialise_event(event: Event) -> dict:
    return {
        "type": "event",
        "event": event.model_dump(),
        "cursor": event.seq,
    }


class PartyWorldHub:
    """Fan-out broadcaster for a single :class:`PartyWorld`.

    Each appended world event is dispatched to every subscriber. Sockets
    that raise during ``send_json`` are dropped and closed so a single
    misbehaving client cannot stall the world.
    """

    def __init__(self, world: PartyWorld) -> None:
        self.world = world
        self.subscribers: set[SocketLike] = set()
        self._pending: list[asyncio.Task] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unsub = world.on_event(self._on_event)

    def _capture_loop(self) -> None:
        if self._loop is not None:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def subscribe(self, sock: SocketLike) -> None:
        self._capture_loop()
        self.subscribers.add(sock)

    def unsubscribe(self, sock: SocketLike) -> None:
        self.subscribers.discard(sock)

    def _on_event(self, event: Event) -> None:
        payload = _serialise_event(event)
        # Snapshot subscribers so concurrent unsubscribe is safe.
        snapshot = list(self.subscribers)
        if not snapshot:
            return

        # Determine where to schedule the coroutine.
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        for sock in snapshot:
            coro = self._send_or_drop(sock, payload)
            if running is not None:
                # Same thread / loop — schedule directly.
                task = running.create_task(coro)
                self._pending.append(task)
            elif self._loop is not None:
                # Sync caller from another thread (e.g. TestClient running a
                # sync route handler in a worker thread). Hop onto the loop
                # the hub was first observed on.
                asyncio.run_coroutine_threadsafe(coro, self._loop)
            else:
                # No loop anywhere — drop the coroutine to avoid a
                # "never awaited" warning while preserving safety.
                coro.close()

    async def _send_or_drop(self, sock: SocketLike, payload: dict) -> None:
        try:
            await sock.send_json(payload)
        except Exception:
            self.subscribers.discard(sock)
            try:
                await sock.close()
            except Exception:
                pass

    async def drain(self) -> None:
        """Wait for any pending in-loop send tasks to finish (test helper)."""
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        await asyncio.gather(*pending, return_exceptions=True)

    def teardown(self) -> None:
        self._unsub()
        self.subscribers.clear()
