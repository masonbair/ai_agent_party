# Phase 4 — Multi-User Realtime Plan

> Use superpowers:subagent-driven-development to execute this plan task-by-task.

**Goal:** Push world events over a WebSocket so every client sees joins/leaves/moves/chats in real time. Render all participants in the party space.

**Spec:** `docs/superpowers/specs/2026-05-12-phase4-multiplayer-design.md`

**Hard precondition:** Phase 3 (`feat/phase3-agent-api`) must be merged to the working branch *before* this plan begins. Phase 4 imports `PartyWorld`, `Participant`, the event types, and the party-action endpoints from Phase 3. If you start tasks before Phase 3 has merged, the imports won't resolve.

**Tech additions:**
- Backend: `fastapi`'s built-in WebSocket support (no new deps).
- Frontend: native `WebSocket` (no new deps).
- Tests: `TestClient.websocket_connect` (already in `httpx`/`starlette`).

---

## Task 0: Verify preconditions

**Files:** none.

- [ ] **Step 1: Confirm Phase 3 is merged.** Run `git log --oneline | head -20` and look for commits referencing agent endpoints / `PartyWorld`. If not present, **stop** and surface that to the user.

- [ ] **Step 2: Confirm all tests still pass.**
  Run `cd backend && source .venv/bin/activate && pytest -q` and `cd frontend && npm test`. Both green.

- [ ] **Step 3: Confirm the Phase 3 module surface.** Open `backend/app/world.py` and confirm `PartyWorld` exists with `append_event` and an `events` log. Open `backend/app/events.py` and confirm `JoinEvent`, `LeaveEvent`, `MoveEvent`, `ChatEvent`. If the actual module names differ (Phase 3 may have settled on different filenames), adjust each task's imports accordingly — the *behaviour* contract from the Phase 3 spec is what matters.

No commit.

---

## Task 1: `PartyWorld.on_event` callback registry

**Files:**
- Modify: `backend/app/world.py`
- Modify: `backend/tests/test_world.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_world.py`:

```python
from app.events import MoveEvent
from app.world import PartyWorld


def test_on_event_callback_is_invoked_on_append():
    world = PartyWorld(party_slug="cream-terrazzo", world_width=800, world_height=500)
    received = []
    world.on_event(received.append)
    # Drive a state change that emits a MoveEvent.
    # (Phase 3 makes this happen via .move(); use whatever method the world exposes.)
    p = world.join(participant_id="p1", username="alice", color="#ff6b9d", kind="human")
    world.move(participant_id=p.id, x=300, y=200)
    move_events = [e for e in received if isinstance(e, MoveEvent)]
    assert len(move_events) == 1
    assert move_events[0].x == 300 and move_events[0].y == 200


def test_on_event_supports_multiple_callbacks_and_unregister():
    world = PartyWorld(party_slug="cream-terrazzo", world_width=800, world_height=500)
    a, b = [], []
    unsub = world.on_event(a.append)
    world.on_event(b.append)
    world.join(participant_id="p1", username="alice", color="#ff6b9d", kind="human")
    assert len(a) == 1 and len(b) == 1
    unsub()  # returned by on_event
    world.join(participant_id="p2", username="bob", color="#4dd0e1", kind="human")
    assert len(a) == 1  # unsubscribed
    assert len(b) == 2
```

If `PartyWorld`'s constructor or method signatures differ from this guess, adjust the test to match the real shape (do *not* invent new methods).

- [ ] **Step 2: Verify failure.** `cd backend && source .venv/bin/activate && pytest tests/test_world.py -v` — the two new tests fail with `AttributeError: 'PartyWorld' object has no attribute 'on_event'`.

- [ ] **Step 3: Implement.**

In `backend/app/world.py`, add a callback registry on `PartyWorld`:

```python
from typing import Callable

# Inside PartyWorld.__init__:
self._listeners: list[Callable[[Event], None]] = []

def on_event(self, callback: Callable[[Event], None]) -> Callable[[], None]:
    """Register a callback fired synchronously after each event is appended.
    Returns an `unsubscribe` callable that removes the callback."""
    self._listeners.append(callback)
    def _unsub() -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)
    return _unsub
```

Find the existing `append_event` (or whatever Phase 3 named it) and add **after** the event lands in the log:

