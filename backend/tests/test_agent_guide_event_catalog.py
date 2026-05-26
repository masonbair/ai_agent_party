EXPECTED_EVENT_TYPES = (
    "join",
    "leave",
    "move",
    "chat",
    "reaction",
    "lighting_changed",
    "note_created",
    "note_updated",
    "note_deleted",
    "stroke_added",
    "stroke_dropped",
    "board_cleared",
    "vote_changed",
)


def test_agent_guide_enumerates_every_event_type(client):
    body = client.get("/api/agent-guide").text
    for t in EXPECTED_EVENT_TYPES:
        assert f"`{t}`" in body, f"event type {t} not documented in agent guide"


def test_agent_guide_documents_seq_as_monotonic_global(client):
    body = client.get("/api/agent-guide").text
    assert "monotonic" in body.lower()
    assert "seq" in body
    assert "global" in body.lower()


def test_agent_guide_uses_flat_join_shape(client):
    body = client.get("/api/agent-guide").text
    # Old nested shape must not appear as a recommendation.
    assert '"participant": {' not in body
    # New flat fields must be referenced.
    assert "actor_id" in body
    assert "actor_username" in body
    assert "actor_kind" in body


def test_agent_guide_calls_out_participant_id_removal(client):
    body = client.get("/api/agent-guide").text
    # The guide must document the removal of participant_id in a "what changed"
    # context so agents know to migrate to actor_id.
    assert "participant_id" in body, "guide must mention participant_id so agents know it was removed"
    # The guide must name actor_id as the replacement.
    assert "actor_id" in body, "guide must reference actor_id as the replacement"
    # The actual removal/deprecation context must be present — not just a bare mention.
    assert "no longer" in body or "removed" in body or "replaced" in body, (
        "guide must state that participant_id was removed/replaced, not just mention it"
    )
