"""Tests for GET /api/parties/{slug}/context (Tasks 8-9)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _reg_agent(client: TestClient):
    def _make(*, username="Bot", color="#4dd0e1", style="reactive"):
        r = client.post(
            "/api/agents",
            json={"username": username, "color": color, "style": style},
        )
        assert r.status_code == 200, r.text
        return r.json()
    return _make


@pytest.fixture
def _join(client: TestClient):
    def _make(slug, principal):
        r = client.post(
            f"/api/parties/{slug}/join",
            json={"principal": principal},
        )
        assert r.status_code == 200, r.json()
        return r.json()
    return _make


# ---- Task 8: Happy path ----

def test_context_returns_digest_shape(client: TestClient, _reg_agent, _join):
    a = _reg_agent(style="ambient")
    _join("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    r = client.get(
        "/api/parties/cream-terrazzo/context",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {
        "room",
        "active_modules",
        "recent_chat",
        "nearby_participants",
        "suggested_openers",
    }
    assert "type" not in body
    assert "seq" not in body
    assert 2 <= len(body["suggested_openers"]) <= 3


def test_context_404_for_unknown_slug(client: TestClient, _reg_agent):
    a = _reg_agent()
    r = client.get(
        "/api/parties/no-such-room/context",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    assert r.status_code == 404


def test_context_409_when_not_in_party(client: TestClient, _reg_agent):
    a = _reg_agent()
    # Did not join — proximity has no anchor.
    r = client.get(
        "/api/parties/cream-terrazzo/context",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "not_in_party"


# ---- Task 9: Rate limit cooldown ----

def test_context_cooldown_blocks_second_call(
    client: TestClient, _reg_agent, _join, monkeypatch
):
    a = _reg_agent()
    _join("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    params = {"viewer_kind": "agent", "viewer_id": a["agent_id"]}

    fake_now = [1000.0]
    monkeypatch.setattr("app.rate_limit._now", lambda: fake_now[0])

    r1 = client.get("/api/parties/cream-terrazzo/context", params=params)
    assert r1.status_code == 200

    # Immediate retry → rate_limited envelope (429).
    r2 = client.get("/api/parties/cream-terrazzo/context", params=params)
    assert r2.status_code == 429
    body = r2.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["retry_after_ms"] > 0

    # After 5s, allowed again.
    fake_now[0] += 5.01
    r3 = client.get("/api/parties/cream-terrazzo/context", params=params)
    assert r3.status_code == 200
