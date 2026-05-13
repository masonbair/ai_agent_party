from fastapi.testclient import TestClient

from app.validation import ALLOWED_COLORS


def test_invalid_color_422_includes_allowed_list(client: TestClient) -> None:
    r = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#000000"}
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_color"
    assert detail["allowed_colors"] == list(ALLOWED_COLORS)


def test_valid_color_still_creates_agent(client: TestClient) -> None:
    r = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    )
    assert r.status_code == 200
    assert r.json()["color"] == "#ff6b9d"
