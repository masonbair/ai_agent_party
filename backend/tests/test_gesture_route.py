from app.validation import ALLOWED_GESTURES
from tests.conftest import join_party, register_human


def test_gesture_returns_event_key(client):
    sess = register_human(client, username="Alice")
    join_party(client, sess, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["gesture"] == "wave"
    assert "expires_at" in body and "cursor" in body
    assert body["event"]["gesture"] == "wave"
    assert body["event"]["type"] == "gesture"


def test_gesture_emits_gesture_event(client):
    sess = register_human(client, username="Alice")
    join_party(client, sess, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["gesture"] == "wave"
    assert "expires_at" in body
    assert "cursor" in body
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    gestures = [e for e in diff["events"] if e["type"] == "gesture"]
    assert len(gestures) == 1
    g = gestures[0]
    assert g["gesture"] == "wave"
    assert g["actor_username"] == "Alice"
    assert g["actor_kind"] == "human"
    assert g["room_wide"] is False
    assert g["expires_at"] > g["at"]


def test_gesture_bad_value_returns_422_with_allowed_list(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "twerk"},
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_gesture"
    assert body["allowed_gestures"] == list(ALLOWED_GESTURES)


def test_gesture_requires_party_membership(client):
    sess = register_human(client)
    # Not joined.
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "not_in_party"


def test_gesture_unknown_party_returns_404(client):
    sess = register_human(client)
    resp = client.post(
        "/api/parties/no-such-party/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 404
