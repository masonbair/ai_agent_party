from fastapi.testclient import TestClient


def _register_human(client: TestClient, username: str = "DJ", color: str = "#ff6b9d") -> dict:
    user = client.post("/api/session", json={"username": username, "color": color}).json()
    return {**user, "principal": {"kind": "human", "id": user["session_id"]}}


def _join(client: TestClient, user: dict, slug: str = "cream-terrazzo") -> None:
    r = client.post(
        f"/api/parties/{slug}/join",
        json={"principal": user["principal"]},
    )
    assert r.status_code == 200, r.json()


def test_music_play_returns_state(client: TestClient) -> None:
    user = _register_human(client)
    _join(client, user)
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["music"]["track_id"] == "lofi-loop"
    assert body["music"]["playing"] is True
    assert body["music"]["volume"] == 50
    assert "cursor" in body


def test_music_set_volume(client: TestClient) -> None:
    user = _register_human(client)
    _join(client, user)
    client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "set_volume",
            "track_id": "lofi-loop",
            "volume": 10,
        },
    )
    assert r.status_code == 200
    assert r.json()["music"]["volume"] == 10


def test_music_unknown_track_422_with_allowed_list(client: TestClient) -> None:
    user = _register_human(client)
    _join(client, user)
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "play",
            "track_id": "rickroll",
        },
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_track"
    assert "allowed_tracks" in detail
    assert "lofi-loop" in detail["allowed_tracks"]


def test_music_bad_volume_422(client: TestClient) -> None:
    user = _register_human(client)
    _join(client, user)
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "set_volume",
            "track_id": "lofi-loop",
            "volume": 500,
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_volume"


def test_music_not_in_party_409(client: TestClient) -> None:
    user = _register_human(client)
    # NOT joined
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 409


def test_music_unknown_party_404(client: TestClient) -> None:
    user = _register_human(client)
    r = client.post(
        "/api/parties/no-such-party/music",
        json={
            "principal": user["principal"],
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 404


def test_music_bad_action_422(client: TestClient) -> None:
    user = _register_human(client)
    _join(client, user)
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": user["principal"],
            "action": "nuke",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_action"
