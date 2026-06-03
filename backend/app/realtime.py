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

from app.events import ChatEvent, Event
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


def _serialise_ambient_chat(event: ChatEvent) -> dict:
    """A contentless chat frame for out-of-range observers: enough to render a
    'someone's talking over there' puff, with the message text omitted."""
    return {
        "type": "event",
        "event": {
            "type": "chat",
            "seq": event.seq,
            "actor_id": event.actor_id,
            "actor_username": event.actor_username,
            "actor_kind": event.actor_kind,
            "actor_color": event.actor_color,
            "at": event.at,
            "ambient": True,
        },
        "cursor": event.seq,
    }


class PartyWorldHub:
    """Fan-out broadcaster for a single :class:`PartyWorld`.

    Each appended world event is dispatched to every subscriber. Sockets
    that raise during ``send_json`` are dropped and closed so a single
    misbehaving client cannot stall the world.

    Tracks one live socket per ``principal_key`` (``"<kind>:<id>"``);
    a second ``subscribe`` for the same key evicts the prior socket.
    """

    def __init__(self, world: PartyWorld) -> None:
        self.world = world
        self.subscribers: set[SocketLike] = set()
        self._by_principal: dict[str, SocketLike] = {}
        self._participant_by_sock: dict[SocketLike, str] = {}
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

    def subscribe(
        self, sock: SocketLike, principal_key: str, participant_id: str
    ) -> None:
        self._capture_loop()
        old = self._by_principal.get(principal_key)
        if old is not None and old is not sock:
            self._evict(old, participant_id)
        self._by_principal[principal_key] = sock
        self.subscribers.add(sock)
        self._participant_by_sock[sock] = participant_id

    def unsubscribe(self, sock: SocketLike, principal_key: str) -> None:
        self.subscribers.discard(sock)
        self._participant_by_sock.pop(sock, None)
        if self._by_principal.get(principal_key) is sock:
            del self._by_principal[principal_key]

    def _evict(self, old: SocketLike, participant_id: str) -> None:
        self.subscribers.discard(old)
        self._participant_by_sock.pop(old, None)
        self._dispatch(self._send_evict_and_close(old))
        try:
            self.world.leave(participant_id)
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

    def _on_event(self, event: Event) -> None:
        snapshot = list(self.subscribers)
        if not snapshot:
            return
        full = _serialise_event(event)
        # Only chat is proximity-scoped here; positions/presence/room-wide
        # events broadcast unchanged.
        if not isinstance(event, ChatEvent) or getattr(event, "room_wide", False):
            for sock in snapshot:
                self._dispatch(self._send_or_drop(sock, full))
            return
        ambient = _serialise_ambient_chat(event)
        for sock in snapshot:
            pid = self._participant_by_sock.get(sock)
            in_range = pid is not None and self.world.visible_to(pid, event)
            self._dispatch(self._send_or_drop(sock, full if in_range else ambient))

    async def _send_or_drop(self, sock: SocketLike, payload: dict) -> None:
        try:
            await sock.send_json(payload)
        except Exception:
            self.subscribers.discard(sock)
            self._participant_by_sock.pop(sock, None)
            stale = [k for k, v in self._by_principal.items() if v is sock]
            for k in stale:
                del self._by_principal[k]
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
        self._by_principal.clear()
        self._participant_by_sock.clear()
