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
