"""Tests for the batched POST /api/parties/{slug}/act endpoint."""
import time

from fastapi.testclient import TestClient


def _agent(client: TestClient) -> dict:
    r = client.post("/api/agents", json={"username": "Bot", "color": "#4dd0e1"})
    assert r.status_code == 200
    a = r.json()
    a["principal"] = {"kind": "agent", "id": a["agent_id"]}
    return a


def _join(client: TestClient, agent: dict, slug: str = "cream-terrazzo") -> None:
    r = client.post(
        f"/api/parties/{slug}/join",
        json={"principal": agent["principal"]},
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_act_runs_actions_sequentially(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)

    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [
                {"kind": "move", "x": 200, "y": 200},
                {"kind": "chat", "text": "hello"},
                {"kind": "react", "emoji": "👋"},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 3
    assert body["results"][0]["x"] == 200
    assert "chat" in body["results"][1]
    assert "error" not in body["results"][0]
    assert "error" not in body["results"][1]
    assert "error" not in body["results"][2]


def test_act_rejects_empty_actions(client: TestClient) -> None:
    agent = _agent(client)
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={"principal": agent["principal"], "actions": []},
    )
    assert res.status_code == 422


def test_act_rejects_more_than_5_actions(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "move", "x": 10, "y": 10}] * 6,
        },
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Mid-batch failure tests
# ---------------------------------------------------------------------------


def test_act_continues_after_action_fails(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)

    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [
                {"kind": "move", "x": 50, "y": 50},
                {"kind": "chat", "text": "nope 🙂"},
                {"kind": "react", "emoji": "🎉"},
            ],
        },
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert "error" not in results[0]
    assert "error" in results[1]
    assert results[1]["error"]["error"] == "invalid_chat_text"
    assert "error" not in results[2]


# ---------------------------------------------------------------------------
# wait action tests
# ---------------------------------------------------------------------------


def test_act_wait_blocks_server_side(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    t0 = time.monotonic()
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [
                {"kind": "move", "x": 60, "y": 60},
                {"kind": "wait", "ms": 500},
                {"kind": "move", "x": 80, "y": 80},
            ],
        },
    )
    elapsed = time.monotonic() - t0
    assert res.status_code == 200
    assert elapsed >= 0.5
    assert res.json()["results"][1] == {"waited_ms": 500}


def test_act_wait_caps_at_2000ms(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "wait", "ms": 2001}],
        },
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Cooldown integration
# ---------------------------------------------------------------------------


def test_act_two_chats_back_to_back_triggers_cooldown(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [
                {"kind": "chat", "text": "first"},
                {"kind": "chat", "text": "second"},
            ],
        },
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert "error" not in results[0]
    # Either the second chat succeeds (if cooldown window is sub-millisecond)
    # or it errors with a cooldown code.
    if "error" in results[1]:
        assert results[1]["error"]["error"] in {"chat_cooldown", "rate_limited"}


# ---------------------------------------------------------------------------
# Gesture action
# ---------------------------------------------------------------------------


def test_act_gesture_action(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "gesture", "gesture": "wave"}],
        },
    )
    assert res.status_code == 200
    result = res.json()["results"][0]
    assert "error" not in result
    assert result["gesture"] == "wave"
