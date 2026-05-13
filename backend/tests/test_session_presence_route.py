import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _signin(client: TestClient, username: str = "Alice", color: str = "#ff6b9d") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def test_session_ws_accepts_valid_auth_and_holds_open(client: TestClient) -> None:
    user = _signin(client)
    with client.websocket_connect("/api/session/ws") as ws:
        ws.send_json({"type": "auth", "session_id": user["session_id"]})


def test_session_ws_second_connect_evicts_first(client: TestClient) -> None:
    user = _signin(client)
    sid = user["session_id"]
    with client.websocket_connect("/api/session/ws") as ws_a:
        ws_a.send_json({"type": "auth", "session_id": sid})

        with client.websocket_connect("/api/session/ws") as ws_b:
            ws_b.send_json({"type": "auth", "session_id": sid})

            frame = ws_a.receive_json()
            assert frame == {"type": "evicted", "reason": "takeover"}
            with pytest.raises(WebSocketDisconnect):
                ws_a.receive_json()
