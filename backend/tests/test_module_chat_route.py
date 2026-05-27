from fastapi.testclient import TestClient


def _join(client: TestClient, name: str, x: float, y: float) -> str:
    r = client.post("/api/session", json={"username": name, "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_post_module_chat_inside_rect_returns_cursor(client: TestClient) -> None:
    # draw-1 rect: x=620..800 y=420..500 (plus margin=24 each side).
    sid = _join(client, "alex", x=700.0, y=450.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "hi crew"},
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert "cursor" in body
    assert body["module_id"] == "draw-1"


def test_post_module_chat_outside_rect_returns_not_in_range_envelope(
    client: TestClient,
) -> None:
    sid = _join(client, "alex", x=100.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "hi"},
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["error"] == "not_in_range"
    assert body["module_id"] == "draw-1"
    assert "interactionRect" in body
    assert body["actor_position"] == {"x": 100.0, "y": 100.0}


def test_post_module_chat_over_65_chars_returns_invalid_chat_text(
    client: TestClient,
) -> None:
    sid = _join(client, "alex", x=700.0, y=450.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "a" * 100,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_chat_text"


def test_module_chat_cooldown_returns_429_with_retry_after_ms(
    client: TestClient,
) -> None:
    sid = _join(client, "alex", x=700.0, y=450.0)
    # Burst limit is 2; the 3rd back-to-back fails.
    for i in range(2):
        ok = client.post(
            "/api/parties/cream-terrazzo/modules/draw-1/chat",
            json={"principal": {"kind": "human", "id": sid}, "text": f"m{i}"},
        )
        assert ok.status_code == 200, ok.json()
    third = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "m2"},
    )
    assert third.status_code == 429
    body = third.json()["detail"]
    assert body["error"] == "chat_cooldown"
    assert isinstance(body["retry_after_ms"], (int, float))
    assert body["scope"] == "module"
