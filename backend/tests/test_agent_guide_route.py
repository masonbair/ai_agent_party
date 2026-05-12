from fastapi.testclient import TestClient


def test_agent_guide_returns_markdown(client: TestClient) -> None:
    r = client.get("/api/agent-guide")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")


def test_agent_guide_mentions_core_endpoints(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for needle in (
        "POST /api/agents",
        "POST /api/parties/{slug}/join",
        "GET /api/parties/{slug}/observe",
        "POST /api/parties/{slug}/move",
        "POST /api/parties/{slug}/chat",
        "POST /api/parties/{slug}/leave",
    ):
        assert needle in body, f"missing: {needle}"


def test_agent_guide_has_example_loop(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "Example sequence" in body
