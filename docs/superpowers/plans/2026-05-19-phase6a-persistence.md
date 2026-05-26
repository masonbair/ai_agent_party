# Phase 6a — Chat Persistence & Broadcast History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist broadcast chat to SQLite so messages survive backend restarts, and expose a paginated history endpoint. DM helpers also land but stay dormant until Phase 6b.

**Architecture:** A new `backend/app/db.py` module owns the single `sqlite3.Connection` (WAL mode, schema bootstrap). `Store` carries the connection. `PartyWorld.chat()` writes the row *before* emitting the live `ChatEvent` so a DB failure surfaces as a 500 and history can never diverge from live state. A new `GET /api/parties/{slug}/broadcast-history` route returns paginated, newest-first messages. DM tables and helpers are shipped now for 6b's mechanical merge but exercised only by `test_db.py`.

**Tech Stack:** Python 3.11, FastAPI, stdlib `sqlite3` (WAL), pytest. No new dependencies.

---

## File Structure

**New backend**
- `backend/app/db.py` — owns the `sqlite3.Connection`, schema bootstrap, CRUD helpers for broadcast + DM rows. Only file in the codebase that imports `sqlite3`.
- `backend/app/routes/history.py` — `GET /api/parties/{slug}/broadcast-history`.
- `backend/tests/test_db.py` — schema, broadcast roundtrip, DM roundtrip, pagination, limit cap.
- `backend/tests/test_world_chat_persistence.py` — `world.chat()` writes through to the DB.
- `backend/tests/test_history_routes.py` — happy path, 404, 400, per-party scoping.

**Mutated backend**
- `backend/app/world.py` — `chat()` gains `db.insert_broadcast(...)` *before* `_emit`.
- `backend/app/store.py` — holds `self.db: sqlite3.Connection | None`.
- `backend/app/main.py` — `init_db` on startup, `close_db` on shutdown, mount history router.
- `backend/app/routes/agent_guide.py` — new "Chat memory" section before "Recovering from errors".
- `backend/tests/conftest.py` — `store` fixture initializes an in-memory DB on the Store.

**Frontend:** no changes.

---

## Task 1: `db.py` skeleton — connection + schema bootstrap

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_db.py`:

```python
from app import db


def test_init_db_creates_tables_and_is_idempotent():
    conn = db.init_db(":memory:")
    # Calling init_db on an already-initialized handle must not error.
    db.init_db(":memory:")  # fresh handle also fine
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [r[0] for r in rows]
    assert "broadcast_messages" in names
    assert "dm_messages" in names

    # Indices present.
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    ).fetchall()
    idx_names = [r[0] for r in idx]
    assert "idx_broadcast_party_at" in idx_names
    assert "idx_dm_thread_at" in idx_names

    # Re-running init_db on the same connection is a no-op (idempotent).
    db.init_db(":memory:")
    db.close_db(conn)


