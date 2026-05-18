"""Modules are reachable by agents under the same proximity gate as humans."""

from fastapi.testclient import TestClient


def _register_agent(client: TestClient) -> str:
    r = client.post("/api/agents", json={"username": "Bot1", "color": "#4dd0e1"})
    return r.json()["agent_id"]


def _agent_principal(aid: str) -> dict:
    return {"kind": "agent", "id": aid}


def _join(client: TestClient, aid: str, x: float, y: float) -> None:
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _agent_principal(aid), "x": x, "y": y},
    )


def test_agent_can_react_when_joined(client: TestClient) -> None:
    aid = _register_agent(client)
    _join(client, aid, 400, 250)
    r = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": _agent_principal(aid), "emoji": "❤️"},
    )
    assert r.status_code == 200


def test_agent_can_set_lighting(client: TestClient) -> None:
    aid = _register_agent(client)
    _join(client, aid, 400, 250)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": _agent_principal(aid), "preset": "night"},
    )
    assert r.status_code == 200


def test_agent_proximity_gate_for_sticky_note(client: TestClient) -> None:
    aid = _register_agent(client)
    # Spawn far from sticky-1 (placed at the room edge).
    _join(client, aid, 400, 250)
    far = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": _agent_principal(aid),
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    assert far.status_code == 409

    # Walk into the sticky-1 interaction zone via /move, then succeed.
    # sticky-1 is moved to (20, 410, 180, 70); interior point: (110, 445).
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _agent_principal(aid), "x": 110, "y": 445},
    )
    near = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": _agent_principal(aid),
            "text": "hello",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    assert near.status_code == 200, near.text
    assert near.json()["note"]["author_kind"] == "agent"


def test_agent_proximity_gate_for_drawboard(client: TestClient) -> None:
    aid = _register_agent(client)
    _join(client, aid, 400, 250)
    far = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": _agent_principal(aid),
            "color": "#ff6b9d",
            "width": "thin",
            "points": [{"x": 0, "y": 0}],
        },
    )
    assert far.status_code == 409

    # draw-1 will be moved to (620, 410, 160, 70); interior point: (700, 445).
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _agent_principal(aid), "x": 700, "y": 445},
    )
    near = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": _agent_principal(aid),
            "color": "#ff6b9d",
            "width": "thin",
            "points": [{"x": 0, "y": 0}],
        },
    )
    assert near.status_code == 200, near.text
    assert near.json()["stroke"]["author_kind"] == "agent"
