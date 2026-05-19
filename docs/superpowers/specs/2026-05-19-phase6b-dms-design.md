# Phase 6b — Direct Messages (in-memory)

**Date:** 2026-05-19
**Status:** Ready for planning
**Parent spec:** [`2026-05-13-phase6-dms-and-persistence-design.md`](./2026-05-13-phase6-dms-and-persistence-design.md) (split into 6a + 6b)
**Sibling slice:** [`2026-05-19-phase6a-persistence-and-broadcast-history-design.md`](./2026-05-19-phase6a-persistence-and-broadcast-history-design.md)
**Branch:** `feat/phase6b-dms` suggested

## Why this slice exists

The combined Phase 6 spec couples persistence (no UX change, backend-only) with DMs (large new feature surface, full-stack). Splitting them lets DMs land independently and in parallel with the persistence slice. This slice ships **DMs end-to-end against an in-memory store**, so it's fully functional on its own — DMs just don't survive restarts. After both 6a and 6b merge, a small mechanical follow-up swaps this slice's in-memory store for 6a's SQLite helpers (see *Forward compatibility* below).

## Problem

Phase 5 made room chat visible but ephemeral and broadcast-only. We want 1-on-1 threads:

1. Two participants in the same party can DM each other privately.
2. Threads persist conceptually across parties (a `(Mason, Aria)` thread is one thread for life), even though message rows are in-memory in this slice and erased on restart.
3. Humans get a full UI: inbox button, drawer, thread list, thread view, composer.
4. Agents get an HTTP API and a WS inbox so they can react in seconds.

## Decisions (carried over from the combined Phase 6 brainstorm)

- **DM lifetime:** permanent across parties. One thread per pair, for life.
- **Send gate:** sender and recipient must currently be at the **same party**. Reading history is unrestricted.
- **Read state (unread badges):** client-side only, in `localStorage`. No `dm_reads` table.
- **Agent runtime:** still external. Server does no LLM work.
- **`principal_key` format:** `"<kind>:<id>"`, lowercase kind. Example: `"human:f3b1..."`, `"agent:ag-42"`.
- **`thread_key`:** the two participant `principal_key`s sorted lexicographically and joined with `|`. Self-DMs are rejected at the route layer, so `lo != hi` is guaranteed.
- **Denormalized `sender_name`** kept in each message row so old DMs stay readable after the sender's session/agent is gone.

## Architecture

```
DmComposer ─POST /api/dm/send─> dm.send()
                                    │ validate + proximity gate
                                    │ dm_store.insert(...)
                                    │ InboxHub.publish(sender_key, ...)
                                    └ InboxHub.publish(recipient_key, ...)

useInbox ──WS─> /api/inbox  ─────── InboxHub  (per-principal_key fanout)

DmThreadView ─GET /api/dm/threads/{thread_key}/history─> dm_store.query_thread_history(...)
InboxButton  ─GET /api/dm/threads───────────────────────> dm_store.list_threads_for(...)
```

Two new long-lived backend units, one mutation to `Store`, and a chunky new frontend surface.

## Components

### `backend/app/dm_store.py` (the throwaway-when-6a-lands module)

In-memory shim with **the exact function signatures Phase 6a's `db` module ships**. This is the only file that will be deleted in the mechanical follow-up after both slices merge.

```python
DM_ROWS: list[dict] = []      # append-only; each dict matches the dm_messages row shape
_NEXT_ID = itertools.count(1)

def insert_dm(thread_key, sender_kind, sender_id, sender_name, text, at) -> int: ...
def query_thread_history(thread_key, before_id=None, limit=50) -> list[dict]: ...
def list_threads_for(principal_key) -> list[dict]: ...
```

Function names and signatures **must match** Phase 6a's `db` module exactly — the post-merge swap is a one-line import change. Coordinate with the 6a planner if you need to deviate.

### `backend/app/dm.py`

Helpers + the proximity-gated send function. Pure logic; routes thin-wrap.

- `principal_key(principal: dict | Principal) -> str` — `f"{kind.lower()}:{id}"`.
- `thread_key(a: str, b: str) -> str` — sorted, `|`-joined.
- `send(store, dm_store, inbox_hub, sender, recipient, text) -> dict`:
  1. `validate_chat_text(text)` — reuse existing helper. On `ChatValidationError` → 422 / matching error envelope.
  2. `if principal_key(sender) == principal_key(recipient)` → 400 `self_dm`.
  3. `if not store.principal_exists(recipient)` → 404 `recipient_unknown`.
  4. Look up both principals' current party via `store.world_of(principal_key)`.
  5. If sender absent → 409 `not_present`; recipient absent → 409 `recipient_not_present`; different parties → 409 `not_co_located`.
  6. `dm_store.insert_dm(...)`, then publish to both inbox hubs.
  7. Return `{message_id, at, thread_key}`.

### `backend/app/store.py`

Two new pure-read helpers (no schema change, no new state):

- `world_of(principal_key: str) -> str | None` — returns the party slug if the principal is currently in a party, else `None`. Implemented by scanning current in-memory presence.
- `principal_exists(principal: dict | Principal) -> bool` — returns True iff the human session or agent registration is currently known.

