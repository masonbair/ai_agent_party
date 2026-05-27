from __future__ import annotations

from fastapi.testclient import TestClient

from app.events import Participant
from app.store import Store


def _seed(store: Store, name: str = "Alice") -> str:
    sess = store.create_session(username=name, color="#ff6b9d")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    world.join(
        Participant(
            id=sess.session_id, kind="human", username=name,
            color="#ff6b9d", x=200.0, y=200.0, joined_at=0.0,
        )
    )
    return sess.session_id


def test_chat_response_includes_full_event_payload(client: TestClient, store: Store):
    pid = _seed(store)
    resp = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "human", "id": pid}, "text": "hello"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "event" in body
    ev = body["event"]
    assert ev["type"] == "chat"
    assert ev["text"] == "hello"
    assert ev["actor_id"] == pid
    assert ev["actor_username"] == "Alice"
    assert ev["actor_kind"] == "human"
    assert isinstance(ev["seq"], int)
    assert isinstance(ev["at"], float)
    assert body["cursor"] == ev["seq"]


def test_move_response_includes_full_event_payload(client: TestClient, store: Store):
    pid = _seed(store)
    resp = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": pid}, "x": 250.0, "y": 260.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "event" in body
    ev = body["event"]
    assert ev["type"] == "move"
    assert ev["actor_id"] == pid
    # Move events store post-slide x/y; we don't assert exact values, just shape.
    assert isinstance(ev["x"], float)
    assert isinstance(ev["y"], float)
    assert isinstance(ev["seq"], int)
    # Top-level convenience fields preserved for backwards compat.
    assert body["x"] == ev["x"]
    assert body["y"] == ev["y"]
    assert "zone" in body
    assert body["cursor"] == ev["seq"]


def test_react_response_includes_full_event_payload(client: TestClient, store: Store):
    pid = _seed(store)
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": pid}, "emoji": "👋"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "event" in body
    ev = body["event"]
    assert ev["type"] == "reaction"
    assert ev["actor_id"] == pid
    assert ev["actor_username"] == "Alice"
    assert ev["emoji"] == body["emoji"]
    assert body["expires_at"] == ev["expires_at"]
    assert body["cursor"] == ev["seq"]
