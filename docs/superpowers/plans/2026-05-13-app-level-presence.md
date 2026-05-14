# App-Level Presence + Leave-On-Disconnect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the navigation race that logs users out when entering a party, AND make tab close remove the user's avatar from any party they were in.

**Architecture:** Replace per-page `useSessionPresence` calls (Lobby + Party) with a single instance mounted at App.tsx. A new `SessionIdContext` provides reactive session_id state. On the server, clean WS disconnect schedules `world.leave` for that session after a 3-second grace period; the same session reconnecting cancels the timer.

**Tech Stack:** Backend: Python 3.11+, FastAPI, pytest-asyncio. Frontend: React 18, TypeScript, vitest, React Testing Library.

**Spec:** `docs/superpowers/specs/2026-05-13-app-level-presence-design.md`

---

## File Map

**Backend**
- Modify: `backend/app/session_presence.py` — add `_pending_leaves`, grace-period leave scheduling.
- Modify: `backend/tests/test_session_presence.py` — three new tests.

**Frontend**
- Create: `frontend/src/contexts/SessionIdContext.tsx`
- Create: `frontend/src/components/SessionPresenceManager.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/hooks/useSession.ts` — read from context; remove obsolete exports.
- Modify: `frontend/src/pages/SignIn.tsx` — use `setSessionId` from context.
- Modify: `frontend/src/pages/Lobby.tsx` — remove `useSessionPresence` call and related imports.
- Modify: `frontend/src/pages/Party.tsx` — remove `useSessionPresence` call; party-WS `onEvicted` uses context.
- Modify: `frontend/tests/SignIn.test.tsx` — wrap renders in `<SessionIdProvider>`.
- Modify: `frontend/tests/Lobby.test.tsx` — wrap renders; delete the obsolete presence-WS test.
- Modify: `frontend/tests/Party.test.tsx` — wrap renders.
- Create: `frontend/tests/SessionIdContext.test.tsx`
- Create: `frontend/tests/App.test.tsx`

---

## Backend Tasks

### Task 1: Grace-period leave on clean disconnect

**Files:**
- Modify: `backend/app/session_presence.py`
- Modify: `backend/tests/test_session_presence.py`

- [ ] **Step 1: Append three failing tests to `backend/tests/test_session_presence.py`**

```python
@pytest.mark.asyncio
async def test_clean_unsubscribe_schedules_leave_after_grace() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_alice())
    store = FakeStoreWithWorlds([world])
    hub = SessionPresenceHub(store)
    hub.GRACE_SECONDS = 0.05  # speed up the test

    a = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.unsubscribe(a, "sid-1")

    await asyncio.sleep(0.15)
    assert "sid-1" not in world.participants


@pytest.mark.asyncio
async def test_resubscribe_within_grace_cancels_leave() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_alice())
    store = FakeStoreWithWorlds([world])
    hub = SessionPresenceHub(store)
    hub.GRACE_SECONDS = 0.1

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.unsubscribe(a, "sid-1")
    # Resubscribe quickly — should cancel pending leave.
    await asyncio.sleep(0.02)
    hub.subscribe(b, "sid-1")

    await asyncio.sleep(0.15)
    assert "sid-1" in world.participants


@pytest.mark.asyncio
async def test_eviction_still_leaves_immediately() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_alice())
    store = FakeStoreWithWorlds([world])
    hub = SessionPresenceHub(store)
    hub.GRACE_SECONDS = 10.0  # ensure the grace-path is not what removes Alice

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.subscribe(b, "sid-1")  # evicts a
    await hub.drain()

    # Eviction must remove Alice immediately, without waiting for grace.
    assert "sid-1" not in world.participants
```

- [ ] **Step 2: Run — expect failures**

```
backend/.venv/bin/pytest backend/tests/test_session_presence.py -v -k "grace or immediately"
```

- [ ] **Step 3: Modify `backend/app/session_presence.py`**

Replace the file with:

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
```

- [ ] **Step 4: Run — expect PASS**

```
backend/.venv/bin/pytest backend/tests/test_session_presence.py -v
```

- [ ] **Step 5: Run full backend suite**

```
backend/.venv/bin/pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/session_presence.py backend/tests/test_session_presence.py
git commit -m "feat(session-presence): grace-period leave on clean disconnect"
```

---

## Frontend Tasks

### Task 2: Create `SessionIdContext`

**Files:**
- Create: `frontend/src/contexts/SessionIdContext.tsx`
- Create: `frontend/tests/SessionIdContext.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/SessionIdContext.test.tsx`:
```tsx
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  SessionIdProvider,
  useSessionId,
} from '../src/contexts/SessionIdContext';

