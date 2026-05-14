# App-Level Presence + Leave-On-Disconnect

**Date:** 2026-05-13
**Status:** Draft
**Branch:** `feat/session-takeover` (extends in-progress work)

## Problem

Two related issues with the current per-page `useSessionPresence`:

1. **Navigation race.** When the user moves from Lobby to Party in the same tab, the Lobby's presence WS closes and the Party's opens. If the new auth frame arrives at the server *before* the close packet is processed, the server thinks Party's WS is a duplicate of the still-registered Lobby socket, evicts it (no-op — already closing), and as a side effect calls `world.leave(session_id)` across all worlds — kicking the user out of the party they just joined.

2. **Tab close does not remove the avatar.** When the user closes the tab while in a party, Party.tsx's leave-on-unmount HTTP call may not complete before the browser kills the process. The avatar persists in the world for everyone else.

## Solution Overview

- **Move the presence WS to a single instance at the App level.** It opens when the user is authenticated and stays open across page navigation. No close/open race during normal navigation.
- **On clean WS disconnect, schedule `world.leave` across all worlds after a 3-second grace period.** The same session reconnecting within the grace cancels the timer. Real tab closes (no reconnect) trigger the leave.
- **Eviction keeps its existing immediate `world.leave`** — a takeover should not wait.

Out of scope: auto-rejoin after a long network blip; reconciling per-tab claim tokens.

## Architecture

```
App.tsx
 ├── SessionIdProvider              (reactive sessionId state, mirrors localStorage)
 │    ├── SessionPresenceManager     (calls useSessionPresence once; handles onEvicted)
 │    └── Routes
 │         ├── SignIn                (no longer calls useSessionPresence)
 │         ├── Lobby                 (no longer calls useSessionPresence)
 │         └── Party                 (no longer calls useSessionPresence;
 │                                    party-WS hook keeps its own onEvicted as before)
```

The presence WS lifecycle is now tied to App.tsx, not page mounts. Page navigation never tears it down.

## Components

### Frontend

**`frontend/src/contexts/SessionIdContext.tsx` (new)**

```ts
type SessionIdContextValue = {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
};

const SESSION_ID_KEY = 'session_id';

export function SessionIdProvider({children}: {children: React.ReactNode}) {
  const [sessionId, setSessionIdState] = useState<string | null>(
    () => localStorage.getItem(SESSION_ID_KEY)
  );
  const setSessionId = useCallback((id: string | null) => {
    if (id == null) localStorage.removeItem(SESSION_ID_KEY);
    else localStorage.setItem(SESSION_ID_KEY, id);
    setSessionIdState(id);
  }, []);
  // ...provide context
}

export function useSessionId(): SessionIdContextValue;
```

The provider is the only place that writes to `localStorage["session_id"]`.

**`frontend/src/App.tsx`**

```tsx
<SessionIdProvider>
  <SessionPresenceManager />
  <Routes>
    <Route path="/" element={<SignIn />} />
    <Route path="/lobby" element={<Lobby />} />
    <Route path="/party/:slug" element={<Party />} />
  </Routes>
</SessionIdProvider>
```

`SessionPresenceManager` reads `sessionId` from context and calls `useSessionPresence({sessionId, onEvicted})`. `onEvicted` calls `setSessionId(null)` and `navigate('/?takeover=1', {replace: true})`. The component renders `null`.

**`frontend/src/pages/SignIn.tsx` (modify)**
- Replace `setStoredSessionId(user.session_id)` with `setSessionId(user.session_id)` from context.

**`frontend/src/hooks/useSession.ts` (modify)**
- Read `sessionId` from `useSessionId()` instead of `getStoredSessionId()`.
- On 404 from `GET /api/session/{id}`, call `setSessionId(null)` instead of `clearStoredSessionId()`.
- Internal effect re-runs when `sessionId` changes.

**`frontend/src/pages/Lobby.tsx` (modify — remove)**
- Delete the `useSessionPresence` call, the `useCallback` for `onEvicted`, and the `clearStoredSessionId` / `useSessionPresence` imports.

**`frontend/src/pages/Party.tsx` (modify — partial cleanup)**
- Delete the `useSessionPresence` call. The party-WS hook's `onEvicted` STAYS (it's the agent path and defense in depth). Change that `onEvicted` to call `setSessionId(null)` + `navigate` via the same context approach (extracted into `handleTakeover = useCallback(...)`).

**`frontend/src/hooks/useSession.ts` exports cleanup**
- Remove `setStoredSessionId` and `clearStoredSessionId` exports — the context owns localStorage now. `getStoredSessionId` can also be removed; the context reads `localStorage.getItem(SESSION_ID_KEY)` directly in its initializer.

**`frontend/tests/Lobby.test.tsx` (modify — remove)**
- Delete the `'opens a session presence WebSocket when authed'` test (covered by a new App-level test).

**`frontend/tests/App.test.tsx` (new)**
- Render `<App>` wrapped with `<MemoryRouter>` and assert: with a valid stored session_id, a WebSocket constructor is called for `/api/session/ws` exactly once across navigation between `/lobby` and `/party/cream-terrazzo`.

