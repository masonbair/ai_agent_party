# Session Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evict the prior browser as soon as a second authenticated browser connects, even when that second browser is on the Lobby (no party-WS). Add a session-scoped WebSocket that Lobby and Party both open.

**Architecture:** New `SessionPresenceHub` on the `Store` tracks one socket per `session_id`. A new WS endpoint at `/api/session/ws` accepts auth, hands the socket to the hub, and the hub evicts duplicates — sending `{type:"evicted",reason:"takeover"}`, closing the old socket, and calling `world.leave(session_id)` on every world the user was in. A new `useSessionPresence` hook is mounted by Lobby and Party; on eviction it clears `session_id` and routes to `/?takeover=1` (the existing banner already handles the rest).

**Tech Stack:** Backend: Python 3.11+, FastAPI, pytest, pytest-asyncio. Frontend: React 18, TypeScript, vitest, React Testing Library.

**Spec:** `docs/superpowers/specs/2026-05-13-session-presence-design.md`
**Companion spec (existing party-WS eviction):** `docs/superpowers/specs/2026-05-13-session-takeover-design.md`

---

## File Map

**Backend**
- Modify: `backend/app/store.py` — add `worlds()` method and lazy `session_presence` accessor.
- Create: `backend/app/session_presence.py` — `SessionPresenceHub`, `StoreLike` protocol.
- Modify: `backend/app/routes/session.py` — add `/ws` WebSocket endpoint.
- Create: `backend/tests/test_session_presence.py` — unit tests for the hub.
- Create: `backend/tests/test_session_presence_route.py` — integration tests for the WS endpoint.

**Frontend**
- Create: `frontend/src/hooks/useSessionPresence.ts` — opens the session WS, evict handling.
- Modify: `frontend/src/pages/Lobby.tsx` — call the hook when authed.
- Modify: `frontend/src/pages/Party.tsx` — call the hook alongside existing party-WS eviction; share one `handleTakeover` callback.
- Create: `frontend/tests/useSessionPresence.test.ts` — hook test.
- Modify: `frontend/tests/Lobby.test.tsx` — assert eviction handling.

---

## Backend Tasks

### Task 1: Store exposes worlds() and a lazy session_presence accessor

**Files:**
- Modify: `backend/app/store.py`
- Modify: `backend/tests/test_store.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_store.py`:
```python
def test_store_worlds_returns_initialized_worlds() -> None:
    from app.store import Store

    store = Store()
    assert list(store.worlds()) == []
    w = store.get_or_create_world("cream-terrazzo")
    assert w is not None
    assert list(store.worlds()) == [w]


def test_store_session_presence_is_lazy_and_idempotent() -> None:
    from app.store import Store
    from app.session_presence import SessionPresenceHub

    store = Store()
    hub1 = store.session_presence
    hub2 = store.session_presence
    assert isinstance(hub1, SessionPresenceHub)
    assert hub1 is hub2
```

- [ ] **Step 2: Run — expect failure (`app.session_presence` does not exist yet)**

```
backend/.venv/bin/pytest backend/tests/test_store.py -v -k "worlds or session_presence"
```

- [ ] **Step 3: Create the module skeleton so the import resolves**

Create `backend/app/session_presence.py` with the minimum needed for Task 1:
```python
from __future__ import annotations

from typing import Iterable, Protocol

from app.world import PartyWorld


class StoreLike(Protocol):
    def worlds(self) -> Iterable[PartyWorld]: ...


class SessionPresenceHub:
    """Tracks one live WebSocket per ``session_id``. Filled in by Task 2."""

    def __init__(self, store: StoreLike) -> None:
        self._store = store
```

- [ ] **Step 4: Modify `backend/app/store.py`**

Add the import at the top (after the existing imports):
```python
from app.session_presence import SessionPresenceHub
```

Add a private slot in `Store.__init__`:
```python
        self._session_presence: SessionPresenceHub | None = None
```

Add two methods to `Store` (anywhere after `delete_session`):
```python
    def worlds(self) -> list[PartyWorld]:
        return list(self._worlds.values())

    @property
    def session_presence(self) -> SessionPresenceHub:
        if self._session_presence is None:
            self._session_presence = SessionPresenceHub(self)
        return self._session_presence
```

