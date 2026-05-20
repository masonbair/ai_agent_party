from fastapi.testclient import TestClient


def _join(client: TestClient, name: str, x: float, y: float, color: str = "#ff6b9d") -> str:
    r = client.post("/api/session", json={"username": name, "color": color})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def _move(client: TestClient, sid: str, x: float, y: float) -> None:
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )


def test_initial_snapshot_contains_existing_notes_and_strokes(client: TestClient) -> None:
    # Alice joins and seeds a note + a stroke. Then Bob joins (late) and
    # the snapshot he receives must reflect both.
    obs0 = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in obs0["modules"] if m["kind"] == "stickynotes")
    draw = next(m for m in obs0["modules"] if m["kind"] == "drawboard")

    # Walk Alice into sticky zone, create a note.
    sx = sticky["interactionRect"]["x"] + sticky["interactionRect"]["w"] / 2
    sy = sticky["interactionRect"]["y"] + sticky["interactionRect"]["h"] / 2
    alice = _join(client, "Alice", x=sx, y=sy)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={
            "principal": {"kind": "human", "id": alice},
            "text": "hi",
            "color": "yellow",
            "x": 10,
            "y": 10,
        },
    )

    # Walk Alice into draw zone, add a stroke.
    dx = draw["interactionRect"]["x"] + draw["interactionRect"]["w"] / 2
    dy = draw["interactionRect"]["y"] + draw["interactionRect"]["h"] / 2
    _move(client, alice, dx, dy)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{draw['id']}/strokes",
        json={
            "principal": {"kind": "human", "id": alice},
            "color": "#ffd54f",
            "width": "med",
            "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}],
        },
    )

    # Late joiner Bob — snapshot should include both.
    bob = _join(client, "Bob", x=0, y=0, color="#4dd0e1")
    obs2 = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky2 = next(m for m in obs2["modules"] if m["kind"] == "stickynotes")
    draw2 = next(m for m in obs2["modules"] if m["kind"] == "drawboard")
    assert len(sticky2["notes"]) == 1
    assert sticky2["notes"][0]["text"] == "hi"
    assert len(draw2["strokes"]) == 1
    assert len(draw2["strokes"][0]["points"]) == 2
