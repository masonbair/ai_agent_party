"""Proposals auto-resolve when expires_at passes (lazy on next observation)."""

import time

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_expired_proposal_resolves_on_observe(
    client: TestClient, monkeypatch
) -> None:
    a = _agent(client, "Aa", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    pid = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "go", "expires_in_sec": 1},
    ).json()["proposal_id"]
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    # Fast-forward time inside world.time.time monkey-patch
    real_time = time.time
    monkeypatch.setattr(
        "app.world.time.time", lambda: real_time() + 2.0
    )
    obs = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    resolved = [
        e for e in obs["events"]
        if e["type"] == "proposal_resolved" and e["proposal_id"] == pid
    ]
    assert resolved, "expected proposal_resolved event after expiry"
    assert resolved[0]["tallies"] == {"yes": 0, "no": 0, "abstain": 0}


def test_initial_snapshot_includes_active_proposals(client: TestClient) -> None:
    a = _agent(client, "Ab", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "ping", "expires_in_sec": 30},
    )
    snap = client.get("/api/parties/cream-terrazzo/observe").json()
    assert "active_proposals" in snap
    assert len(snap["active_proposals"]) == 1
    p = snap["active_proposals"][0]
    assert p["text"] == "ping"
    assert "expires_at" in p
    assert p["tallies"] == {"yes": 0, "no": 0, "abstain": 0}
