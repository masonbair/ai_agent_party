from __future__ import annotations

from fastapi.testclient import TestClient

from app.events import Participant
from app.store import Store


SLUG = "cream-terrazzo"


def _join(store: Store, ident: str, kind: str, username: str) -> None:
    world = store.get_or_create_world(SLUG)
    assert world is not None
    world.join(
        Participant(
            id=ident,
            kind=kind,
            username=username,
            color="#ff6b9d",
            x=0.0,
            y=0.0,
            joined_at=0.0,
        )
    )


def _two_humans(store: Store) -> tuple[str, str]:
    alice = store.create_session(username="Alice", color="#ff6b9d")
    bob = store.create_session(username="Bob", color="#9c27b0")
    _join(store, alice.session_id, "human", "Alice")
    _join(store, bob.session_id, "human", "Bob")
    return alice.session_id, bob.session_id


def test_post_dm_send_happy_path(client: TestClient, store: Store) -> None:
    a, b = _two_humans(store)
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "human", "id": b},
            "text": "hello",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["thread_key"] == f"human:{min(a, b)}|human:{max(a, b)}"
    assert isinstance(body["message_id"], int)


def test_post_dm_send_self_dm_rejected(client: TestClient, store: Store) -> None:
    a, _ = _two_humans(store)
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "human", "id": a},
            "text": "hi",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "self_dm"


def test_post_dm_send_unknown_recipient(client: TestClient, store: Store) -> None:
    a, _ = _two_humans(store)
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "agent", "id": "nope"},
            "text": "hi",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "recipient_unknown"


def test_post_dm_send_cross_party_succeeds(client: TestClient, store: Store) -> None:
    """DMs deliver regardless of party presence — the cross-party gate is gone."""
    alice = store.create_session(username="Alice", color="#ff6b9d")
    bob = store.create_session(username="Bob", color="#9c27b0")
    _join(store, alice.session_id, "human", "Alice")
    # Bob is registered but never joined any party.
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": alice.session_id},
            "recipient": {"kind": "human", "id": bob.session_id},
            "text": "hi",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["thread_key"] == (
        f"human:{min(alice.session_id, bob.session_id)}"
        f"|human:{max(alice.session_id, bob.session_id)}"
    )
    assert isinstance(body["message_id"], int)


def test_post_dm_send_principal_unknown(client: TestClient, store: Store) -> None:
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": "no-such-session"},
            "recipient": {"kind": "human", "id": "x"},
            "text": "hi",
        },
    )
    assert resp.status_code == 401


def test_post_dm_send_invalid_text(client: TestClient, store: Store) -> None:
    a, b = _two_humans(store)
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "human", "id": b},
            "text": "   ",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_chat_text"


def test_get_threads_returns_recent_first(client: TestClient, store: Store) -> None:
    a, b = _two_humans(store)
    carol = store.create_session(username="Carol", color="#4dd0e1")
    _join(store, carol.session_id, "human", "Carol")
    # a -> b
    client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "human", "id": b},
            "text": "hi bob",
        },
    )
    # a -> carol
    client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "human", "id": carol.session_id},
            "text": "hi carol",
        },
    )
    resp = client.get(
        "/api/dm/threads",
        params={"principal_kind": "human", "principal_id": a},
    )
    assert resp.status_code == 200
    threads = resp.json()["threads"]
    assert len(threads) == 2
    # Most recent (a->carol) first
    assert threads[0]["last_text"] == "hi carol"


def test_get_threads_requires_known_principal(client: TestClient) -> None:
    resp = client.get(
        "/api/dm/threads",
        params={"principal_kind": "human", "principal_id": "bogus"},
    )
    assert resp.status_code == 401


def test_get_history_paginates(client: TestClient, store: Store) -> None:
    a, b = _two_humans(store)
    ids: list[int] = []
    for i in range(3):
        r = client.post(
            "/api/dm/send",
            json={
                "principal": {"kind": "human", "id": a},
                "recipient": {"kind": "human", "id": b},
                "text": f"msg {i}",
            },
        )
        ids.append(r.json()["message_id"])
    tk = f"human:{min(a, b)}|human:{max(a, b)}"
    resp = client.get(
        f"/api/dm/threads/{tk}/history",
        params={
            "principal_kind": "human",
            "principal_id": a,
            "limit": 2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [m["id"] for m in body["messages"]] == [ids[2], ids[1]]
    resp2 = client.get(
        f"/api/dm/threads/{tk}/history",
        params={
            "principal_kind": "human",
            "principal_id": a,
            "before_id": ids[1],
        },
    )
    assert [m["id"] for m in resp2.json()["messages"]] == [ids[0]]


def test_get_history_403_for_outsider(client: TestClient, store: Store) -> None:
    a, b = _two_humans(store)
    carol = store.create_session(username="Carol", color="#4dd0e1")
    _join(store, carol.session_id, "human", "Carol")
    client.post(
        "/api/dm/send",
        json={
            "principal": {"kind": "human", "id": a},
            "recipient": {"kind": "human", "id": b},
            "text": "secret",
        },
    )
    tk = f"human:{min(a, b)}|human:{max(a, b)}"
    resp = client.get(
        f"/api/dm/threads/{tk}/history",
        params={
            "principal_kind": "human",
            "principal_id": carol.session_id,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "dm_forbidden"