```python
for cb in list(self._listeners):
    try:
        cb(event)
    except Exception:
        # A misbehaving listener must never break world bookkeeping.
        pass
```

The `list(self._listeners)` snapshot makes it safe for a listener to unsubscribe itself during dispatch.

- [ ] **Step 4: Verify it passes.** Same pytest command as Step 2. Both new tests pass; all prior tests still pass.

- [ ] **Step 5: Commit.**

```bash
git add backend/app/world.py backend/tests/test_world.py
git commit -m "feat(backend): PartyWorld on_event callback registry"
```

---

## Task 2: `PartyWorldHub` — per-party subscriber set + broadcast

**Files:**
- Create: `backend/app/realtime.py`
- Create: `backend/tests/test_realtime.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_realtime.py`:

```python
import asyncio
import pytest

from app.events import JoinEvent
from app.realtime import PartyWorldHub
from app.world import PartyWorld


class FakeSocket:
    def __init__(self, fail_on: int | None = None):
        self.sent: list[dict] = []
        self.closed = False
        self._fail_on = fail_on

    async def send_json(self, payload: dict) -> None:
        if self._fail_on is not None and len(self.sent) == self._fail_on:
            raise RuntimeError("simulated broken pipe")
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_hub_broadcasts_to_subscribers():
    world = PartyWorld(party_slug="cream-terrazzo", world_width=800, world_height=500)
    hub = PartyWorldHub(world)
    sock = FakeSocket()
    hub.subscribe(sock)
    world.join(participant_id="p1", username="alice", color="#ff6b9d", kind="human")
    await asyncio.sleep(0)  # let pending broadcasts drain
    await hub.drain()
    assert len(sock.sent) == 1
    assert sock.sent[0]["type"] == "event"
    assert sock.sent[0]["event"]["type"] == "join"


@pytest.mark.asyncio
async def test_hub_drops_misbehaving_subscriber():
    world = PartyWorld(party_slug="cream-terrazzo", world_width=800, world_height=500)
    hub = PartyWorldHub(world)
    good, bad = FakeSocket(), FakeSocket(fail_on=0)
    hub.subscribe(good)
    hub.subscribe(bad)
    world.join(participant_id="p1", username="alice", color="#ff6b9d", kind="human")
    await hub.drain()
    assert bad.closed
    assert bad not in hub.subscribers
    assert good in hub.subscribers
    assert len(good.sent) == 1
```

Add `pytest-asyncio` to `backend/pyproject.toml` dev dependencies if not already present:

```toml
[project.optional-dependencies]
dev = [
  "pytest==8.3.3",
  "httpx==0.27.2",
  "pytest-asyncio==0.24.0",
]
```

…and to the pytest section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Install + verify failure.**

```bash
cd backend && source .venv/bin/activate && pip install -e ".[dev]"
pytest tests/test_realtime.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.realtime'`.

- [ ] **Step 3: Implement.**

Create `backend/app/realtime.py`:

```python
import asyncio
from typing import Protocol

from app.events import Event
from app.world import PartyWorld


class SocketLike(Protocol):
    async def send_json(self, payload: dict) -> None: ...
    async def close(self) -> None: ...


def _serialise_event(event: Event) -> dict:
    # Pydantic v2 dump; cursor (`seq`) is already on the event.
    return {"type": "event", "event": event.model_dump(), "cursor": event.seq}


class PartyWorldHub:
    """Fan-out broadcaster for a single PartyWorld."""

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
        for sock in list(self.subscribers):
            task = asyncio.create_task(self._send_or_drop(sock, payload))
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
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        await asyncio.gather(*pending, return_exceptions=True)

    def teardown(self) -> None:
        self._unsub()
        self.subscribers.clear()
```

- [ ] **Step 4: Verify passing.** `pytest tests/test_realtime.py -v` → 2 passed.

- [ ] **Step 5: Commit.**

```bash
git add backend/app/realtime.py backend/tests/test_realtime.py backend/pyproject.toml
git commit -m "feat(backend): PartyWorldHub broadcasts world events to subscribers"
```

---

## Task 3: Hub registry on `Store`

**Files:**
- Modify: `backend/app/store.py`
- Modify: `backend/tests/test_store.py`

- [ ] **Step 1: Failing test.**

Append to `backend/tests/test_store.py`:

