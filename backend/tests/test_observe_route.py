from fastapi.testclient import TestClient


def _human(client: TestClient, username: str = "Alice", color: str = "#ff6b9d") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def _principal_human(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def test_observe_initial_returns_room_and_empty_participants(client: TestClient) -> None:
    r = client.get("/api/parties/cream-terrazzo/observe")
    assert r.status_code == 200
    body = r.json()
    assert body["room"]["slug"] == "cream-terrazzo"
    assert body["room"]["worldSize"] == {"width": 800, "height": 500}
    assert len(body["room"]["zones"]) == 3
    assert body["room"]["zones"][0].keys() == {
        "id", "label", "x", "y", "width", "height", "centerX", "centerY",
    }
    assert body["room"]["walls"][0].keys() == {"x", "y", "width", "height"}
    assert body["room"]["music"] == "Music coming soon"
    assert body["participants"] == []
    assert body["cursor"] == 0


def test_observe_initial_returns_participants_with_zone(client: TestClient) -> None:
    user = _human(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    )
    body = client.get("/api/parties/cream-terrazzo/observe").json()
    assert len(body["participants"]) == 1
    p = body["participants"][0]
    assert p["username"] == "Alice"
    assert p["zone"] == "dance"


def test_observe_404_for_unknown_party(client: TestClient) -> None:
    r = client.get("/api/parties/does-not-exist/observe")
    assert r.status_code == 404


def test_observe_diff_returns_only_new_events(client: TestClient) -> None:
    user = _human(client)
    join = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()
    cursor = join["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    )
    r = client.get(f"/api/parties/cream-terrazzo/observe?since={cursor}")
    body = r.json()
    assert "room" not in body
    assert len(body["events"]) == 1
    assert body["events"][0]["type"] == "move"
    assert body["events"][0]["zone"] == "dance"


def test_observe_diff_collapses_consecutive_moves(client: TestClient) -> None:
    user = _human(client)
    cursor = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()["cursor"]
    for i in range(1, 11):
        client.post(
            "/api/parties/cream-terrazzo/move",
            json={"principal": _principal_human(user), "x": i * 10, "y": i * 5},
        )
    body = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    moves = [e for e in body["events"] if e["type"] == "move"]
    assert len(moves) == 1
    assert moves[0]["x"] == 100.0


def test_observe_diff_empty_when_caught_up(client: TestClient) -> None:
    user = _human(client)
    body = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()
    cursor = body["cursor"]
    r = client.get(f"/api/parties/cream-terrazzo/observe?since={cursor}")
    assert r.json() == {"events": [], "cursor": cursor}
