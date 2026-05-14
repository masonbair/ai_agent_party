# Session Presence (Lobby-Wide Takeover)

**Date:** 2026-05-13
**Status:** Draft
**Branch:** `feat/session-takeover` (extends the in-progress work)

## Problem

The existing session takeover (see `2026-05-13-session-takeover-design.md`) only fires when both browsers reach the *same party* WebSocket. If Browser A is on the Lobby and Browser B opens the same app with the same `session_id`, neither side has a party-WS connection — so nothing evicts A.

We want eviction the moment a second authenticated browser instance exists, regardless of which authed page it's on.

Trigger: same `session_id` is used by a second long-lived connection. Out of scope: agent-only flows (agents register via HTTP and use party WS only — handled by the existing party-WS eviction), cross-account collision (different sessions, same username), idle timeout.

## Architecture

Add a session-scoped WebSocket separate from the party WS. Every authenticated route in the SPA opens it; the server tracks one live socket per `session_id` and evicts on duplicate. The party-WS eviction stays untouched as defense in depth and as the path for agents.

```
Lobby/Party mount ──open──▶ /api/session/ws  ──auth─▶ SessionPresenceHub.subscribe(sock, session_id)
                                                              │
                                                ┌─────────────┼──────────────┐
                                                ▼             ▼              ▼
                                          old sock exists?  register new   (no-op if none)
                                                │             sock
                                                ▼
                                          send {type:"evicted",reason:"takeover"}
                                          close old sock
                                          for world in store: world.leave(session_id) if member
```

Two independent units, mirroring the party layer:

- `SessionPresenceHub` — maps `session_id → socket`, performs the eviction.
- `session_ws` route — accepts the WS, validates the auth frame, hands the socket to the hub.

Cross-world cleanup happens *server-side* inside the hub: the hub holds a reference to the `Store` so it can iterate `Store.worlds()` and call `world.leave(session_id)` on any world the evicted user was joined to. Doing it server-side guarantees the avatar disappears even if the evicted browser is offline, slow, or in a tab the OS has throttled.

## Components

### Backend

**`backend/app/session_presence.py`** (new module)

```python
class SessionPresenceHub:
    def __init__(self, store_ref: StoreLike) -> None:
        self._store = store_ref            # for world iteration on evict
        self._by_session: dict[str, SocketLike] = {}
        self._pending: list[asyncio.Task] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def subscribe(self, sock: SocketLike, session_id: str) -> None: ...
    def unsubscribe(self, sock: SocketLike, session_id: str) -> None: ...
    def _evict(self, old: SocketLike, session_id: str) -> None: ...
    async def _send_evict_and_close(self, sock: SocketLike) -> None: ...
    def _dispatch(self, coro) -> None: ...
```

- `subscribe` follows the same shape as `PartyWorldHub.subscribe`: if a different socket already owns `session_id`, call `_evict(old, session_id)` then register new.
- `_evict` discards old from any internal tracking, dispatches the evict frame + close, then iterates `self._store.worlds()` and calls `world.leave(session_id)` on each world that contains a participant with that id (best-effort try/except).
- `unsubscribe` has the same `is sock` guard as the party hub.
- Async dispatch reuses the same pattern (`_capture_loop`, `_dispatch`) as `PartyWorldHub`.

`StoreLike` is a small Protocol:
```python
class StoreLike(Protocol):
    def worlds(self) -> Iterable[PartyWorld]: ...
```

**`backend/app/store.py`** (modify)

- Add `worlds(self) -> Iterable[PartyWorld]` returning `self._worlds.values()`.
- Add lazy `session_presence` property that creates one `SessionPresenceHub(self)` on first access (single instance for app lifetime).

**`backend/app/routes/session.py`** (modify)

Add a `@router.websocket("/ws")` endpoint:
- Accept the socket.
- Read first frame: `{type:"auth", session_id: str}`.
- If session not found in store → send `{type:"error", detail:"invalid session"}` and close.
- Else: `hub.subscribe(websocket, session_id)`, then loop on `receive_text()` (we never act on subsequent client frames; the loop keeps the socket alive until `WebSocketDisconnect`).
- `finally: hub.unsubscribe(websocket, session_id)`.

Route URL: `/api/session/ws` (the session router already has prefix `/api/session`).

### Frontend

**`frontend/src/hooks/useSessionPresence.ts`** (new)

```ts
type Options = { sessionId: string | null; onEvicted?: () => void };
export function useSessionPresence({ sessionId, onEvicted }: Options): void;
```