- [ ] **Step 5: Run the new tests — they should now pass**

```
backend/.venv/bin/pytest backend/tests/test_store.py -v -k "worlds or session_presence"
```

- [ ] **Step 6: Run the full backend suite to confirm no regressions**

```
backend/.venv/bin/pytest -q
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/store.py backend/app/session_presence.py backend/tests/test_store.py
git commit -m "feat(store): worlds() and lazy session_presence accessor"
```

---

### Task 2: SessionPresenceHub evicts a prior socket for the same session_id

**Files:**
- Modify: `backend/app/session_presence.py`
- Create: `backend/tests/test_session_presence.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_session_presence.py`:
```python
import asyncio

import pytest

from app.session_presence import SessionPresenceHub


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


class FakeStore:
    def worlds(self):
        return []


@pytest.mark.asyncio
async def test_presence_hub_evicts_prior_socket_for_same_session_id() -> None:
    hub = SessionPresenceHub(FakeStore())
    a = FakeSocket()
    b = FakeSocket()

    hub.subscribe(a, "sid-1")
    hub.subscribe(b, "sid-1")

    await hub.drain()
    assert {"type": "evicted", "reason": "takeover"} in a.sent
    assert a.closed is True
    assert hub._by_session["sid-1"] is b


@pytest.mark.asyncio
async def test_presence_hub_unsubscribe_does_not_clear_replaced_slot() -> None:
    hub = SessionPresenceHub(FakeStore())
    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.subscribe(b, "sid-1")
    await hub.drain()

    hub.unsubscribe(a, "sid-1")  # late teardown from evicted A

    assert hub._by_session["sid-1"] is b


@pytest.mark.asyncio
async def test_presence_hub_clean_unsubscribe_clears_slot() -> None:
    hub = SessionPresenceHub(FakeStore())
    a = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.unsubscribe(a, "sid-1")
    assert "sid-1" not in hub._by_session
```

- [ ] **Step 2: Run — expect failure**

```
backend/.venv/bin/pytest backend/tests/test_session_presence.py -v
```

- [ ] **Step 3: Implement `SessionPresenceHub` in `backend/app/session_presence.py`**

Replace the file contents with:
```python
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

    A second ``subscribe`` for the same id evicts the prior socket:
    sends ``{"type":"evicted","reason":"takeover"}``, closes it, and
    removes the participant from every world it was in.
    """

    def __init__(self, store: StoreLike) -> None:
        self._store = store
        self._by_session: dict[str, SocketLike] = {}
        self._pending: list[asyncio.Task] = []
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
        old = self._by_session.get(session_id)
        if old is not None and old is not sock:
            self._evict(old, session_id)
        self._by_session[session_id] = sock

    def unsubscribe(self, sock: SocketLike, session_id: str) -> None:
        if self._by_session.get(session_id) is sock:
            del self._by_session[session_id]

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
```

- [ ] **Step 4: Run new tests — expect PASS**

```
backend/.venv/bin/pytest backend/tests/test_session_presence.py -v
```

- [ ] **Step 5: Run full backend suite — confirm no regressions**

```
backend/.venv/bin/pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/session_presence.py backend/tests/test_session_presence.py
git commit -m "feat(session-presence): hub evicts duplicate session_id sockets"
```

---

### Task 3: Eviction calls world.leave on every world the user is in

**Files:**
- Modify: `backend/tests/test_session_presence.py`

The hub's `_evict` already calls `world.leave(session_id)` for every world (Task 2 implementation). This task pins the behavior with a test that uses real `PartyWorld` instances.

- [ ] **Step 1: Append the test**

```python
from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.world import PartyWorld


def _alice() -> Participant:
    return Participant(
        id="sid-1",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=400.0,
        y=250.0,
        joined_at=1715533200.0,
    )


class FakeStoreWithWorlds:
    def __init__(self, worlds_: list[PartyWorld]) -> None:
        self._worlds = worlds_

    def worlds(self):
        return self._worlds


@pytest.mark.asyncio
async def test_presence_hub_evict_leaves_active_world() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_alice())
    store = FakeStoreWithWorlds([world])

    hub = SessionPresenceHub(store)
    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.subscribe(b, "sid-1")
    await hub.drain()

    assert "sid-1" not in world.participants


@pytest.mark.asyncio
async def test_presence_hub_evict_tolerates_missing_participant() -> None:
    # User has presence WS open but never joined any party. Evict must not raise.
    world = PartyWorld(CREAM_TERRAZZO)
    store = FakeStoreWithWorlds([world])

    hub = SessionPresenceHub(store)
    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, "sid-2")
    hub.subscribe(b, "sid-2")
    await hub.drain()

    assert {"type": "evicted", "reason": "takeover"} in a.sent
```

