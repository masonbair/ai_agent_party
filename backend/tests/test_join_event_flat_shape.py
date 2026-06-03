from tests.conftest import register_human, join_party


def test_join_event_is_flat(client):
    alice = register_human(client, username="Alice")
    cur_resp = client.get("/api/parties/cream-terrazzo/observe").json()
    cursor_before = cur_resp["cursor"]
    join_party(client, alice, "cream-terrazzo")
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor_before}"
    ).json()
    joins = [e for e in diff["events"] if e["type"] == "join"]
    assert len(joins) == 1
    j = joins[0]
    # Flat actor fields
    assert j["actor_id"] == alice["principal"]["id"]
    assert j["actor_username"] == "Alice"
    assert j["actor_kind"] == "human"
    # Spawn coordinates at top level
    assert "x" in j and "y" in j
    assert isinstance(j["x"], (int, float))
    assert isinstance(j["y"], (int, float))
    # Zone derived at event time (may be None if spawn lies in no zone)
    assert "zone" in j
    # No nested participant alias
    assert "participant" not in j
    # No legacy participant_id either
    assert "participant_id" not in j


def test_join_http_response_still_has_nested_participant(client):
    """The /join request/response body is distinct from the event stream.

    Frontend callers of POST /join read body.participant.x to place the
    avatar; that contract stays.
    """
    alice = register_human(client, username="Alice")
    resp = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": alice["principal"]},
    )
    body = resp.json()
    assert "participant" in body
    assert body["participant"]["username"] == "Alice"