```python
def test_store_returns_same_hub_for_repeat_slug_lookups():
    store = Store()
    h1 = store.get_or_create_hub("cream-terrazzo")
    h2 = store.get_or_create_hub("cream-terrazzo")
    assert h1 is h2


def test_store_creates_separate_hub_per_party():
    store = Store()
    a = store.get_or_create_hub("cream-terrazzo")
    b = store.get_or_create_hub("speakeasy")
    assert a is not b


def test_store_returns_none_for_unknown_slug_hub():
    store = Store()
    assert store.get_or_create_hub("does-not-exist") is None
```

- [ ] **Step 2: Verify failure.** `pytest tests/test_store.py -v` — three new tests fail.

- [ ] **Step 3: Implement.**

In `backend/app/store.py`, add (alongside the existing `_worlds` dict that Phase 3 should have introduced; if Phase 3 named it differently, reuse the existing `get_or_create_world(slug)` helper):

```python
from app.realtime import PartyWorldHub

# In Store.__init__:
self._hubs: dict[str, PartyWorldHub] = {}

def get_or_create_hub(self, slug: str) -> PartyWorldHub | None:
    if slug not in self._parties:
        return None
    if slug in self._hubs:
        return self._hubs[slug]
    world = self.get_or_create_world(slug)  # Phase 3 helper
    hub = PartyWorldHub(world)
    self._hubs[slug] = hub
    return hub
```

- [ ] **Step 4: Verify passing.** `pytest tests/test_store.py -v` — all pass.

- [ ] **Step 5: Commit.**

```bash
git add backend/app/store.py backend/tests/test_store.py
git commit -m "feat(backend): Store.get_or_create_hub for per-party realtime fan-out"
```

---

## Task 4: WebSocket route

**Files:**
- Modify: `backend/app/routes/parties.py`
- Create: `backend/tests/test_realtime_route.py`

- [ ] **Step 1: Failing test.**

Create `backend/tests/test_realtime_route.py`:

```python
from fastapi.testclient import TestClient


def test_ws_rejects_unknown_party_slug(client: TestClient):
    with pytest.raises(Exception):
        # Connection should fail; some FastAPI versions raise on enter,
        # others let you read a close frame. Accept either.
        with client.websocket_connect("/api/parties/does-not-exist/ws") as ws:
            ws.receive_json()


def test_ws_handshake_rejects_bad_principal(client: TestClient):
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": "nope"}})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid principal"}


def test_ws_sends_snapshot_after_valid_auth(client: TestClient):
    session = client.post(
        "/api/session", json={"username": "alice", "color": "#ff6b9d"}
    ).json()
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": session["session_id"]}})
        frame = ws.receive_json()
        assert frame["type"] == "snapshot"
        assert "room" in frame and "participants" in frame and "cursor" in frame


def test_ws_pushes_event_when_another_principal_joins(client: TestClient):
    alice = client.post("/api/session", json={"username": "alice", "color": "#ff6b9d"}).json()
    bob = client.post("/api/session", json={"username": "bob", "color": "#4dd0e1"}).json()
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": alice["session_id"]}})
        ws.receive_json()  # snapshot
        # Bob joins via the HTTP route → Alice's WS should get an event
        r = client.post(
            "/api/parties/cream-terrazzo/join",
            json={"principal": {"kind": "human", "id": bob["session_id"]}},
        )
        assert r.status_code == 200
        frame = ws.receive_json()
        assert frame["type"] == "event"
        assert frame["event"]["type"] == "join"
        assert frame["event"]["participant"]["username"] == "bob"
```

Add `import pytest` at the top.