- [ ] **Step 2: Run — expect PASS**

```
backend/.venv/bin/pytest backend/tests/test_session_presence.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_session_presence.py
git commit -m "test(session-presence): evict leaves world participants and tolerates non-members"
```

---

### Task 4: `/api/session/ws` endpoint — auth and subscribe

**Files:**
- Modify: `backend/app/routes/session.py`
- Create: `backend/tests/test_session_presence_route.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_session_presence_route.py`:
```python
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _signin(client: TestClient, username: str = "Alice", color: str = "#ff6b9d") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def test_session_ws_accepts_valid_auth_and_holds_open(client: TestClient) -> None:
    user = _signin(client)
    with client.websocket_connect("/api/session/ws") as ws:
        ws.send_json({"type": "auth", "session_id": user["session_id"]})
        # No immediate error frame; the connection stays open. To confirm
        # there is no pending payload waiting, the test simply exits the
        # context manager, which closes cleanly.
    # Reaching here means no WebSocketDisconnect was raised.


def test_session_ws_second_connect_evicts_first(client: TestClient) -> None:
    user = _signin(client)
    sid = user["session_id"]
    with client.websocket_connect("/api/session/ws") as ws_a:
        ws_a.send_json({"type": "auth", "session_id": sid})

        with client.websocket_connect("/api/session/ws") as ws_b:
            ws_b.send_json({"type": "auth", "session_id": sid})

            frame = ws_a.receive_json()
            assert frame == {"type": "evicted", "reason": "takeover"}
            with pytest.raises(WebSocketDisconnect):
                ws_a.receive_json()
```

- [ ] **Step 2: Run — expect failure (endpoint does not exist)**

```
backend/.venv/bin/pytest backend/tests/test_session_presence_route.py -v
```

- [ ] **Step 3: Add the WebSocket endpoint**

Modify `backend/app/routes/session.py`. Add these imports at the top alongside the existing ones:
```python
from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect, status
```

Add the new endpoint at the bottom of the file:
```python
@router.websocket("/ws")
async def session_ws(
    websocket: WebSocket,
    store: Store = Depends(_store_dep),
) -> None:
    await websocket.accept()

    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()
        return

    if not isinstance(frame, dict) or frame.get("type") != "auth":
        await websocket.send_json({"type": "error", "detail": "invalid session"})
        await websocket.close()
        return

    session_id = frame.get("session_id")
    if not isinstance(session_id, str) or store.get_session(session_id) is None:
        await websocket.send_json({"type": "error", "detail": "invalid session"})
        await websocket.close()
        return

    hub = store.session_presence
    hub.subscribe(websocket, session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket, session_id)
```

- [ ] **Step 4: Run the new test — expect PASS**

```
backend/.venv/bin/pytest backend/tests/test_session_presence_route.py -v
```

- [ ] **Step 5: Run the full backend suite — confirm no regressions**

```
backend/.venv/bin/pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/session.py backend/tests/test_session_presence_route.py
git commit -m "feat(session-ws): /api/session/ws evicts duplicate session_id"
```

---

### Task 5: `/api/session/ws` rejects unknown session_id and bad auth

**Files:**
- Modify: `backend/tests/test_session_presence_route.py`

The endpoint already rejects these cases (Task 4). Pin both with tests.

- [ ] **Step 1: Append two tests**

```python
def test_session_ws_rejects_unknown_session_id(client: TestClient) -> None:
    with client.websocket_connect("/api/session/ws") as ws:
        ws.send_json({"type": "auth", "session_id": "does-not-exist"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid session"}


def test_session_ws_rejects_non_auth_first_frame(client: TestClient) -> None:
    with client.websocket_connect("/api/session/ws") as ws:
        ws.send_json({"type": "ping"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid session"}
```

