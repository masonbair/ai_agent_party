from fastapi.testclient import TestClient

from app.errors import NOT_IN_PARTY, PRINCIPAL_UNKNOWN
from app.validation import ALLOWED_COLORS


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


def test_agent_guide_lists_every_allowed_color(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for hex_color in ALLOWED_COLORS:
        assert hex_color in body, f"missing color {hex_color}"


def test_agent_guide_documents_zone_centers(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "centerX" in body
    assert "centerY" in body


def test_agent_guide_documents_poll_cadence(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "1-2" in body or "1–2" in body
    assert "poll" in body.lower()


def test_agent_guide_warns_about_bearer_token(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text.lower()
    assert "password" in body or "bearer" in body


def test_agent_guide_documents_error_codes(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert PRINCIPAL_UNKNOWN in body
    assert NOT_IN_PARTY in body


def test_agent_guide_mentions_modules(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for needle in (
        "## Modules",
        "approachSlots",
        "POST /api/parties/{slug}/react",
        "POST /api/parties/{slug}/lighting",
        "POST /api/parties/{slug}/modules/{module_id}/notes",
        "POST /api/parties/{slug}/modules/{module_id}/strokes",
        "vote_clear",
    ):
        assert needle in body, f"missing: {needle}"
        
def test_agent_guide_mentions_broadcast_history(client):
    body = client.get("/api/agent-guide").text
    assert "## Chat memory" in body
    assert "/broadcast-history" in body
    assert "before_id" in body
    # Must appear before the error-recovery section.
    assert body.index("## Chat memory") < body.index("## Recovering from errors")
    # DM docs are present (added post Phase 6a).
    assert "/api/dm" in body
