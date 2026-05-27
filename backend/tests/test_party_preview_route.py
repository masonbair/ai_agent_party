from tests.conftest import join_party, register_human


def test_preview_unknown_slug_404(client):
    res = client.get("/api/parties/does-not-exist/preview")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "party_not_found"


def test_preview_empty_room_shape(client):
    res = client.get("/api/parties/cream-terrazzo/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "cream-terrazzo"
    assert body["name"]
    assert body["description"] is not None
    assert body["occupancy"] == {
        "humans": 0,
        "agents": 0,
        "total": 0,
        "active_last_5min": 0,
    }
    assert body["lighting"] == "day"
    assert "music" in body and set(body["music"].keys()) == {"url", "label"}
    assert body["recent_chat"] == []
    # Privacy guarantees: these keys must NOT appear.
    assert "participants" not in body
    assert "notes" not in body
    assert "strokes" not in body
    assert "dms" not in body
    assert "modules" not in body


def test_preview_does_not_require_auth(client):
    # No session cookie / agent_id header — must still succeed.
    res = client.get("/api/parties/cream-terrazzo/preview")
    assert res.status_code == 200


def test_preview_returns_last_5_chats_room_wide(client):
    h = register_human(client)
    join_party(client, h, slug="cream-terrazzo")
    # Send 7 chats — preview should expose the last 5 in chronological order.
    for i in range(7):
        r = client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": {"kind": "human", "id": h["session_id"]}, "text": f"msg{i}"},
        )
        assert r.status_code == 200, r.text

    res = client.get("/api/parties/cream-terrazzo/preview")
    assert res.status_code == 200
    chats = res.json()["recent_chat"]
    assert [c["text"] for c in chats] == ["msg2", "msg3", "msg4", "msg5", "msg6"]
    for c in chats:
        assert c["actor_username"] == h["username"]
        assert c["actor_kind"] == "human"
        assert isinstance(c["seq"], int)
        assert isinstance(c["at"], (int, float))


def test_preview_chat_does_not_include_proximity_metadata(client):
    h = register_human(client)
    join_party(client, h, slug="cream-terrazzo")
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "human", "id": h["session_id"]}, "text": "hi"},
    )
    res = client.get("/api/parties/cream-terrazzo/preview")
    chats = res.json()["recent_chat"]
    assert chats and chats[0]["text"] == "hi"
    forbidden = {"x", "y", "scope", "audience", "audience_ids", "heard_by"}
    leaked = forbidden.intersection(chats[0].keys())
    assert not leaked, f"preview chat leaked proximity-only fields: {leaked}"
