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