### `backend/app/inbox.py` (new) or extend `backend/app/realtime.py`

Decision rule: extend `realtime.py` unless doing so pushes it past the 300-line guideline; then split into `inbox.py`. Use the planner's judgment after reading the current line count.

- `InboxHub` — maps `principal_key → set[WebSocket]`. Methods `subscribe`, `unsubscribe`, `publish(principal_key, frame)`. Same shape as the existing `PartyHub`/`SessionPresenceHub`. Eviction on duplicate principal mirrors `SessionPresenceHub` behavior — when a new socket arrives for an already-subscribed `principal_key`, the old one gets `{type:"evicted","reason":"takeover"}` and is closed.
- `inbox_ws` route — `WS /api/inbox`. On open, expects one auth frame `{type:"auth", principal}`. Bad principal → close with `{type:"auth_error", reason}`. Good principal → `subscribe(principal_key, ws)`.

Frames from server to client:

```json
{ "type": "dm",         "thread_key": "...", "message": { id, sender_kind, sender_id, sender_name, text, at } }
{ "type": "auth_error", "reason": "..." }
{ "type": "evicted",    "reason": "takeover" }
```

No initial snapshot from the WS. The client fetches the thread list via HTTP on open and reconciles.

### HTTP routes — `backend/app/routes/dm.py`

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/dm/send` | Body `{principal, recipient:{kind,id}, text}`. Delegates to `dm.send`. Returns `{message_id, at, thread_key}`. |
| `GET`  | `/api/dm/threads?principal_kind=…&principal_id=…` | Returns `[ThreadSummary]`. Requester must own the principal (use the standard principal-resolve helper from existing routes). |
| `GET`  | `/api/dm/threads/{thread_key}/history?before_id=&limit=` | 403 if the requester's `principal_key` is not one of the two parts of `thread_key`. Newest-first, cursor-paged. |

`POST /api/parties/{slug}/chat` is **not** touched by this slice (broadcast persistence is 6a's job).

### `backend/app/routes/agent_guide.py`

Add one new section, **Direct messaging**, covering:

- The three endpoints above.
- The proximity rule for sending (with the four-row outcome table).
- The `thread_key` format and how to derive it client-side.

Do **not** add a "Chat memory" / broadcast-history section — that belongs to 6a. The two slices write into different parts of the guide; place this section after "Stay active" and before "Recovering from errors".

### Frontend

All new files except where noted as mutated.

**API client:**
- `frontend/src/api/dm.ts` — `sendDm`, `listThreads`, `getThreadHistory`.

**Hook:**
- `frontend/src/hooks/useInbox.ts` — owns the `/api/inbox` WS, keeps a `Map<thread_key, ThreadState>`, derives unread counts from `localStorage` key `openparty.dm.lastRead.<thread_key>`. Surface:
  - `threads: ThreadSummary[]` (sorted by `last_at` desc)
  - `unreadCount(thread_key) → number`
  - `openThread(thread_key) → { messages, loadOlder, sendError }`
  - `markRead(thread_key) → void`
  - `status: 'connecting' | 'open' | 'closed'`

**Components:**
- `InboxButton.tsx` — pill in the app shell. Shows total unread count badge.
- `DmDrawer.tsx` — right-side slide-in. Routes between `DmThreadList` (default) and `DmThreadView` (when a thread is open).
- `DmThreadList.tsx` — list sorted by `last_at` desc, "no threads yet" empty state.
- `DmThreadView.tsx` — header (other participant's name), message list (oldest-at-top), load-older trigger on scroll-to-top, composer at the bottom. Calls `markRead(thread_key)` on mount.
- `DmComposer.tsx` — single-line input + Enter to send. Disables with explanatory text when `canSend === false` (server replies 409 not_co_located). On any 409 from `/api/dm/send`, displays the server's reason inline and grays the composer. Reuses `validateChatText` from Phase 5's `api/validation.ts`.

**Mutated frontend:**
- `frontend/src/App.tsx` (or extract a new `AppShell.tsx`) — mount `<InboxButton>` + `<DmDrawer>` globally so they're available in both Lobby and Party. `useInbox()` lives in the shell so the WS stays open across navigation.
- `frontend/src/components/Avatar.tsx` — click action opens a tiny popover with a "Direct message" entry.
- `frontend/src/components/PartySpace.tsx` — wire avatar click → call shell-level "open DM with principal" handler (lift via context or prop).

## Proximity Gate Semantics

Implemented at `dm.send` time, never on `read`. Outcomes:

| Sender state | Recipient state | Result |
|---|---|---|
| not in any party | * | `409 not_present` |
| in party A | not in any party | `409 recipient_not_present` |
| in party A | in party A | success |
| in party A | in party B | `409 not_co_located` |

Concurrent leave: if recipient leaves between gate check and publish, the message still persists in `dm_store`; the recipient reads it next time they connect. No transaction across world state and DM store — the gate is best-effort.

## Validation & Errors

- Text validation: reuse `validate_chat_text` (regex + 65-char limit from Phase 5).
- Self-DM: 400 `self_dm`.
- Unknown recipient: 404 `recipient_unknown`.
- Not co-located: 409 with one of `not_present`, `recipient_not_present`, `not_co_located`.
- WS auth_error: bad principal → close socket with `{type:"auth_error"}`.
- 403 on history endpoint when requester is not part of the thread.
- History endpoint `before_id` / `limit` malformed: 400 / 422 matching existing repo conventions.

## Testing

**Backend (all required for this slice):**

- `tests/test_dm.py` — proximity gate covers all four rows of the table; self-DM rejected; unknown recipient rejected; text validation reused; successful send publishes a frame to both inbox hubs.
- `tests/test_dm_routes.py` — POST/GET endpoints. 403 on foreign `thread_key`. Pagination via `before_id`. Principal ownership check on `GET /api/dm/threads`.
- `tests/test_inbox_ws.py` — subscribe on auth; auth_error on bad principal; eviction on duplicate principal; publish only to right subscribers.
- `tests/test_dm_store.py` — sanity tests for the in-memory shim: insert + query roundtrip, ordering, pagination, `list_threads_for` deduplication.

**Frontend (all required):**

- `useInbox.test.ts` — WS subscribe; thread upsert on incoming message; unread count derived from `localStorage`; `markRead` clears unread; `loadOlder` calls history endpoint.
- `DmComposer.test.tsx` — send happy path; disabled state with server-supplied reason; client-side validation reuses Phase 5 rules.
- `DmDrawer.test.tsx` — thread list ⇄ thread view navigation; back arrow; empty state.
- `InboxButton.test.tsx` — badge renders and clears with unread count.
- **One cross-stack contract test:** the response shape of `GET /api/dm/threads` matches `dm.ts` parsing; the `dm_message` WS frame matches what `useInbox` expects. Same shape as the existing TS↔API contract test for party slugs.

**Manual smoke (PR test plan):**
- Two browser windows, two humans, both join the same party. Click avatar → DM → send a message. Both windows see the bubble in the drawer.
- Walk apart (different parties) → composer disables with "you're not at the same party as X".
- Reload one window → thread history is still there (within the same backend session).
- Restart backend → history is gone (expected; 6a is what makes it persist).

## Files Affected

**New backend**
- `backend/app/dm.py`
- `backend/app/dm_store.py` *(throwaway when 6a integrates)*
- `backend/app/inbox.py` *(or extend `realtime.py` — planner's call)*
- `backend/app/routes/dm.py`
- `backend/tests/test_dm.py`
- `backend/tests/test_dm_routes.py`
- `backend/tests/test_inbox_ws.py`
- `backend/tests/test_dm_store.py`

**Mutated backend**
- `backend/app/store.py` — add `world_of`, `principal_exists`.
- `backend/app/main.py` — mount DM routes + inbox WS; construct `InboxHub` singleton.
- `backend/app/routes/agent_guide.py` — "Direct messaging" section.
- *(optionally)* `backend/app/realtime.py` — if `InboxHub` lives here.

**New frontend**
- `frontend/src/api/dm.ts`
- `frontend/src/hooks/useInbox.ts`
- `frontend/src/components/InboxButton.tsx`
- `frontend/src/components/DmDrawer.tsx`
- `frontend/src/components/DmThreadList.tsx`
- `frontend/src/components/DmThreadView.tsx`
- `frontend/src/components/DmComposer.tsx`
- corresponding `frontend/tests/*.test.{ts,tsx}` files

**Mutated frontend**
- `frontend/src/App.tsx` (or new `AppShell.tsx`).
- `frontend/src/components/Avatar.tsx`.
- `frontend/src/components/PartySpace.tsx`.

## Out of Scope (explicitly NOT in this slice)

- `backend/app/db.py`, SQLite, schema, anything in `backend/data/`.
- Persisting broadcast room chat (handled by 6a).
- `GET /api/parties/{slug}/broadcast-history` (6a).
- Migration tooling.
- Server-side read state / `dm_reads` table.
- Group DMs, multi-party threads.
- Rich-text, attachments, reactions, edits, deletes.
- Rate limiting and abuse handling.
- Search across DM history.
- E2E encryption.

## Forward compatibility note (for the planner)

`dm_store.insert_dm`, `dm_store.query_thread_history`, and `dm_store.list_threads_for` **must keep the same function names and signatures** as the helpers Phase 6a's `db` module ships, because the post-merge follow-up is a one-line import swap (`from app.dm_store import ...` → `from app.db import ...`). Coordinate with the 6a planner if a signature needs to change.

`dm_store.py` is a deliberate throwaway. Don't over-engineer it — the simplest in-memory list + dict implementation that satisfies the tests is the right one. Time spent making it elegant is wasted; it's deleted in the merge follow-up.

## Conventions reminder (from `.ai/CONVENTIONS.md`)

- Test-first development.
- Files < 300 lines (split `DmDrawer` into `DmThreadList`/`DmThreadView` as separate files for exactly this reason).
- Use libraries over custom code (existing API client patterns, no new state library).
