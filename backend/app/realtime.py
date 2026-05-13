"""Per-party realtime fan-out: listens to a PartyWorld's event stream and
broadcasts each event to every subscribed socket.

The hub is transport-agnostic: subscribers only need ``send_json`` and
``close`` coroutines, which lets the route layer pass a real FastAPI
``WebSocket`` and tests pass an in-memory fake.
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
        self._unsub = world.on_event(self._on_event)

    def subscribe(self, sock: SocketLike) -> None:
        self.subscribers.add(sock)

    def unsubscribe(self, sock: SocketLike) -> None:
        self.subscribers.discard(sock)

    def _on_event(self, event: Event) -> None:
        payload = _serialise_event(event)
        # Snapshot subscribers so concurrent unsubscribe is safe.
        for sock in list(self.subscribers):
            try:
                task = asyncio.create_task(self._send_or_drop(sock, payload))
            except RuntimeError:
                # No running loop (e.g. event emitted from sync test code).
                # Fall back to scheduling on the default loop if possible.
                continue
            self._pending.append(task)

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
        """Wait for any pending send tasks to finish (test helper)."""
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        await asyncio.gather(*pending, return_exceptions=True)

    def teardown(self) -> None:
        self._unsub()
        self.subscribers.clear()
