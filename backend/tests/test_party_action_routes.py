from fastapi.testclient import TestClient


def _human(client: TestClient) -> dict:
    return client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()


def _agent(client: TestClient) -> dict:
    return client.post(
        "/api/agents", json={"username": "Bot1", "color": "#4dd0e1"}
    ).json()


def _principal_human(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def _principal_agent(agent: dict) -> dict:
    return {"kind": "agent", "id": agent["agent_id"]}


def test_join_returns_participant_and_cursor(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["participant"]["username"] == "Alice"
    assert body["participant"]["kind"] == "human"
    assert body["cursor"] == 1


def test_join_uses_world_center_by_default(client: TestClient) -> None:
    user = _human(client)
    body = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()
    assert body["participant"]["x"] == 400.0
    assert body["participant"]["y"] == 250.0


def test_join_honours_explicit_coords(client: TestClient) -> None:
    user = _human(client)
    body = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    ).json()
    assert body["participant"]["x"] == 200.0


def test_join_404_for_unknown_party(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/does-not-exist/join",
        json={"principal": _principal_human(user)},
    )
    assert r.status_code == 404


def test_join_401_for_invalid_principal(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": "nope"}},
    )
    assert r.status_code == 401


def test_join_401_for_kind_mismatch(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": user["session_id"]}},
    )
    assert r.status_code == 401


def test_move_clamps_to_bounds_and_returns_zone(client: TestClient) -> None:
    user = _human(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["x"] == 200.0
    assert body["y"] == 100.0
    assert body["zone"] == "dance"
    assert body["cursor"] >= 2


def test_move_409_when_not_joined(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 100, "y": 100},
    )
    assert r.status_code == 409


def test_chat_happy_path_returns_cursor(client: TestClient) -> None:
    agent = _agent(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_agent(agent)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal_agent(agent), "text": "hello!"},
    )
    assert r.status_code == 200
    assert r.json()["cursor"] >= 2


def test_chat_422_for_invalid_text(client: TestClient) -> None:
    agent = _agent(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_agent(agent)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal_agent(agent), "text": "nope 🙂"},
    )
    assert r.status_code == 422


def test_chat_409_when_not_joined(client: TestClient) -> None:
    agent = _agent(client)
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal_agent(agent), "text": "hello"},
    )
    assert r.status_code == 409


def test_leave_204_then_409_on_followup_move(client: TestClient) -> None:
    user = _human(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": _principal_human(user)},
    )
    assert r.status_code == 204
    r2 = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 100, "y": 100},
    )
    assert r2.status_code == 409