- [ ] **Step 2: Verify failure.** `pytest tests/test_realtime_route.py -v` — all fail (route doesn't exist).

- [ ] **Step 3: Implement.**

In `backend/app/routes/parties.py`, add (after the existing `/observe` route):

```python
from fastapi import WebSocket, WebSocketDisconnect, status
from app.realtime import PartyWorldHub


@router.websocket("/{slug}/ws")
async def party_ws(
    websocket: WebSocket,
    slug: str,
    store: Store = Depends(_store_dep),
):
    party = store.get_party(slug)
    if party is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()

    # First frame must be auth.
    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    principal = (frame or {}).get("principal") if frame.get("type") == "auth" else None
    if not _principal_is_valid(principal, store):
        await websocket.send_json({"type": "error", "detail": "invalid principal"})
        await websocket.close()
        return

    hub = store.get_or_create_hub(slug)
    assert hub is not None
    # Send snapshot.
    world = store.get_or_create_world(slug)
    snapshot = world.observe(since=None)
    await websocket.send_json({"type": "snapshot", **snapshot})
    hub.subscribe(websocket)
    try:
        while True:
            # Ignore client frames after auth in this phase, but read them
            # so the socket remains responsive to close.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket)
```

If `_principal_is_valid` doesn't already exist alongside the other party-action routes from Phase 3, reuse the helper Phase 3 introduced (likely named `_resolve_principal` or similar). The exact name is the only adjustment needed.

- [ ] **Step 4: Verify passing.** `pytest tests/test_realtime_route.py -v` — all pass.

- [ ] **Step 5: Commit.**

```bash
git add backend/app/routes/parties.py backend/tests/test_realtime_route.py
git commit -m "feat(backend): WebSocket endpoint streams party events to subscribers"
```

---

## Task 5: Frontend party API wrappers

**Files:**
- Create: `frontend/src/api/party.ts`

- [ ] **Step 1: Implement (no tests — thin wrappers, exercised by hook + page tests).**

```typescript
import { apiPost } from './client';
import type { Participant } from './types';

export type Principal = { kind: 'human' | 'agent'; id: string };

export async function joinParty(slug: string, principal: Principal): Promise<{
  participant: Participant;
  cursor: number;
}> {
  return apiPost(`/api/parties/${slug}/join`, { principal });
}

export async function leaveParty(slug: string, principal: Principal): Promise<void> {
  await apiPost(`/api/parties/${slug}/leave`, { principal });
}

export async function moveInParty(
  slug: string,
  principal: Principal,
  x: number,
  y: number,
): Promise<{ x: number; y: number; cursor: number }> {
  return apiPost(`/api/parties/${slug}/move`, { principal, x, y });
}

export async function chatInParty(
  slug: string,
  principal: Principal,
  text: string,
): Promise<{ cursor: number }> {
  return apiPost(`/api/parties/${slug}/chat`, { principal, text });
}
```

Add `Participant` to `frontend/src/api/types.ts` if Phase 3 didn't (mirror Phase 3's backend `Participant` shape):

```typescript
export type Participant = {
  id: string;
  kind: 'human' | 'agent';
  username: string;
  color: string;
  x: number;
  y: number;
};
```

- [ ] **Step 2: Type-check.** `cd frontend && npx tsc -b` — clean.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/api/party.ts frontend/src/api/types.ts
git commit -m "feat(frontend): party-action API wrappers"
```

---

## Task 6: `useRealtimeParty` hook

**Files:**
- Create: `frontend/src/hooks/useRealtimeParty.ts`
- Create: `frontend/tests/useRealtimeParty.test.ts`

- [ ] **Step 1: Failing test.**

Create `frontend/tests/useRealtimeParty.test.ts`:

```typescript
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRealtimeParty } from '../src/hooks/useRealtimeParty';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  sent: string[] = [];
  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => this.onopen?.(new Event('open')));
  }
  send(payload: string) {
    this.sent.push(payload);
  }
  close() {
    this.onclose?.(new CloseEvent('close'));
  }
  receive(obj: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(obj) }));
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const selfPrincipal = { kind: 'human' as const, id: 'sid-1' };

