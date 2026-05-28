from fastapi.testclient import TestClient


def test_post_session_creates_and_returns_user(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "Alice", "color": "#ff6b9d"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "Alice"
    assert body["color"] == "#ff6b9d"
    assert isinstance(body["session_id"], str) and len(body["session_id"]) >= 8


def test_post_session_rejects_bad_username(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "a", "color": "#ff6b9d"})
    assert r.status_code == 422


def test_post_session_rejects_bad_color(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "Alice", "color": "#000000"})
    assert r.status_code == 422


def test_post_session_rejects_injection_like_username(client: TestClient) -> None:
    r = client.post(
        "/api/session", json={"username": "bob; DROP TABLE", "color": "#ff6b9d"}
    )
    assert r.status_code == 422


def test_get_session_returns_existing_user(client: TestClient) -> None:
    created = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    r = client.get(f"/api/session/{created['session_id']}")
    assert r.status_code == 200
    assert r.json()["username"] == "Alice"


def test_get_session_404_for_unknown(client: TestClient) -> None:
    r = client.get("/api/session/unknown-id")
    assert r.status_code == 404


def test_post_session_rejects_blocked_username(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "damn", "color": "#ff6b9d"})
    assert r.status_code == 422


def test_post_session_allows_clean_username(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "Sunshine", "color": "#ff6b9d"})
    assert r.status_code == 200


def test_delete_session_204_then_404(client: TestClient) -> None:
    created = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    r = client.delete(f"/api/session/{created['session_id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/session/{created['session_id']}")
    assert r2.status_code == 404
