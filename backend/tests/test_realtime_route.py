import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _human(client: TestClient, username: str = "Alice", color: str = "#ff6b9d") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def test_ws_rejects_unknown_party_slug(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/parties/does-not-exist/ws") as ws:
            # The server should close before sending anything; receiving here
            # raises WebSocketDisconnect.
            ws.receive_json()


def test_ws_handshake_rejects_bad_principal(client: TestClient) -> None:
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": "nope"}})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid principal"}


def test_ws_sends_snapshot_after_valid_auth(client: TestClient) -> None:
    user = _human(client)
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json(
            {
                "type": "auth",
                "principal": {"kind": "human", "id": user["session_id"]},
            }
        )
        frame = ws.receive_json()
        assert frame["type"] == "snapshot"
        assert "room" in frame
        assert "participants" in frame
        assert "cursor" in frame
        assert frame["room"]["slug"] == "cream-terrazzo"


def test_ws_pushes_event_when_another_principal_joins(client: TestClient) -> None:
    alice = _human(client, username="Alice", color="#ff6b9d")
    bob = _human(client, username="Bob", color="#4dd0e1")
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json(
            {
                "type": "auth",
                "principal": {"kind": "human", "id": alice["session_id"]},
            }
        )
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"
        # Bob joins via the HTTP route → Alice's WS should get an event.
        r = client.post(
            "/api/parties/cream-terrazzo/join",
            json={"principal": {"kind": "human", "id": bob["session_id"]}},
        )
        assert r.status_code == 200
        frame = ws.receive_json()
        assert frame["type"] == "event"
        assert frame["event"]["type"] == "join"
        assert frame["event"]["actor_username"] == "Bob"


def test_ws_first_frame_non_auth_is_rejected(client: TestClient) -> None:
    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws:
        ws.send_json({"type": "ping"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid principal"}
