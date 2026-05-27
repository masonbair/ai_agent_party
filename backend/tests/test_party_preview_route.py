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
