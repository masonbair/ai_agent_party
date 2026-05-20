from fastapi.testclient import TestClient

from app.validation import REACTION_EMOJI_ALLOWLIST


def _join(client: TestClient) -> str:
    r = client.post("/api/session", json={"username": "alice", "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": 100, "y": 100},
    )
    return sid


def test_invalid_emoji_returns_allowed_emojis(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🦄"},
    )
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["error"] == "invalid_emoji"
    assert body["allowed_emojis"] == list(REACTION_EMOJI_ALLOWLIST)
