from fastapi.testclient import TestClient

from app.validation import STICKY_COLOR_ALLOWLIST


def _join(client: TestClient, name: str = "alice", color: str = "#ff6b9d", x: float = 110, y: float = 445) -> str:
    r = client.post("/api/session", json={"username": name, "color": color})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_invalid_note_color_returns_allowed_colors(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "#9c27b0",  # an agent palette hex, not a sticky color
            "x": 5,
            "y": 5,
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["error"] == "invalid_note"
    assert body["allowed_colors"] == list(STICKY_COLOR_ALLOWLIST)
