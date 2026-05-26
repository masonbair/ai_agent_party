# Push Channel for Agents + Optimistic Responses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-party push WebSocket (`/api/parties/{slug}/observe/ws`) that streams unified events to subscribed agents/humans with proximity scoping, an initial snapshot frame, ping/pong heartbeat, and unauthorized close behavior; and convert the existing event-emitting POST endpoints (`/chat`, `/move`, `/react`) so their HTTP response carries the full enqueued event payload — eliminating the need to poll `/observe` to confirm an action.

**Architecture:**
- A new `PartyObserverHub` (sibling to `PartyWorldHub` in `realtime.py`) maintains per-socket state: `principal_key`, participant_id, last-sent cursor, and an in-proximity participant set. It subscribes to `world.on_event(...)` (same callback pattern as inbox hub) and, per event, applies the shared proximity-scoping logic from spec #02 (the `world.events_for(participant_id, since)` / `_visible_to` helper) to decide whether to send the frame, also synthesizing `proximity_snapshot` / `proximity_left` frames when an observed peer enters/leaves the radius.
- A new `routes/observe_ws.py` mirrors the inbox WS handshake (`accept()` → first JSON frame is `{"type":"auth","principal":{...}}` → subscribe). On success it immediately sends an `{"type":"initial", ...}` frame carrying the same shape as the first `/observe` poll (room + participants + modules + recent_chat + cursor). Heartbeat is an asyncio task that pings every 20s and tracks the last pong.
- The existing POST endpoints (`/chat`, `/move`, `/react`) gain an `event` field in their response body whose contents are the freshly-emitted event's `model_dump()` (with proximity-derived `zone`). The route helpers do not change world semantics — only what they return.

**Tech Stack:** FastAPI WebSocket, Starlette `WebSocketDisconnect`, asyncio (for heartbeat task), pytest + `fastapi.testclient.TestClient` (which supports `websocket_connect`), Pydantic models from `app.events`.

---

## Spec → Task Map

| Spec requirement | Task(s) |
|---|---|
| (1) `GET /api/parties/{slug}/observe/ws` endpoint with auth handshake | 3, 4, 5 |
| (1) Proximity-scoped push using spec #02 helper, with snapshot/left synthesis | 6, 7 |
| (1) Last-sent cursor per socket | 6 |
| (2) Initial snapshot frame on subscribe | 4 |
| (3) Ping/pong heartbeat (20s ping, 30s timeout) | 8 |
| (4) Auth failure closes with code 4401 + reason JSON | 5 |
| (5) Multiple concurrent sockets per principal | 2, 6 |
| (6) Optimistic response on `/chat` | 9 |
| (6) Optimistic response on `/move` | 10 |
| (6) Optimistic response on `/react` | 11 |
| (7) Agent guide section for real-time agents | 12 |
| Frontend types updated | 13 |
| Final smoke test | 14 |

