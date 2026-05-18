from fastapi.testclient import TestClient


def _join(client: TestClient, name: str = "alice", color: str = "#ff6b9d", x: float = 100, y: float = 100) -> str:
    r = client.post("/api/session", json={"username": name, "color": color})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_create_note_happy_path(client: TestClient) -> None:
    sid = _join(client, x=100, y=100)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 5,
            "y": 5,
        },
    )
    assert r.status_code == 200, r.text
    note = r.json()["note"]
    assert note["text"] == "hi" and note["author_id"] == sid


def test_patch_note_only_author(client: TestClient) -> None:
    sid = _join(client, x=100, y=100)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    note_id = r.json()["note"]["id"]
    sid2 = _join(client, name="bob", color="#4dd0e1", x=100, y=100)
    r3 = client.patch(
        f"/api/parties/cream-terrazzo/modules/sticky-1/notes/{note_id}",
        json={"principal": {"kind": "human", "id": sid2}, "text": "hax"},
    )
    assert r3.status_code == 403


def test_delete_note_happy_path(client: TestClient) -> None:
    sid = _join(client, x=100, y=100)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    note_id = r.json()["note"]["id"]
    r2 = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/modules/sticky-1/notes/{note_id}",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r2.status_code == 204


def test_create_note_not_in_zone_409(client: TestClient) -> None:
    sid = _join(client, name="carla", color="#81c784", x=700, y=400)
    r = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    assert r.status_code == 409
