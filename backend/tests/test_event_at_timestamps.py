import time

from fastapi.testclient import TestClient


def _human(client: TestClient) -> dict:
    return client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()


def _principal(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def test_join_move_chat_events_all_have_at(client: TestClient) -> None:
    user = _human(client)
    before = time.time()
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(user)},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(user), "x": 200, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(user), "text": "hi"},
    )
    after = time.time()

    diff = client.get("/api/parties/cream-terrazzo/observe?since=0").json()
    types_with_at = {e["type"]: e["at"] for e in diff["events"]}
    assert {"join", "move", "chat"} <= types_with_at.keys()
    for ts in types_with_at.values():
        assert before - 1.0 <= ts <= after + 1.0