function Probe() {
  const { sessionId, setSessionId } = useSessionId();
  return (
    <>
      <span data-testid="sid">{sessionId ?? ''}</span>
      <button onClick={() => setSessionId('sid-2')}>set</button>
      <button onClick={() => setSessionId(null)}>clear</button>
    </>
  );
}

describe('SessionIdContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    localStorage.clear();
  });

  it('initializes sessionId from localStorage', () => {
    localStorage.setItem('session_id', 'sid-stored');
    render(
      <SessionIdProvider>
        <Probe />
      </SessionIdProvider>,
    );
    expect(screen.getByTestId('sid').textContent).toBe('sid-stored');
  });

  it('setSessionId(id) updates state and writes localStorage', () => {
    render(
      <SessionIdProvider>
        <Probe />
      </SessionIdProvider>,
    );
    act(() => {
      screen.getByText('set').click();
    });
    expect(screen.getByTestId('sid').textContent).toBe('sid-2');
    expect(localStorage.getItem('session_id')).toBe('sid-2');
  });

  it('setSessionId(null) clears state and removes localStorage entry', () => {
    localStorage.setItem('session_id', 'sid-stored');
    render(
      <SessionIdProvider>
        <Probe />
      </SessionIdProvider>,
    );
    act(() => {
      screen.getByText('clear').click();
    });
    expect(screen.getByTestId('sid').textContent).toBe('');
    expect(localStorage.getItem('session_id')).toBeNull();
  });
});
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

```
cd frontend && npx vitest run tests/SessionIdContext.test.tsx
```

- [ ] **Step 3: Create the context**

Create `frontend/src/contexts/SessionIdContext.tsx`:
```tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export const SESSION_ID_KEY = 'session_id';

type SessionIdContextValue = {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
};

const SessionIdContext = createContext<SessionIdContextValue | null>(null);

export function SessionIdProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionIdState] = useState<string | null>(
    () => localStorage.getItem(SESSION_ID_KEY),
  );
  const setSessionId = useCallback((id: string | null) => {
    if (id == null) localStorage.removeItem(SESSION_ID_KEY);
    else localStorage.setItem(SESSION_ID_KEY, id);
    setSessionIdState(id);
  }, []);

  return (
    <SessionIdContext.Provider value={{ sessionId, setSessionId }}>
      {children}
    </SessionIdContext.Provider>
  );
}

export function useSessionId(): SessionIdContextValue {
  const ctx = useContext(SessionIdContext);
  if (ctx == null) {
    throw new Error('useSessionId must be used inside <SessionIdProvider>');
  }
  return ctx;
}
```

- [ ] **Step 4: Run — expect PASS**

```
cd frontend && npx vitest run tests/SessionIdContext.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/SessionIdContext.tsx frontend/tests/SessionIdContext.test.tsx
git commit -m "feat(session): SessionIdContext provider mirroring localStorage"
```

---

### Task 3: Create `SessionPresenceManager` component

**Files:**
- Create: `frontend/src/components/SessionPresenceManager.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/SessionPresenceManager.tsx`:
```tsx
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionId } from '../contexts/SessionIdContext';
import { useSessionPresence } from '../hooks/useSessionPresence';

export default function SessionPresenceManager() {
  const { sessionId, setSessionId } = useSessionId();
  const navigate = useNavigate();

  const onEvicted = useCallback(() => {
    setSessionId(null);
    navigate('/?takeover=1', { replace: true });
  }, [navigate, setSessionId]);

  useSessionPresence({ sessionId, onEvicted });
  return null;
}
```

This is verified by Task 9's App test; no per-component test is needed.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SessionPresenceManager.tsx
git commit -m "feat(session): SessionPresenceManager component"
```

---

### Task 4: Wire `App.tsx` with provider and manager

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import { Route, Routes } from 'react-router-dom';
import SessionPresenceManager from './components/SessionPresenceManager';
import { SessionIdProvider } from './contexts/SessionIdContext';
import Lobby from './pages/Lobby';
import Party from './pages/Party';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <SessionIdProvider>
      <SessionPresenceManager />
      <Routes>
        <Route path="/" element={<SignIn />} />
        <Route path="/lobby" element={<Lobby />} />
        <Route path="/party/:slug" element={<Party />} />
      </Routes>
    </SessionIdProvider>
  );
}
```

