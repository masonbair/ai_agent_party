from tests.conftest import register_human, join_party


def test_chat_event_uses_actor_id_only(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": alice["principal"], "text": "hello"},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    chats = [e for e in diff["events"] if e["type"] == "chat"]
    assert len(chats) == 1
    c = chats[0]
    assert c["actor_id"] == alice["principal"]["id"]
    assert c["actor_username"] == "Alice"
    assert c["actor_kind"] == "human"
    assert "participant_id" not in c
