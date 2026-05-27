"""POST /follow records follower→target on the world."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_follow_stores_relationship(client: TestClient) -> None:
    a = _agent(client, "Follower", "#4dd0e1")
    b = _agent(client, "Target", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    r = client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    assert r.status_code == 200
    assert r.json()["target_id"] == b["agent_id"]


def test_follow_self_returns_400(client: TestClient) -> None:
    a = _agent(client, "Solo", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": a["agent_id"]},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "cannot_follow_self"


def test_follow_unknown_target_returns_404(client: TestClient) -> None:
    a = _agent(client, "Fa", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": "nope"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "target_not_in_party"


def test_follow_auto_clears_on_follower_leave(client: TestClient) -> None:
    a = _agent(client, "Fo", "#4dd0e1")
    b = _agent(client, "To", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    client.post("/api/parties/cream-terrazzo/leave", json={"principal": _p(a)})
    # Re-join a at fixed pos; verify b moving does NOT auto-pull a.
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(a), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 700, "y": 400},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    ).json()
    assert (r["x"], r["y"]) == (100.0, 100.0)


def test_unfollow_clears(client: TestClient) -> None:
    a = _agent(client, "Fa", "#4dd0e1")
    b = _agent(client, "Ta", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/unfollow",
        json={"principal": _p(a)},
    )
    assert r.status_code == 204