### Backend

**`backend/app/session_presence.py` (modify)**

Add grace-period leave scheduling:

```python
GRACE_SECONDS = 3.0

class SessionPresenceHub:
    def __init__(self, store: StoreLike) -> None:
        ...
        self._pending_leaves: dict[str, asyncio.TimerHandle] = {}

    def subscribe(self, sock, session_id):
        # cancel any pending leave timer for this session
        timer = self._pending_leaves.pop(session_id, None)
        if timer is not None:
            timer.cancel()
        # existing eviction logic continues
        ...

    def unsubscribe(self, sock, session_id):
        if self._by_session.get(session_id) is sock:
            del self._by_session[session_id]
            self._schedule_leave(session_id)

    def _schedule_leave(self, session_id: str) -> None:
        if self._loop is None:
            # No captured loop yet (only happens before any subscribe). Skip.
            return
        existing = self._pending_leaves.pop(session_id, None)
        if existing is not None:
            existing.cancel()
        handle = self._loop.call_later(
            GRACE_SECONDS,
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
```

Eviction (`_evict`) stays unchanged — it calls `world.leave` immediately (no grace).

For test ergonomics, expose the grace constant on the class so a test can monkey-patch a tiny value (or accept an override in the constructor — see tests).

### Testing

**Backend (`backend/tests/test_session_presence.py` — append):**
- `test_clean_unsubscribe_schedules_leave_after_grace` — patch `GRACE_SECONDS` to 0.05; Alice joins world; subscribe + unsubscribe; `await asyncio.sleep(0.1)`; assert Alice not in world.
- `test_resubscribe_within_grace_cancels_leave` — same setup; resubscribe at 0.02s; sleep to 0.1s; assert Alice still in world.
- `test_eviction_still_leaves_immediately` — A subscribes; Alice joins; B subscribes (evicts A). Assert Alice immediately not in world (no waiting for grace).

**Frontend:**
- New `frontend/tests/SessionIdContext.test.tsx`: provider initializes from localStorage; `setSessionId(id)` updates state and localStorage; `setSessionId(null)` clears both.
- New `frontend/tests/App.test.tsx`: WebSocket constructor count = 1 across an in-memory navigation Lobby → Party.
- Existing `useRealtimeParty` and `SignIn` tests continue to pass with minor adjustments (SignIn writes via context; tests should wrap render in `<SessionIdProvider>`).
- Delete the obsolete Lobby test asserting presence-WS.

## Migration / Cleanup Summary

| File | Action |
|---|---|
| `frontend/src/contexts/SessionIdContext.tsx` | **CREATE** |
| `frontend/src/components/SessionPresenceManager.tsx` | **CREATE** (small component calling the hook) |
| `frontend/src/App.tsx` | **MODIFY** — wrap with provider + manager |
| `frontend/src/hooks/useSession.ts` | **MODIFY** — read from context; remove `setStoredSessionId` / `clearStoredSessionId` / `getStoredSessionId` exports |
| `frontend/src/pages/SignIn.tsx` | **MODIFY** — use `useSessionId().setSessionId` |
| `frontend/src/pages/Lobby.tsx` | **MODIFY** — remove `useSessionPresence`, `useCallback` for `onEvicted`, related imports |
| `frontend/src/pages/Party.tsx` | **MODIFY** — remove `useSessionPresence`; rewire party-WS `onEvicted` to use context |
| `frontend/tests/Lobby.test.tsx` | **MODIFY** — delete the presence-WS test |
| `frontend/tests/SignIn.test.tsx` | **MODIFY** — wrap render in `<SessionIdProvider>` |
| `frontend/tests/Party.test.tsx` | **MODIFY** — wrap render in `<SessionIdProvider>` |
| `frontend/tests/App.test.tsx` | **CREATE** — single-WS-across-navigation assertion |
| `frontend/tests/SessionIdContext.test.tsx` | **CREATE** |
| `backend/app/session_presence.py` | **MODIFY** — pending-leaves dict, schedule on clean unsubscribe, cancel on subscribe |
| `backend/tests/test_session_presence.py` | **MODIFY** — three new tests for grace behavior |

## Error Handling

- **`_loop is None` when `_schedule_leave` runs.** Only possible if `unsubscribe` is the first hub call (before any `subscribe` captures the loop). Skip the schedule silently. In practice this never happens because subscribe always runs first.
- **`world.leave` raises** when the participant isn't in that world. Already handled by per-world try/except in `_run_leave`.
- **Timer races with eviction.** If a takeover happens while a pending leave is scheduled for the same session_id, the new `subscribe` cancels the timer (we don't want to leave AFTER a new tab takes over). The eviction's own immediate `world.leave` covers the actual takeover semantics.
- **App.tsx unmounts in unexpected order.** Provider unmounts after children. The presence WS cleanup runs during App teardown — same as tab close.

## Open Questions

None blocking.
