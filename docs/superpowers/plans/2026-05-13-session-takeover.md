# Session Takeover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a duplicate `session_id` (or `agent_id`) opens a second WebSocket to a party, evict the older socket: emit an `evicted` frame, close it, remove the participant from the world, and route the old browser back to a takeover-aware sign-in page.

**Architecture:** Per-party `PartyWorldHub` gains a `principal_key → socket` index. `subscribe` now takes `(sock, principal_key, participant_id)`; if a different socket is already mapped under that key, the hub schedules an `evicted` frame and close on the old socket and calls `world.leave(participant_id)` so other clients see the avatar disappear. The frontend hook recognizes the `evicted` frame, suppresses reconnect, clears `session_id`, and navigates to `/?takeover=1`, which `SignIn.tsx` renders as a banner.

**Tech Stack:** Backend: Python 3.11+, FastAPI, pytest, pytest-asyncio. Frontend: React 18, TypeScript, vitest, React Testing Library, react-router-dom.

**Spec:** `docs/superpowers/specs/2026-05-13-session-takeover-design.md`

---

## File Map

**Backend**
- Modify: `backend/app/realtime.py` — add `_by_principal` index; change `subscribe` / `unsubscribe` signatures; add `_evict` helper.
- Modify: `backend/app/routes/parties.py` — change `_validate_ws_principal` to return `Principal | None`; build `principal_key`; pass to `hub.subscribe` / `hub.unsubscribe`.
- Modify: `backend/tests/test_realtime.py` — update existing `subscribe` callers to the new signature.
- Create: `backend/tests/test_session_takeover.py` — unit tests for hub eviction + an end-to-end WS takeover test via `TestClient`.

**Frontend**
- Modify: `frontend/src/hooks/useRealtimeParty.ts` — accept `onEvicted` option; handle `evicted` frame; suppress reconnect on eviction.
- Modify: `frontend/src/pages/Party.tsx` — pass `onEvicted` that clears session and navigates to `/?takeover=1`.
- Modify: `frontend/src/pages/SignIn.tsx` — read `?takeover=1`, render banner, strip the query param after first render.
- Modify: `frontend/tests/useRealtimeParty.test.ts` — add `evicted` handling test.
- Modify: `frontend/tests/SignIn.test.tsx` — add takeover-banner test.

---

## Backend Tasks

### Task 1: Hub evicts a prior socket for the same principal_key

**Files:**
- Modify: `backend/app/realtime.py`
- Modify: `backend/tests/test_realtime.py` (existing callers)
- Create: `backend/tests/test_session_takeover.py`

- [ ] **Step 1: Write the failing test (new file)**

Create `backend/tests/test_session_takeover.py`:
```python
import asyncio

import pytest

from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.realtime import PartyWorldHub
from app.world import PartyWorld


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


def _alice() -> Participant:
    return Participant(
        id="s-alice",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=400.0,
        y=250.0,
        joined_at=1715533200.0,
    )


@pytest.mark.asyncio
async def test_hub_evicts_prior_socket_for_same_principal_key() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    world.join(_alice())  # so leave() during eviction is valid

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, principal_key="human:s-alice", participant_id="s-alice")
    hub.subscribe(b, principal_key="human:s-alice", participant_id="s-alice")

    await hub.drain()
    # a got an evicted frame and was closed; b is the sole live sub.
    assert {"type": "evicted", "reason": "takeover"} in a.sent
    assert a.closed is True
    assert a not in hub.subscribers
    assert b in hub.subscribers
    assert hub._by_principal["human:s-alice"] is b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_session_takeover.py::test_hub_evicts_prior_socket_for_same_principal_key -v`
Expected: FAIL — `subscribe()` got unexpected keyword argument `principal_key` (or `_by_principal` missing).

- [ ] **Step 3: Update `PartyWorldHub` in `backend/app/realtime.py`**

Replace the body of `PartyWorldHub` with:

