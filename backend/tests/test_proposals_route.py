"""POST /proposals creates a proposal; POST /proposals/{id}/vote tallies."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_create_proposal_returns_event_key(client: TestClient) -> None:
    a = _agent(client, "Proposer2", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "pizza or tacos", "expires_in_sec": 30},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "proposal_id" in body and "expires_at" in body
    assert body["event"]["type"] == "proposal_created"


def test_vote_proposal_returns_event_key(client: TestClient) -> None:
    a = _agent(client, "Voter2", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    created = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "pizza or tacos", "expires_in_sec": 30},
    ).json()
    pid = created["proposal_id"]
    r = client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "yes"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tallies" in body
    assert body["event"]["type"] == "proposal_vote"


def test_create_proposal_returns_id_and_expiry(client: TestClient) -> None:
    a = _agent(client, "Proposer", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "lets dance", "expires_in_sec": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert "proposal_id" in body
    assert isinstance(body["expires_at"], float)


def test_proposal_created_event_is_room_wide(client: TestClient) -> None:
    a = _agent(client, "Pp", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "go home", "expires_in_sec": 5},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    created = [e for e in events if e["type"] == "proposal_created"]
    assert created
    assert created[0]["room_wide"] is True
    assert created[0]["text"] == "go home"
    assert created[0]["actor_id"] == a["agent_id"]


def test_create_proposal_invalid_expiry(client: TestClient) -> None:
    a = _agent(client, "Pq", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "hi", "expires_in_sec": 0},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_expiry"

    r2 = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "hi", "expires_in_sec": 999},
    )
    assert r2.status_code == 422
    assert r2.json()["detail"]["error"] == "invalid_expiry"


def test_create_proposal_invalid_text(client: TestClient) -> None:
    a = _agent(client, "Pr", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "", "expires_in_sec": 5},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_proposal_text"


def test_vote_overwrites_previous(client: TestClient) -> None:
    a = _agent(client, "Av", "#4dd0e1")
    b = _agent(client, "Bv", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    pid = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "dance", "expires_in_sec": 10},
    ).json()["proposal_id"]
    client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "yes"},
    )
    client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(b), "vote": "no"},
    )
    # A changes mind:
    r = client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "abstain"},
    )
    tallies = r.json()["tallies"]
    assert tallies == {"yes": 0, "no": 1, "abstain": 1}


def test_vote_unknown_proposal_404(client: TestClient) -> None:
    a = _agent(client, "Aw", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals/nope/vote",
        json={"principal": _p(a), "vote": "yes"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "proposal_not_found"


def test_vote_invalid_choice_422(client: TestClient) -> None:
    a = _agent(client, "Ax", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    pid = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "hi", "expires_in_sec": 5},
    ).json()["proposal_id"]
    r = client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "maybe"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_vote"
