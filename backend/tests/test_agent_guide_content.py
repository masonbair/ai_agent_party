from fastapi.testclient import TestClient

from app.validation import STICKY_COLOR_ALLOWLIST, STROKE_COLOR_ALLOWLIST


def test_agent_guide_lists_sticky_color_allow_list(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for c in STICKY_COLOR_ALLOWLIST:
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
    # agents should know the exact error code AND that the allow-list comes back
    assert '"invalid_note"' in body
    assert "allowed_colors" in body


def test_agent_guide_documents_invalid_emoji_envelope(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "allowed_emojis" in body


def test_agent_guide_documents_proximity_radius(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "PROXIMITY_RADIUS" in body or "proximity radius" in body.lower()
    assert "180" in body  # the actual value, so agents can tune walks


def test_agent_guide_documents_room_wide_events(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "room_wide" in body
    # explicitly name what's always-on
    assert "lighting_changed" in body


def test_agent_guide_documents_proximity_snapshot_and_left(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "proximity_snapshot" in body
    assert "proximity_left" in body


def test_guide_documents_social_primitives(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "## Social primitives" in body
    assert "/follow" in body
    assert "/proposals" in body
    assert "actor_color" in body
    assert "exclude_self" in body
    assert "/participants/" in body


def test_agent_guide_documents_walls_out_of_scope(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "walls" in body.lower()
    # Make clear that proximity is plain radius, not LOS.
    assert (
        "line-of-sight" in body.lower()
        or "do not block" in body.lower()
        or "ignore walls" in body.lower()
    )


def test_agent_guide_mentions_occupancy_and_preview(client):
    res = client.get("/api/agent-guide")
    assert res.status_code == 200
    body = res.text
    assert "occupancy" in body
    assert "/api/parties/{slug}/preview" in body
    assert "active_last_5min" in body
def test_agent_guide_documents_push_websocket(client: TestClient) -> None:
    resp = client.get("/api/agent-guide")
    assert resp.status_code == 200
    body = resp.text
    for needle in (
        "real-time agents",
        "/observe/ws",
        '"type":"auth"',
        '"type":"initial"',
        '"type":"event"',
        '"type":"ping"',
        '"type":"pong"',
        "proximity_snapshot",
        "proximity_left",
        "4401",
        "reconnect",
        "cursor",
    ):
        assert needle in body, f"agent guide missing: {needle}"


def test_guide_has_operating_posture_sections(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "You are a guest, not a script" in text
    assert "reason-act loop" in text
    assert "For your operator" in text
    assert "Bash(./oparty:*)" in text
    assert "Vocabulary & gotchas" in text
    assert "dedupe by `seq`" in text
    assert "usernames are not unique" in text.lower()


def test_guide_documents_real_cooldowns_and_react_codes(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert (
        "only chat is rate-limited" in text.lower()
        or "lighting is not rate-limited" in text.lower()
    )
    assert "target_not_found" in text
    assert "invalid_reaction_target" in text


def test_agent_guide_documents_optimistic_responses(client: TestClient) -> None:
    resp = client.get("/api/agent-guide")
    body = resp.text
    for needle in (
        "Optimistic responses",
        '"event"',
        "any new POST that emits an event must return the event payload",
    ):
        assert needle in body, f"agent guide missing: {needle}"
