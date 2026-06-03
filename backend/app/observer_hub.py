"""Per-party push hub for /observe/ws.

Mirrors PartyWorldHub but per-subscriber state includes the participant
identity (for proximity scoping) and a last-sent cursor. One participant
may have multiple concurrent sockets (one per tab/agent process); each
gets its own cursor and proximity tracker.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from app.events import Event
from app.world import PartyWorld, PROXIMITY_RADIUS, within_proximity


class SocketLike(Protocol):
    async def send_json(self, payload: dict) -> None: ...

    async def close(self, code: int | None = None) -> None: ...


class _SocketState:
    __slots__ = ("principal_key", "participant_id", "cursor", "in_proximity")

    def __init__(self, principal_key: str, participant_id: str, cursor: int) -> None:
        self.principal_key = principal_key
        self.participant_id = participant_id
        self.cursor = cursor
        # Set of *other* participant ids currently visible (in radius).
        # Seeded at subscribe() time from the current world state so that
        # subsequent events correctly detect enters/leaves relative to that
        # baseline. Modified in place by _refresh_proximity on each event.
        self.in_proximity: set[str] = set()


class PartyObserverHub:
    def __init__(self, world: PartyWorld) -> None:
        self.world = world
        self.sockets: dict[object, _SocketState] = {}
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
        self, sock: SocketLike, *, principal_key: str, participant_id: str
    ) -> None:
        self._capture_loop()
        state = _SocketState(
            principal_key=principal_key,
            participant_id=participant_id,
            cursor=self.world.cursor,
        )
        # Seed proximity baseline from current world state so subsequent events
        # correctly detect enters/leaves relative to who's already in range.
        state.in_proximity = self._initial_in_proximity(participant_id)
        self.sockets[sock] = state

    def unsubscribe(self, sock: SocketLike) -> None:
        self.sockets.pop(sock, None)

    def cursor_of(self, sock: SocketLike) -> int:
        st = self.sockets.get(sock)
        return -1 if st is None else st.cursor

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

    def _serialise(self, event: Event) -> dict:
        return {
            "type": "event",
            "event": event.model_dump(),
            "cursor": event.seq,
        }

    def _initial_in_proximity(self, observer_id: str) -> set[str]:
        """Set of peer ids currently within PROXIMITY_RADIUS of observer."""
        try:
            return self.world.peers_in_proximity(observer_id)
        except AttributeError:
            # Fallback: derive from participants + radius constant.
            me = self.world.participants.get(observer_id)
            if me is None:
                return set()
            r2 = PROXIMITY_RADIUS * PROXIMITY_RADIUS
            out: set[str] = set()
            for pid, p in self.world.participants.items():
                if pid == observer_id:
                    continue
                if (p.x - me.x) ** 2 + (p.y - me.y) ** 2 <= r2:
                    out.add(pid)
            return out

    def _refresh_proximity(self, state: _SocketState) -> tuple[set[str], set[str]]:
        now_in = self._initial_in_proximity(state.participant_id)
        entered = now_in - state.in_proximity
        left = state.in_proximity - now_in
        state.in_proximity = now_in
        return entered, left

    def _participant_view(self, pid: str) -> dict:
        p = self.world.participants.get(pid)
        if p is None:
            return {"id": pid}
        return {
            "id": p.id,
            "kind": p.kind,
            "username": p.username,
            "color": p.color,
            "x": p.x,
            "y": p.y,
            "zone": self.world.derive_zone(p.x, p.y),
        }

    def _on_event(self, event: Event) -> None:
        if not self.sockets:
            return
        for sock, state in list(self.sockets.items()):
            try:
                visible = self.world.visible_to(state.participant_id, event)
            except Exception:
                visible = False
            entered, left = self._refresh_proximity(state)
            for pid in entered:
                self._dispatch(self._send_or_drop(sock, {
                    "type": "proximity_snapshot",
                    "participant_id": pid,
                    "participant": self._participant_view(pid),
                    "cursor": event.seq,
                }))
            for pid in left:
                self._dispatch(self._send_or_drop(sock, {
                    "type": "proximity_left",
                    "participant_id": pid,
                    "cursor": event.seq,
                }))
            if visible:
                payload = self._serialise(event)
                state.cursor = event.seq
                self._dispatch(self._send_or_drop(sock, payload))
            elif entered or left:
                # Even when the event itself isn't visible, the proximity
                # frames advance the cursor so reconnect resumes cleanly.
                state.cursor = event.seq

    async def _send_or_drop(self, sock: SocketLike, payload: dict) -> None:
        try:
            await sock.send_json(payload)
        except Exception:
            self.sockets.pop(sock, None)
            try:
                await sock.close()
            except Exception:
                pass

    async def drain(self) -> None:
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        await asyncio.gather(*pending, return_exceptions=True)

    def teardown(self) -> None:
        self._unsub()
        self.sockets.clear()
