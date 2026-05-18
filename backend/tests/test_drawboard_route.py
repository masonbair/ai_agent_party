from fastapi.testclient import TestClient


def _join_near_draw(
    client: TestClient,
    name: str = "alice",
    color: str = "#ff6b9d",
    x: float = 640,
    y: float = 160,
) -> str:
    r = client.post("/api/session", json={"username": name, "color": color})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_add_stroke_happy_path(client: TestClient) -> None:
    sid = _join_near_draw(client)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": "#ff6b9d",
            "width": "med",
            "points": [{"x": 1, "y": 1}, {"x": 5, "y": 5}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["stroke"]["author_id"] == sid


def test_add_stroke_invalid_color_400(client: TestClient) -> None:
    sid = _join_near_draw(client)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": "rebeccapurple",
            "width": "med",
            "points": [{"x": 1, "y": 1}],
        },
    )
    assert r.status_code == 400


def test_clear_solo_clears_immediately(client: TestClient) -> None:
    sid = _join_near_draw(client)
    client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": "#ff6b9d",
            "width": "thin",
            "points": [{"x": 0, "y": 0}],
        },
    )
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/clear",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r.status_code == 200
    assert r.json()["cleared"] is True


def test_clear_two_voters_progressive(client: TestClient) -> None:
    s1 = _join_near_draw(client, name="alice", color="#ff6b9d", x=640, y=160)
    s2 = _join_near_draw(client, name="bob", color="#4dd0e1", x=620, y=180)
    r1 = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/clear",
        json={"principal": {"kind": "human", "id": s1}},
    )
    assert r1.json() == {"votes": 1, "needed": 2, "cleared": False}
    r2 = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/clear",
        json={"principal": {"kind": "human", "id": s2}},
    )
    assert r2.json()["cleared"] is True
