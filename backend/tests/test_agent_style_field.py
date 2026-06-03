"""Tests for the `style` field on Agent (Tasks 1-3)."""

import pytest
from fastapi.testclient import TestClient

from app.events import Agent


# --- Task 1: Agent model ---

def test_agent_model_accepts_style():
    a = Agent(agent_id="a1", username="Bot", color="#ff6b9d", style="chatty")
    assert a.style == "chatty"


def test_agent_model_defaults_style_to_reactive():
    a = Agent(agent_id="a1", username="Bot", color="#ff6b9d")
    assert a.style == "reactive"


# --- Task 2: POST /api/agents ---

def test_create_agent_accepts_style(client: TestClient):
    r = client.post(
        "/api/agents",
        json={"username": "Bot", "color": "#ff6b9d", "style": "chatty"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["style"] == "chatty"


def test_create_agent_defaults_style(client: TestClient):
    r = client.post("/api/agents", json={"username": "Bot2", "color": "#ff6b9d"})
    assert r.status_code == 200
    assert r.json()["style"] == "reactive"


def test_create_agent_rejects_bad_style(client: TestClient):
    r = client.post(
        "/api/agents",
        json={"username": "Bot3", "color": "#ff6b9d", "style": "loud"},
    )
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["error"] == "invalid_style"
    assert set(body["allowed_styles"]) == {"chatty", "ambient", "reactive"}


# --- Task 3: Observe participants include style ---

@pytest.fixture
def _reg_agent(client: TestClient):
    """Return a callable that registers an agent with optional style."""
    def _make(*, username="Bot", color="#4dd0e1", style="reactive"):
        r = client.post(
            "/api/agents",
            json={"username": username, "color": color, "style": style},
        )
        assert r.status_code == 200, r.text
        return r.json()
    return _make


@pytest.fixture
def _reg_human(client: TestClient):
    """Return a callable that registers a human session."""
    def _make(*, username="Alice", color="#ff6b9d"):
        r = client.post(
            "/api/session",
            json={"username": username, "color": color},
        )
        assert r.status_code == 200, r.text
        return r.json()
    return _make


@pytest.fixture
def _join(client: TestClient):
    """Return a callable that joins a party given a raw principal dict."""
    def _make(slug, principal):
        r = client.post(
            f"/api/parties/{slug}/join",
            json={"principal": principal},
        )
        assert r.status_code == 200, r.json()
        return r.json()
    return _make


def test_observe_participants_include_agent_style(client: TestClient, _reg_agent, _join):
    a = _reg_agent(style="ambient")
    _join("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    r = client.get("/api/parties/cream-terrazzo/observe")
    assert r.status_code == 200
    me = next(p for p in r.json()["participants"] if p["id"] == a["agent_id"])
    assert me["style"] == "ambient"


def test_observe_participants_humans_have_null_style(client: TestClient, _reg_human, _join):
    h = _reg_human()
    _join("cream-terrazzo", {"kind": "human", "id": h["session_id"]})
    r = client.get("/api/parties/cream-terrazzo/observe")
    me = next(p for p in r.json()["participants"] if p["id"] == h["session_id"])
    assert me.get("style") is None
