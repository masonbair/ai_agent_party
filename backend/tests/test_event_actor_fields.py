from fastapi.testclient import TestClient


def _join(client: TestClient, name: str, color: str = "#ff6b9d") -> str:
    r = client.post("/api/session", json={"username": name, "color": color})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    return sid


def test_move_event_carries_actor_fields(client: TestClient) -> None:
    alice = _join(client, "Alice", "#ff6b9d")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": alice}, "x": 123.0, "y": 45.0},
    )
    diff = client.get(f"/api/parties/cream-terrazzo/observe?since={cur}").json()
    moves = [e for e in diff["events"] if e["type"] == "move"]
    assert moves, "expected at least one move event"
    mv = moves[-1]
    assert mv["actor_id"] == alice
    assert mv["actor_username"] == "Alice"
    assert mv["actor_kind"] == "human"
    assert "participant_id" not in mv


def test_chat_event_carries_actor_fields(client: TestClient) -> None:
    alice = _join(client, "Alice", "#ff6b9d")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "human", "id": alice}, "text": "hello"},
    )
    diff = client.get(f"/api/parties/cream-terrazzo/observe?since={cur}").json()
    chat = [e for e in diff["events"] if e["type"] == "chat"][-1]
    assert chat["actor_id"] == alice
    assert chat["actor_username"] == "Alice"
    assert chat["actor_kind"] == "human"
    assert "participant_id" not in chat


def test_reaction_event_carries_actor_username_and_kind(client: TestClient) -> None:
    alice = _join(client, "Alice", "#ff6b9d")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": alice}, "emoji": "🔥"},
    )
    diff = client.get(f"/api/parties/cream-terrazzo/observe?since={cur}").json()
    rx = [e for e in diff["events"] if e["type"] == "reaction"][-1]
    assert rx["actor_id"] == alice  # already required
    assert rx["actor_username"] == "Alice"
    assert rx["actor_kind"] == "human"


def test_leave_event_carries_actor_fields(client: TestClient) -> None:
    alice = _join(client, "Alice", "#ff6b9d")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": {"kind": "human", "id": alice}},
    )
    diff = client.get(f"/api/parties/cream-terrazzo/observe?since={cur}").json()
    leaves = [e for e in diff["events"] if e["type"] == "leave"]
    assert leaves
    lv = leaves[-1]
    assert lv["actor_id"] == alice
    assert lv["actor_username"] == "Alice"
    assert lv["actor_kind"] == "human"
    assert "participant_id" not in lv
