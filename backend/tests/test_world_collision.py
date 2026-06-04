import math

from fastapi.testclient import TestClient

from app.collision import MIN_AVATAR_SEPARATION
from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.world import PartyWorld


def _p(pid: str, x: float, y: float) -> Participant:
    return Participant(
        id=pid, kind="human", username=pid, color="#ff6b9d",
        x=x, y=y, joined_at=1715533200.0,
    )


def test_move_separates_overlapping_avatars():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 300.0, 300.0))
    world.join(_p("b", 600.0, 300.0))
    # b tries to walk onto a's exact spot.
    world.move("b", 300.0, 300.0)
    a = world.participants["a"]
    b = world.participants["b"]
    dist = math.hypot(a.x - b.x, a.y - b.y)
    assert dist >= MIN_AVATAR_SEPARATION - 1e-6


def _human(client: TestClient, username: str = "Alice") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": "#ff6b9d"}
    ).json()


def _agent(client: TestClient, username: str = "Bot1") -> dict:
    return client.post(
        "/api/agents", json={"username": username, "color": "#4dd0e1"}
    ).json()


def _join_human(client: TestClient, user: dict) -> None:
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": user["session_id"]}, "x": 200, "y": 100},
    )


def _join_agent(client: TestClient, agent: dict) -> None:
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]}, "x": 200, "y": 100},
    )


def test_agent_move_into_wall_is_blocked(client: TestClient) -> None:
    # cream-terrazzo wall: x=50%, y=0-30%, width=0.75%, height=30%.
    # World 800x500 -> wall x:400-406 inflated 386-420; y:0-150 inflated -14 to 164.
    agent = _agent(client)
    _join_agent(client, agent)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "agent", "id": agent["agent_id"]},
            "x": 400,
            "y": 100,
        },
    )
    assert r.status_code == 200
    body = r.json()
    # X-only (400, 100) inside the wall; Y-only (200, 100) clear -> result (200, 100).
    assert (body["x"], body["y"]) == (200.0, 100.0)


def test_human_move_into_wall_is_blocked_same_as_agent(client: TestClient) -> None:
    user = _human(client)
    _join_human(client, user)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "human", "id": user["session_id"]},
            "x": 400,
            "y": 100,
        },
    )
    body = r.json()
    assert (body["x"], body["y"]) == (200.0, 100.0)


def test_move_clear_of_walls_unchanged(client: TestClient) -> None:
    agent = _agent(client)
    _join_agent(client, agent)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "agent", "id": agent["agent_id"]},
            "x": 250,
            "y": 250,
        },
    )
    body = r.json()
    assert (body["x"], body["y"]) == (250.0, 250.0)
