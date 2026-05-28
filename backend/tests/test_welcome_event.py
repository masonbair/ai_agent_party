"""Tests for WelcomeEvent: model shape, emission, targeted delivery (Tasks 5-7)."""

import pytest
from fastapi.testclient import TestClient

from app.events import WelcomeEvent


# ---- Task 5: Model shape ----

def test_welcome_event_shape():
    ev = WelcomeEvent(
        seq=42,
        at=1.0,
        target_actor_id="agent-1",
        actor_id="agent-1",
        actor_username="Bot",
        actor_kind="agent",
        room={"slug": "cream-terrazzo"},
        active_modules=[],
        recent_chat=[],
        nearby_participants=[],
        suggested_openers=["hi"],
    )
    assert ev.type == "welcome"
    assert ev.target_actor_id == "agent-1"
    dumped = ev.model_dump()
    assert dumped["type"] == "welcome"
    assert dumped["target_actor_id"] == "agent-1"


# ---- Task 6 & 7: Emission and targeted delivery ----

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


def test_welcome_event_emitted_on_agent_join(client: TestClient, _reg_agent, _join):
    a = _reg_agent(style="chatty")
    _join("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    # Pull events as the joining agent
    r = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    snap = r.json()
    assert "welcome" in snap, f"keys: {list(snap.keys())}"
    w = snap["welcome"]
    assert w is not None, "welcome was None"
    assert w["target_actor_id"] == a["agent_id"]
    assert w["actor_id"] == a["agent_id"]
    assert "suggested_openers" in w
    assert 2 <= len(w["suggested_openers"]) <= 3
    assert "room" in w
    assert "active_modules" in w
    assert "nearby_participants" in w


def test_welcome_not_emitted_on_human_join(client: TestClient):
    h = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": h["session_id"]}},
    )
    r = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"viewer_kind": "human", "viewer_id": h["session_id"]},
    )
    snap = r.json()
    assert snap.get("welcome") is None


def test_welcome_event_only_delivered_to_joiner(client: TestClient, _reg_agent, _join):
    a = _reg_agent()
    b = _reg_agent(username="Other")
    _join("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    _join("cream-terrazzo", {"kind": "agent", "id": b["agent_id"]})
    # b polls since=0 looking at the event log; b must NOT see a's welcome event
    r = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": 0, "viewer_kind": "agent", "viewer_id": b["agent_id"]},
    )
    events = r.json().get("events", [])
    welcomes = [e for e in events if e.get("type") == "welcome"]
    assert all(e["target_actor_id"] == b["agent_id"] for e in welcomes)
    # b should see ITS OWN welcome event but not a's
    assert any(e["target_actor_id"] == b["agent_id"] for e in welcomes)
    assert not any(e["target_actor_id"] == a["agent_id"] for e in welcomes)