- [ ] **Step 2: Run — expect PASS**

```
backend/.venv/bin/pytest backend/tests/test_session_presence_route.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_session_presence_route.py
git commit -m "test(session-ws): reject unknown session_id and non-auth first frame"
```

---

### Task 6: Cross-stack end-to-end — second presence WS removes user from a party world

**Files:**
- Modify: `backend/tests/test_session_presence_route.py`

This pins the full server-side behavior: A joins a party via HTTP, opens presence WS; B opens presence WS with same session_id; assert the world no longer contains A.

- [ ] **Step 1: Append the test**

```python
def test_presence_eviction_removes_participant_from_world(client: TestClient) -> None:
    user = _signin(client)
    sid = user["session_id"]
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r.status_code == 200

    with client.websocket_connect("/api/session/ws") as ws_a:
        ws_a.send_json({"type": "auth", "session_id": sid})

        with client.websocket_connect("/api/session/ws") as ws_b:
            ws_b.send_json({"type": "auth", "session_id": sid})

            evict = ws_a.receive_json()
            assert evict == {"type": "evicted", "reason": "takeover"}

    # After eviction, the world should no longer hold sid.
    r = client.get("/api/parties/cream-terrazzo/observe")
    body = r.json()
    ids = [p["id"] for p in body["participants"]]
    assert sid not in ids
```

- [ ] **Step 2: Run — expect PASS**

```
backend/.venv/bin/pytest backend/tests/test_session_presence_route.py::test_presence_eviction_removes_participant_from_world -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_session_presence_route.py
git commit -m "test(session-ws): eviction removes participant from party worlds"
```

---

## Frontend Tasks

### Task 7: `useSessionPresence` hook

**Files:**
- Create: `frontend/src/hooks/useSessionPresence.ts`
- Create: `frontend/tests/useSessionPresence.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/useSessionPresence.test.ts`:
```ts
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionPresence } from '../src/hooks/useSessionPresence';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    });
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
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

describe('useSessionPresence', () => {
  it('opens a WS and sends auth with the session_id', async () => {
    renderHook(() => useSessionPresence({ sessionId: 'sid-1' }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('/api/session/ws');
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', session_id: 'sid-1' });
  });

  it('does not open a WS when sessionId is null', async () => {
    renderHook(() => useSessionPresence({ sessionId: null }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('invokes onEvicted, closes, and suppresses reconnect on an evicted frame', async () => {
    const onEvicted = vi.fn();
    renderHook(() => useSessionPresence({ sessionId: 'sid-1', onEvicted }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];

    act(() => ws.receive({ type: 'evicted', reason: 'takeover' }));

    expect(onEvicted).toHaveBeenCalledTimes(1);
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('reconnects with backoff on an unexpected close', async () => {
    renderHook(() => useSessionPresence({ sessionId: 'sid-1' }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];

    act(() => ws.close());

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
  });
});
```

- [ ] **Step 2: Run — expect failure**

```
cd frontend && npx vitest run tests/useSessionPresence.test.ts
```

- [ ] **Step 3: Implement the hook**

Create `frontend/src/hooks/useSessionPresence.ts`:
```ts
import { useEffect, useRef } from 'react';

type Options = {
  sessionId: string | null;
  onEvicted?: () => void;
};

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/session/ws`;
}

