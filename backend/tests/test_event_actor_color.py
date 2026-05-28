"""Every event with actor_* fields must also carry actor_color."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _principal(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_move_event_includes_actor_color(client: TestClient) -> None:
    a = _agent(client, "Mover", "#4dd0e1")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(a)},
    )
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(a), "x": 200, "y": 200},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    moves = [e for e in events if e["type"] == "move"]
    assert moves, "expected at least one move event"
    assert moves[0]["actor_color"] == "#4dd0e1"


def test_chat_event_includes_actor_color(client: TestClient) -> None:
    a = _agent(client, "Talker", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(a)},
    )
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(a), "text": "hello"},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    chats = [e for e in events if e["type"] == "chat"]
    assert chats
    assert chats[0]["actor_color"] == "#ff6b9d"