- [ ] **Step 2: Run full frontend suite — expect PASS**

The Lobby and Party tests still render those pages directly (not via `<App>`), so the manager isn't mounted in those tests. Existing behavior is preserved.

```
cd frontend && npx vitest run
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(app): wrap routes in SessionIdProvider with SessionPresenceManager"
```

---

### Task 5: Migrate `useSession` and `SignIn` to use the context

**Files:**
- Modify: `frontend/src/hooks/useSession.ts`
- Modify: `frontend/src/pages/SignIn.tsx`
- Modify: `frontend/tests/SignIn.test.tsx`
- Modify: `frontend/tests/Lobby.test.tsx`
- Modify: `frontend/tests/Party.test.tsx`

This task switches `useSession` to read from `SessionIdContext` and SignIn to write via it. All page tests must wrap renders in `<SessionIdProvider>` in the SAME commit so tests stay green.

- [ ] **Step 1: Replace `frontend/src/hooks/useSession.ts`**

```ts
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { useSessionId } from '../contexts/SessionIdContext';
import type { User } from '../api/types';

type State =
  | { status: 'loading' }
  | { status: 'authed'; user: User }
  | { status: 'anon' };

export function useSession(): State {
  const { sessionId, setSessionId } = useSessionId();
  const [state, setState] = useState<State>({ status: 'loading' });
  const navigate = useNavigate();

  useEffect(() => {
    if (!sessionId) {
      setState({ status: 'anon' });
      navigate('/', { replace: true });
      return;
    }
    setState({ status: 'loading' });
    apiGet<User>(`/api/session/${sessionId}`)
      .then((user) => setState({ status: 'authed', user }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setSessionId(null);
        }
        setState({ status: 'anon' });
        navigate('/', { replace: true });
      });
  }, [sessionId, navigate, setSessionId]);

  return state;
}
```

(The `setStoredSessionId`/`clearStoredSessionId`/`getStoredSessionId` exports are removed in Task 8 once all callers are migrated; for now, leave them in place but unused.)

Wait — actually keep them in this commit too, since callers (Party.tsx) still import them. We'll delete after Task 7. To keep this file compiling, leave the old `STORAGE_KEY` and exports at the bottom for now.

Use this version that preserves the old exports:
```ts
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { useSessionId } from '../contexts/SessionIdContext';
import type { User } from '../api/types';

const STORAGE_KEY = 'session_id';

export function getStoredSessionId(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setStoredSessionId(id: string): void {
  localStorage.setItem(STORAGE_KEY, id);
}

export function clearStoredSessionId(): void {
  localStorage.removeItem(STORAGE_KEY);
}

type State =
  | { status: 'loading' }
  | { status: 'authed'; user: User }
  | { status: 'anon' };

export function useSession(): State {
  const { sessionId, setSessionId } = useSessionId();
  const [state, setState] = useState<State>({ status: 'loading' });
  const navigate = useNavigate();

  useEffect(() => {
    if (!sessionId) {
      setState({ status: 'anon' });
      navigate('/', { replace: true });
      return;
    }
    setState({ status: 'loading' });
    apiGet<User>(`/api/session/${sessionId}`)
      .then((user) => setState({ status: 'authed', user }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setSessionId(null);
        }
        setState({ status: 'anon' });
        navigate('/', { replace: true });
      });
  }, [sessionId, navigate, setSessionId]);

  return state;
}
```

- [ ] **Step 2: Update `frontend/src/pages/SignIn.tsx`**

Two changes:

2a. Replace the import line:
```ts
import {
  clearStoredSessionId,
  getStoredSessionId,
  setStoredSessionId,
} from '../hooks/useSession';
```
with:
```ts
import { useSessionId } from '../contexts/SessionIdContext';
```

2b. Inside the `SignIn` component body, after `const [searchParams, setSearchParams] = useSearchParams();`, add:
```ts
  const { setSessionId } = useSessionId();
```

2c. Remove the entire `useEffect` block that calls `getStoredSessionId()` and `apiGet(...)` — that responsibility moved to `useSession`/the context. The remaining useEffect (takeover param stripping) stays.

Actually wait — SignIn's purpose is to render the form when the user is NOT signed in. If they ARE signed in (valid session in localStorage), SignIn should auto-redirect to /lobby. That logic exists today as a useEffect in SignIn.

