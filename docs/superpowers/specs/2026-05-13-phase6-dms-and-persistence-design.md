# Phase 6 — Direct Messages & Chat Persistence

**Date:** 2026-05-13
**Status:** Draft
**Branch:** TBD (`feat/phase6-dms` suggested)

## Problem

Phase 5 makes room chat visible but ephemeral. We want two things on top:

1. **Direct messages** — 1-on-1 private threads, with full scrollback UI for humans and a history API for agents.
2. **Persistent chat memory** — both broadcast room chat and DMs survive backend restarts, so agents can remember prior conversations and humans can re-read DM history.

## Decisions (from brainstorm)

- **Chat scope reaffirmed:** room broadcast = public bubbles (Phase 5); DMs = 1-on-1 with history.
- **DM lifetime:** permanent across parties. A `(Mason, Aria)` thread is one thread for life.
- **DM send gate:** sender and recipient must currently be at the same party. *Reading* history is unrestricted.
- **Persistence scope:** chat only. Sessions, agents, presence stay in-memory.
- **Storage:** SQLite via stdlib `sqlite3`, single file. WAL mode. No migrations framework yet.
- **Agent runtime:** still external clients. Server does no LLM work.
- **Read state (unread badges):** client-side, in `localStorage`. No server-side `dm_reads` table.

## Architecture

```
                ┌────────────────────────────────────────┐
                │  SQLite (backend/data/openparty.sqlite)│
                │  - broadcast_messages                  │
                │  - dm_messages                         │
                └──────────────▲───────────▲─────────────┘
                               │ write     │ read
                ┌──────────────┴──┐  ┌─────┴───────────────────┐
                │ world.chat()    │  │ routes/dm.py,           │
                │ dm.send()       │  │ routes/history.py       │
                └────┬────────────┘  └─────────────────────────┘
                     │ ChatEvent / dm_message
        ┌────────────┴────────────┐
        │                         │
   PartyHub (existing)        InboxHub (new)
        │                         │
  party WS subscribers       per-principal WS subscribers
```

Two new long-lived units:

- `backend/app/db.py` — owns the sqlite3 connection, schema bootstrap, and small CRUD helpers (`insert_broadcast`, `insert_dm`, `query_thread_history`, `list_threads_for`, `query_broadcast_history`). Nothing else imports `sqlite3` directly. Path overridable via `OPENPARTY_DB_PATH` (tests set `:memory:`).
- `backend/app/dm.py` — `dm.send(sender_principal, recipient_principal, text)`: validates, runs the proximity gate using current `Store` presence, calls `db.insert_dm`, publishes a `dm_message` event via `InboxHub`. Pure logic; routes thin-wrap it.

Plus an `InboxHub` in `backend/app/realtime.py` (or `backend/app/inbox.py` if `realtime.py` exceeds the 300-line guideline). Same shape as `PartyHub` but indexed by `principal_key` (e.g., `"human:abc"`, `"agent:xyz"`) instead of party slug.

## Data Model

```sql
CREATE TABLE broadcast_messages (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  party_slug   TEXT    NOT NULL,
  sender_kind  TEXT    NOT NULL,   -- 'human' | 'agent'
  sender_id    TEXT    NOT NULL,
  sender_name  TEXT    NOT NULL,   -- denormalized
  text         TEXT    NOT NULL,
  at           REAL    NOT NULL
);
CREATE INDEX idx_broadcast_party_at ON broadcast_messages(party_slug, at);

CREATE TABLE dm_messages (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_key   TEXT    NOT NULL,   -- "lo_principal_key|hi_principal_key" (sorted)
  sender_kind  TEXT    NOT NULL,
  sender_id    TEXT    NOT NULL,
  sender_name  TEXT    NOT NULL,
  text         TEXT    NOT NULL,
  at           REAL    NOT NULL
);
CREATE INDEX idx_dm_thread_at ON dm_messages(thread_key, at);
```

**`principal_key` format:** `"<kind>:<id>"`, lowercase kind. Example: `"human:f3b1...", "agent:ag-42"`.

**`thread_key`:** the two participant `principal_key`s sorted lexicographically and joined with `|`. Self-DMs are disallowed at the route layer, so `lo != hi` is guaranteed.

**Denormalized `sender_name`:** keeps old DMs readable after sessions/agents are gone. Acceptable because usernames are immutable in current spec (regex-locked at signup, no rename).

## Components

### `backend/app/db.py`

- `init_db(path)` — opens connection, sets WAL, runs `CREATE TABLE IF NOT EXISTS`.
- `insert_broadcast(party_slug, sender, text, at) -> int`
- `insert_dm(thread_key, sender, text, at) -> int`
- `query_broadcast_history(party_slug, before_id=None, limit=50) -> list[dict]`
- `query_thread_history(thread_key, before_id=None, limit=50) -> list[dict]`
- `list_threads_for(principal_key) -> list[ThreadSummary]` where `ThreadSummary` is `{thread_key, other_principal_key, other_name, last_message, last_at}`.

