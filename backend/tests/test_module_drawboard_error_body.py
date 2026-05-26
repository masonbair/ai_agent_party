from fastapi.testclient import TestClient

from app.validation import STROKE_COLOR_ALLOWLIST, STROKE_WIDTH_ALLOWLIST


def _join_at_draw(client: TestClient, name: str = "alice") -> str:
    r = client.post("/api/session", json={"username": name, "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": 700, "y": 445},
    )
    return sid


def test_invalid_stroke_color_returns_allowlists(client: TestClient) -> None:
    sid = _join_at_draw(client)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": "#abcabc",  # not in stroke allow-list
            "width": "med",
            "points": [{"x": 1, "y": 1}],
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["error"] == "invalid_stroke"
    assert body["allowed_colors"] == list(STROKE_COLOR_ALLOWLIST)
    assert body["allowed_widths"] == list(STROKE_WIDTH_ALLOWLIST)


def test_invalid_stroke_width_returns_allowlists(client: TestClient) -> None:
    sid = _join_at_draw(client)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": STROKE_COLOR_ALLOWLIST[0],
            "width": "huge",
            "points": [{"x": 1, "y": 1}],
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["error"] == "invalid_stroke"
    assert body["allowed_widths"] == list(STROKE_WIDTH_ALLOWLIST)