Better path: SignIn should call `useSession()`. If `session.status === 'authed'`, navigate to `/lobby`. This is the same pattern Lobby/Party use.

2c (revised): replace the existing useEffect (which manually calls `apiGet` to validate) with:
```ts
  const session = useSession();
  useEffect(() => {
    if (session.status === 'authed') {
      navigate('/lobby', { replace: true });
    }
  }, [session.status, navigate]);
```

Drop the previous `useEffect` that called `apiGet`. Drop the `apiGet`/`ApiError`/`User` imports if no longer used.

2d. Replace `setStoredSessionId(user.session_id);` in `onSubmit` with:
```ts
      setSessionId(user.session_id);
```

- [ ] **Step 3: Wrap renders in all page tests with `<SessionIdProvider>`**

For each of the three test files, wrap the `<MemoryRouter>` block in a `<SessionIdProvider>`. Example pattern (do this for `SignIn.test.tsx`, `Lobby.test.tsx`, `Party.test.tsx`):

Add to the import block at the top of each file:
```ts
import { SessionIdProvider } from '../src/contexts/SessionIdContext';
```

Then wrap every `render(...)` call's outermost element:
```tsx
render(
  <SessionIdProvider>
    <MemoryRouter initialEntries={[...]}>
      {/* ...existing children... */}
    </MemoryRouter>
  </SessionIdProvider>,
);
```

Apply the same wrap to the `renderSignIn()` helper inside `SignIn.test.tsx`.

- [ ] **Step 4: Run all frontend tests — expect PASS**

```
cd frontend && npx vitest run
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSession.ts frontend/src/pages/SignIn.tsx frontend/tests/SignIn.test.tsx frontend/tests/Lobby.test.tsx frontend/tests/Party.test.tsx
git commit -m "feat(session): useSession + SignIn use SessionIdContext"
```

---

### Task 6: Remove `useSessionPresence` from Lobby

**Files:**
- Modify: `frontend/src/pages/Lobby.tsx`
- Modify: `frontend/tests/Lobby.test.tsx`

- [ ] **Step 1: Replace `frontend/src/pages/Lobby.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyConfig } from '../api/types';
import PartyPreview from '../components/PartyPreview';
import { useSession } from '../hooks/useSession';

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

- [ ] **Step 2: Remove the now-obsolete presence-WS test from `frontend/tests/Lobby.test.tsx`**

Delete the entire `it('opens a session presence WebSocket when authed', ...)` block (it asserts behavior that has moved to the App-level manager).

If `vi.unstubAllGlobals` was added to the suite `afterEach` solely for that test, remove it as well — no other test in this file stubs globals.

- [ ] **Step 3: Run Lobby tests — expect PASS**

```
cd frontend && npx vitest run tests/Lobby.test.tsx
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Lobby.tsx frontend/tests/Lobby.test.tsx
git commit -m "refactor(lobby): drop per-page useSessionPresence (moved to App)"
```

---

### Task 7: Remove `useSessionPresence` from Party; rewire party-WS `onEvicted`

**Files:**
- Modify: `frontend/src/pages/Party.tsx`

- [ ] **Step 1: Replace `frontend/src/pages/Party.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PartySpace from '../components/PartySpace';
import { ApiError, apiGet } from '../api/client';
import type { PartyConfig } from '../api/types';
import { useSession } from '../hooks/useSession';
import { joinParty, leaveParty, moveInParty, type Principal } from '../api/party';
import { useRealtimeParty } from '../hooks/useRealtimeParty';
import { useSessionId } from '../contexts/SessionIdContext';