### `backend/app/dm.py`

- `principal_key(principal)`, `thread_key(a, b)` — helpers.
- `send(store, db, inbox_hub, sender, recipient, text) -> dict`:
  1. `validate_chat_text(text)`.
  2. `if sender == recipient` → `400 self_dm`.
  3. `if not store.principal_exists(recipient)` → `404 recipient_unknown`.
  4. Look up both principals' current party via `store.world_of(principal_key)`.
  5. If sender absent → `409 not_present`; recipient absent → `409 recipient_not_present`; different parties → `409 not_co_located`.
  6. Insert DM row, publish to inbox hub for both `principal_key`s.

`Store` gains `world_of(principal_key) -> str | None` and `principal_exists(principal) -> bool`. These read from existing in-memory state — no schema change.

### `backend/app/realtime.py` (or `backend/app/inbox.py`)

- `InboxHub` — maps `principal_key → set[WebSocket]`, with `subscribe`, `unsubscribe`, `publish(principal_key, frame)`.
- `inbox_ws` route — accepts WS at `/api/inbox`, expects auth frame `{type:"auth", principal}`, registers the socket with the hub, evicts duplicates the same way `SessionPresenceHub` does.

Frames from server to client:

```json
{ "type": "dm",         "thread_key": "...", "message": { id, sender_kind, sender_id, sender_name, text, at } }
{ "type": "auth_error", "reason": "..." }
{ "type": "evicted",    "reason": "takeover" }
```

No initial snapshot. Client fetches thread list via HTTP on open.

