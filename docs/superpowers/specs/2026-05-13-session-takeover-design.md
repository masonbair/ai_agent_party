# Session Takeover (Second-Connection-Wins)

**Date:** 2026-05-13
**Status:** Draft
**Branch:** `feat/session-takeover` (off `feat/phase4-multiplayer`)

## Problem

A `session_id` can currently be reused in multiple browser tabs or windows (shared `localStorage`, manual copy). Both connections appear as the same participant, and the world ends up with conflicting movement from "one" person. We want exactly one live WebSocket per principal: the newest connection wins; the older one is forced back to sign-in and removed from the party.

Trigger: the **same `session_id`** (or `agent_id`) authenticates a second WebSocket while an earlier one is still live. This applies symmetrically to humans and agents — the hub treats any duplicate principal the same.

Out of scope: cross-party takeover (the user only inhabits one party at a time in the current UI), idle/timeout eviction, multi-device "approved sessions" UX, rate limiting.

## Architecture

The takeover lives entirely at the WebSocket layer. HTTP endpoints (`/api/session`, party actions) are not changed — they're stateless per call and naturally tolerate duplicate use.

Per-party `PartyWorldHub` already owns the set of live subscribers for one world. We extend it with a principal → socket index so a new `subscribe` call can evict any prior socket for that principal.

```
new WS  ──auth──▶  party_ws handler
                       │
                       ▼
              hub.subscribe(sock, principal_key)
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  old sock exists?  register new   (no-op if none)
        │              sock
        ▼
  send {type:"evicted"}  ──▶ old browser
  close old sock (4001)
  world.leave(participant_id) ──▶ broadcasts "leave"
```

## Components

### Backend

**`PartyWorldHub` (`backend/app/realtime.py`)**

Add:
```python
self._by_principal: dict[str, SocketLike] = {}
```

Change `subscribe(sock)` → `subscribe(sock, principal_key, participant_id)`:
1. Look up `old = self._by_principal.get(principal_key)`.
2. If `old is not None and old is not sock`:
   - Schedule `old.send_json({"type": "evicted", "reason": "takeover"})` (best-effort, swallow exceptions).
   - Schedule `old.close(code=4001)`.
   - Remove `old` from `self.subscribers`.
   - Call `self.world.leave(participant_id)` — this appends a `leave` event, which the hub fans out to remaining subscribers so other clients see the avatar disappear.
3. `self._by_principal[principal_key] = sock`; `self.subscribers.add(sock)`.

Change `unsubscribe(sock)`:
- Discard `sock` from `self.subscribers`.
- If `self._by_principal.get(principal_key) is sock`, remove that key. **Do not** remove if a newer sock has already replaced it (the new sock owns the slot).

Scheduling note: the hub already captures an event loop in `_capture_loop` and dispatches via `create_task` or `run_coroutine_threadsafe`. Eviction must use the same dispatch path so it works under both the live ASGI server and `TestClient` (which runs sync routes in a worker thread).

**`routes/parties.py` — `party_ws` handler**

`_validate_ws_principal` currently returns `bool`. Change it to return `Principal | None` so the handler can build `principal_key = f"{principal.kind}:{principal.id}"` after auth.

Replace `hub.subscribe(websocket)` with:
```python
hub.subscribe(websocket, principal_key, participant_id=principal.id)
```

The `finally` block calls `hub.unsubscribe(websocket, principal_key)`. The `principal_key` is passed explicitly (rather than reverse-looking it up) so the unsubscribe path is symmetric with subscribe and doesn't scan the dict.

### Frontend

**`useRealtimeParty.ts` — handle `evicted`**

Add an optional `onEvicted?: () => void` to `Options`.

Add an `evictedRef = useRef(false)`. In `onmessage`:
```ts
if (f.type === 'evicted') {
  evictedRef.current = true;
  onEvicted?.();
  ws.close();
  return;
}
```

In `onclose`, gate the reconnect scheduling:
```ts
if (cancelled || evictedRef.current) return;
```

**`Party.tsx` — wire the handler**

Pass `onEvicted` into `useRealtimeParty`:
```ts
onEvicted: () => {
  clearStoredSessionId();
  navigate('/?takeover=1', { replace: true });
}
```

**`SignIn.tsx` — takeover banner**

On mount, read `searchParams.get('takeover')`. If present:
- Render a notice above the form: "You were signed out because this account was opened in another window."
- Remove the query param via `setSearchParams({}, { replace: true })` so a refresh doesn't keep the banner.

**`useSession.ts`** — no changes required. The existing 404 handler in `useSession` already clears `session_id` and routes home if the session record is gone; takeover doesn't delete the session record, only kicks the older socket, so the local cleanup is driven by the WS path.

## Data Flow

1. Browser A authenticates WS to `/api/parties/cream-terrazzo/ws` with `session_id=S`. Hub records `human:S → A`.
2. Browser B (same `S`, copied via localStorage / second tab) opens WS to same path. Auth succeeds.
3. Hub finds `human:S → A` already mapped. It:
   - Sends `{type:"evicted",reason:"takeover"}` to A.
   - Closes A with code 4001.
   - Calls `world.leave(S)` → broadcasts `leave` event to all remaining sockets in the party.
   - Maps `human:S → B`.
4. B receives the next snapshot/events without A's avatar.
5. A's frontend gets `evicted`, suppresses reconnect, clears `session_id`, routes to `/?takeover=1`.
6. SignIn shows the banner.

## Error Handling

| Case | Behavior |
|---|---|
| Old sock already closed when we try to evict | `send_json` raises → existing `_send_or_drop` pattern catches and drops. We still clear the index and proceed. |
| `world.leave` raises (participant somehow already gone) | Log and continue — index still updated, new sock still registered. |
| New WS auth fails (invalid principal) | Old socket is untouched — eviction only runs after successful auth. Existing `invalid principal` close path stands. |
| `unsubscribe` runs after a newer socket replaced this one | The `if self._by_principal.get(key) is sock` guard prevents clearing the newer slot. |

## Testing

**Backend (pytest):**
- `test_hub_evicts_prior_socket_for_same_principal` — register fake socket A with `principal_key="human:S"`, register fake socket B with same key; assert A received `evicted` frame, A was closed, B is the sole entry in `_by_principal`.
- `test_hub_evicts_emits_leave_event` — same setup, plus a third subscriber C with a different principal; assert C receives a `leave` event for the evicted participant.
- `test_hub_unsubscribe_does_not_clear_replaced_slot` — A subscribes, B takes over, A's `unsubscribe` runs (simulating its delayed teardown); assert `_by_principal["human:S"] is B`.
- `test_ws_endpoint_evicts_duplicate_session` (TestClient end-to-end) — open one WS, auth, then open a second with the same `session_id`; assert the first WS receives an `evicted` frame and closes.

**Frontend (vitest + RTL):**
- `useRealtimeParty` — feed a mock WS an `evicted` frame; assert `onEvicted` callback fires once, the socket closes, no reconnect timer is scheduled.
- `SignIn` — render with `?takeover=1`; assert banner is visible; assert query param is cleared after mount.

## Migration / Compatibility

No data migration. Old clients (pre-update) that don't recognize the `evicted` frame still observe the socket close and will attempt a reconnect; the server will accept that reconnect as a new takeover (now evicting whichever browser was the most recent winner). The user-visible effect is a brief reconnect loop until one tab is closed — acceptable for an unrelated edge case, since deploying frontend and backend together avoids it in practice.

## Open Questions

None blocking implementation.