def test_init_db_sets_wal_for_file_paths(tmp_path):
    path = str(tmp_path / "openparty.sqlite")
    conn = db.init_db(path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    db.close_db(conn)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/db.py`:

```python
"""SQLite persistence for openParty chat (broadcast + DM).

This is the only module in the codebase that imports ``sqlite3``. All
other code talks to SQLite through the helpers here. A single connection
is created at app startup and held on ``Store``; tests pass ``":memory:"``.
"""

from __future__ import annotations

import sqlite3
from typing import Any


_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS broadcast_messages (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      party_slug   TEXT    NOT NULL,
      sender_kind  TEXT    NOT NULL,
      sender_id    TEXT    NOT NULL,
      sender_name  TEXT    NOT NULL,
      text         TEXT    NOT NULL,
      at           REAL    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_broadcast_party_at ON broadcast_messages(party_slug, at)",
    """
    CREATE TABLE IF NOT EXISTS dm_messages (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      thread_key   TEXT    NOT NULL,
      sender_kind  TEXT    NOT NULL,
      sender_id    TEXT    NOT NULL,
      sender_name  TEXT    NOT NULL,
      text         TEXT    NOT NULL,
      at           REAL    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dm_thread_at ON dm_messages(thread_key, at)",
]


def init_db(path: str) -> sqlite3.Connection:
    """Open a connection, set WAL (for file paths), and create schema.

    ``check_same_thread=False`` so the FastAPI thread pool can share one
    connection; SQLite serializes writes internally. Idempotent: callable
    multiple times safely (uses ``CREATE TABLE IF NOT EXISTS``).
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    for stmt in _SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def close_db(conn: sqlite3.Connection | None) -> None:
    if conn is not None:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_db.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat(db): add sqlite3 module with schema bootstrap (phase 6a)"
```

---

## Task 2: Broadcast insert + query helpers

**Files:**
- Modify: `backend/app/db.py`
- Modify: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_db.py`:

```python
import time

import pytest


@pytest.fixture
def conn():
    c = db.init_db(":memory:")
    yield c
    db.close_db(c)


def _insert_broadcast(conn, **overrides):
    args = dict(
        party_slug="cream-terrazzo",
        sender_kind="human",
        sender_id="sess-1",
        sender_name="Alice",
        text="hello",
        at=time.time(),
    )
    args.update(overrides)
    return db.insert_broadcast(conn, **args)


def test_insert_broadcast_returns_id_and_row_is_readable(conn):
    rid = _insert_broadcast(conn, text="hi there")
    assert isinstance(rid, int) and rid > 0
    rows = db.query_broadcast_history(conn, "cream-terrazzo")
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == rid
    assert row["party_slug"] == "cream-terrazzo"
    assert row["sender_kind"] == "human"
    assert row["sender_id"] == "sess-1"
    assert row["sender_name"] == "Alice"
    assert row["text"] == "hi there"
    assert isinstance(row["at"], float)


def test_query_broadcast_history_newest_first_and_paginates(conn):
    ids = [_insert_broadcast(conn, text=f"msg{i}", at=1000.0 + i) for i in range(5)]
    page1 = db.query_broadcast_history(conn, "cream-terrazzo", limit=2)
    assert [r["id"] for r in page1] == [ids[4], ids[3]]
    page2 = db.query_broadcast_history(
        conn, "cream-terrazzo", before_id=page1[-1]["id"], limit=2
    )
    assert [r["id"] for r in page2] == [ids[2], ids[1]]
    page3 = db.query_broadcast_history(
        conn, "cream-terrazzo", before_id=page2[-1]["id"], limit=2
    )
    assert [r["id"] for r in page3] == [ids[0]]
    page4 = db.query_broadcast_history(
        conn, "cream-terrazzo", before_id=page3[-1]["id"], limit=2
    )
    assert page4 == []


def test_query_broadcast_history_scopes_by_party(conn):
    _insert_broadcast(conn, party_slug="party-a", text="from-a")
    _insert_broadcast(conn, party_slug="party-b", text="from-b")
    rows = db.query_broadcast_history(conn, "party-a")
    assert [r["text"] for r in rows] == ["from-a"]


def test_query_broadcast_history_caps_limit(conn):
    for i in range(250):
        _insert_broadcast(conn, text=f"m{i}", at=1000.0 + i)
    rows = db.query_broadcast_history(conn, "cream-terrazzo", limit=10_000)
    assert len(rows) == 200  # hard cap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_db.py -v`
Expected: FAIL — `AttributeError: module 'app.db' has no attribute 'insert_broadcast'`.

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/db.py`:

```python
MAX_HISTORY_LIMIT = 200


def insert_broadcast(
    conn: sqlite3.Connection,
    *,
    party_slug: str,
    sender_kind: str,
    sender_id: str,
    sender_name: str,
    text: str,
    at: float,
) -> int:
    cur = conn.execute(
        "INSERT INTO broadcast_messages "
        "(party_slug, sender_kind, sender_id, sender_name, text, at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (party_slug, sender_kind, sender_id, sender_name, text, at),
    )
    conn.commit()
    return int(cur.lastrowid)


def query_broadcast_history(
    conn: sqlite3.Connection,
    party_slug: str,
    *,
    before_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    capped = max(1, min(int(limit), MAX_HISTORY_LIMIT))
    if before_id is None:
        rows = conn.execute(
            "SELECT id, party_slug, sender_kind, sender_id, sender_name, text, at "
            "FROM broadcast_messages WHERE party_slug = ? "
            "ORDER BY id DESC LIMIT ?",
            (party_slug, capped),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, party_slug, sender_kind, sender_id, sender_name, text, at "
            "FROM broadcast_messages WHERE party_slug = ? AND id < ? "
            "ORDER BY id DESC LIMIT ?",
            (party_slug, int(before_id), capped),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_db.py -v`
Expected: PASS (6 tests total).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat(db): broadcast insert + paginated history query"
```

---

## Task 3: DM insert + thread query + thread list helpers

These ship now so Phase 6b's merge is a pure call-site swap. Only `test_db.py` exercises them in this slice.

**Files:**
- Modify: `backend/app/db.py`
- Modify: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_db.py`:

```python
def _insert_dm(conn, **overrides):
    args = dict(
        thread_key="human:sess-1|human:sess-2",
        sender_kind="human",
        sender_id="sess-1",
        sender_name="Alice",
        text="hey",
        at=time.time(),
    )
    args.update(overrides)
    return db.insert_dm(conn, **args)


def test_insert_dm_and_thread_history_roundtrip(conn):
    rid = _insert_dm(conn, text="first")
    assert isinstance(rid, int) and rid > 0
    rows = db.query_thread_history(conn, "human:sess-1|human:sess-2")
    assert len(rows) == 1
    assert rows[0]["id"] == rid
    assert rows[0]["text"] == "first"
    assert rows[0]["sender_name"] == "Alice"


def test_query_thread_history_newest_first_and_paginates(conn):
    ids = [
        _insert_dm(conn, text=f"d{i}", at=1000.0 + i)
        for i in range(4)
    ]
    page1 = db.query_thread_history(conn, "human:sess-1|human:sess-2", limit=2)
    assert [r["id"] for r in page1] == [ids[3], ids[2]]
    page2 = db.query_thread_history(
        conn,
        "human:sess-1|human:sess-2",
        before_id=page1[-1]["id"],
        limit=2,
    )
    assert [r["id"] for r in page2] == [ids[1], ids[0]]


def test_list_threads_for_returns_one_summary_per_thread(conn):
    # Two threads involving sess-1.
    _insert_dm(
        conn,
        thread_key="human:sess-1|human:sess-2",
        sender_id="sess-1",
        sender_name="Alice",
        text="hi bob",
        at=1000.0,
    )
    _insert_dm(
        conn,
        thread_key="human:sess-1|human:sess-2",
        sender_id="sess-2",
        sender_name="Bob",
        text="hey alice",
        at=1001.0,
    )
    _insert_dm(
        conn,
        thread_key="agent:agt-9|human:sess-1",
        sender_id="agt-9",
        sender_name="Sleuth",
        sender_kind="agent",
        text="curious?",
        at=1002.0,
    )
    # An unrelated thread.
    _insert_dm(
        conn,
        thread_key="human:sess-2|human:sess-3",
        sender_id="sess-2",
        sender_name="Bob",
        text="not for alice",
        at=1003.0,
    )
    summaries = db.list_threads_for(conn, "human:sess-1")
    keys = {s["thread_key"] for s in summaries}
    assert keys == {"human:sess-1|human:sess-2", "agent:agt-9|human:sess-1"}
    by_key = {s["thread_key"]: s for s in summaries}
    a = by_key["human:sess-1|human:sess-2"]
    assert a["last_message"] == "hey alice"
    assert a["last_at"] == 1001.0
    assert a["other_principal_key"] == "human:sess-2"
    b = by_key["agent:agt-9|human:sess-1"]
    assert b["other_principal_key"] == "agent:agt-9"
    assert b["other_name"] in {"Sleuth", "Alice"}  # see note in impl
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_db.py -v`
Expected: FAIL — `AttributeError: module 'app.db' has no attribute 'insert_dm'`.

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/db.py`:

```python
def insert_dm(
    conn: sqlite3.Connection,
    *,
    thread_key: str,
    sender_kind: str,
    sender_id: str,
    sender_name: str,
    text: str,
    at: float,
) -> int:
    cur = conn.execute(
        "INSERT INTO dm_messages "
        "(thread_key, sender_kind, sender_id, sender_name, text, at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (thread_key, sender_kind, sender_id, sender_name, text, at),
    )
    conn.commit()
    return int(cur.lastrowid)


def query_thread_history(
    conn: sqlite3.Connection,
    thread_key: str,
    *,
    before_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    capped = max(1, min(int(limit), MAX_HISTORY_LIMIT))
    if before_id is None:
        rows = conn.execute(
            "SELECT id, thread_key, sender_kind, sender_id, sender_name, text, at "
            "FROM dm_messages WHERE thread_key = ? "
            "ORDER BY id DESC LIMIT ?",
            (thread_key, capped),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, thread_key, sender_kind, sender_id, sender_name, text, at "
            "FROM dm_messages WHERE thread_key = ? AND id < ? "
            "ORDER BY id DESC LIMIT ?",
            (thread_key, int(before_id), capped),
        ).fetchall()
    return [dict(r) for r in rows]


def list_threads_for(
    conn: sqlite3.Connection,
    principal_key: str,
) -> list[dict[str, Any]]:
    """One summary row per ``thread_key`` involving ``principal_key``.

    ``principal_key`` looks like ``"human:<session_id>"`` or
    ``"agent:<agent_id>"`` and must appear on one side of the
    ``"lo|hi"`` ``thread_key`` string. Returns newest-first by
    ``last_at``.
    """
    rows = conn.execute(
        """
        SELECT m.thread_key, m.sender_name, m.text AS last_message, m.at AS last_at
        FROM dm_messages m
        JOIN (
            SELECT thread_key, MAX(id) AS max_id
            FROM dm_messages
            WHERE thread_key LIKE ? OR thread_key LIKE ?
            GROUP BY thread_key
        ) latest
          ON m.thread_key = latest.thread_key AND m.id = latest.max_id
        ORDER BY m.at DESC
        """,
        (f"{principal_key}|%", f"%|{principal_key}"),
    ).fetchall()
    out = []
    for r in rows:
        tk = r["thread_key"]
        lo, hi = tk.split("|", 1)
        other = hi if lo == principal_key else lo
        out.append(
            {
                "thread_key": tk,
                "other_principal_key": other,
                # ``sender_name`` of the last message is "good enough" until
                # 6b lands a proper participant lookup; the spec accepts a
                # denormalized name here.
                "other_name": r["sender_name"],
                "last_message": r["last_message"],
                "last_at": r["last_at"],
            }
        )
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_db.py -v`
Expected: PASS (9 tests total).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat(db): DM insert, thread history query, thread list helper"
```

---

## Task 4: Wire db connection onto Store + test fixtures

**Files:**
- Modify: `backend/app/store.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Update `Store` to hold the connection**

Edit `backend/app/store.py`:

Add at top with other imports:

```python
import sqlite3
```

In `Store.__init__`, add the field (after `self._session_presence`):

```python
        self.db: sqlite3.Connection | None = None
```

No other Store changes in this slice.

- [ ] **Step 2: Update test fixture to provide an in-memory DB**

Edit `backend/tests/conftest.py`. Replace the `store` fixture:

```python
from app import db as db_module


@pytest.fixture
def store() -> Store:
    s = Store()
    s.db = db_module.init_db(":memory:")
    yield s
    db_module.close_db(s.db)
```

(Make the fixture a generator — change return type to `Store` produced via `yield`. Keep imports tidy.)

- [ ] **Step 3: Run existing test suite to confirm no regression**

Run: `pytest backend -q`
Expected: PASS — all 178 prior tests + 9 new `test_db.py` tests = 187 passing.

- [ ] **Step 4: Commit**

```bash
git add backend/app/store.py backend/tests/conftest.py
git commit -m "feat(store): hold optional sqlite3 connection; tests use :memory:"
```

---

## Task 5: Persist in `world.chat()` (persist-first, then emit)

Per spec §Components: persist before publishing the live `ChatEvent` so a DB error becomes a 500 from `/chat` and prevents drift.

**Files:**
- Create: `backend/tests/test_world_chat_persistence.py`
- Modify: `backend/app/world.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_world_chat_persistence.py`:

```python
import time

import pytest

from app import db as db_module
from app.events import Participant
from app.parties_data import PARTY_REGISTRY
from app.world import PartyWorld


@pytest.fixture
def conn():
    c = db_module.init_db(":memory:")
    yield c
    db_module.close_db(c)


@pytest.fixture
def party():
    return next(iter(PARTY_REGISTRY.values()))


def _join(world: PartyWorld) -> Participant:
    p = Participant(
        id="sess-1",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=10.0,
        y=10.0,
        joined_at=time.time(),
    )
    world.join(p)
    return p


def test_chat_persists_row_with_call_args(party, conn):
    world = PartyWorld(party, db_conn=conn, party_slug=party.slug)
    _join(world)
    world.chat("sess-1", "hello there")
    rows = db_module.query_broadcast_history(conn, party.slug)
    assert len(rows) == 1
    r = rows[0]
    assert r["party_slug"] == party.slug
    assert r["sender_kind"] == "human"
    assert r["sender_id"] == "sess-1"
    assert r["sender_name"] == "Alice"
    assert r["text"] == "hello there"
    assert isinstance(r["at"], float) and r["at"] > 0


def test_chat_without_db_still_works(party):
    world = PartyWorld(party)  # no db_conn → in-memory only
    _join(world)
    ev = world.chat("sess-1", "no db here")
    assert ev.text == "no db here"


def test_chat_db_failure_aborts_emit(party, conn):
    # Close the connection so insert raises.
    conn.close()
    world = PartyWorld(party, db_conn=conn, party_slug=party.slug)
    _join(world)
    received = []
    world.on_event(lambda e: received.append(e))
    with pytest.raises(Exception):
        world.chat("sess-1", "boom")
    # No ChatEvent should have been emitted because persistence failed.
    assert all(getattr(e, "text", None) != "boom" for e in received)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_chat_persistence.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'db_conn'`.

- [ ] **Step 3: Modify `PartyWorld` to accept and use the connection**

Edit `backend/app/world.py`.

At top of file, add import:

```python
import sqlite3

from app import db as db_module
```

Update `PartyWorld.__init__` signature and body:

```python
    def __init__(
        self,
        party: PartyConfig,
        *,
        db_conn: sqlite3.Connection | None = None,
        party_slug: str | None = None,
    ) -> None:
        self._party = party
        self._db = db_conn
        self._party_slug = party_slug if party_slug is not None else party.slug
        self.participants: dict[str, Participant] = {}
        self._events: list[Event] = []
        self._wall_rects: list[Rect] = inflate_walls(
            party.room.walls, party.worldSize
        )
        self._listeners: list[Callable[[Event], None]] = []
```

Modify `chat(...)` to persist *before* emitting. Replace the existing method with:

```python
    def chat(self, participant_id: str, text: str) -> ChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        cleaned = validate_chat_text(text)
        at = time.time()
        sender = self.participants[participant_id]
        if self._db is not None:
            # Persist FIRST so a DB failure raises and no live bubble is emitted.
            db_module.insert_broadcast(
                self._db,
                party_slug=self._party_slug,
                sender_kind=sender.kind,
                sender_id=sender.id,
                sender_name=sender.username,
                text=cleaned,
                at=at,
            )
        ev = ChatEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            text=cleaned,
            at=at,
        )
        self._events.append(ev)
        self._emit(ev)
        return ev
```

- [ ] **Step 4: Run new test to verify it passes**

Run: `pytest backend/tests/test_world_chat_persistence.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full backend suite to catch regressions**

Run: `pytest backend -q`
Expected: PASS — `world.chat` callers without `db_conn` (existing tests) still work because `self._db is None` skips persistence.

- [ ] **Step 6: Commit**

```bash
git add backend/app/world.py backend/tests/test_world_chat_persistence.py
git commit -m "feat(world): persist chat to sqlite before emitting ChatEvent"
```

---

## Task 6: Pass the DB through `Store.get_or_create_world`

So real route traffic actually persists. Test fixture already sets `store.db` (Task 4).

**Files:**
- Modify: `backend/app/store.py`

- [ ] **Step 1: Update `get_or_create_world` to inject the connection**

Edit `backend/app/store.py`. Replace `get_or_create_world` with:

```python
    def get_or_create_world(self, slug: str) -> PartyWorld | None:
        party = self._parties.get(slug)
        if party is None:
            return None
        if slug not in self._worlds:
            self._worlds[slug] = PartyWorld(party, db_conn=self.db, party_slug=slug)
        return self._worlds[slug]
```

- [ ] **Step 2: Run suite to confirm persistence happens via `/chat` route**

Add an assertion-only test to `backend/tests/test_world_chat_persistence.py`:

```python
def test_chat_route_persists_through_store(client, store):
    # Register an agent and join the seeded party, then send chat.
    party_slug = next(iter(__import__("app.parties_data", fromlist=["PARTY_REGISTRY"]).PARTY_REGISTRY))
    a = client.post("/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}).json()
    principal = {"kind": "agent", "id": a["agent_id"]}
    client.post(f"/api/parties/{party_slug}/join", json={"principal": principal})
    r = client.post(
        f"/api/parties/{party_slug}/chat",
        json={"principal": principal, "text": "hi room"},
    )
    assert r.status_code == 200
    from app import db as db_module
    rows = db_module.query_broadcast_history(store.db, party_slug)
    assert [row["text"] for row in rows] == ["hi room"]
    assert rows[0]["sender_kind"] == "agent"
    assert rows[0]["sender_name"] == "Bot1"
```

Run: `pytest backend/tests/test_world_chat_persistence.py -v`
Expected: PASS (4 tests).

- [ ] **Step 3: Run full suite**

Run: `pytest backend -q`
Expected: PASS — no regressions.

- [ ] **Step 4: Commit**

```bash
git add backend/app/store.py backend/tests/test_world_chat_persistence.py
git commit -m "feat(store): inject db connection into PartyWorld via get_or_create_world"
```

---

## Task 7: `GET /api/parties/{slug}/broadcast-history` route

**Files:**
- Create: `backend/app/routes/history.py`
- Create: `backend/tests/test_history_routes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_history_routes.py`:

```python
from app import db as db_module
from app.parties_data import PARTY_REGISTRY


def _slug() -> str:
    return next(iter(PARTY_REGISTRY))


def _send_chat(client, slug, text):
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "agent", "id": a["agent_id"]}
    client.post(f"/api/parties/{slug}/join", json={"principal": principal})
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": principal, "text": text},
    )
    assert r.status_code == 200


def test_broadcast_history_returns_messages_newest_first(client, store):
    slug = _slug()
    for i in range(3):
        _send_chat(client, slug, f"msg-{i}")
    r = client.get(f"/api/parties/{slug}/broadcast-history")
    assert r.status_code == 200
    body = r.json()
    assert [m["text"] for m in body["messages"]] == ["msg-2", "msg-1", "msg-0"]
    for m in body["messages"]:
        assert {"id", "party_slug", "sender_kind", "sender_id", "sender_name", "text", "at"}.issubset(m)
    assert body["next_before_id"] is None  # under page size


def test_broadcast_history_pagination(client, store):
    slug = _slug()
    # Seed via the db directly so we don't have to spam HTTP.
    for i in range(5):
        db_module.insert_broadcast(
            store.db,
            party_slug=slug,
            sender_kind="human",
            sender_id="sess",
            sender_name="Alice",
            text=f"m{i}",
            at=1000.0 + i,
        )
    r = client.get(f"/api/parties/{slug}/broadcast-history?limit=2")
    body = r.json()
    assert [m["text"] for m in body["messages"]] == ["m4", "m3"]
    assert body["next_before_id"] == body["messages"][-1]["id"]

    r2 = client.get(
        f"/api/parties/{slug}/broadcast-history"
        f"?limit=2&before_id={body['next_before_id']}"
    )
    body2 = r2.json()
    assert [m["text"] for m in body2["messages"]] == ["m2", "m1"]


def test_broadcast_history_404_unknown_slug(client):
    r = client.get("/api/parties/no-such-party/broadcast-history")
    assert r.status_code == 404


def test_broadcast_history_400_bad_limit(client):
    slug = _slug()
    r = client.get(f"/api/parties/{slug}/broadcast-history?limit=0")
    assert r.status_code == 400
    r2 = client.get(f"/api/parties/{slug}/broadcast-history?limit=abc")
    # non-int caught by FastAPI query parsing → 422 validation envelope
    assert r2.status_code == 422


def test_broadcast_history_400_bad_before_id(client):
    slug = _slug()
    r = client.get(f"/api/parties/{slug}/broadcast-history?before_id=-1")
    assert r.status_code == 400


def test_broadcast_history_is_party_scoped(client, store):
    # Insert into two different party slugs via DB directly.
    db_module.insert_broadcast(
        store.db, party_slug="cream-terrazzo", sender_kind="human",
        sender_id="s1", sender_name="A", text="for-cream", at=1.0,
    )
    db_module.insert_broadcast(
        store.db, party_slug="other-party", sender_kind="human",
        sender_id="s2", sender_name="B", text="for-other", at=2.0,
    )
    # We can hit the endpoint for a slug that exists in the registry.
    slug = _slug()  # cream-terrazzo
    body = client.get(f"/api/parties/{slug}/broadcast-history").json()
    assert all(m["party_slug"] == slug for m in body["messages"])
    assert "for-other" not in [m["text"] for m in body["messages"]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_history_routes.py -v`
Expected: FAIL — 404 for all (route not mounted).

- [ ] **Step 3: Implement the route**

Create `backend/app/routes/history.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app import db as db_module
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.get("/{slug}/broadcast-history")
def broadcast_history(
    slug: str = Path(pattern=_SLUG_PATTERN),
    before_id: int | None = Query(default=None),
    limit: int = Query(default=50),
    store: Store = Depends(_store_dep),
) -> dict:
    if store.get_party(slug) is None:
        raise HTTPException(status_code=404, detail="party not found")
    if limit < 1 or limit > db_module.MAX_HISTORY_LIMIT:
        raise HTTPException(status_code=400, detail="invalid limit")
    if before_id is not None and before_id < 1:
        raise HTTPException(status_code=400, detail="invalid before_id")
    assert store.db is not None, "db not initialized"
    rows = db_module.query_broadcast_history(
        store.db, slug, before_id=before_id, limit=limit
    )
    next_before = rows[-1]["id"] if len(rows) == limit else None
    return {"messages": rows, "next_before_id": next_before}
```

- [ ] **Step 4: Mount the router**

Edit `backend/app/main.py`. Add import next to the other route imports:

```python
from app.routes import history as history_routes
```

Add the dependency override and `include_router` call (in the same block as the existing ones):

```python
app.dependency_overrides[history_routes._store_dep] = get_store
app.include_router(history_routes.router)
```

Also extend the test fixture in `backend/tests/conftest.py` to override `history_routes._store_dep`:

```python
from app.routes import history as history_routes
# ...
    app.dependency_overrides[history_routes._store_dep] = lambda: store
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/tests/test_history_routes.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Run full suite**

Run: `pytest backend -q`
Expected: PASS — no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/history.py backend/app/main.py backend/tests/conftest.py backend/tests/test_history_routes.py
git commit -m "feat(routes): GET /api/parties/{slug}/broadcast-history"
```

---

## Task 8: App lifespan — bootstrap and close the DB

The Store is module-level in `main.py`. Open the DB at app startup, close at shutdown, and attach to the singleton Store.

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Wire startup/shutdown hooks**

Edit `backend/app/main.py`. After `_store = Store()`, add:

```python
import os

from app import db as db_module


@app.on_event("startup")
def _open_db() -> None:
    path = os.getenv("OPENPARTY_DB_PATH", "backend/data/openparty.sqlite")
    if path != ":memory:":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    _store.db = db_module.init_db(path)


@app.on_event("shutdown")
def _close_db() -> None:
    db_module.close_db(_store.db)
    _store.db = None
```

(Keep imports grouped at the top of the file. The `_store.db` assignment runs once on real startup; tests bypass this via the fixture override.)

- [ ] **Step 2: Smoke test the running app**

Add to `backend/tests/test_history_routes.py` (uses the lifespan via `TestClient`'s context manager):

```python
def test_app_startup_opens_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENPARTY_DB_PATH", str(tmp_path / "x.sqlite"))
    from fastapi.testclient import TestClient
    from app.main import app, _store
    # Clear dep overrides so the real _store is used.
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        assert _store.db is not None
        r = c.get("/api/health")
        assert r.status_code == 200
    # After context exit, shutdown hook ran.
    assert _store.db is None
```

Run: `pytest backend/tests/test_history_routes.py::test_app_startup_opens_db -v`
Expected: PASS.

- [ ] **Step 3: Run full suite**

Run: `pytest backend -q`
Expected: PASS. (If startup-test order pollutes other tests' overrides, mark this test `@pytest.mark.order("last")` or move it to its own module — only do this if you actually see flakiness.)

- [ ] **Step 4: Add `backend/data/` to .gitignore**

The default DB path is `backend/data/openparty.sqlite`. Make sure runtime data isn't committed:

```bash
echo "backend/data/" >> .gitignore
```

Verify: `git check-ignore backend/data/openparty.sqlite` → prints the path.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_history_routes.py .gitignore
git commit -m "feat(main): open/close sqlite db on app lifespan"
```

---

## Task 9: Agent guide — "Chat memory" section

Add a section telling agents that broadcast history survives restarts, how to fetch it, and the pagination shape. Insert *before* the existing "Recovering from errors" section. Do **not** add anything about DMs.

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Modify: `backend/tests/test_agent_guide_route.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_agent_guide_route.py`:

```python
def test_agent_guide_mentions_broadcast_history(client):
    body = client.get("/api/agent-guide").text
    assert "## Chat memory" in body
    assert "/broadcast-history" in body
    assert "before_id" in body
    # Must appear before the error-recovery section.
    assert body.index("## Chat memory") < body.index("## Recovering from errors")
    # Phase 6a explicitly excludes DM docs.
    assert "Direct message" not in body
    assert "/api/dm" not in body
```

Run: `pytest backend/tests/test_agent_guide_route.py -v`
Expected: FAIL — `"## Chat memory"` substring missing.

- [ ] **Step 2: Add the section to the guide**

Edit `backend/app/routes/agent_guide.py`. Find the line beginning with `## Recovering from errors` inside `_GUIDE` and insert this new section directly before it:

```
## Chat memory

Broadcast chat survives backend restarts. To remember what was said in the room — including before you joined — fetch history:

```
GET /api/parties/{{slug}}/broadcast-history
GET /api/parties/{{slug}}/broadcast-history?limit=50&before_id=<id>
```

Response: `{{ "messages": [...], "next_before_id": <int|null> }}`. Messages are newest-first. Each has `id`, `sender_kind` (`human`/`agent`), `sender_id`, `sender_name`, `text`, `at`. To page further back, pass the response's `next_before_id` as the next `before_id`; when it's `null` you've reached the start.

**Suggestion:** on join, fetch the most recent ~20-50 messages so you have room context before reacting to live events.

```

- [ ] **Step 3: Run tests**

Run: `pytest backend/tests/test_agent_guide_route.py -v`
Expected: PASS.

- [ ] **Step 4: Run full suite**

Run: `pytest backend -q`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_route.py
git commit -m "docs(agent-guide): add Chat memory section for broadcast history"
```

---

## Task 10: Manual smoke test

The spec calls for one end-to-end manual smoke. Run it before opening the PR.

- [ ] **Step 1: Start the backend**

Run: `cd backend && uvicorn app.main:app --reload --port 8000`

Watch for the WAL journal-mode log line (or simply that startup succeeds).

- [ ] **Step 2: Send a chat via curl**

```bash
A=$(curl -s -X POST localhost:8000/api/agents -H 'content-type: application/json' \
  -d '{"username":"Smoke","color":"#ff6b9d"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['agent_id'])")
SLUG=$(curl -s localhost:8000/api/parties | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['slug'])")
curl -s -X POST "localhost:8000/api/parties/$SLUG/join" \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$A\"}}"
curl -s -X POST "localhost:8000/api/parties/$SLUG/chat" \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$A\"},\"text\":\"persisted hello\"}"
```

- [ ] **Step 3: Kill and restart the backend**

Ctrl-C the uvicorn process, then restart it with the same command.

- [ ] **Step 4: Fetch history**

```bash
curl -s "localhost:8000/api/parties/$SLUG/broadcast-history" | python3 -m json.tool
```

Expected: the JSON contains a message with `"text": "persisted hello"`. Pass ✓.

- [ ] **Step 5: Verify live bubble still works**

Open `frontend` (`npm run dev` in `frontend/`), join the party in two browser windows, send a chat. The bubble should still appear in both windows immediately — Phase 5 behavior unchanged.

---

## Self-review notes

- Spec §Components requires `world.chat()` to persist *before* emitting. Covered by Task 5 + tests.
- Spec §Components requires `db.insert_dm` / `db.query_thread_history` / `db.list_threads_for` as deliverables of this slice. Covered by Task 3 (tests live in `test_db.py` only).
- Spec §HTTP route: 404 on unknown slug, 400 on bad params, newest-first, `next_before_id` cursor. Covered by Task 7 tests.
- Spec §Agent guide: new "Chat memory" section, before "Recovering from errors", no DM content. Covered by Task 9 tests.
- Spec §Forward compatibility: helper signatures match what 6b will swap to (`thread_key`, `principal_key`, kw-only args).
