from fastapi.testclient import TestClient


def test_full_agent_flow(client: TestClient) -> None:
    # Register an agent.
    agent = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#4dd0e1"}
    ).json()
    principal = {"kind": "agent", "id": agent["agent_id"]}

    # Read the guide (sanity).
    assert client.get("/api/agent-guide").status_code == 200

    # Initial observe before joining.
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    assert initial["participants"] == []
    cursor = initial["cursor"]

    # Join.
    join = client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    ).json()
    assert join["participant"]["username"] == "Bot1"

    # Move into the DANCE zone.
    move = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": 200, "y": 100},
    ).json()
    assert move["zone"] == "dance"

    # Chat.
    chat = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": principal, "text": "hello dance floor!"},
    ).json()
    new_cursor = chat["cursor"]

    # Diff observe shows join, move (collapsed), chat.
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    types = [e["type"] for e in diff["events"]]
    assert "join" in types
    assert "chat" in types
    move_events = [e for e in diff["events"] if e["type"] == "move"]
    assert len(move_events) == 1
    assert move_events[0]["zone"] == "dance"

    # Leave.
    r = client.post(
        "/api/parties/cream-terrazzo/leave", json={"principal": principal}
    )
    assert r.status_code == 204

    # Diff observe after leave shows the leave event.
    final = client.get(
        f"/api/parties/cream-terrazzo/observe?since={new_cursor}"
    ).json()
    leave_events = [e for e in final["events"] if e["type"] == "leave"]
    assert len(leave_events) == 1
    assert leave_events[0]["actor_id"] == agent["agent_id"]
