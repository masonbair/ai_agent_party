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
    assert "participant_id" in body  # mentioned in "what changed" so agents notice
    assert "actor_id" in body