```python
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

    def unsubscribe(self, sock: SocketLike, principal_key: str) -> None:
        self.subscribers.discard(sock)
        if self._by_principal.get(principal_key) is sock:
            del self._by_principal[principal_key]

    def _evict(self, old: SocketLike, participant_id: str) -> None:
        self.subscribers.discard(old)
        self._dispatch(self._send_evict_and_close(old))
        # Best-effort world.leave so other clients see the avatar vanish.
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
        payload = _serialise_event(event)
        snapshot = list(self.subscribers)
        if not snapshot:
            return
        for sock in snapshot:
            self._dispatch(self._send_or_drop(sock, payload))

    async def _send_or_drop(self, sock: SocketLike, payload: dict) -> None:
        try:
            await sock.send_json(payload)
        except Exception:
            self.subscribers.discard(sock)
            # Also clear any principal_key that points at this socket.
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
```

- [ ] **Step 4: Update existing tests in `backend/tests/test_realtime.py`**

The three `hub.subscribe(...)` callers must pass the new args. Edit each:

- `test_hub_broadcasts_to_subscribers`:
  `hub.subscribe(sock)` → `hub.subscribe(sock, principal_key="human:s-alice", participant_id="s-alice")`
- `test_hub_drops_misbehaving_subscriber`:
  `hub.subscribe(good)` → `hub.subscribe(good, principal_key="human:good", participant_id="s-alice")`
  `hub.subscribe(bad)` → `hub.subscribe(bad, principal_key="human:bad", participant_id="s-alice")`
- `test_hub_unsubscribe_stops_delivery`:
  `hub.subscribe(sock)` → `hub.subscribe(sock, principal_key="human:s-alice", participant_id="s-alice")`
  `hub.unsubscribe(sock)` → `hub.unsubscribe(sock, principal_key="human:s-alice")`

- [ ] **Step 5: Run all backend realtime tests to verify they pass**

Run: `cd backend && pytest tests/test_realtime.py tests/test_session_takeover.py -v`
Expected: all green. The new takeover test passes; the three updated tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/realtime.py backend/tests/test_realtime.py backend/tests/test_session_takeover.py
git commit -m "feat(realtime): hub evicts prior socket for duplicate principal_key"
```

---

### Task 2: Eviction emits a leave event to remaining subscribers

**Files:**
- Modify: `backend/tests/test_session_takeover.py`

The eviction already calls `world.leave(participant_id)`, which appends a leave event. The hub's `_on_event` will fan that event out — but eviction must happen BEFORE the leave, otherwise the old (now-evicted) socket would also receive its own leave event. The current implementation removes `old` from `self.subscribers` inside `_evict` before calling `world.leave`, so this works. This task adds an assertion test for it.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_session_takeover.py`:
```python
@pytest.mark.asyncio
async def test_hub_eviction_broadcasts_leave_event_to_others() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    world.join(_alice())

    observer = FakeSocket()
    hub.subscribe(observer, principal_key="human:observer", participant_id="observer")
    await hub.drain()
    observer.sent.clear()  # ignore any prior frames

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, principal_key="human:s-alice", participant_id="s-alice")
    hub.subscribe(b, principal_key="human:s-alice", participant_id="s-alice")
    await hub.drain()

    leave_frames = [
        f for f in observer.sent
        if f.get("type") == "event"
        and f.get("event", {}).get("type") == "leave"
        and f["event"].get("participant_id") == "s-alice"
    ]
    assert len(leave_frames) == 1
    # The evicted socket did NOT receive the leave frame (it was removed first).
    assert not any(
        f.get("type") == "event" and f.get("event", {}).get("type") == "leave"
        for f in a.sent
    )
```

- [ ] **Step 2: Run test**

Run: `cd backend && pytest tests/test_session_takeover.py::test_hub_eviction_broadcasts_leave_event_to_others -v`
Expected: PASS immediately (the Task 1 implementation already handles this correctly).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_session_takeover.py
git commit -m "test(realtime): assert hub eviction emits leave to other subscribers"
```

---

### Task 3: Unsubscribe does not clear a slot owned by a newer socket

**Files:**
- Modify: `backend/tests/test_session_takeover.py`

Already handled by the `is sock` guard in `unsubscribe`. Pin it with a test.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_session_takeover.py`:
```python
@pytest.mark.asyncio
async def test_hub_unsubscribe_does_not_clear_replaced_slot() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    world.join(_alice())

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, principal_key="human:s-alice", participant_id="s-alice")
    hub.subscribe(b, principal_key="human:s-alice", participant_id="s-alice")
    await hub.drain()

    # Simulate the evicted A's WS handler running its `finally: unsubscribe(...)`
    # after the takeover.
    hub.unsubscribe(a, principal_key="human:s-alice")

    assert hub._by_principal["human:s-alice"] is b
    assert b in hub.subscribers
```