describe('useRealtimeParty', () => {
  it('opens a WS to the party slug and sends auth as the first frame', async () => {
    renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await Promise.resolve();
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('/api/parties/cream-terrazzo/ws');
    expect(JSON.parse(ws.sent[0])).toEqual({
      type: 'auth',
      principal: selfPrincipal,
    });
  });

  it('populates participants from a snapshot', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await Promise.resolve();
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-1', kind: 'human', username: 'alice', color: '#ff6b9d', x: 100, y: 100 },
          { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 200, y: 200 },
        ],
        cursor: 5,
      }),
    );
    expect(result.current.participants.map((p) => p.id).sort()).toEqual(['sid-1', 'sid-2']);
  });

  it('applies a join event', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await Promise.resolve();
    const ws = MockWebSocket.instances[0];
    act(() => ws.receive({ type: 'snapshot', room: {}, participants: [], cursor: 0 }));
    act(() =>
      ws.receive({
        type: 'event',
        event: {
          seq: 1,
          type: 'join',
          participant: {
            id: 'sid-2',
            kind: 'human',
            username: 'bob',
            color: '#4dd0e1',
            x: 200,
            y: 200,
          },
        },
        cursor: 1,
      }),
    );
    expect(result.current.participants).toHaveLength(1);
    expect(result.current.participants[0].username).toBe('bob');
  });

  it('updates position from a move event for other participants', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await Promise.resolve();
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 200, y: 200 },
        ],
        cursor: 0,
      }),
    );
    act(() =>
      ws.receive({
        type: 'event',
        event: { seq: 1, type: 'move', participant_id: 'sid-2', x: 300, y: 250 },
        cursor: 1,
      }),
    );
    const bob = result.current.participants.find((p) => p.id === 'sid-2')!;
    expect(bob.x).toBe(300);
    expect(bob.y).toBe(250);
  });

  it('ignores move events for self', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await Promise.resolve();
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-1', kind: 'human', username: 'alice', color: '#ff6b9d', x: 100, y: 100 },
        ],
        cursor: 0,
      }),
    );
    act(() =>
      ws.receive({
        type: 'event',
        event: { seq: 1, type: 'move', participant_id: 'sid-1', x: 999, y: 999 },
        cursor: 1,
      }),
    );
    const me = result.current.participants.find((p) => p.id === 'sid-1')!;
    expect(me.x).toBe(100);  // unchanged
  });

  it('removes a participant on leave', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await Promise.resolve();
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 200, y: 200 },
        ],
        cursor: 0,
      }),
    );
    act(() =>
      ws.receive({
        type: 'event',
        event: { seq: 1, type: 'leave', participant_id: 'sid-2' },
        cursor: 1,
      }),
    );
    expect(result.current.participants).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Verify failure.** `cd frontend && npm test -- useRealtimeParty` — module not found.

- [ ] **Step 3: Implement.**

Create `frontend/src/hooks/useRealtimeParty.ts`:

```typescript
import { useEffect, useRef, useState } from 'react';
import type { Participant } from '../api/types';
import type { Principal } from '../api/party';

type Options = { slug: string; principal: Principal };

type Status = 'connecting' | 'open' | 'closed';

function wsUrlFor(slug: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/parties/${slug}/ws`;
}

export function useRealtimeParty({ slug, principal }: Options) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [status, setStatus] = useState<Status>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      setStatus('connecting');
      const ws = new WebSocket(wsUrlFor(slug));
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', principal }));
        backoffRef.current = 1000;
        setStatus('open');
      };

      ws.onmessage = (e: MessageEvent) => {
        let frame: unknown;
        try {
          frame = JSON.parse(typeof e.data === 'string' ? e.data : '');
        } catch {
          return;
        }
        if (!frame || typeof frame !== 'object') return;
        const f = frame as { type?: string };
        if (f.type === 'snapshot') {
          const s = frame as { participants: Participant[] };
          setParticipants(s.participants);
        } else if (f.type === 'event') {
          const ev = (frame as { event: { type: string } }).event;
          if (ev.type === 'join') {
            const p = (ev as unknown as { participant: Participant }).participant;
            setParticipants((prev) =>
              prev.some((q) => q.id === p.id) ? prev : [...prev, p],
            );
          } else if (ev.type === 'leave') {
            const id = (ev as unknown as { participant_id: string }).participant_id;
            setParticipants((prev) => prev.filter((q) => q.id !== id));
          } else if (ev.type === 'move') {
            const m = ev as unknown as { participant_id: string; x: number; y: number };
            if (m.participant_id === principal.id) return; // ignore self-echo
            setParticipants((prev) =>
              prev.map((q) =>
                q.id === m.participant_id ? { ...q, x: m.x, y: m.y } : q,
              ),
            );
          }
        }
      };

      ws.onclose = () => {
        setStatus('closed');
        if (cancelled) return;
        const delay = Math.min(backoffRef.current, 8000);
        backoffRef.current = Math.min(backoffRef.current * 2, 8000);
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // Close handler runs next; no extra cleanup here.
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, [slug, principal.id, principal.kind]);

  return { participants, status };
}
```

- [ ] **Step 4: Verify passing.** `npm test -- useRealtimeParty` — 6 passed.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/hooks/useRealtimeParty.ts frontend/tests/useRealtimeParty.test.ts
git commit -m "feat(frontend): useRealtimeParty WebSocket subscription hook"
```

