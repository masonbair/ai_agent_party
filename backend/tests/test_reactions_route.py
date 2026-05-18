from fastapi.testclient import TestClient


def _join(client: TestClient, x: float = 400, y: float = 250) -> str:
    r = client.post("/api/session", json={"username": "alice", "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_react_happy_path(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "❤️"},
    )
    assert r.status_code == 200
    assert r.json()["emoji"] == "❤️"


def test_react_unknown_emoji_400(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "💩"},
    )
    assert r.status_code == 400


def test_react_not_joined_409(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "bob", "color": "#4dd0e1"})
    sid = r.json()["session_id"]
    r = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "❤️"},
    )
    assert r.status_code == 409


def test_react_unknown_party_404(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "bob", "color": "#4dd0e1"})
    sid = r.json()["session_id"]
    r = client.post(
        "/api/parties/no-such/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "❤️"},
    )
    assert r.status_code == 404