export default function Party() {
  const session = useSession();
  const navigate = useNavigate();
  const { setSessionId } = useSessionId();
  const { slug } = useParams<{ slug: string }>();
  const [party, setParty] = useState<PartyConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leaveHovered, setLeaveHovered] = useState(false);

  useEffect(() => {
    if (!slug || session.status !== 'authed') return;
    apiGet<PartyConfig>(`/api/parties/${slug}`)
      .then(setParty)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setError('Party not found');
          navigate('/lobby', { replace: true });
        } else {
          setError('Failed to load party');
        }
      });
  }, [slug, session.status, navigate]);

  const ready = session.status === 'authed' && party !== null;
  const principal: Principal | null = ready
    ? { kind: 'human', id: session.user.session_id }
    : null;

  const handleTakeover = useCallback(() => {
    setSessionId(null);
    navigate('/?takeover=1', { replace: true });
  }, [navigate, setSessionId]);

  const { participants } = useRealtimeParty(
    ready && principal
      ? { slug: party!.slug, principal, onEvicted: handleTakeover }
      : { slug: '', principal: { kind: 'human', id: '' } },
  );

  useEffect(() => {
    if (!ready || !principal || !party) return;
    const slugForCleanup = party.slug;
    const pForCleanup = principal;
    joinParty(slugForCleanup, pForCleanup).catch(() => {});
    return () => {
      leaveParty(slugForCleanup, pForCleanup).catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, party?.slug, principal?.id]);

  if (session.status !== 'authed') return null;
  if (error && !party) return <p role="alert">{error}</p>;
  if (!party) return <p>Loading party…</p>;

  const onMove = (x: number, y: number) => {
    if (!principal) return;
    moveInParty(party.slug, principal, x, y).catch(() => {});
  };

  return (
    <main>
      <header
        style={{
          padding: 'clamp(8px, 2vw, 16px) clamp(12px, 3vw, 24px)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h1 style={{ margin: 0, fontSize: 'clamp(20px, 4vw, 28px)' }}>{party.name}</h1>
        <button
          type="button"
          onClick={() => navigate('/lobby')}
          onMouseEnter={() => setLeaveHovered(true)}
          onMouseLeave={() => setLeaveHovered(false)}
          style={{
            background: party.theme.accent,
            color: '#fff',
            border: 'none',
            padding: '8px 16px',
            borderRadius: 999,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            transform: leaveHovered ? 'translateY(-1px)' : 'translateY(0)',
            boxShadow: leaveHovered
              ? '0 4px 10px rgba(0,0,0,0.15)'
              : '0 2px 6px rgba(0,0,0,0.10)',
            transition: 'transform 120ms ease, box-shadow 120ms ease',
          }}
        >
          ← Leave party
        </button>
      </header>
      <PartySpace
        party={party}
        user={session.user}
        participants={participants}
        onMove={onMove}
      />
    </main>
  );
}
```

(Differences from current file: removed `useSessionPresence` import and call; removed the import of `clearStoredSessionId` from `'../hooks/useSession'`; added `useSessionId` import; `handleTakeover` now uses `setSessionId(null)` instead of `clearStoredSessionId()`.)

- [ ] **Step 2: Run Party tests — expect PASS**

```
cd frontend && npx vitest run tests/Party.test.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Party.tsx
git commit -m "refactor(party): drop per-page useSessionPresence; rewire takeover via context"
```

---

### Task 8: Remove now-unused exports from `useSession.ts`

**Files:**
- Modify: `frontend/src/hooks/useSession.ts`

- [ ] **Step 1: Replace `frontend/src/hooks/useSession.ts`**

```ts
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { useSessionId } from '../contexts/SessionIdContext';
import type { User } from '../api/types';

type State =
  | { status: 'loading' }
  | { status: 'authed'; user: User }
  | { status: 'anon' };

export function useSession(): State {
  const { sessionId, setSessionId } = useSessionId();
  const [state, setState] = useState<State>({ status: 'loading' });
  const navigate = useNavigate();

  useEffect(() => {
    if (!sessionId) {
      setState({ status: 'anon' });
      navigate('/', { replace: true });
      return;
    }
    setState({ status: 'loading' });
    apiGet<User>(`/api/session/${sessionId}`)
      .then((user) => setState({ status: 'authed', user }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setSessionId(null);
        }
        setState({ status: 'anon' });
        navigate('/', { replace: true });
      });
  }, [sessionId, navigate, setSessionId]);

  return state;
}
```

(Removed: `STORAGE_KEY`, `getStoredSessionId`, `setStoredSessionId`, `clearStoredSessionId`.)

- [ ] **Step 2: Confirm no other files reference the removed exports**

```
cd frontend && grep -rn "getStoredSessionId\|setStoredSessionId\|clearStoredSessionId" src/ tests/
```
Expected output: nothing.

- [ ] **Step 3: Run full frontend suite — expect PASS**

```
cd frontend && npx vitest run
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useSession.ts
git commit -m "refactor(session): remove obsolete localStorage exports from useSession"
```

---

### Task 9: New App-level test — single WS across navigation

**Files:**
- Create: `frontend/tests/App.test.tsx`

- [ ] **Step 1: Write the test**

Create `frontend/tests/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

class FakeWS {
  static instances: FakeWS[] = [];
  static SESSION_WS_INSTANCES: FakeWS[] = [];
  url: string;
  readyState = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  sent: string[] = [];
  constructor(url: string) {
    this.url = url;
    FakeWS.instances.push(this);
    if (url.includes('/api/session/ws')) {
      FakeWS.SESSION_WS_INSTANCES.push(this);
    }
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.(new Event('open'));
    });
  }
  send(payload: string) {
    this.sent.push(payload);
  }
  close() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent('close'));
  }
}