---

## Task 7: `useMovement.onMove` throttled callback

**Files:**
- Modify: `frontend/src/hooks/useMovement.ts`
- Modify: `frontend/tests/useMovement.test.ts`

- [ ] **Step 1: Failing test.**

Append to `frontend/tests/useMovement.test.ts`:

```typescript
  it('emits throttled onMove callbacks as position changes', () => {
    const raf = setupRaf();
    const onMove = vi.fn();
    const { result: _ } = renderHook(() =>
      useMovement({
        worldWidth: 800,
        worldHeight: 500,
        speed: 400,
        onMove,
        moveThrottleMs: 100,
        start: { x: 100, y: 100 },
      }),
    );

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
      raf.tick(20); // ~320ms simulated time → expect ~3 throttled emits
    });

    expect(onMove.mock.calls.length).toBeGreaterThan(0);
    expect(onMove.mock.calls.length).toBeLessThanOrEqual(4);
    const [lastX, lastY] = onMove.mock.calls[onMove.mock.calls.length - 1];
    expect(lastX).toBeGreaterThan(100);
    expect(lastY).toBe(100);
  });
```

- [ ] **Step 2: Verify failure.** `npm test -- useMovement` — new test fails.

- [ ] **Step 3: Implement.**

Add to the `Options` type and the hook body in `frontend/src/hooks/useMovement.ts`:

```typescript
type Options = {
  worldWidth: number;
  worldHeight: number;
  speed: number;
  walls?: MovementWall[];
  start?: Point;
  onMove?: (x: number, y: number) => void;
  moveThrottleMs?: number;
};

// Inside useMovement, before the loop useEffect:
const onMoveRef = useRef(opts.onMove);
onMoveRef.current = opts.onMove;
const lastEmitRef = useRef<{ time: number; x: number; y: number }>({
  time: 0,
  x: NaN,
  y: NaN,
});
const throttleMs = opts.moveThrottleMs ?? 100;

// Inside the rAF loop, immediately after `setPosition(clamped)`:
const nowMs = (typeof performance !== 'undefined' ? performance.now() : Date.now());
if (
  onMoveRef.current &&
  (clamped.x !== lastEmitRef.current.x || clamped.y !== lastEmitRef.current.y) &&
  nowMs - lastEmitRef.current.time >= throttleMs
) {
  lastEmitRef.current = { time: nowMs, x: clamped.x, y: clamped.y };
  onMoveRef.current(clamped.x, clamped.y);
}
```

- [ ] **Step 4: Verify passing.** All useMovement tests pass.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/hooks/useMovement.ts frontend/tests/useMovement.test.ts
git commit -m "feat(frontend): useMovement.onMove throttled callback"
```

---

## Task 8: Avatar `variant` prop

**Files:**
- Modify: `frontend/src/components/Avatar.tsx`

- [ ] **Step 1: Modify the component.**

Add a `variant?: 'self' | 'other'` prop. When `'self'`, render an extra `box-shadow: inset 0 0 0 2px white` ring on the inner circle and set `data-self="true"` on the wrapper. Default `'other'`.

```tsx
type Props = {
  username: string;
  color: string;
  x: number;
  y: number;
  worldWidth: number;
  worldHeight: number;
  variant?: 'self' | 'other';
};

export default function Avatar({
  username,
  color,
  x,
  y,
  worldWidth,
  worldHeight,
  variant = 'other',
}: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  return (
    <div
      data-self={variant === 'self' ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
        transition: 'left 150ms linear, top 150ms linear',
      }}
    >
      {/* label unchanged */}
      <div
        style={{
          position: 'absolute',
          bottom: 28,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 12,
          background: 'rgba(255,255,255,0.9)',
          padding: '1px 6px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
          fontWeight: 600,
        }}
      >
        {username}
      </div>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          background: color,
          border: '2px solid white',
          boxShadow:
            variant === 'self'
              ? '0 2px 6px rgba(0,0,0,0.25), inset 0 0 0 2px rgba(255,255,255,0.8)'
              : '0 2px 6px rgba(0,0,0,0.25)',
        }}
      />
    </div>
  );
}
```

Existing tests pass — the default is `'other'` which is the same visual as before (just a slightly different transition value: 80ms → 150ms to handle 10 Hz remote updates).

- [ ] **Step 2: Verify.** `npm test` — all pass.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/Avatar.tsx
git commit -m "feat(frontend): Avatar variant prop (self vs other)"
```

