"""Direct participant lookup — bypasses proximity scoping for id resolution."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _principal(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_lookup_returns_participant_fields(client: TestClient) -> None:
    a = _agent(client, "Lookee", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(a), "x": 123.0, "y": 234.0},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == a["agent_id"]
    assert body["username"] == "Lookee"
    assert body["color"] == "#ff6b9d"
    assert body["kind"] == "agent"
    assert body["x"] == 123.0
    assert body["y"] == 234.0
    assert "zone" in body
    assert "facing" in body


def test_lookup_404_when_not_in_party(client: TestClient) -> None:
    r = client.get(
        "/api/parties/cream-terrazzo/participants/no-such-id"
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "not_in_party"


def test_lookup_404_when_party_missing(client: TestClient) -> None:
    r = client.get("/api/parties/no-such-party/participants/whatever")
    assert r.status_code == 404
