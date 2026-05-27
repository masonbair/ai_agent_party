from tests.conftest import join_party, register_human


def _get_participant_id(sess: dict) -> str:
    """Extract the resolved participant id from a register_human/agent response."""
    principal = sess["principal"]
    # For humans: principal has kind="human", id=session_id
    # The session_id IS the participant id used in the world
    return principal["id"]


def test_react_with_target_actor_id_attaches_to_event(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    bob_id = _get_participant_id(bob)
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_actor_id": bob_id,
        },
    )
    assert resp.status_code == 200
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rx = [e for e in diff["events"] if e["type"] == "reaction"][-1]
    assert rx["actor_username"] == "Alice"
    assert rx["target_actor_id"] == bob_id
    assert rx.get("target_seq") is None


def test_react_with_target_seq_attaches_to_event(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    # Bob says hi — get the cursor before and after to find the seq.
    cur_before = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": bob["principal"], "text": "hi all"},
    )
    # Get the seq of Bob's chat from the events.
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur_before}"
    ).json()
    bob_chat_seq = next(
        e["seq"] for e in diff["events"] if e["type"] == "chat"
    )
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "👍",
            "target_seq": bob_chat_seq,
        },
    )
    assert resp.status_code == 200
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rx = [e for e in diff["events"] if e["type"] == "reaction"][-1]
    assert rx["target_seq"] == bob_chat_seq
    assert rx.get("target_actor_id") is None


def test_react_with_both_targets_is_422(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_seq": 1,
            "target_actor_id": _get_participant_id(bob),
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_reaction_target"


def test_react_with_missing_target_actor_is_404(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_actor_id": "no-such-participant",
        },
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["error"] == "target_not_found"


def test_react_with_missing_target_seq_is_404(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_seq": 999_999,
        },
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["error"] == "target_not_found"


def test_react_without_target_still_works(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": alice["principal"], "emoji": "🔥"},
    )
    assert resp.status_code == 200
