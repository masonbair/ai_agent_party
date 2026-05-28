from fastapi.testclient import TestClient


def test_no_proposals_returns_empty_list(client: TestClient) -> None:
    snap = client.get("/api/parties/cream-terrazzo/observe").json()
    assert snap["active_proposals"] == []


def test_resolved_proposals_drop_from_snapshot(
    client: TestClient, monkeypatch
) -> None:
    import time
    a = client.post(
        "/api/agents", json={"username": "Ac", "color": "#4dd0e1"}
    ).json()
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": a["agent_id"]}},
    )
    client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={
            "principal": {"kind": "agent", "id": a["agent_id"]},
            "text": "xx",
            "expires_in_sec": 1,
        },
    )
    real_time = time.time
    monkeypatch.setattr("app.world.time.time", lambda: real_time() + 2.0)
    snap = client.get("/api/parties/cream-terrazzo/observe").json()
    assert snap["active_proposals"] == []
