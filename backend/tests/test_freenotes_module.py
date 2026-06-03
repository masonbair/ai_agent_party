from fastapi.testclient import TestClient


def _join(client: TestClient, name: str, x: float, y: float) -> str:
    r = client.post("/api/session", json={"username": name, "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_cream_terrazzo_seeds_freenotes_module(client: TestClient) -> None:
    resp = client.get("/api/parties/cream-terrazzo/observe")
    assert resp.status_code == 200
    mods = resp.json()["modules"]
    kinds = {m["kind"] for m in mods}
    assert "freenotes" in kinds
    free = next(m for m in mods if m["kind"] == "freenotes")
    assert free["id"] == "freenotes-1"
    # Freenotes has no interactionRect (notes are world-wide).
    assert "interactionRect" not in free
    assert free["notes"] == []


def test_create_freenote_anywhere_in_room_succeeds(client: TestClient) -> None:
    sid = _join(client, "alex", x=100.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "graffiti",
            "color": "pink",
            "x": 400.0,
            "y": 250.0,
        },
    )
    assert resp.status_code == 200, resp.json()
    note = resp.json()["note"]
    assert note["x"] == 400.0
    assert note["y"] == 250.0
    assert note["text"] == "graffiti"


def test_create_freenote_outside_worldsize_clamps_to_room(client: TestClient) -> None:
    sid = _join(client, "alex", x=100.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "x",
            "color": "pink",
            "x": 5000.0,  # cream-terrazzo width is 800
            "y": -100.0,
        },
    )
    assert resp.status_code == 200
    note = resp.json()["note"]
    assert 0.0 <= note["x"] <= 800.0
    assert 0.0 <= note["y"] <= 500.0