const partyResponse = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: { clipPath: null, border: '6px solid #8b6f47', borderRadius: 12, walls: [] },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('App-level session presence', () => {
  beforeEach(() => {
    FakeWS.instances = [];
    FakeWS.SESSION_WS_INSTANCES = [];
    vi.stubGlobal('WebSocket', FakeWS);
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      const u = String(url);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (u.includes('/api/session/')) {
        return jsonResponse({ session_id: 'sid-1', username: 'Alice', color: '#ff6b9d' });
      }
      if (u.endsWith('/api/parties') && method === 'GET') {
        return jsonResponse({ parties: [partyResponse] });
      }
      if (u.endsWith('/api/parties/cream-terrazzo')) {
        return jsonResponse(partyResponse);
      }
      if (method === 'POST' && u.endsWith('/api/parties/cream-terrazzo/join')) {
        return jsonResponse({
          participant: {
            id: 'sid-1',
            kind: 'human',
            username: 'Alice',
            color: '#ff6b9d',
            x: 100,
            y: 100,
          },
          cursor: 0,
        });
      }
      if (method === 'POST' && u.endsWith('/api/parties/cream-terrazzo/leave')) {
        return new Response(null, { status: 204 });
      }
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('opens exactly one session WS that persists across Lobby -> Party navigation', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <App />
      </MemoryRouter>,
    );

    // Wait for Lobby to render.
    await screen.findByText(/Pick a party/);
    expect(FakeWS.SESSION_WS_INSTANCES).toHaveLength(1);
    const sessionWs = FakeWS.SESSION_WS_INSTANCES[0];

    // Click into the party. Lobby unmounts; Party mounts.
    await userEvent.click(
      await screen.findByRole('button', { name: /cream terrazzo lounge/i }),
    );

    // The Party page header should render.
    await screen.findByText(/Cream Terrazzo Lounge/);

    // Still exactly one session WS — the original — never closed.
    expect(FakeWS.SESSION_WS_INSTANCES).toHaveLength(1);
    expect(FakeWS.SESSION_WS_INSTANCES[0]).toBe(sessionWs);
    expect(sessionWs.readyState).toBe(1);
  });
});
```

- [ ] **Step 2: Run the test — expect PASS**

```
cd frontend && npx vitest run tests/App.test.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/App.test.tsx
git commit -m "test(app): verify session WS persists across navigation"
```

---

### Task 10: Smoke check

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

1. `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
2. `cd frontend && npm run dev`
3. Sign in as Alice in Browser A → Lobby. Click into the party. Confirm you do NOT get logged out (this was the original bug).
4. Open a private Browser B; set the same `session_id` in localStorage; navigate to `/lobby`. Confirm Browser A is bounced to `/?takeover=1` with the banner and (if A was in the party) Alice's avatar disappears for any third observer.
5. Sign in fresh in Browser A. Enter the party. Close the tab. After ~3 seconds, observe in a third browser that Alice's avatar disappears from the party.
6. Sign in fresh in Browser A. Enter the party. Disable network for 1 second, re-enable. Confirm Alice's avatar stays (reconnect within grace).

- [ ] **Step 4: No commit (verification only)**

---

## Self-Review Notes

- **Spec coverage:**
  - Navigation race fix → Task 4 (App-level manager) + Task 9 (test).
  - Grace-period leave on clean disconnect → Task 1.
  - SessionIdContext → Task 2.
  - SessionPresenceManager component → Task 3.
  - SignIn / useSession migration → Task 5.
  - Lobby cleanup → Task 6.
  - Party cleanup + party-WS handler rewire → Task 7.
  - Obsolete export removal → Task 8.
  - Single-WS-across-nav test → Task 9.
- **Type consistency:** `setSessionId(id | null)` uniform across context, useSession, SignIn, SessionPresenceManager, Party.
- **No placeholders or unfilled code blocks.**
- **Each commit leaves the test suite green** because the context migration (Task 5) wraps page tests in the provider in the same commit as the useSession switch.
