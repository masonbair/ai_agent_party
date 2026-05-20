from fastapi.testclient import TestClient

from app.validation import STROKE_COLOR_ALLOWLIST


def test_agent_guide_lists_sticky_color_allow_list(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for c in ("yellow", "pink", "blue", "green"):
        assert c in body


def test_agent_guide_lists_stroke_width_enum(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for w in ("thin", "med", "thick"):
        assert w in body


def test_agent_guide_lists_stroke_color_allow_list(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for c in STROKE_COLOR_ALLOWLIST:
        assert c in body


def test_agent_guide_documents_note_response_shape(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    # response body documented enough for an agent to extract the id
    assert "note.id" in body or '"id"' in body
    assert "cursor" in body


def test_agent_guide_documents_stroke_response_shape(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "stroke.id" in body or '"id"' in body


def test_agent_guide_has_approach_pattern(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "Approaching" in body or "approach" in body.lower()
    assert "approachSlots" in body


def test_agent_guide_has_reactive_loop_example(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "reactive loop" in body.lower() or "Reactive loop" in body


def test_agent_guide_documents_recent_chat_and_actor_fields(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "recent_chat" in body
    assert "actor_username" in body
    assert "actor_kind" in body


def test_agent_guide_clarifies_room_modules_vs_top_level_modules(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "room.modules" in body
    assert "live" in body.lower() or "top-level" in body


def test_agent_guide_documents_invalid_note_envelope(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    # agents should know they get the allow-list back on rejection
    assert "allowed_colors" in body


def test_agent_guide_documents_invalid_emoji_envelope(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "allowed_emojis" in body
