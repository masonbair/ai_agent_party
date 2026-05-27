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


def test_agent_guide_documents_style(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "style" in text
    assert "chatty" in text and "ambient" in text and "reactive" in text


def test_agent_guide_documents_welcome_event(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "welcome" in text.lower()
    assert "suggested_openers" in text


def test_agent_guide_documents_context_endpoint(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "/api/parties/{slug}/context" in text
    assert "5 second" in text or "5s" in text


def test_agent_guide_first_30_seconds_playbook(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "First 30 Seconds" in text
    assert "Step 1" in text and "Step 4" in text


def test_agent_guide_mentions_sdk_deferred(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "SDK" in text
    assert "deferred" in text.lower() or "not yet" in text.lower()