---

## Task 9: `PartySpace` renders all participants

**Files:**
- Modify: `frontend/src/components/PartySpace.tsx`
- Modify: `frontend/tests/Party.test.tsx` (add a multi-participant assertion)

- [ ] **Step 1: Update the multi-participant assertion.**

Extend the Party test mock to return participants in the snapshot (via the WS mock) — but since `Party.test.tsx` doesn't currently mock the WebSocket, the cleanest place is a new test file. Create `frontend/tests/PartySpace.multi.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PartySpace from '../src/components/PartySpace';

const party = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: { clipPath: null, border: '6px solid #8b6f47', borderRadius: 12, walls: [] },
};

const selfUser = { session_id: 'sid-1', username: 'alice', color: '#ff6b9d' };

const participants = [
  { id: 'sid-1', kind: 'human' as const, username: 'alice', color: '#ff6b9d', x: 200, y: 200 },
  { id: 'sid-2', kind: 'human' as const, username: 'bob', color: '#4dd0e1', x: 400, y: 300 },
];

describe('PartySpace with multiple participants', () => {
  it('renders one avatar per participant and marks the local user', () => {
    render(<PartySpace party={party as any} user={selfUser} participants={participants} />);
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
    const selves = document.querySelectorAll('[data-self="true"]');
    expect(selves.length).toBe(1);
  });
});
```

- [ ] **Step 2: Modify `PartySpace`.**

Change `PartySpace`'s signature to accept `participants?: Participant[]` and `onMove?: (x: number, y: number) => void`. Render avatars from `participants` (falling back to the local user only when participants is undefined — backward compat). The local user is identified by `participant.id === user.session_id`.

```tsx
import { useRef } from 'react';
import type { Participant, PartyConfig, User } from '../api/types';
import { useMovement } from '../hooks/useMovement';
import Avatar from './Avatar';
import MusicPill from './MusicPill';
import Wall from './Wall';
import Zone from './Zone';

const SPEED = 220;

type Props = {
  party: PartyConfig;
  user: User;
  participants?: Participant[];
  onMove?: (x: number, y: number) => void;
};

