from app.validation import ALLOWED_COSMETIC_EFFECTS
from tests.conftest import join_party, register_human


def test_cosmetic_emits_event(client):
    sess = register_human(client, username="Alice")
    join_party(client, sess, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    resp = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["effect"] == "confetti"
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    cosm = [e for e in diff["events"] if e["type"] == "cosmetic"]
    assert len(cosm) == 1
    c = cosm[0]
    assert c["effect"] == "confetti"
    assert c["room_wide"] is True
    assert c["actor_username"] == "Alice"
    assert c["expires_at"] > c["at"]


def test_cosmetic_bad_value_returns_422_with_allowed_list(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "rain"},
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_cosmetic"
    assert body["allowed_effects"] == list(ALLOWED_COSMETIC_EFFECTS)


def test_cosmetic_cooldown_one_per_ten_seconds(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    r1 = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert r2.status_code == 429
    body = r2.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["scope"] == "cosmetic"
    assert 0 < body["retry_after_ms"] <= 10_000


def test_cosmetic_requires_party_membership(client):
    sess = register_human(client)
    resp = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert resp.status_code == 409
