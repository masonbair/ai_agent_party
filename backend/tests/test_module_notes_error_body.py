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


def test_create_note_not_in_range_includes_rect_and_actor_position(
    client,
) -> None:
    r = client.post("/api/session", json={"username": "alex", "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    # Join far from sticky-1 (sticky-1 is at x=0, y=420, w=180, h=80 in cream-terrazzo).
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": 400.0, "y": 100.0},
    )
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 10.0,
            "y": 10.0,
        },
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["error"] == "not_in_range"
    assert body["module_id"] == "sticky-1"
    rect = body["interactionRect"]
    assert rect["w"] > 0 and rect["h"] > 0
    pos = body["actor_position"]
    assert pos == {"x": 400.0, "y": 100.0}