export default function PartySpace({ party, user, participants, onMove }: Props) {
  const { width, height } = party.worldSize;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
    walls: party.room.walls,
    onMove,
    moveThrottleMs: 100,
  });
  const floorRef = useRef<HTMLDivElement>(null);

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    setTarget({
      x: ((e.clientX - rect.left) / rect.width) * width,
      y: ((e.clientY - rect.top) / rect.height) * height,
    });
  }

  // If participants is provided, render everyone (overriding the local-only view).
  // Otherwise fall back to the single-player path: render only the local user.
  const renderList =
    participants && participants.length > 0
      ? participants.map((p) =>
          p.id === user.session_id ? { ...p, x: position.x, y: position.y } : p,
        )
      : [
          {
            id: user.session_id,
            kind: 'human' as const,
            username: user.username,
            color: user.color,
            x: position.x,
            y: position.y,
          },
        ];

  return (
    <div
      style={{
        width: 'min(95vw, 1000px)',
        aspectRatio: `${width} / ${height}`,
        margin: '24px auto',
        position: 'relative',
      }}
    >
      <div
        ref={floorRef}
        onClick={onClick}
        style={{
          position: 'absolute',
          inset: 0,
          background: party.theme.floor,
          border: party.room.border,
          borderRadius: party.room.borderRadius ?? 0,
          clipPath: party.room.clipPath ?? 'none',
          overflow: 'hidden',
          boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        {party.zones.map((z) => (
          <Zone key={z.id} zone={z} />
        ))}
        {party.room.walls.map((w, i) => (
          <Wall key={i} wall={w} />
        ))}
        {renderList.map((p) => (
          <Avatar
            key={p.id}
            username={p.username}
            color={p.color}
            x={p.x}
            y={p.y}
            worldWidth={width}
            worldHeight={height}
            variant={p.id === user.session_id ? 'self' : 'other'}
          />
        ))}
        <MusicPill label={party.music.label} />
      </div>
    </div>
  );
}
```

The local user's x/y is overridden with the hook's `position` — that keeps the local avatar visually responsive even if the server hasn't echoed yet.

- [ ] **Step 3: Verify.** `npm test` — including the new multi test — passes.

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/components/PartySpace.tsx frontend/tests/PartySpace.multi.test.tsx
git commit -m "feat(frontend): PartySpace renders all participants and wires onMove"
```

---

## Task 10: Wire join/leave/observe in the Party page

**Files:**
- Modify: `frontend/src/pages/Party.tsx`
- Modify: `frontend/tests/Party.test.tsx`

- [ ] **Step 1: Test changes.**

Extend `frontend/tests/Party.test.tsx`'s mock fetch to handle `/join` and `/leave` POSTs (return 200 with a stub body for join; 204 for leave). Add an assertion that on mount, the fetch mock is called with `/api/parties/cream-terrazzo/join`. Add an `it` for unmount triggering `/leave`.

(The full test file is already long; add two short cases at the bottom of the existing `describe`.)

```tsx
  it('calls /join on mount', async () => {
    render(
      <MemoryRouter initialEntries={['/party/cream-terrazzo']}>
        <Routes>
          <Route path="/party/:slug" element={<Party />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByLabelText('zone-dance'); // wait for party to load
    const joinCall = (globalThis.fetch as any).mock.calls.find(
      ([url]: [string]) => typeof url === 'string' && url.endsWith('/api/parties/cream-terrazzo/join'),
    );
    expect(joinCall).toBeDefined();
  });
```

The /leave assertion is similar but uses unmount via `unmount()` from `render`.

- [ ] **Step 2: Verify failure.** `npm test -- Party` — the new assertions fail.

- [ ] **Step 3: Implement.**

In `frontend/src/pages/Party.tsx`, wire `useRealtimeParty`, call `joinParty` on mount and `leaveParty` on unmount, and pass `participants` + `onMove` (via `moveInParty`) to `PartySpace`:

```tsx
// inside the component body, after party load:
const principal = { kind: 'human' as const, id: session.user.session_id };
const { participants } = useRealtimeParty({ slug: party.slug, principal });

useEffect(() => {
  joinParty(party.slug, principal).catch(() => {});
  return () => {
    leaveParty(party.slug, principal).catch(() => {});
  };
}, [party.slug, principal.id]);

const onMove = (x: number, y: number) => {
  moveInParty(party.slug, principal, x, y).catch(() => {});
};

// In the render:
<PartySpace party={party} user={session.user} participants={participants} onMove={onMove} />
```

Where `useEffect` is already imported. Be careful to only set up the effect when `party` and `session.user` are present (gate behind the existing null-checks).

- [ ] **Step 4: Verify passing.** `npm test` — all green.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/pages/Party.tsx frontend/tests/Party.test.tsx
git commit -m "feat(frontend): Party page joins on mount, leaves on unmount, streams via WS"
```

---

## Task 11: Integration smoke

**Files:** none.

- [ ] **Step 1: Run everything.**

```bash
cd backend && source .venv/bin/activate && pytest -v
cd frontend && npm test
cd frontend && npm run build
```

All green; build clean.

- [ ] **Step 2: Manual browser smoke.**

```bash
# Terminal A
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
# Terminal B
cd frontend && npm run dev
```

Open `http://localhost:5173` in **two browser windows** (or one normal + one private). Sign in as different users in each. Both pick Cream Terrazzo. Confirm:

- Each window shows two avatars (yours with the white inner ring, the other without).
- Moving in one window updates the other within ~150ms.
- Closing one window removes that avatar from the other within ~1s.
- Refreshing one window re-creates its avatar in the other.

Open the browser dev tools → Network → WS tab. Confirm one open WebSocket per window with snapshot + event frames.

- [ ] **Step 3: If everything works, no further commit.** If you noticed a regression, fix it (small commit) before declaring done.

---

## Out of scope (for reference)

- Voice / audio (Step 5+).
- Chat UI (Step 5+ — the backend supports chat already; rendering a chat panel is a follow-up).
- Server-side wall collision (still client-only).
- Cross-process WebSocket fan-out (Redis pub/sub) — single-process demo.
- Reconnection state migration beyond the snapshot reset.