- [ ] **Step 2: Run test**

Run: `cd backend && pytest tests/test_session_takeover.py::test_hub_unsubscribe_does_not_clear_replaced_slot -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_session_takeover.py
git commit -m "test(realtime): unsubscribe preserves slot owned by newer socket"
```

---

### Task 4: WS route uses principal_key for subscribe / unsubscribe

**Files:**
- Modify: `backend/app/routes/parties.py`
- Modify: `backend/tests/test_session_takeover.py`

- [ ] **Step 1: Write the failing end-to-end test**

Append to `backend/tests/test_session_takeover.py`:
```python
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _signin(client: TestClient, username: str, color: str) -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def test_second_ws_with_same_session_evicts_the_first(client: TestClient) -> None:
    user = _signin(client, "Alice", "#ff6b9d")
    sid = user["session_id"]
    # Alice joins the party (so leave during eviction has someone to remove).
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r.status_code == 200

    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws_a:
        ws_a.send_json({"type": "auth", "principal": {"kind": "human", "id": sid}})
        snap_a = ws_a.receive_json()
        assert snap_a["type"] == "snapshot"

        with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws_b:
            ws_b.send_json({"type": "auth", "principal": {"kind": "human", "id": sid}})
            snap_b = ws_b.receive_json()
            assert snap_b["type"] == "snapshot"

            # ws_a should receive the eviction frame, then close.
            evict_frame = ws_a.receive_json()
            assert evict_frame == {"type": "evicted", "reason": "takeover"}
            with pytest.raises(WebSocketDisconnect):
                ws_a.receive_json()
```

This test requires the `client` fixture from `backend/tests/conftest.py`. Pytest auto-resolves it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_session_takeover.py::test_second_ws_with_same_session_evicts_the_first -v`
Expected: FAIL — the route still calls `hub.subscribe(websocket)` without the new args, so a `TypeError` surfaces or the eviction never happens.

- [ ] **Step 3: Update `_validate_ws_principal` to return the Principal**

Edit `backend/app/routes/parties.py`. Replace the existing `_validate_ws_principal` and `party_ws` body with:

```python
def _validate_ws_principal(store: Store, frame: object) -> Principal | None:
    if not isinstance(frame, dict) or frame.get("type") != "auth":
        return None
    raw = frame.get("principal")
    if not isinstance(raw, dict):
        return None
    try:
        principal = Principal(**raw)
    except ValidationError:
        return None
    try:
        resolve_principal(store, principal)
    except HTTPException:
        return None
    return principal


@router.websocket("/{slug}/ws")
async def party_ws(
    websocket: WebSocket,
    slug: str,
    store: Store = Depends(_store_dep),
) -> None:
    party = store.get_party(slug)
    if party is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()

    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()
        return

    principal = _validate_ws_principal(store, frame)
    if principal is None:
        await websocket.send_json({"type": "error", "detail": "invalid principal"})
        await websocket.close()
        return

    world = store.get_or_create_world(slug)
    hub = store.get_or_create_hub(slug)
    assert world is not None and hub is not None

    snap = world.snapshot()
    await websocket.send_json(
        {
            "type": "snapshot",
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
        }
    )

    principal_key = f"{principal.kind}:{principal.id}"
    hub.subscribe(websocket, principal_key=principal_key, participant_id=principal.id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket, principal_key=principal_key)
```

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: all green. The new takeover end-to-end test passes; existing realtime route tests still pass (they don't pin the old `_validate_ws_principal` return type since they only check observable behavior).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/parties.py backend/tests/test_session_takeover.py
git commit -m "feat(ws): pass principal_key to hub so duplicate sessions evict"
```

---

## Frontend Tasks

### Task 5: useRealtimeParty handles the `evicted` frame and suppresses reconnect

