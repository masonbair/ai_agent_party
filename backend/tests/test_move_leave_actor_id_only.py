from tests.conftest import register_human, join_party


def test_move_event_uses_actor_id_only(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": alice["principal"], "x": 100.0, "y": 100.0},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    moves = [e for e in diff["events"] if e["type"] == "move"]
    assert moves, "expected one move event"
    m = moves[-1]
    assert m["actor_id"] == alice["principal"]["id"]
    assert m["actor_username"] == "Alice"
    assert m["actor_kind"] == "human"
    assert "participant_id" not in m


def test_leave_event_uses_actor_id_only(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": alice["principal"]},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    leaves = [e for e in diff["events"] if e["type"] == "leave"]
    assert len(leaves) == 1
    lv = leaves[0]
    assert lv["actor_id"] == alice["principal"]["id"]
    assert lv["actor_username"] == "Alice"
    assert lv["actor_kind"] == "human"
    assert "participant_id" not in lv


def test_reaction_event_actor_fields_required(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": alice["principal"], "emoji": "🔥"},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rxs = [e for e in diff["events"] if e["type"] == "reaction"]
    assert rxs and rxs[0]["actor_username"] == "Alice"
    assert rxs[0]["actor_kind"] == "human"
