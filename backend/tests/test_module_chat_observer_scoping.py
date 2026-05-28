from fastapi.testclient import TestClient


def _join(client: TestClient, name: str, x: float, y: float) -> str:
    r = client.post("/api/session", json={"username": name, "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_module_chat_visible_to_participant_inside_rect(
    client: TestClient,
) -> None:
    a = _join(client, "alex", x=700.0, y=450.0)
    b = _join(client, "bee", x=700.0, y=450.0)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": a}, "text": "hi crew"},
    )
    # Observer b is inside the rect.
    resp = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "principal_id": b, "principal_kind": "human"},
    )
    types = [e["type"] for e in resp.json()["events"]]
    assert "module_chat" in types


def test_module_chat_hidden_from_participant_outside_rect(
    client: TestClient,
) -> None:
    a = _join(client, "alex", x=700.0, y=450.0)
    b = _join(client, "bee", x=100.0, y=100.0)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": a}, "text": "hi crew"},
    )
    resp = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "principal_id": b, "principal_kind": "human"},
    )
    types = [e["type"] for e in resp.json()["events"]]
    assert "module_chat" not in types