**Out of scope (do NOT touch):**
- A batched `/act` endpoint (spec #10 owns it).
- Module endpoints' optimistic responses (specs #04, #05, #06, #07 own their own endpoints and will follow the documented contract — this plan only adds the **doc note** in the agent guide).
- Frontend SDK / React hooks (spec #11).
- Wall-aware line-of-sight (out of scope per shared brief §5/6).
- Changing the proximity radius constant (spec #02 owns).

---

## File Structure

**Create:**
- `backend/app/observer_hub.py` — `PartyObserverHub`: per-socket cursor + proximity state; subscribes to `world.on_event(...)`.
- `backend/app/routes/observe_ws.py` — FastAPI WebSocket route.
- `backend/tests/test_observe_hub.py` — unit tests for the hub (proximity scoping, cursor advance, multi-socket per principal).
- `backend/tests/test_observe_ws_route.py` — integration tests for the WS endpoint (handshake, initial frame, push, heartbeat, 4401 close).
- `backend/tests/test_optimistic_responses.py` — round-trip tests for `/chat`, `/move`, `/react` returning event payloads.

**Modify:**
- `backend/app/store.py` — add `get_or_create_observer_hub(slug)` paralleling `get_or_create_hub`.
- `backend/app/main.py` — mount `observe_ws_routes.router`, wire dependency override.
- `backend/app/routes/party_actions.py:102-139` — `/chat`, `/move` responses include `event` payload.
- `backend/app/routes/reactions.py:32-53` — `/react` response includes `event` payload.
- `backend/app/routes/agent_guide.py` — add "real-time agents" section.
- `frontend/src/api/types.ts` — add `ObserveWsAuthFrame`, `ObserveWsInitialFrame`, `ObserveWsEventFrame`, `ObserveWsPing`/`Pong`, `ObserveWsProximitySnapshot`/`Left`; extend `ChatResponse`, `MoveResponse`, `ReactResponse` with the new `event` field.

**Assumed already-landed from spec #02 (DO NOT IMPLEMENT — reference only):**
- `PROXIMITY_RADIUS` constant in `app/world.py`.
- `PartyWorld.events_for(participant_id: str, since: int) -> dict` returning proximity-scoped events plus `proximity_snapshot`/`proximity_left` synthetic entries.
- A per-call helper `PartyWorld.visible_to(observer_id: str, event: Event) -> bool` (or equivalently named) used to decide if a single event should be pushed.

If your spec #02 implementation named these differently, fix the call sites in tasks 6 and 7 to match — do not rename their definitions here.

---

## Task 1: Confirm spec #02 helpers exist (no code change)

**Files:** none (read-only).

- [ ] **Step 1:** Run:

```bash
grep -n "PROXIMITY_RADIUS\|events_for\|visible_to\|_visible_to" backend/app/world.py
```

Expected: at least one match for each. If `events_for` and a `visible_to`-style helper do not exist, STOP and coordinate with the spec #02 owner — this plan depends on them. Do not re-implement proximity here.

- [ ] **Step 2:** Confirm `proximity_snapshot` / `proximity_left` synthetic frames are documented in `docs/superpowers/plans/feature-backlog-2026-05-26/02-*.md`. Note the frame shape used there — every subsequent task in this plan must emit the same shape.

(No commit; this is verification only.)

---

## Task 2: Hub skeleton — construction + per-socket state

**Files:**
- Create: `backend/app/observer_hub.py`
- Test: `backend/tests/test_observe_hub.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_observe_hub.py
from __future__ import annotations

import asyncio
import pytest

from app.events import Participant
from app.observer_hub import PartyObserverHub
from app.store import Store


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self, code: int | None = None) -> None:
        self.closed = True


def _seed(store: Store, name: str, x: float, y: float):
    sess = store.create_session(username=name, color="#ff6b9d")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    world.join(
        Participant(
            id=sess.session_id, kind="human", username=name,
            color="#ff6b9d", x=x, y=y, joined_at=0.0,
        )
    )
    return sess.session_id, world


@pytest.mark.asyncio
async def test_subscribe_tracks_socket_and_cursor():
    store = Store()
    pid, world = _seed(store, "Alice", 100.0, 100.0)
    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid, participant_id=pid)
    assert sock in hub.sockets
    assert hub.cursor_of(sock) == world.cursor
    hub.teardown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_observe_hub.py::test_subscribe_tracks_socket_and_cursor -x --tb=short`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.observer_hub'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/observer_hub.py
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
from app.world import PartyWorld


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
        # Used to synthesize proximity_left frames when a peer drops out.
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
        self.sockets[sock] = _SocketState(
            principal_key=principal_key,
            participant_id=participant_id,
            cursor=self.world.cursor,
        )

    def unsubscribe(self, sock: SocketLike) -> None:
        self.sockets.pop(sock, None)

    def cursor_of(self, sock: SocketLike) -> int:
        st = self.sockets.get(sock)
        return -1 if st is None else st.cursor

    def _on_event(self, event: Event) -> None:
        # Implemented in Task 6.
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_observe_hub.py::test_subscribe_tracks_socket_and_cursor -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/observer_hub.py backend/tests/test_observe_hub.py
git commit -m "feat(observe-ws): scaffold PartyObserverHub with per-socket cursor"
```

---

## Task 3: Store hook for observer hub

**Files:**
- Modify: `backend/app/store.py`
- Test: `backend/tests/test_observe_hub.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_observe_hub.py`:

```python
def test_store_returns_one_observer_hub_per_party():
    store = Store()
    hub1 = store.get_or_create_observer_hub("cream-terrazzo")
    hub2 = store.get_or_create_observer_hub("cream-terrazzo")
    assert hub1 is hub2
    assert store.get_or_create_observer_hub("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_observe_hub.py::test_store_returns_one_observer_hub_per_party -x --tb=short`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'get_or_create_observer_hub'`.

- [ ] **Step 3: Wire the store**

In `backend/app/store.py`:

Add the import near the others:

```python
from app.observer_hub import PartyObserverHub
```

In `Store.__init__`, after the `self._hubs` line, add:

```python
        self._observer_hubs: dict[str, PartyObserverHub] = {}
```

At the bottom of the class, add:

```python
    def get_or_create_observer_hub(self, slug: str) -> PartyObserverHub | None:
        if slug not in self._parties:
            return None
        if slug in self._observer_hubs:
            return self._observer_hubs[slug]
        world = self.get_or_create_world(slug)
        assert world is not None
        hub = PartyObserverHub(world)
        self._observer_hubs[slug] = hub
        return hub
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_observe_hub.py -x --tb=short`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/store.py backend/tests/test_observe_hub.py
git commit -m "feat(observe-ws): expose get_or_create_observer_hub on Store"
```

---

## Task 4: WS route — handshake + initial frame

**Files:**
- Create: `backend/app/routes/observe_ws.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_observe_ws_route.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_observe_ws_route.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.events import Participant
from app.store import Store


def _seed_alice(store: Store) -> str:
    sess = store.create_session(username="Alice", color="#ff6b9d")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    world.join(
        Participant(
            id=sess.session_id, kind="human", username="Alice",
            color="#ff6b9d", x=200.0, y=200.0, joined_at=0.0,
        )
    )
    return sess.session_id


def test_ws_handshake_returns_initial_snapshot(client: TestClient, store: Store):
    pid = _seed_alice(store)
    with client.websocket_connect("/api/parties/cream-terrazzo/observe/ws") as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": pid}})
        frame = ws.receive_json()
        assert frame["type"] == "initial"
        assert frame["room"]["slug"] == "cream-terrazzo"
        assert isinstance(frame["participants"], list)
        assert any(p["id"] == pid for p in frame["participants"])
        assert isinstance(frame["modules"], list)
        assert isinstance(frame["recent_chat"], list)
        assert isinstance(frame["cursor"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_observe_ws_route.py -x --tb=short`
Expected: FAIL — `WebSocketException`/404 (route does not exist).

- [ ] **Step 3: Implement the route**

```python
# backend/app/routes/observe_ws.py
"""Push WebSocket: /api/parties/{slug}/observe/ws.

Handshake:
  - server accept()s
  - client sends {"type":"auth","principal":{"kind":..., "id":...}}
  - server validates -> sends {"type":"initial", ...} -> subscribes
  - on auth failure: server closes with code 4401, reason JSON
    {"error":"unauthorized"}

After subscribe:
  - server pushes per-event frames {"type":"event","event":{...},"cursor":N}
  - proximity_snapshot / proximity_left synthetic frames same as /observe
  - heartbeat: server sends {"type":"ping"} every 20s; client must
    reply {"type":"pong"} within 30s or socket closes

Multiple concurrent sockets per principal are permitted (one per tab/
agent process) — each gets its own cursor and proximity tracker.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.dm import principal_key
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter()


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


_UNAUTHORIZED_CODE = 4401


def _resolve_auth(store: Store, frame: object):
    if not isinstance(frame, dict) or frame.get("type") != "auth":
        return None, "invalid_auth_frame"
    raw = frame.get("principal")
    if not isinstance(raw, dict):
        return None, "invalid_principal"
    try:
        principal = Principal(**raw)
    except ValidationError:
        return None, "invalid_principal"
    try:
        resolved = resolve_principal(store, principal)
    except Exception:
        return None, "principal_unknown"
    return resolved, None


def _room_view(party) -> dict:
    # Mirrors party_actions._room_view; duplicated here to avoid an import
    # cycle between routes modules. If kept in sync becomes painful, lift
    # this to app/realtime.py.
    w = party.worldSize
    return {
        "slug": party.slug,
        "name": party.name,
        "worldSize": {"width": w.width, "height": w.height},
        "zones": [
            {
                "id": z.id, "label": z.label,
                "x": z.x, "y": z.y, "width": z.width, "height": z.height,
                "centerX": (z.x + z.width / 2.0) / 100.0 * w.width,
                "centerY": (z.y + z.height / 2.0) / 100.0 * w.height,
            }
            for z in party.zones
        ],
        "walls": [
            {"x": wl.x, "y": wl.y, "width": wl.width, "height": wl.height}
            for wl in party.room.walls
        ],
        "music": party.music.label,
        "modules": [
            {
                "id": m.id, "kind": m.kind,
                **(
                    {"x": m.x, "y": m.y, "w": m.w, "h": m.h}
                    if m.kind in ("stickynotes", "drawboard") else {}
                ),
                **({"preset": m.preset} if m.kind == "lighting" else {}),
            }
            for m in party.modules
        ],
    }


async def _close_unauthorized(ws: WebSocket, reason: str = "unauthorized") -> None:
    payload = json.dumps({"error": reason})
    try:
        await ws.close(code=_UNAUTHORIZED_CODE, reason=payload)
    except Exception:
        pass


@router.websocket("/api/parties/{slug}/observe/ws")
async def observe_ws(
    websocket: WebSocket,
    slug: str,
    store: Store = Depends(_store_dep),
) -> None:
    party = store.get_party(slug)
    if party is None:
        await websocket.accept()
        await _close_unauthorized(websocket, reason="party_not_found")
        return

    await websocket.accept()
    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception:
        await _close_unauthorized(websocket, reason="invalid_auth_frame")
        return

    resolved, reason = _resolve_auth(store, frame)
    if resolved is None:
        await _close_unauthorized(websocket, reason=reason or "unauthorized")
        return

    world = store.get_or_create_world(slug)
    assert world is not None
    if resolved.id not in world.participants:
        await _close_unauthorized(websocket, reason="not_in_party")
        return

    snap = world.snapshot()
    initial = {
        "type": "initial",
        "room": _room_view(party),
        "participants": snap["participants"],
        "modules": snap["modules"],
        "lighting": snap["lighting"],
        "active_reactions": snap["active_reactions"],
        "recent_chat": world.recent_chat(),
        "cursor": snap["cursor"],
    }
    await websocket.send_json(initial)

    hub = store.get_or_create_observer_hub(slug)
    assert hub is not None
    key = principal_key(resolved)
    hub.subscribe(
        websocket, principal_key=key, participant_id=resolved.id
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket)
```

- [ ] **Step 4: Mount the route**

In `backend/app/main.py` add the import alongside the others:

```python
from app.routes import observe_ws as observe_ws_routes
```

After the existing `inbox_ws_routes` dependency override line add:

```python
app.dependency_overrides[observe_ws_routes._store_dep] = get_store
```

After `app.include_router(inbox_ws_routes.router)` add:

```python
app.include_router(observe_ws_routes.router)
```

- [ ] **Step 5: Wire conftest**

In `backend/tests/conftest.py`, alongside the other `from app.routes import ...` lines add:

```python
from app.routes import observe_ws as observe_ws_routes
```

And inside the `client` fixture, alongside the other overrides, add:

```python
    app.dependency_overrides[observe_ws_routes._store_dep] = lambda: store
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_observe_ws_route.py -x --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/observe_ws.py backend/app/main.py backend/tests/conftest.py backend/tests/test_observe_ws_route.py
git commit -m "feat(observe-ws): handshake + initial snapshot frame"
```

---

## Task 5: WS route — auth failures close with 4401

**Files:**
- Test: `backend/tests/test_observe_ws_route.py`

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_ws_unknown_principal_closes_4401(client: TestClient):
    with client.websocket_connect(
        "/api/parties/cream-terrazzo/observe/ws"
    ) as ws:
        ws.send_json(
            {"type": "auth", "principal": {"kind": "human", "id": "nope"}}
        )
        # The websocket_connect contextmanager will surface close on
        # the next receive; assert via try/except.
        with pytest.raises(Exception) as exc_info:
            ws.receive_json()
        # Starlette TestClient surfaces close code on WebSocketDisconnect.
        from starlette.websockets import WebSocketDisconnect as SWD
        assert isinstance(exc_info.value, SWD)
        assert exc_info.value.code == 4401


def test_ws_malformed_auth_frame_closes_4401(client: TestClient):
    with client.websocket_connect(
        "/api/parties/cream-terrazzo/observe/ws"
    ) as ws:
        ws.send_json({"type": "garbage"})
        with pytest.raises(Exception) as exc_info:
            ws.receive_json()
        from starlette.websockets import WebSocketDisconnect as SWD
        assert isinstance(exc_info.value, SWD)
        assert exc_info.value.code == 4401


def test_ws_unknown_slug_closes_4401(client: TestClient):
    with client.websocket_connect(
        "/api/parties/no-such-party/observe/ws"
    ) as ws:
        with pytest.raises(Exception) as exc_info:
            ws.receive_json()
        from starlette.websockets import WebSocketDisconnect as SWD
        assert isinstance(exc_info.value, SWD)
        assert exc_info.value.code == 4401
```

- [ ] **Step 2: Run tests to verify they pass**

The route (Task 4) already implements 4401 closure. Run:

```bash
cd backend && pytest tests/test_observe_ws_route.py -x --tb=short
```

Expected: all 4 tests pass. If any fail because the test client surfaces something other than a code on `WebSocketDisconnect`, inspect the actual exception with `print(repr(exc_info.value))` and adjust the assertion — but the **route behavior** (calling `close(code=4401, reason=...)`) is correct and must not change.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_observe_ws_route.py
git commit -m "test(observe-ws): assert 4401 close on auth failures"
```

---

## Task 6: Hub — push events with proximity scoping + cursor advance

**Files:**
- Modify: `backend/app/observer_hub.py`
- Test: `backend/tests/test_observe_hub.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_observe_hub.py`:

```python
@pytest.mark.asyncio
async def test_event_pushed_with_cursor_when_visible(monkeypatch):
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 110.0, 110.0)  # within radius

    # Spec #02 helper: returns True iff event is visible to observer.
    # If your spec #02 named this differently, edit this assertion.
    assert hasattr(world, "visible_to")

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    ev = world.chat(pid_b, "hello")
    await hub.drain()

    assert any(f.get("type") == "event" for f in sock.sent)
    pushed = [f for f in sock.sent if f.get("type") == "event"]
    assert pushed[-1]["cursor"] == ev.seq
    assert pushed[-1]["event"]["type"] == "chat"
    assert pushed[-1]["event"]["text"] == "hello"
    assert hub.cursor_of(sock) == ev.seq
    hub.teardown()


@pytest.mark.asyncio
async def test_event_not_pushed_when_out_of_proximity():
    store = Store()
    pid_a, world = _seed(store, "Alice", 0.0, 0.0)
    pid_b, _ = _seed(store, "Bob", 5000.0, 5000.0)  # far away

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    world.chat(pid_b, "hi from afar")
    await hub.drain()

    # No "event" frames should reach Alice for Bob's chat.
    event_frames = [f for f in sock.sent if f.get("type") == "event"]
    assert event_frames == []
    hub.teardown()


@pytest.mark.asyncio
async def test_multiple_sockets_per_principal_each_get_event():
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 110.0, 110.0)

    hub = PartyObserverHub(world)
    s1, s2 = FakeSocket(), FakeSocket()
    hub.subscribe(s1, principal_key="human:" + pid_a, participant_id=pid_a)
    hub.subscribe(s2, principal_key="human:" + pid_a, participant_id=pid_a)

    world.chat(pid_b, "hey both")
    await hub.drain()

    for s in (s1, s2):
        evs = [f for f in s.sent if f.get("type") == "event"]
        assert len(evs) == 1
        assert evs[0]["event"]["text"] == "hey both"
    hub.teardown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_observe_hub.py -x --tb=short`
Expected: FAIL on the three new tests because `_on_event` is a no-op.

- [ ] **Step 3: Implement `_on_event` + dispatch helpers**

Replace the `_on_event` stub and add helpers in `backend/app/observer_hub.py`:

```python
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

    def _on_event(self, event: Event) -> None:
        if not self.sockets:
            return
        # Snapshot to allow concurrent unsubscribe during dispatch.
        for sock, state in list(self.sockets.items()):
            try:
                visible = self.world.visible_to(state.participant_id, event)
            except Exception:
                # If the helper rejects (e.g. observer left mid-event),
                # drop the socket conservatively rather than spam.
                visible = False
            if not visible:
                continue
            payload = self._serialise(event)
            state.cursor = event.seq
            self._dispatch(self._send_or_drop(sock, payload))

    async def _send_or_drop(self, sock: SocketLike, payload: dict) -> None:
        try:
            await sock.send_json(payload)
        except Exception:
            self.sockets.pop(sock, None)
            try:
                await sock.close()
            except Exception:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_observe_hub.py -x --tb=short`
Expected: all observer-hub tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/observer_hub.py backend/tests/test_observe_hub.py
git commit -m "feat(observe-ws): push proximity-scoped events with per-socket cursor"
```

---

## Task 7: Hub — synthesize proximity_snapshot / proximity_left frames on movement

**Files:**
- Modify: `backend/app/observer_hub.py`
- Test: `backend/tests/test_observe_hub.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
@pytest.mark.asyncio
async def test_peer_entering_proximity_emits_snapshot():
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 9000.0, 9000.0)

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    # Bob walks into Alice's proximity radius.
    world.move(pid_b, 110.0, 110.0)
    await hub.drain()

    types = [f.get("type") for f in sock.sent]
    assert "proximity_snapshot" in types
    snap = next(f for f in sock.sent if f["type"] == "proximity_snapshot")
    assert snap["participant_id"] == pid_b


@pytest.mark.asyncio
async def test_peer_leaving_proximity_emits_left():
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 110.0, 110.0)

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    # Hub seeded with current snapshot of peers in proximity.
    state = hub.sockets[sock]
    state.in_proximity.add(pid_b)

    # Bob walks far away.
    world.move(pid_b, 9000.0, 9000.0)
    await hub.drain()

    types = [f.get("type") for f in sock.sent]
    assert "proximity_left" in types
    left = next(f for f in sock.sent if f["type"] == "proximity_left")
    assert left["participant_id"] == pid_b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_observe_hub.py -x --tb=short`
Expected: the two new tests fail.

- [ ] **Step 3: Extend `_on_event` to maintain `in_proximity`**

In `observer_hub.py`, replace `_on_event` with:

```python
    def _initial_in_proximity(self, observer_id: str) -> set[str]:
        """Set of peer ids currently within PROXIMITY_RADIUS of observer."""
        try:
            return self.world.peers_in_proximity(observer_id)  # spec #02
        except AttributeError:
            # Fallback: derive from participants + radius constant.
            from app.world import PROXIMITY_RADIUS  # spec #02 constant
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

    def _refresh_proximity(self, state: "_SocketState") -> tuple[set[str], set[str]]:
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
            # Initial-population: lazily fill in_proximity on first event
            # so a subscriber that joined mid-world starts from current truth.
            if not state.in_proximity:
                state.in_proximity = self._initial_in_proximity(state.participant_id)
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
```

If spec #02 ships frame shapes for `proximity_snapshot`/`proximity_left` that differ, update the dict literals above to match — keep the keys spec #02 defined.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_observe_hub.py -x --tb=short`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/observer_hub.py backend/tests/test_observe_hub.py
git commit -m "feat(observe-ws): synthesize proximity_snapshot/left frames"
```

---

## Task 8: Heartbeat — 20s ping, 30s pong-timeout

**Files:**
- Modify: `backend/app/routes/observe_ws.py`
- Test: `backend/tests/test_observe_ws_route.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_observe_ws_route.py`:

```python
def test_ws_emits_ping_after_interval(client: TestClient, store: Store, monkeypatch):
    # Shrink interval so the test is fast.
    from app.routes import observe_ws as obs
    monkeypatch.setattr(obs, "HEARTBEAT_INTERVAL", 0.05)
    monkeypatch.setattr(obs, "HEARTBEAT_TIMEOUT", 1.0)

    pid = _seed_alice(store)
    with client.websocket_connect(
        "/api/parties/cream-terrazzo/observe/ws"
    ) as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": pid}})
        _initial = ws.receive_json()
        # Within 0.5s we should see at least one ping.
        seen_ping = False
        for _ in range(20):
            frame = ws.receive_json()
            if frame.get("type") == "ping":
                seen_ping = True
                ws.send_json({"type": "pong"})
                break
        assert seen_ping


def test_ws_closes_when_pong_overdue(client: TestClient, store: Store, monkeypatch):
    from app.routes import observe_ws as obs
    monkeypatch.setattr(obs, "HEARTBEAT_INTERVAL", 0.05)
    monkeypatch.setattr(obs, "HEARTBEAT_TIMEOUT", 0.1)

    pid = _seed_alice(store)
    from starlette.websockets import WebSocketDisconnect as SWD
    with pytest.raises(SWD):
        with client.websocket_connect(
            "/api/parties/cream-terrazzo/observe/ws"
        ) as ws:
            ws.send_json({"type": "auth", "principal": {"kind": "human", "id": pid}})
            _initial = ws.receive_json()
            # Never reply to ping. The server should drop us.
            for _ in range(50):
                ws.receive_json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_observe_ws_route.py -k heartbeat -x --tb=short` — both fail (no ping ever sent).

- [ ] **Step 3: Implement heartbeat + concurrent receive loop**

Replace the receive-loop section in `backend/app/routes/observe_ws.py` (everything after `hub.subscribe(...)` down to the `finally` block). Also add module-level constants near the top:

```python
HEARTBEAT_INTERVAL = 20.0  # seconds between pings
HEARTBEAT_TIMEOUT = 30.0   # seconds without pong before close
```

Add this import at the top:

```python
import asyncio
import time
```

And replace the post-subscribe section with:

```python
    last_pong = time.monotonic()

    async def _heartbeat() -> None:
        nonlocal last_pong
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    return
                if time.monotonic() - last_pong > HEARTBEAT_TIMEOUT:
                    try:
                        await websocket.close(code=1011, reason="pong_timeout")
                    except Exception:
                        pass
                    return
        except asyncio.CancelledError:
            return

    async def _read_loop() -> None:
        nonlocal last_pong
        try:
            while True:
                msg = await websocket.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "pong":
                    last_pong = time.monotonic()
        except WebSocketDisconnect:
            return
        except Exception:
            return

    hb = asyncio.create_task(_heartbeat())
    rl = asyncio.create_task(_read_loop())
    try:
        done, pending = await asyncio.wait(
            {hb, rl}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        for t in pending:
            try:
                await t
            except Exception:
                pass
    finally:
        hub.unsubscribe(websocket)
        try:
            await websocket.close()
        except Exception:
            pass
```

Remove the prior `try/except WebSocketDisconnect / finally hub.unsubscribe` block — the new code owns lifecycle.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_observe_ws_route.py -x --tb=short`
Expected: all observe-ws route tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/observe_ws.py backend/tests/test_observe_ws_route.py
git commit -m "feat(observe-ws): 20s ping / 30s pong-timeout heartbeat"
```

---

## Task 9: Optimistic response on `/chat`

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Create: `backend/tests/test_optimistic_responses.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_optimistic_responses.py
from __future__ import annotations

from fastapi.testclient import TestClient

from app.events import Participant
from app.store import Store


def _seed(store: Store, name: str = "Alice") -> str:
    sess = store.create_session(username=name, color="#ff6b9d")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    world.join(
        Participant(
            id=sess.session_id, kind="human", username=name,
            color="#ff6b9d", x=200.0, y=200.0, joined_at=0.0,
        )
    )
    return sess.session_id


def test_chat_response_includes_full_event_payload(client: TestClient, store: Store):
    pid = _seed(store)
    resp = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "human", "id": pid}, "text": "hello"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "event" in body
    ev = body["event"]
    assert ev["type"] == "chat"
    assert ev["text"] == "hello"
    assert ev["participant_id"] == pid
    assert ev["actor_id"] == pid
    assert ev["actor_username"] == "Alice"
    assert ev["actor_kind"] == "human"
    assert isinstance(ev["seq"], int)
    assert isinstance(ev["at"], float)
    assert body["cursor"] == ev["seq"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_optimistic_responses.py::test_chat_response_includes_full_event_payload -x --tb=short`
Expected: FAIL — `"event" not in body`.

- [ ] **Step 3: Update the chat handler**

In `backend/app/routes/party_actions.py`, replace the body of `chat(...)` (currently lines 122-139) with:

```python
@router.post("/{slug}/chat")
def chat(
    body: ChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.chat(resolved.id, body.text)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(INVALID_CHAT_TEXT, message=str(exc)),
        )
    return {"event": ev.model_dump(), "cursor": world.cursor}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_optimistic_responses.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Verify no existing test depends on the old (sparse) shape**

```bash
cd backend && pytest tests/ -x --tb=short -q
```

Expected: all green. If `test_party_action_routes.py` or any other test asserts the chat response shape is `{"cursor": ...}` only, update those assertions to either include the new `event` key or accept it — DO NOT revert the optimistic shape.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_optimistic_responses.py
git commit -m "feat(optimistic): /chat returns full event payload"
```

---

## Task 10: Optimistic response on `/move`

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Modify: `backend/tests/test_optimistic_responses.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_move_response_includes_full_event_payload(client: TestClient, store: Store):
    pid = _seed(store)
    resp = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": pid}, "x": 250.0, "y": 260.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "event" in body
    ev = body["event"]
    assert ev["type"] == "move"
    assert ev["participant_id"] == pid
    assert ev["actor_id"] == pid
    # Move events store post-slide x/y; we don't assert exact values, just shape.
    assert isinstance(ev["x"], float)
    assert isinstance(ev["y"], float)
    assert isinstance(ev["seq"], int)
    # Top-level convenience fields preserved for backwards compat.
    assert body["x"] == ev["x"]
    assert body["y"] == ev["y"]
    assert "zone" in body
    assert body["cursor"] == ev["seq"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_optimistic_responses.py::test_move_response_includes_full_event_payload -x --tb=short`
Expected: FAIL — `"event" not in body`.

- [ ] **Step 3: Update the move handler**

Replace `move(...)` in `backend/app/routes/party_actions.py` (currently lines 102-119) with:

```python
@router.post("/{slug}/move")
def move(
    body: MoveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.move(resolved.id, body.x, body.y)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    return {
        "event": ev.model_dump(),
        "x": ev.x,
        "y": ev.y,
        "zone": world.derive_zone(ev.x, ev.y),
        "cursor": world.cursor,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_optimistic_responses.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Verify full suite still green**

```bash
cd backend && pytest tests/ -x --tb=short -q
```

Update any older tests that asserted only the top-level fields if they break (they should still pass since the existing keys are preserved).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_optimistic_responses.py
git commit -m "feat(optimistic): /move returns full event payload"
```

---

## Task 11: Optimistic response on `/react`

**Files:**
- Modify: `backend/app/routes/reactions.py`
- Modify: `backend/tests/test_optimistic_responses.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_react_response_includes_full_event_payload(client: TestClient, store: Store):
    pid = _seed(store)
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": pid}, "emoji": "wave"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "event" in body
    ev = body["event"]
    assert ev["type"] == "reaction"
    assert ev["actor_id"] == pid
    assert ev["actor_username"] == "Alice"
    assert ev["emoji"] == body["emoji"]
    assert body["expires_at"] == ev["expires_at"]
    assert body["cursor"] == ev["seq"]
```

If `"wave"` is not in `REACTION_EMOJI_ALLOWLIST`, replace with any allow-listed value — check `app/validation.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_optimistic_responses.py::test_react_response_includes_full_event_payload -x --tb=short`
Expected: FAIL — `"event" not in body`.

- [ ] **Step 3: Update the react handler**

In `backend/app/routes/reactions.py`, replace the `return` at the bottom of `react(...)` (line 53) with:

```python
    return {
        "event": ev.model_dump(),
        "emoji": ev.emoji,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_optimistic_responses.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Verify full suite still green**

```bash
cd backend && pytest tests/ -x --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/reactions.py backend/tests/test_optimistic_responses.py
git commit -m "feat(optimistic): /react returns full event payload"
```

---

## Task 12: Agent guide — real-time agents section

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Test: `backend/tests/test_agent_guide_content.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_agent_guide_content.py`:

```python
def test_agent_guide_documents_push_websocket(client):
    resp = client.get("/api/agent-guide")
    assert resp.status_code == 200
    body = resp.text
    for needle in (
        "real-time agents",
        "/observe/ws",
        '"type":"auth"',
        '"type":"initial"',
        '"type":"event"',
        '"type":"ping"',
        '"type":"pong"',
        "proximity_snapshot",
        "proximity_left",
        "4401",
        "reconnect",
        "cursor",
    ):
        assert needle in body, f"agent guide missing: {needle}"


def test_agent_guide_documents_optimistic_responses(client):
    resp = client.get("/api/agent-guide")
    body = resp.text
    for needle in (
        "Optimistic responses",
        '"event"',
        "any new POST that emits an event must return the event payload",
    ):
        assert needle in body, f"agent guide missing: {needle}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_guide_content.py::test_agent_guide_documents_push_websocket -x --tb=short`
Expected: FAIL — needles missing.

- [ ] **Step 3: Add the section**

In `backend/app/routes/agent_guide.py`, locate the markdown string returned by the route and append the following section near the end (before any trailing closing marker — adapt to the file's existing structure):

````markdown
## Real-time agents (push channel)

Polling `/observe` every 4-5s is fine for casual agents, but for snappy
behavior subscribe to the push channel.

### WebSocket: `GET /api/parties/{slug}/observe/ws`

1. Open the WebSocket.
2. Send an `auth` frame as your first message:
   ```json
   {"type":"auth","principal":{"kind":"agent","id":"<your agent_id>"}}
   ```
3. The server replies with an `initial` frame — same shape as the first
   `/observe` poll, so you can render without a separate REST call:
   ```json
   {
     "type":"initial",
     "room":{...},
     "participants":[...],
     "modules":[...],
     "lighting":"day",
     "active_reactions":[],
     "recent_chat":[...],
     "cursor": 42
   }
   ```
4. After that, the server pushes per-event frames as they happen, scoped
   to your proximity radius (peers near you only):
   ```json
   {"type":"event","event":{"type":"chat","seq":43,"...":"..."},"cursor":43}
   ```
5. When a peer walks into or out of your radius you get synthetic frames:
   ```json
   {"type":"proximity_snapshot","participant_id":"<id>","participant":{...},"cursor":44}
   {"type":"proximity_left","participant_id":"<id>","cursor":45}
   ```

### Heartbeat

Every 20 seconds the server sends `{"type":"ping"}`. You MUST reply
`{"type":"pong"}` within 30 seconds or the socket is closed. A trivial
echo loop satisfies this.

### Authentication failures

If your `principal` is unknown or the auth frame is malformed, the
server closes with WebSocket close code **4401** and reason JSON
`{"error":"<reason>"}` (e.g. `unauthorized`, `principal_unknown`,
`not_in_party`). Re-register before reconnecting.

### Reconnection with cursor-resume

Each push frame carries a `cursor` value. If your socket drops:

1. Reconnect to `/observe/ws` and complete the `auth` handshake.
2. The `initial` frame's `cursor` tells you the server's current state.
3. For events you may have missed between the last cursor you saw and
   the new `initial.cursor`, fetch them once with
   `GET /api/parties/{slug}/observe?since=<last_cursor>`.
4. Resume processing push frames.

Multiple concurrent sockets per principal are allowed (one per tab or
agent process). Each gets its own cursor and proximity tracker.

## Optimistic responses

POST endpoints that emit a world event return the event payload in the
response so you don't have to poll `/observe` to confirm:

```json
POST /api/parties/{slug}/chat
{"principal":{...},"text":"hi"}

200 OK
{
  "event": {"type":"chat","seq":17,"participant_id":"...","text":"hi","actor_id":"...","actor_username":"...","actor_kind":"agent","at":1716700000.1},
  "cursor": 17
}
```

`/move` and `/react` follow the same pattern (also `/gesture`,
`/proposals`, module endpoints once specs #04-#07 land). Rule of thumb:
**any new POST that emits an event must return the event payload** under
the `event` key in its response body.
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_agent_guide_content.py -x --tb=short`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "docs(agent-guide): document /observe/ws + optimistic responses"
```

---

## Task 13: Frontend types

**Files:**
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Locate the existing response types**

```bash
grep -n "ChatResponse\|MoveResponse\|ReactResponse\|ObserveSnapshot" frontend/src/api/types.ts
```

If these don't exist, locate equivalent type names — but DO NOT invent file paths. If `frontend/src/api/types.ts` doesn't exist, skip this task and note it in the final smoke task.

- [ ] **Step 2: Add the new types**

Append (and edit existing response types in place):

```typescript
// --- Observe push channel ---
export type ObserveWsAuthFrame = {
  type: "auth";
  principal: { kind: "human" | "agent"; id: string };
};

export type ObserveWsInitialFrame = {
  type: "initial";
  room: unknown; // matches the snapshot's `room` payload
  participants: unknown[];
  modules: unknown[];
  lighting: string;
  active_reactions: unknown[];
  recent_chat: unknown[];
  cursor: number;
};

export type ObserveWsEventFrame = {
  type: "event";
  event: { type: string; seq: number; at: number; [k: string]: unknown };
  cursor: number;
};

export type ObserveWsProximitySnapshot = {
  type: "proximity_snapshot";
  participant_id: string;
  participant: unknown;
  cursor: number;
};

export type ObserveWsProximityLeft = {
  type: "proximity_left";
  participant_id: string;
  cursor: number;
};

export type ObserveWsPing = { type: "ping" };
export type ObserveWsPong = { type: "pong" };

export type ObserveWsFrame =
  | ObserveWsInitialFrame
  | ObserveWsEventFrame
  | ObserveWsProximitySnapshot
  | ObserveWsProximityLeft
  | ObserveWsPing;
```

In the existing `ChatResponse`, `MoveResponse`, `ReactResponse` definitions, add an `event:` field (use the existing event-payload type if one exists in this file; otherwise type as `{ type: string; seq: number; [k: string]: unknown }`).

- [ ] **Step 3: Run frontend type-check**

```bash
cd frontend && npm run typecheck 2>&1 | tail -30
```

Expected: no new errors introduced. If existing consumers of `ChatResponse` etc. now error because they don't destructure `event`, that's fine — adding a field is backwards-compatible.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "types(frontend): add observe-ws frame types + event field on POST responses"
```

---

## Task 14: Manual smoke + full-suite verification

**Files:** none (read-only).

- [ ] **Step 1: Run the full backend test suite**

```bash
cd backend && pytest tests/ -x --tb=short
```

Expected: all green. Investigate any failure before claiming completion — do NOT skip or `xfail` tests.

- [ ] **Step 2: Manual smoke (optional, requires running server)**

Open two terminals:

Terminal A — start server:
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

Terminal B — register and connect:
```bash
# 1. Register a human session
curl -s -X POST http://localhost:8000/api/session \
  -H 'content-type: application/json' \
  -d '{"username":"Smoke","color":"#ff6b9d"}'
# Note the session_id from the response, call it $SID.

# 2. Join the party
curl -s -X POST http://localhost:8000/api/parties/cream-terrazzo/join \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"}}"

# 3. Open the push WS (using websocat or similar)
websocat ws://localhost:8000/api/parties/cream-terrazzo/observe/ws
> {"type":"auth","principal":{"kind":"human","id":"<SID>"}}
# Expect: initial frame, then live event frames as you POST /chat.
```

- [ ] **Step 3: Verify optimistic responses by hand**

```bash
curl -s -X POST http://localhost:8000/api/parties/cream-terrazzo/chat \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"},\"text\":\"smoke\"}" | jq
```

Expected: response body contains `event.type == "chat"`, `event.seq`, `event.actor_*`, and `cursor == event.seq`.

- [ ] **Step 4: No commit (verification only)**

If any step revealed a bug, fix it under TDD (add a failing test, fix, commit) before declaring done.

---

## Self-review notes

- **Spec coverage:** every spec line maps to a task (see Spec → Task map). Auth-frame failure paths, heartbeat timing, multi-socket-per-principal, proximity snapshot/left synthesis, initial frame shape, and optimistic `/chat` `/move` `/react` are all covered with their own TDD step.
- **Out-of-scope guardrails:** Task 12's agent-guide note explicitly says future POST event-emitters must return `event` — but no task here modifies endpoints owned by other specs (gestures #05, proposals #06, music #07, module chat #04). Their specs adopt the contract from the start.
- **Reused vs duplicated:** proximity decisions reuse `world.visible_to(...)` and `world.peers_in_proximity(...)` from spec #02. The fallback `PROXIMITY_RADIUS` computation in `_initial_in_proximity` is purely defensive and only runs if spec #02's helper doesn't exist — strip it once spec #02 is confirmed merged.
- **Type consistency:** `seq`/`cursor` are integers everywhere; `event` payloads are `model_dump()` of the existing Pydantic `Event` union (no new shape introduced).
- **Frequent commits:** one commit per task (14 commits total).

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/feature-backlog-2026-05-26/09-push-and-optimistic-responses.md`.** (Skipping execution-mode choice per coordination prompt — this plan is one of 11 in a round and the orchestrator picks execution mode.)
