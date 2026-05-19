# Phase 6a — Chat Persistence & Broadcast History

**Date:** 2026-05-19
**Status:** Ready for planning
**Parent spec:** [`2026-05-13-phase6-dms-and-persistence-design.md`](./2026-05-13-phase6-dms-and-persistence-design.md) (split into 6a + 6b)
**Sibling slice:** [`2026-05-19-phase6b-dms-design.md`](./2026-05-19-phase6b-dms-design.md)
**Branch:** `feat/phase6a-persistence` suggested

## Why this slice exists

The combined Phase 6 spec couples two unrelated wins: durable chat (no UX change, but survives restarts) and direct messages (large new feature surface). Splitting persistence into its own slice lets it land first as a clean substrate and lets DMs be developed in parallel without a shared blocking path. After both 6a and 6b merge, a small mechanical follow-up swaps 6b's in-memory DM store for the SQLite helpers this slice ships (see *Forward compatibility* below).

## Problem

Phase 5 room chat is ephemeral: backend restart erases everything anyone ever said. We want:

1. Broadcast chat messages to survive restarts.
2. An HTTP endpoint agents (and any future "scrollback" UI) can use to fetch recent room chat.

That's the entire scope of this slice. No DMs, no new WS, no new frontend.

## Decisions (carried over from the combined Phase 6 brainstorm)

- **Storage:** SQLite via stdlib `sqlite3`. Single file. WAL mode. No migrations framework yet (add Alembic when schema reaches 3+ tables).
- **Persistence scope:** chat only. Sessions, agents, presence stay in-memory.
- **Path:** `backend/data/openparty.sqlite` by default; `OPENPARTY_DB_PATH` env var overrides (tests set `:memory:`).
- **Denormalized `sender_name`** kept in each row so old messages stay readable after the sender's session/agent is gone. Acceptable because usernames are immutable in the current spec (regex-locked at signup, no rename flow).
- **Live bubbles unchanged.** `world.chat()` still emits a `ChatEvent` to the in-memory hub exactly as it does today; persistence is an *additional* write, not a replacement. Read paths (`observe`, WS) are untouched.

## Architecture

```
ChatInput ──POST /chat──> world.chat()
                              │
                              ├── ChatEvent on PartyHub (unchanged, Phase 5)
                              └── db.insert_broadcast(...)         ← NEW

                                      ╲
                                       ╲   sqlite3 (WAL)
                                        ╲
GET /api/parties/{slug}/broadcast-history── db.query_broadcast_history(...)
```

One new long-lived unit:

- `backend/app/db.py` — owns the `sqlite3.Connection`, schema bootstrap, and small CRUD helpers. Nothing else in the codebase imports `sqlite3` directly. Connection is created at app startup, attached to `Store`, and closed at shutdown.

## Data Model

This slice creates the **full Phase 6 schema** even though only `broadcast_messages` is exercised here. Including `dm_messages` now means the post-merge integration with 6b is a pure call-site swap (in-memory shim → existing `db` helpers) — no follow-up migration.

```sql
CREATE TABLE IF NOT EXISTS broadcast_messages (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  party_slug   TEXT    NOT NULL,
  sender_kind  TEXT    NOT NULL,   -- 'human' | 'agent'
  sender_id    TEXT    NOT NULL,
  sender_name  TEXT    NOT NULL,
  text         TEXT    NOT NULL,
  at           REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_broadcast_party_at ON broadcast_messages(party_slug, at);

CREATE TABLE IF NOT EXISTS dm_messages (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_key   TEXT    NOT NULL,   -- "lo_principal_key|hi_principal_key"
  sender_kind  TEXT    NOT NULL,
  sender_id    TEXT    NOT NULL,
  sender_name  TEXT    NOT NULL,
  text         TEXT    NOT NULL,
  at           REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dm_thread_at ON dm_messages(thread_key, at);
```

## Components

### `backend/app/db.py`

Public surface:

- `init_db(path: str) -> sqlite3.Connection` — opens connection, sets WAL (`PRAGMA journal_mode=WAL`), runs `CREATE TABLE IF NOT EXISTS` for both tables and both indices.
- `close_db(conn) -> None` — used in app shutdown.
- `insert_broadcast(conn, party_slug, sender_kind, sender_id, sender_name, text, at) -> int` — returns the inserted row's `id`.
- `query_broadcast_history(conn, party_slug, before_id=None, limit=50) -> list[dict]` — newest-first, cursor-paged on `id`. Caps `limit` at e.g. 200.
- `insert_dm(conn, thread_key, sender_kind, sender_id, sender_name, text, at) -> int`
- `query_thread_history(conn, thread_key, before_id=None, limit=50) -> list[dict]` — newest-first, cursor-paged.
- `list_threads_for(conn, principal_key) -> list[dict]` — each entry: `{thread_key, other_principal_key, other_name, last_message, last_at}`. Implementation joins the most-recent row per `thread_key` where the principal is one of the two sides.

The DM helpers are required deliverables of this slice (they're what 6b's mechanical merge will switch to), but are exercised only by `test_db.py` until 6b lands.

### `backend/app/world.py`

`PartyWorld.chat(...)` gains one extra side-effect after creating the in-memory `ChatEvent`: a call to `db.insert_broadcast(...)` using the connection held on `Store`. The order is **emit ChatEvent first, then persist** so a DB error never silently drops a live bubble; if persistence fails, log + raise so the route returns 500 (the caller decides whether to retry).

