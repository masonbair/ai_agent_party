from fastapi.testclient import TestClient

from app.errors import INVALID_CHAT_TEXT, INVALID_COLOR, VALIDATION_ERROR


def test_pydantic_bad_username_uses_envelope_shape(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "a", "color": "#ff6b9d"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == VALIDATION_ERROR
    assert any(f["field"] == "username" for f in detail["fields"])


def test_pydantic_bad_payload_shape_uses_envelope(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "Alice"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == VALIDATION_ERROR
    assert any(f["field"] == "color" for f in detail["fields"])


def test_agents_bad_username_uses_envelope_shape(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "a", "color": "#ff6b9d"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == VALIDATION_ERROR
    assert any(f["field"] == "username" for f in detail["fields"])


def test_chat_invalid_text_uses_envelope_shape(client: TestClient) -> None:
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post("/api/parties/cream-terrazzo/join", json={"principal": principal})
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": principal, "text": "<script>"},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == INVALID_CHAT_TEXT
    assert "message" in detail


def test_color_envelope_unchanged(client: TestClient) -> None:
    # Regression check: the existing color 422 envelope keeps its specific code.
    r = client.post("/api/agents", json={"username": "Bot1", "color": "#000000"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == INVALID_COLOR
