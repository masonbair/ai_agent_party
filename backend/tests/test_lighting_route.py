from fastapi.testclient import TestClient


def _join(client: TestClient) -> str:
    r = client.post("/api/session", json={"username": "alice", "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    return sid


def test_set_lighting_happy_path(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "night"},
    )
    assert r.status_code == 200
    assert r.json()["preset"] == "night"
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    assert obs["lighting"] == "night"


def test_set_lighting_unknown_preset_422(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "rainbow"},
    )
    assert r.status_code == 422


def test_set_lighting_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "night"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["preset"] == "night"
    assert "cursor" in body
    assert body["event"]["preset"] == "night"
    assert body["event"]["type"] == "lighting_changed"


def test_set_lighting_unknown_preset_echoes_allowed(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "dawn"},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_preset"
    assert detail["allowed_presets"] == ["day", "dusk", "night", "party"]


def test_set_lighting_not_joined_409(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "bob", "color": "#4dd0e1"})
    sid = r.json()["session_id"]
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "day"},
    )
    assert r.status_code == 409