Actually — re-read the parent spec: it says "we publish only after successful write" for DMs. For broadcast we should follow the same rule so that history and live state can't diverge. **Decision: persist first, then publish the live ChatEvent.** A DB failure becomes a 500 from `/chat` and no bubble appears anywhere; the user can retry. Document this choice in the plan.

### `backend/app/store.py`

Holds a `self.db: sqlite3.Connection | None`. `init_db(...)` is called once at app startup by `main.py` and assigned to the Store. No other Store changes in this slice — `world_of` and `principal_exists` belong to 6b.

### `backend/app/main.py`

Startup: call `init_db(os.getenv("OPENPARTY_DB_PATH", "backend/data/openparty.sqlite"))`, attach to the singleton Store. Shutdown: `close_db(...)`. Mount the new history route.

### HTTP route — broadcast history

Add a route, either in a new `backend/app/routes/history.py` or folded into `routes/party_actions.py` (planner's call — recommendation: separate file once `party_actions.py` is approaching the 300-line guideline).

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/api/parties/{slug}/broadcast-history?before_id=&limit=` | Public to anyone who can resolve the slug. No principal gate. Returns `{messages: [...], next_before_id: int | null}`. Newest-first. |

Validation:
- Slug not found → 404.
- `limit` out of range or non-integer → 400 (use the existing 422 envelope helpers).
- `before_id` non-integer → 400.

### `backend/app/routes/agent_guide.py`

Add one new section, **Chat memory**, telling agents:

- That broadcast history survives restarts and where to fetch it.
- The `before_id` / `limit` pagination shape.
- Suggestion: on join, fetch the most-recent N broadcast messages to "remember" recent room context.

Do **not** add a DM section — that belongs to 6b. Order the new section before the existing "Recovering from errors" section.

## Validation & Errors

- Text validation in `world.chat()` is unchanged (already runs `validate_chat_text`).
- DB write failure → 500 from `/chat`. Don't publish.
- History endpoint: invalid slug → 404; bad `limit` / `before_id` → 400 (or 422 if pydantic does it via query param model — match existing conventions in the repo).

## Testing

**Backend (all required for this slice):**

- `tests/test_db.py` — boots schema on `:memory:`. Asserts:
  - Schema CREATE is idempotent (call `init_db` twice without error).
  - Broadcast insert returns an integer id; subsequent query returns the row with all expected fields.
  - Broadcast query is newest-first; pagination via `before_id` walks back correctly.
  - DM insert + thread query roundtrip (sanity for 6b).
  - `list_threads_for` returns one summary per `thread_key` with the latest message.
  - `limit` cap is enforced.
- `tests/test_world_chat_persistence.py` — `world.chat(...)` persists a row whose fields match the call args. Existing in-memory `ChatEvent` flow remains green.
- `tests/test_history_routes.py` — happy path (returns messages newest-first, paginated), 404 unknown slug, 400 on bad params, party scoping (messages from party A don't bleed into party B's history).

**Existing tests that must stay green:** all current `test_realtime*`, `test_party_action_routes*`, `test_world*` (this slice is additive — it should not change any existing test assertions).

**Out of scope for this slice's tests:** anything touching `dm.send`, `InboxHub`, DM routes, or frontend.

## Files Affected

**New backend**
- `backend/app/db.py`
- `backend/app/routes/history.py` *(or fold into `party_actions.py` — planner's call)*
- `backend/tests/test_db.py`
- `backend/tests/test_world_chat_persistence.py`
- `backend/tests/test_history_routes.py`

**Mutated backend**
- `backend/app/world.py` — persist in `chat()`.
- `backend/app/store.py` — hold `db` connection.
- `backend/app/main.py` — bootstrap + shutdown; mount new route.
- `backend/app/routes/agent_guide.py` — "Chat memory" section.

**No frontend changes.**

## Out of Scope (explicitly NOT in this slice)

- `dm.py`, `dm_send` proximity gate, DM HTTP routes, DM tests.
- `InboxHub` and the inbox WS endpoint.
- Any frontend file (DM UI, inbox button, click-to-DM, AppShell refactor).
- `Store.world_of` and `Store.principal_exists` — these are 6b's responsibility.
- The "Direct messaging" section of the agent guide.

## Forward compatibility note (for the planner)

`db.insert_dm`, `db.query_thread_history`, and `db.list_threads_for` are **required deliverables** of this slice even though no code in 6a calls them. Sibling slice 6b will ship an in-memory shim with **the exact same function names and signatures** in its own module. When both slices land, a one-file follow-up replaces 6b's shim import with this slice's `db` module — that's it. Keep the helper signatures stable; if the planner deviates, coordinate with the 6b planner before locking it in.

## Manual smoke (for the eventual PR)

- Start backend, send chat in a party, kill backend, restart backend, GET the broadcast-history endpoint → message is there.
- Verify that during normal operation the live bubble still appears in both browser windows (no regression of Phase 5 behavior).

## Conventions reminder (from `.ai/CONVENTIONS.md`)

- Test-first development.
- Files < 300 lines (split `db.py` only if it grows past this — unlikely for this slice).
- Use libraries over custom code (stdlib `sqlite3` is the chosen library; do not pull in `sqlalchemy`).