export function useSessionPresence({ sessionId, onEvicted }: Options): void {
  const evictedRef = useRef(false);

  useEffect(() => {
    if (!sessionId) return;
    evictedRef.current = false;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let backoff = 1000;
    let ws: WebSocket | null = null;

    function connect() {
      if (cancelled) return;
      ws = new WebSocket(wsUrl());

      ws.onopen = () => {
        ws?.send(JSON.stringify({ type: 'auth', session_id: sessionId }));
        backoff = 1000;
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
        if (f.type === 'evicted') {
          evictedRef.current = true;
          onEvicted?.();
          ws?.close();
          return;
        }
      };

      ws.onclose = () => {
        if (cancelled || evictedRef.current) return;
        const delay = Math.min(backoff, 8000);
        backoff = Math.min(backoff * 2, 8000);
        reconnectTimer = setTimeout(connect, delay);
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer != null) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [sessionId, onEvicted]);
}
```

- [ ] **Step 4: Run hook tests — expect PASS**

```
cd frontend && npx vitest run tests/useSessionPresence.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSessionPresence.ts frontend/tests/useSessionPresence.test.ts
git commit -m "feat(session-presence): useSessionPresence hook with evict handling"
```

---

### Task 8: Lobby mounts the presence hook

**Files:**
- Modify: `frontend/src/pages/Lobby.tsx`
- Modify: `frontend/tests/Lobby.test.tsx`

- [ ] **Step 1: Write the failing test**

Append a test to `frontend/tests/Lobby.test.tsx` (inside the existing `describe` block). First, ensure the file's imports include `vi`, `MemoryRouter`, `Routes`, `Route`, and what's already there. If a `MockWebSocket` is not already set up, mirror the pattern from `useSessionPresence.test.ts` — but the simpler approach for Lobby is to NOT stub WebSocket and instead assert that when the user is authed, a WebSocket constructor was called for `/api/session/ws`.

Append:
```tsx
  it('opens a session presence WebSocket when authed', async () => {
    const seen: string[] = [];
    class FakeWS {
      url: string;
      onopen: ((e: Event) => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onclose: ((e: CloseEvent) => void) | null = null;
      onerror: ((e: Event) => void) | null = null;
      readyState = 0;
      constructor(url: string) {
        this.url = url;
        seen.push(url);
      }
      send() {}
      close() {}
    }
    vi.stubGlobal('WebSocket', FakeWS);

    // Stub the two HTTP calls Lobby makes: session check + parties list.
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as URL).toString();
      if (url.endsWith('/api/session/sid-1')) {
        return new Response(
          JSON.stringify({ session_id: 'sid-1', username: 'Alice', color: '#ff6b9d' }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url.endsWith('/api/parties')) {
        return new Response(JSON.stringify({ parties: [] }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    localStorage.setItem('session_id', 'sid-1');
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
        </Routes>
      </MemoryRouter>,
    );

    // Wait for authed state to settle and the hook effect to run.
    await screen.findByText(/Pick a party/);
    expect(seen.some((u) => u.includes('/api/session/ws'))).toBe(true);

    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
  });
```

If `Lobby.test.tsx` doesn't already import `vi`, add `vi` to the existing `vitest` import.

- [ ] **Step 2: Run — expect failure**

```
cd frontend && npx vitest run tests/Lobby.test.tsx -t "session presence WebSocket"
```

- [ ] **Step 3: Modify `frontend/src/pages/Lobby.tsx`**

Replace the file with:
```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyConfig } from '../api/types';
import PartyPreview from '../components/PartyPreview';
import { clearStoredSessionId, useSession } from '../hooks/useSession';
import { useSessionPresence } from '../hooks/useSessionPresence';

export default function Lobby() {
  const session = useSession();
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyConfig[] | null>(null);

  useEffect(() => {
    if (session.status !== 'authed') return;
    apiGet<PartiesListResponse>('/api/parties')
      .then((res) => setParties(res.parties))
      .catch(() => setParties([]));
  }, [session.status]);

  const onEvicted = useCallback(() => {
    clearStoredSessionId();
    navigate('/?takeover=1', { replace: true });
  }, [navigate]);

  useSessionPresence({
    sessionId: session.status === 'authed' ? session.user.session_id : null,
    onEvicted,
  });

  if (session.status !== 'authed') return null;

  return (
    <main
      style={{
        maxWidth: 'min(1100px, 92vw)',
        margin: 'clamp(24px, 6vh, 40px) auto',
        padding: 'clamp(16px, 4vw, 24px)',
      }}
    >
      <h1 style={{ fontSize: 'clamp(22px, 5vw, 32px)', margin: 0 }}>
        Pick a party, {session.user.username}
      </h1>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))',
          gap: 16,
          marginTop: 16,
        }}
      >
        {parties === null && <p>Loading parties…</p>}
        {parties?.map((p) => (
          <button
            key={p.slug}
            type="button"
            onClick={() => navigate(`/party/${p.slug}`)}
            style={{
              textAlign: 'left',
              padding: 12,
              border: `2px solid ${p.theme.accent}`,
              borderRadius: 12,
              background: '#fff',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <PartyPreview party={p} />
            <div>
              <strong>{p.name}</strong>
              <p style={{ margin: '4px 0 0', color: '#555' }}>{p.description}</p>
            </div>
          </button>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Run Lobby tests — expect PASS**

```
cd frontend && npx vitest run tests/Lobby.test.tsx
```

- [ ] **Step 5: Run full frontend suite — confirm no regressions**

```
cd frontend && npx vitest run
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Lobby.tsx frontend/tests/Lobby.test.tsx
git commit -m "feat(lobby): mount session presence WS for cross-page takeover"
```

---

### Task 9: Party page mounts the presence hook with the shared handler

**Files:**
- Modify: `frontend/src/pages/Party.tsx`

The Party page already has an `onEvicted` for `useRealtimeParty`. Extract that into a shared `handleTakeover` callback and pass it to both hooks.

- [ ] **Step 1: Replace the relevant section of `frontend/src/pages/Party.tsx`**

Open `frontend/src/pages/Party.tsx`. Add the import for the new hook near the top:
```ts
import { useSessionPresence } from '../hooks/useSessionPresence';
```

Also ensure `useCallback` is imported from `react`:
```ts
import { useCallback, useEffect, useState } from 'react';
```

Replace the existing `useRealtimeParty(...)` call block with:
```tsx
  const handleTakeover = useCallback(() => {
    clearStoredSessionId();
    navigate('/?takeover=1', { replace: true });
  }, [navigate]);

  useSessionPresence({
    sessionId: session.status === 'authed' ? session.user.session_id : null,
    onEvicted: handleTakeover,
  });

  const { participants } = useRealtimeParty(
    ready && principal
      ? { slug: party!.slug, principal, onEvicted: handleTakeover }
      : { slug: '', principal: { kind: 'human', id: '' } },
  );
```

- [ ] **Step 2: Run Party tests — expect PASS (the hook is non-blocking; existing tests don't trigger eviction)**

```
cd frontend && npx vitest run tests/Party.test.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Party.tsx
git commit -m "feat(party): mount session presence WS alongside party WS"
```

---

### Task 10: Full-stack smoke check

**Files:** none (verification only).

- [ ] **Step 1: Run full backend suite**

```
backend/.venv/bin/pytest -q
```
Expected: all green.

- [ ] **Step 2: Run full frontend suite**

```
cd frontend && npx vitest run
```
Expected: all green.

- [ ] **Step 3: Manual smoke**

1. Start backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`.
2. Start frontend: `cd frontend && npm run dev`.
3. Sign in as Alice in Browser A; arrive on `/lobby`.
4. Copy `session_id` from Browser A's localStorage. In a private Browser B, set the same `session_id` in localStorage and open `http://localhost:5173/lobby`.
5. Confirm Browser A jumps back to sign-in with the takeover banner — without entering a party.
6. Repeat, but with Browser A on the party page after joining. Confirm A is booted to sign-in AND Alice's avatar disappears for any third observer in the same party.

- [ ] **Step 4: No commit (verification only)**

---

## Self-Review Notes

- Spec coverage:
  - Architecture diagram → Tasks 2 + 4 (hub + endpoint).
  - Server-side cross-world cleanup → Tasks 2 (impl) + 3 (test) + 6 (end-to-end test).
  - `StoreLike` protocol, `worlds()`, `session_presence` lazy property → Task 1.
  - `useSessionPresence` hook → Task 7.
  - Lobby + Party shared `handleTakeover` → Tasks 8, 9.
  - All "Error Handling" cases from the spec are covered: invalid auth frame (Task 5), unknown session_id (Task 5), already-evicted unsubscribe (Task 2), missing participant in a world (Task 3 — `test_presence_hub_evict_tolerates_missing_participant`).
- Type/name consistency: `_by_session`, `session_id`, `principal_key` vs `session_id` — note the new hub uses `session_id` (humans only), while the existing party hub uses `principal_key` (kind + id). This is deliberate; the new hub is human-only per the spec.
- Frame shape `{type:"evicted", reason:"takeover"}` matches the existing party-WS path so the same SignIn banner flow handles both.
- No placeholders, no skipped code blocks.