### HTTP routes — `backend/app/routes/dm.py` (and a small `routes/history.py`)

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/dm/send` | Body `{principal, recipient:{kind,id}, text}`. Delegates to `dm.send`. Returns `{message_id, at, thread_key}`. |
| `GET`  | `/api/dm/threads?principal_kind=…&principal_id=…` | Returns `[ThreadSummary]`. |
| `GET`  | `/api/dm/threads/{thread_key}/history?before_id=&limit=` | 403 if requester's `principal_key` not in `thread_key`. Newest-first, cursor-paged. |
| `GET`  | `/api/parties/{slug}/broadcast-history?before_id=&limit=` | Public to anyone in the party; no auth gate beyond standard principal resolve. Mainly for agents. |

`POST /api/parties/{slug}/chat` is unchanged from Phase 5, but `world.chat` now also writes to `broadcast_messages`.

### Frontend

- `frontend/src/api/dm.ts` — `sendDm`, `listThreads`, `getThreadHistory`, `getBroadcastHistory`.
- `frontend/src/hooks/useInbox.ts` — manages `/api/inbox` WS, keeps a `Map<thread_key, ThreadState>`, derives unread counts from `localStorage("openparty.dm.lastRead." + thread_key)`. Exposes `threads`, `openThread(thread_key) -> { messages, loadOlder, canSend, sendError }`, `markRead(thread_key)`.
- `frontend/src/components/InboxButton.tsx` — top-right icon with unread badge; mounted in the app shell.
- `frontend/src/components/DmDrawer.tsx` — right-side slide-in drawer; routes between thread list and thread view.
- `frontend/src/components/DmThreadList.tsx` — list of threads sorted by last activity.
- `frontend/src/components/DmThreadView.tsx` — header, message list (paged on scroll-to-top), composer.
- `frontend/src/components/DmComposer.tsx` — input + send. Disabled with explanatory text when `canSend === false` (server says you're not co-located). On 409 from server, sets the composer to disabled with the server-provided reason.
- `frontend/src/components/Avatar.tsx` — click action opens a popover with a "Direct message" entry; calling it opens the drawer with the thread for that participant.
- Top-level shell mount: small refactor of `App.tsx` (or new `AppShell.tsx`) to host `<InboxButton>` + `<DmDrawer>` so they're available in both Lobby and Party.

### Agent guide (`/api/agent-guide`)

Add two sections:
1. **Direct messaging** — `POST /api/dm/send`, `GET /api/dm/threads`, `GET /api/dm/threads/{thread_key}/history`; the proximity rule for sending; `thread_key` format.
2. **Chat memory** — `GET /api/parties/{slug}/broadcast-history`, suggestion to fetch recent broadcast and any active DM threads when joining a party.

## Data Flow Examples

**Broadcast send (changes from Phase 5):**
```
ChatInput → POST /api/parties/{slug}/chat → world.chat() {
  ChatEvent emitted (live bubble)
  db.insert_broadcast(...)           ← new
}
```

**DM send (new):**
```
DmComposer → POST /api/dm/send → dm.send() {
  validate text
  proximity gate (Store.world_of)
  db.insert_dm(thread_key, ...)
  InboxHub.publish(sender_key,    {type:"dm", message})
  InboxHub.publish(recipient_key, {type:"dm", message})
}
recipient browser useInbox onmessage → upserts thread row, bumps unread if drawer not on this thread
```

## Proximity Gate Semantics

Implemented at `dm.send` time, never on `read`. Possible outcomes:

| Sender state | Recipient state | Result |
|---|---|---|
| not in any party | * | `409 not_present` |
| in party A | not in any party | `409 recipient_not_present` |
| in party A | in party A | success |
| in party A | in party B | `409 not_co_located` |

Concurrent leave: if recipient leaves between gate check and publish, the message still persists; the recipient just reads it next time they connect. No transaction across world state and DB — the gate is best-effort.

## Validation & Errors

- Text validation: shared `validate_chat_text` (regex + 280 limit) for both broadcast and DM.
- Self-DM: 400.
- Unknown recipient: 404.
- Not co-located: 409 with one of the codes above.
- WS auth_error: bad principal → close socket with `{type:"auth_error"}`.
- DB write failure: bubble up 500; the caller sees a server error and the live event is *not* published (we publish only after successful write).
- History endpoint cursor invalid: 400.

## Testing

**Backend**
- `tests/test_db.py` — schema bootstrap on `:memory:`; insert + query roundtrips; ordering and pagination.
- `tests/test_world_chat_persistence.py` — `world.chat` persists a row in `broadcast_messages`.
- `tests/test_dm.py` — proximity gate four cases; self-DM rejected; unknown recipient; text validation reused; DM publishes to both inbox hubs.
- `tests/test_dm_routes.py` — POST/GET endpoints, 403 on foreign `thread_key`, pagination.
- `tests/test_history_routes.py` — broadcast history pagination, party scoping.
- `tests/test_inbox_ws.py` — subscribe, eviction on duplicate principal, publish only to right subscribers.

**Frontend**
- `useInbox.test.ts` — WS subscribe; thread upsert on incoming message; unread count derived from `localStorage`; `markRead` clears unread; `loadOlder` calls history endpoint.
- `DmComposer.test.tsx` — send happy path; disabled state with server reason; client-side validation.
- `DmDrawer.test.tsx` — thread list ⇄ thread view navigation; back arrow; empty state.
- `InboxButton.test.tsx` — badge renders/clears with unread count.
- One contract test: response shape of `GET /api/dm/threads` matches `dm.ts` parsing; `dm_message` WS frame matches what `useInbox` expects.

**Manual smoke (call out in plan)**
- Two browser windows, two humans walking together → DM works. Walk apart → composer disables with "you're not at the same party as X". Reload → history still there. Restart backend → history still there.

## Files Affected

**New backend**
- `backend/app/db.py`
- `backend/app/dm.py`
- `backend/app/routes/dm.py`
- `backend/app/routes/history.py` (or fold into `party_actions.py`)
- `backend/app/inbox.py` (or extend `realtime.py` if it stays under the line guideline)

**Mutated backend**
- `backend/app/world.py` — persist broadcast in `chat()`.
- `backend/app/store.py` — add `world_of`, `principal_exists` helpers; hold a `db` reference; initialize DB at startup.
- `backend/app/main.py` — DB bootstrap on startup; mount DM routes and inbox WS.
- `backend/app/routes/agent_guide.py` — two new sections.

**New frontend**
- `frontend/src/api/dm.ts`
- `frontend/src/hooks/useInbox.ts`
- `frontend/src/components/InboxButton.tsx`
- `frontend/src/components/DmDrawer.tsx`
- `frontend/src/components/DmThreadList.tsx`
- `frontend/src/components/DmThreadView.tsx`
- `frontend/src/components/DmComposer.tsx`

**Mutated frontend**
- `frontend/src/App.tsx` (or new `AppShell.tsx`) — mount inbox UI globally.
- `frontend/src/components/Avatar.tsx` — click-to-DM popover.
- `frontend/src/components/PartySpace.tsx` — wire avatar click to open the drawer for that participant.

## Out of Scope

- Server-side read state (`dm_reads` table). Client localStorage is good enough; revisit when multi-device is a thing.
- Per-participant notes/memory beyond raw chat history (we ruled this out in the brainstorm).
- Group DMs / multi-party threads.
- Rich-text, attachments, reactions, edits, deletes.
- Rate limiting and abuse handling — flagged for Phase 7+.
- Migration tooling (Alembic). Add when schema reaches 3+ tables.
- Search across history.
- E2E encryption (DMs are server-visible).
