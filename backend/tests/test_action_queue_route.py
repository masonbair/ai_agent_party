"""Tests for the server-side action queue routes.

POST   /api/parties/{slug}/queue    — schedule a batch
GET    /api/parties/{slug}/queue    — list pending
DELETE /api/parties/{slug}/queue/{qid} — cancel
"""
import datetime as dt
import time

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers (mirror the pattern used in other test files)
# ---------------------------------------------------------------------------


def _agent(client: TestClient, username: str = "Bot") -> dict:
    r = client.post("/api/agents", json={"username": username, "color": "#4dd0e1"})
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


def _future_iso(ms: int = 300) -> str:
    return (dt.datetime.utcnow() + dt.timedelta(milliseconds=ms)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _far_future_iso() -> str:
    return (dt.datetime.utcnow() + dt.timedelta(seconds=10)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


# ---------------------------------------------------------------------------
# Basic scheduling
# ---------------------------------------------------------------------------


def test_queue_immediate_execution_runs_actions(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    res = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "move", "x": 150, "y": 150}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "queue_id" in body
    assert "scheduled_for" in body

    # Poll /observe until we see the move (max 2s).
    deadline = time.time() + 2.0
    seen = False
    while time.time() < deadline:
        obs = client.get("/api/parties/cream-terrazzo/observe").json()
        me = next(
            (p for p in obs["participants"] if p["id"] == agent["principal"]["id"]),
            None,
        )
        if me is not None and me["x"] == 150:
            seen = True
            break
        time.sleep(0.05)
    assert seen, "queued action did not execute within 2s"


def test_queue_scheduled_start_at_future(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    # Use a far-future start_at so the task is still pending when we list.
    iso = _far_future_iso()
    res = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "move", "x": 222, "y": 222}],
            "start_at": iso,
        },
    )
    assert res.status_code == 200
    qid = res.json()["queue_id"]

    # Immediately listing should show this queue pending.
    listed = client.get(
        "/api/parties/cream-terrazzo/queue",
        params={"agent_id": agent["principal"]["id"]},
    ).json()
    assert any(q["queue_id"] == qid for q in listed["queues"])


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_queue_cancellation(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    res = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "move", "x": 333, "y": 333}],
            "start_at": _far_future_iso(),
        },
    )
    qid = res.json()["queue_id"]
    cancel = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/queue/{qid}",
        json={"principal": agent["principal"]},
    )
    assert cancel.status_code == 204


# ---------------------------------------------------------------------------
# Queue limits
# ---------------------------------------------------------------------------


def test_queue_limit_max_3_pending(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    body = {
        "principal": agent["principal"],
        "actions": [{"kind": "move", "x": 1, "y": 1}],
        "start_at": _far_future_iso(),
    }
    for _ in range(3):
        assert (
            client.post("/api/parties/cream-terrazzo/queue", json=body).status_code
            == 200
        )
    fourth = client.post("/api/parties/cream-terrazzo/queue", json=body)
    assert fourth.status_code == 429
    assert fourth.json()["detail"]["error"] == "queue_limit"


def test_queue_slot_frees_after_completion(client: TestClient) -> None:
    agent = _agent(client)
    _join(client, agent)
    body = {
        "principal": agent["principal"],
        "actions": [{"kind": "move", "x": 1, "y": 1}],
    }
    for _ in range(3):
        assert (
            client.post("/api/parties/cream-terrazzo/queue", json=body).status_code
            == 200
        )
    time.sleep(0.3)  # let immediate tasks drain
    res = client.post("/api/parties/cream-terrazzo/queue", json=body)
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Principal isolation
# ---------------------------------------------------------------------------


def test_queue_principal_isolation(client: TestClient) -> None:
    a = _agent(client, "Alpha")
    b = _agent(client, "Beta")
    _join(client, a)
    _join(client, b)

    qid = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": a["principal"],
            "actions": [{"kind": "move", "x": 1, "y": 1}],
            "start_at": _far_future_iso(),
        },
    ).json()["queue_id"]

    # b should not see a's queue.
    listed = client.get(
        "/api/parties/cream-terrazzo/queue",
        params={"agent_id": b["principal"]["id"]},
    ).json()
    assert not any(q["queue_id"] == qid for q in listed["queues"])

    # b should not be able to cancel a's queue.
    cancel = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/queue/{qid}",
        json={"principal": b["principal"]},
    )
    assert cancel.status_code == 403


# ---------------------------------------------------------------------------
# Cooldown regression
# ---------------------------------------------------------------------------


def test_queued_chat_respects_cooldown(client: TestClient) -> None:
    """Chat via /chat, then queue another chat — cooldown path is exercised."""
    agent = _agent(client)
    _join(client, agent)

    r1 = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": agent["principal"], "text": "live"},
    )
    assert r1.status_code == 200

    q = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent["principal"],
            "actions": [{"kind": "chat", "text": "queued"}],
        },
    )
    assert q.status_code == 200

    # Wait for the queue to fire; either outcome is valid but the live msg
    # must always appear.
    time.sleep(0.2)
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    texts = [c["text"] for c in obs["recent_chat"]]
    assert "live" in texts
    # "queued" may or may not be present depending on cooldown window.
