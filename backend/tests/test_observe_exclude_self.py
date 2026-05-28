"""?exclude_self=true filters out events whose actor_id == requester."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_exclude_self_drops_own_chat_events(client: TestClient) -> None:
    a = _agent(client, "Self", "#4dd0e1")
    b = _agent(client, "Other", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _p(a), "text": "from a"},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _p(b), "text": "from b"},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/observe"
        f"?since={cursor}&exclude_self=true"
        f"&principal_kind=agent&principal_id={a['agent_id']}"
    )
    events = r.json()["events"]
    chats = [e for e in events if e["type"] == "chat"]
    assert all(e.get("actor_id") != a["agent_id"] for e in chats)
    assert any(e.get("actor_id") == b["agent_id"] for e in chats)


def test_exclude_self_default_off(client: TestClient) -> None:
    a = _agent(client, "Self", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _p(a), "text": "hi"},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    )
    chats = [e for e in r.json()["events"] if e["type"] == "chat"]
    assert any(e.get("actor_id") == a["agent_id"] for e in chats)
