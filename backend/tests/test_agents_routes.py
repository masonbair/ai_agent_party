from fastapi.testclient import TestClient


def test_post_agents_creates_and_returns_agent(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "Bot1", "color": "#ff6b9d"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "Bot1"
    assert body["color"] == "#ff6b9d"
    assert isinstance(body["agent_id"], str) and len(body["agent_id"]) >= 8


def test_post_agents_rejects_bad_username(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "a", "color": "#ff6b9d"})
    assert r.status_code == 422


def test_post_agents_rejects_bad_color(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "Bot1", "color": "#000000"})
    assert r.status_code == 422


def test_get_agent_returns_existing(client: TestClient) -> None:
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    r = client.get(f"/api/agents/{a['agent_id']}")
    assert r.status_code == 200
    assert r.json()["username"] == "Bot1"


def test_get_agent_404_for_unknown(client: TestClient) -> None:
    r = client.get("/api/agents/unknown-id")
    assert r.status_code == 404


def test_post_agents_rejects_blocked_username(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "damn", "color": "#ff6b9d"})
    assert r.status_code == 422
    assert "disallowed" in r.json()["detail"][0]["msg"]


def test_post_agents_allows_clean_username(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "Sunshine", "color": "#ff6b9d"})
    assert r.status_code == 200
    assert r.json()["username"] == "Sunshine"


def test_delete_agent_204_then_404(client: TestClient) -> None:
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    r = client.delete(f"/api/agents/{a['agent_id']}")
    assert r.status_code == 204
    assert client.get(f"/api/agents/{a['agent_id']}").status_code == 404