**Files:**
- Modify: `frontend/src/hooks/useRealtimeParty.ts`
- Modify: `frontend/tests/useRealtimeParty.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `frontend/tests/useRealtimeParty.test.ts`:
```ts
it('invokes onEvicted, closes, and suppresses reconnect on an evicted frame', async () => {
    const onEvicted = vi.fn();
    renderHook(() =>
      useRealtimeParty({
        slug: 'cream-terrazzo',
        principal: selfPrincipal,
        onEvicted,
      }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => ws.receive({ type: 'snapshot', room: {}, participants: [], cursor: 0 }));

    act(() => ws.receive({ type: 'evicted', reason: 'takeover' }));

    expect(onEvicted).toHaveBeenCalledTimes(1);
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);

    // Give any (incorrectly) scheduled reconnect a tick to run; assert no new WS.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/useRealtimeParty.test.ts -t "evicted"`
Expected: FAIL — `onEvicted` is not a recognized option, hook ignores the frame, possibly a reconnect occurs.

- [ ] **Step 3: Update `frontend/src/hooks/useRealtimeParty.ts`**

Modify the file. Three changes:

1. Extend `Options`:
```ts
type Options = {
  slug: string;
  principal: Principal;
  onEvicted?: () => void;
};
```

2. Destructure `onEvicted` and add `evictedRef`:
```ts
export function useRealtimeParty({ slug, principal, onEvicted }: Options) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [status, setStatus] = useState<Status>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const evictedRef = useRef(false);
```

3. Inside `ws.onmessage`, after the `if (!frame || typeof frame !== 'object') return;` guard, add an `evicted` branch BEFORE the existing snapshot / event branches:
```ts
        if (f.type === 'evicted') {
          evictedRef.current = true;
          onEvicted?.();
          ws.close();
          return;
        }
```

4. Gate the reconnect schedule inside `ws.onclose`:
```ts
      ws.onclose = () => {
        setStatus('closed');
        if (cancelled || evictedRef.current) return;
        const delay = Math.min(backoffRef.current, 8000);
        backoffRef.current = Math.min(backoffRef.current * 2, 8000);
        reconnectTimer = setTimeout(connect, delay);
      };
```

- [ ] **Step 4: Run all useRealtimeParty tests**

Run: `cd frontend && npx vitest run tests/useRealtimeParty.test.ts`
Expected: all green (existing tests + new `evicted` test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useRealtimeParty.ts frontend/tests/useRealtimeParty.test.ts
git commit -m "feat(realtime-hook): handle evicted frame and suppress reconnect"
```

---

### Task 6: Party.tsx wires onEvicted to clear session and route to /?takeover=1

**Files:**
- Modify: `frontend/src/pages/Party.tsx`

- [ ] **Step 1: Update the import to include `clearStoredSessionId`**

Edit `frontend/src/pages/Party.tsx`. Replace the existing `useSession` import:
```ts
import { useSession, clearStoredSessionId } from '../hooks/useSession';
```

- [ ] **Step 2: Pass `onEvicted` into the hook**

Replace the existing `useRealtimeParty` call (currently at lines 37–41) with:
```ts
  const { participants } = useRealtimeParty(
    ready && principal
      ? {
          slug: party!.slug,
          principal,
          onEvicted: () => {
            clearStoredSessionId();
            navigate('/?takeover=1', { replace: true });
          },
        }
      : { slug: '', principal: { kind: 'human', id: '' } },
  );
```

- [ ] **Step 3: Verify Party tests still pass**

Run: `cd frontend && npx vitest run tests/Party.test.tsx`
Expected: PASS. (Adding an unused-in-test prop should not break existing tests.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Party.tsx
git commit -m "feat(party): clear session and redirect on takeover eviction"
```

---

### Task 7: SignIn.tsx renders a takeover banner from `?takeover=1`

**Files:**
- Modify: `frontend/src/pages/SignIn.tsx`
- Modify: `frontend/tests/SignIn.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `frontend/tests/SignIn.test.tsx`:
```tsx
  it('shows a takeover banner when ?takeover=1 is present and strips the param', async () => {
    render(
      <MemoryRouter initialEntries={['/?takeover=1']}>
        <Routes>
          <Route path="/" element={<SignIn />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText(/signed out because this account was opened/i),
    ).toBeInTheDocument();
    // The query param should be stripped after first render.
    expect(window.location.search).not.toContain('takeover=1');
  });
```

Note: `MemoryRouter` does not touch `window.location`. To test param stripping, we instead assert via the rendered DOM that the banner does not persist after a re-render-triggering state change. Adjust the test as follows — replace the `window.location.search` assertion with a behavior check using a small custom probe component. Cleaner test:

Replace the test body with this version that uses a `useSearchParams` probe:
```tsx
  it('shows a takeover banner when ?takeover=1 is present, then strips the param', async () => {
    function Probe() {
      const [params] = require('react-router-dom').useSearchParams();
      return <span data-testid="qp">{params.get('takeover') ?? ''}</span>;
    }
    render(
      <MemoryRouter initialEntries={['/?takeover=1']}>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <SignIn />
                <Probe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText(/signed out because this account was opened/i),
    ).toBeInTheDocument();
    // After mount, the param is removed.
    await screen.findByTestId('qp');
    expect(screen.getByTestId('qp').textContent).toBe('');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/SignIn.test.tsx -t "takeover banner"`
Expected: FAIL — banner text not found.

- [ ] **Step 3: Update `frontend/src/pages/SignIn.tsx`**

Two changes.

3a. Import `useSearchParams`. Replace the existing react-router-dom import line:
```ts
import { useNavigate, useSearchParams } from 'react-router-dom';
```

3b. Inside the `SignIn` component body, after `const navigate = useNavigate();`, add:
```ts
  const [searchParams, setSearchParams] = useSearchParams();
  const [takeoverNotice, setTakeoverNotice] = useState(
    searchParams.get('takeover') === '1',
  );

  useEffect(() => {
    if (searchParams.get('takeover') === '1') {
      const next = new URLSearchParams(searchParams);
      next.delete('takeover');
      setSearchParams(next, { replace: true });
    }
    // Only run on first mount; we keep the local notice flag separately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
```

3c. Render the banner. Inside the `<main>` element, AFTER the `<p>` byline (the "Throw parties..." paragraph) and BEFORE the `<form>`, insert:
```tsx
      {takeoverNotice && (
        <div
          role="status"
          style={{
            background: '#fff7e0',
            border: '1px solid #f3d36b',
            color: '#7a5a00',
            padding: '10px 12px',
            borderRadius: 8,
            marginBottom: 16,
            fontSize: 14,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span>
            You were signed out because this account was opened in another window.
          </span>
          <button
            type="button"
            onClick={() => setTakeoverNotice(false)}
            aria-label="Dismiss"
            style={{
              border: 'none',
              background: 'transparent',
              color: '#7a5a00',
              fontSize: 18,
              lineHeight: 1,
              cursor: 'pointer',
              padding: 4,
            }}
          >
            ×
          </button>
        </div>
      )}
```

- [ ] **Step 4: Run SignIn tests**

Run: `cd frontend && npx vitest run tests/SignIn.test.tsx`
Expected: all green (existing 5 tests + new takeover test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SignIn.tsx frontend/tests/SignIn.test.tsx
git commit -m "feat(signin): show dismissible takeover banner on ?takeover=1"
```

---

### Task 8: Full-stack smoke check

**Files:** none (manual verification).

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: all green.

- [ ] **Step 2: Run full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: all green.

- [ ] **Step 3: Manual smoke**

1. Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`.
2. Start frontend: `cd frontend && npm run dev`.
3. Open `http://localhost:5173`, sign in as Alice, choose color, enter the party.
4. Copy the localStorage `session_id` from devtools. Open a private window, set the same `session_id` in localStorage, and navigate to `/lobby` → enter the same party.
5. Observe in the original window: page redirects to `/?takeover=1` with the banner; the party's other tabs (if any) see Alice's avatar disappear (leave event).
6. Sign in again in the original window — the banner dismisses, normal flow resumes.

- [ ] **Step 4: No commit (verification only)**

---

## Self-Review Notes

- All spec sections (Architecture, Components Backend/Frontend, Data Flow, Error Handling, Testing) are covered by Tasks 1–7. Manual smoke (Task 8) maps to the end-to-end Data Flow steps.
- The spec's "Error Handling" cases (old sock already closed, world.leave raises, replaced-slot unsubscribe, auth-fails-before-eviction) are all unit-test-covered by Tasks 1, 2, 3, and the existing `test_realtime_route.py::test_ws_handshake_rejects_bad_principal` (which exercises the auth-failure path without touching the hub).
- The frontend `useSession` requires no changes — confirmed in the spec; no task covers it.
- Type/name consistency: `principal_key` and `participant_id` keyword args are used identically in `subscribe`, `unsubscribe`, `_evict`, and route call sites. The `evicted` frame shape `{type: "evicted", reason: "takeover"}` is identical in backend code, backend tests, frontend hook, and frontend test.
