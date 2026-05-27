from fastapi.testclient import TestClient


def _join(client: TestClient, name: str, x: float, y: float) -> str:
    r = client.post("/api/session", json={"username": name, "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_freenote_visible_only_within_proximity_radius(
    client: TestClient,
) -> None:
    a = _join(client, "alex", x=400.0, y=250.0)
    b = _join(client, "bee", x=400.0, y=250.0)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": a},
            "text": "x",
            "color": "pink",
            "x": 400.0,
            "y": 250.0,
        },
    )
    # b is right next to the note — should see it.
    resp_near = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "principal_id": b, "principal_kind": "human"},
    )
    assert any(e["type"] == "note_created" for e in resp_near.json()["events"])

    # Move b far away.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": b}, "x": 10.0, "y": 10.0},
    )
    cursor2 = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"principal_id": b, "principal_kind": "human"},
    ).json()["cursor"]
    # Create another note far from b.
    client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": a},
            "text": "y",
            "color": "pink",
            "x": 700.0,
            "y": 450.0,
        },
    )
    resp_far = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor2, "principal_id": b, "principal_kind": "human"},
    )
    assert not any(
        e["type"] == "note_created" and e["note"]["text"] == "y"
        for e in resp_far.json()["events"]
    )
