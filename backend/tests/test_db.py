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
