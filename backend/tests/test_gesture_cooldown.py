from tests.conftest import join_party, register_human


def test_gesture_burst_three_then_cooldown(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    # Burst of 3 succeeds.
    for _ in range(3):
        r = client.post(
            "/api/parties/cream-terrazzo/gesture",
            json={"principal": sess["principal"], "gesture": "wave"},
        )
        assert r.status_code == 200, r.json()
    # 4th immediately is rate-limited.
    r4 = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert r4.status_code == 429
    body = r4.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["scope"] == "gesture"
    assert isinstance(body["retry_after_ms"], int)
    assert body["retry_after_ms"] > 0


def test_gesture_bucket_does_not_share_with_chat(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    # Drain gesture bucket.
    for _ in range(3):
        client.post(
            "/api/parties/cream-terrazzo/gesture",
            json={"principal": sess["principal"], "gesture": "wave"},
        )
    # Chat still works (separate bucket).
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": sess["principal"], "text": "hello"},
    )
    assert r.status_code == 200, r.json()