- When `sessionId` is non-null, open WS to `/api/session/ws`. Send `{type:"auth", session_id}` on open.
- On message `{type:"evicted"}`: set internal `evictedRef = true`, call `onEvicted?.()`, close socket, return.
- On message `{type:"error"}`: close. (Bad session; the page's existing `useSession` handler will redirect to sign-in via its 404 path.)
- On close: if `evictedRef`, do not reconnect. Otherwise reconnect with same backoff pattern as `useRealtimeParty` (1s → 8s cap).
- Cleanup on unmount: close socket, clear timers.

The hook returns nothing; effects fire via the callback.

**`frontend/src/pages/Lobby.tsx`** (modify)

Call `useSessionPresence({ sessionId, onEvicted })` where `sessionId` comes from `useSession` (only fires when `status === 'authed'`). `onEvicted` clears the stored session and navigates to `/?takeover=1`.

**`frontend/src/pages/Party.tsx`** (modify)

Same call as Lobby. The handler is identical to the one already wired into `useRealtimeParty`'s `onEvicted` — extract it into a local `const handleTakeover = () => { clearStoredSessionId(); navigate('/?takeover=1', { replace: true }); };` and pass it to both hooks.

## Data Flow

1. Alice signs in (Browser A). `useSession` reports `authed`. Lobby mounts and calls `useSessionPresence` → WS connects → server registers `_by_session["sid-A"] = sockA`.
2. Alice navigates to a party. Lobby unmounts → presence WS closes → server unsubscribes. Party mounts → presence WS opens again → re-registers. (Brief gap is OK; the hub is idempotent on register.)
3. Someone opens Browser B with the same `sid-A` in localStorage (copied or shared device). It lands on Lobby. `useSessionPresence` connects → server finds existing `sockA`:
   - Sends `{type:"evicted",reason:"takeover"}` to sockA.
   - Closes sockA.
   - Iterates worlds: if Alice is in `cream-terrazzo`, calls `world.leave("sid-A")` — leave event fans out to remaining party WS subscribers, the avatar disappears.
   - Registers `sockB`.
4. Browser A's presence hook receives the evict frame → calls `handleTakeover` → clears localStorage `session_id` → navigates to `/?takeover=1` → SignIn shows the banner.
5. Browser A's party WS (if it was on Party page) closes naturally as Party.tsx unmounts; its `finally: unsubscribe(...)` runs harmlessly (the world already booted the participant; the party hub's `is sock` guard does nothing destructive).

## Error Handling

| Case | Behavior |
|---|---|
| Auth frame missing / malformed | Send `{type:"error", detail:"invalid session"}`, close. |
| `session_id` not in store | Same — close cleanly, no eviction. |
| Old sock raises during evict send | Existing try/except swallows it; close path still runs. |
| `world.leave` raises (participant not actually in that world) | try/except per world; continue to next. |
| Evicted browser already navigated away when frame arrives | The browser tab is unmounted; the WS in the closed tab discards the frame. No-op. |
| Both browsers race (simultaneous connects) | Whichever the hub `subscribe` processes second wins. Single-threaded asyncio means there is no actual race; the loser is whichever sock arrived first. |

## Testing

**Backend (pytest):**
- `test_session_presence_evicts_prior_socket` — register fake socket A under `"sid-1"`; register B under same id; assert A received evicted frame, A closed, `_by_session["sid-1"] is B`.
- `test_session_presence_leaves_active_world_on_evict` — Alice joins `cream-terrazzo` via `world.join`; A subscribes presence; B takes over; assert `cream-terrazzo` world no longer contains `"sid-1"`.
- `test_session_presence_evict_handles_multiple_worlds` — Alice in two worlds (smoke test forward-compatibility); both worlds drop her.
- `test_session_ws_endpoint_evicts_duplicate` — TestClient: open `/api/session/ws` twice with same `session_id`, assert first receives evicted frame and closes.
- `test_session_ws_rejects_unknown_session_id` — send auth for a session that doesn't exist, assert error frame and close.

**Frontend (vitest):**
- `useSessionPresence` — feed mock WS an `evicted` frame; assert `onEvicted` fires once; assert no reconnect after backoff window.
- `useSessionPresence` — without `evicted`, an abnormal close triggers reconnect (parity with `useRealtimeParty`).
- `Lobby` — render with `useSession` returning authed; simulate the presence WS sending `evicted`; assert navigation to `/?takeover=1` and `session_id` cleared from localStorage.

## Open Questions

None.
