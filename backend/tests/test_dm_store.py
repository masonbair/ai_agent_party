from app.dm_store import (
    DmStore,
    insert_dm,
    list_threads_for,
    query_thread_history,
)


def _key(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


def test_insert_and_query_roundtrip() -> None:
    store = DmStore()
    a, b = _key("human", "alice"), _key("agent", "bot")
    thread = "|".join(sorted([a, b]))
    mid = insert_dm(
        store,
        thread_key=thread,
        sender_kind="human",
        sender_id="alice",
        sender_name="Alice",
        text="hello",
        at=1.0,
    )
    rows = query_thread_history(store, thread_key=thread)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == mid
    assert row["thread_key"] == thread
    assert row["sender_kind"] == "human"
    assert row["sender_id"] == "alice"
    assert row["sender_name"] == "Alice"
    assert row["text"] == "hello"
    assert row["at"] == 1.0


def test_query_thread_history_newest_first_and_pagination() -> None:
    store = DmStore()
    thread = "agent:bot|human:alice"
    ids = [
        insert_dm(
            store,
            thread_key=thread,
            sender_kind="human",
            sender_id="alice",
            sender_name="Alice",
            text=f"m{i}",
            at=float(i),
        )
        for i in range(5)
    ]
    page1 = query_thread_history(store, thread_key=thread, limit=2)
    assert [r["id"] for r in page1] == [ids[4], ids[3]]
    page2 = query_thread_history(store, thread_key=thread, before_id=ids[3], limit=2)
    assert [r["id"] for r in page2] == [ids[2], ids[1]]
    page3 = query_thread_history(store, thread_key=thread, before_id=ids[1], limit=10)
    assert [r["id"] for r in page3] == [ids[0]]


def test_query_thread_history_ignores_other_threads() -> None:
    store = DmStore()
    t1 = "human:a|human:b"
    t2 = "human:a|human:c"
    insert_dm(
        store,
        thread_key=t1,
        sender_kind="human",
        sender_id="a",
        sender_name="A",
        text="hi b",
        at=1.0,
    )
    insert_dm(
        store,
        thread_key=t2,
        sender_kind="human",
        sender_id="a",
        sender_name="A",
        text="hi c",
        at=2.0,
    )
    rows = query_thread_history(store, thread_key=t1)
    assert [r["text"] for r in rows] == ["hi b"]


def test_list_threads_for_dedups_and_sorts_by_last_at() -> None:
    store = DmStore()
    alice = "human:alice"
    bob = "human:bob"
    carol = "agent:carol"
    t_ab = "|".join(sorted([alice, bob]))
    t_ac = "|".join(sorted([alice, carol]))
    insert_dm(
        store,
        thread_key=t_ab,
        sender_kind="human",
        sender_id="alice",
        sender_name="Alice",
        text="hi bob",
        at=1.0,
    )
    insert_dm(
        store,
        thread_key=t_ac,
        sender_kind="human",
        sender_id="alice",
        sender_name="Alice",
        text="hi carol",
        at=2.0,
    )
    insert_dm(
        store,
        thread_key=t_ab,
        sender_kind="human",
        sender_id="bob",
        sender_name="Bob",
        text="hey",
        at=3.0,
    )
    threads = list_threads_for(store, principal_key=alice)
    assert [t["thread_key"] for t in threads] == [t_ab, t_ac]
    first = threads[0]
    assert first["last_at"] == 3.0
    assert first["last_text"] == "hey"
    assert first["last_sender_kind"] == "human"
    assert first["last_sender_id"] == "bob"
    assert first["last_sender_name"] == "Bob"


def test_list_threads_for_excludes_unrelated() -> None:
    store = DmStore()
    a = "human:a"
    insert_dm(
        store,
        thread_key="human:x|human:y",
        sender_kind="human",
        sender_id="x",
        sender_name="X",
        text="hi",
        at=1.0,
    )
    assert list_threads_for(store, principal_key=a) == []
