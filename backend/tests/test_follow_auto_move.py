"""When a followed target moves, the follower auto-moves toward them
   and stops at PROXIMITY_RADIUS - 20 distance."""

import math

from fastapi.testclient import TestClient

from app.world import PROXIMITY_RADIUS


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_follower_auto_moves_when_target_moves(client: TestClient) -> None:
    a = _agent(client, "Follower", "#4dd0e1")
    b = _agent(client, "Target", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(a), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(b), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 600, "y": 400},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    ).json()
    dx, dy = 600 - r["x"], 400 - r["y"]
    dist = math.hypot(dx, dy)
    expected = PROXIMITY_RADIUS - 20
    assert abs(dist - expected) < 1.0, (
        f"follower should be {expected} units from target, got {dist}"
    )


def test_follower_auto_move_emits_normal_move_event(client: TestClient) -> None:
    a = _agent(client, "Fa", "#4dd0e1")
    b = _agent(client, "Ta", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(a), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(b), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 600, "y": 400},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    follower_moves = [
        e for e in events
        if e["type"] == "move" and e["actor_id"] == a["agent_id"]
    ]
    assert follower_moves, "expected a synthetic move for the follower"
    # Auto-moves must not be tagged room_wide (proximity-scoped like normal).
    for e in follower_moves:
        assert e.get("room_wide", False) is False


def test_follow_auto_clears_on_target_leave(client: TestClient) -> None:
    a = _agent(client, "Follower", "#4dd0e1")
    b = _agent(client, "Target", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    client.post("/api/parties/cream-terrazzo/leave", json={"principal": _p(b)})
    # Re-join b; following should NOT resume.
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 700, "y": 400},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    ).json()
    # Follower should be at its original spawn (world center 400,250), not
    # near (700,400).
    assert (r["x"], r["y"]) == (400.0, 250.0)
