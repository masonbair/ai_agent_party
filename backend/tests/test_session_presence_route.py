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


def test_session_ws_rejects_unknown_session_id(client: TestClient) -> None:
    with client.websocket_connect("/api/session/ws") as ws:
        ws.send_json({"type": "auth", "session_id": "does-not-exist"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid session"}


def test_session_ws_rejects_non_auth_first_frame(client: TestClient) -> None:
    with client.websocket_connect("/api/session/ws") as ws:
        ws.send_json({"type": "ping"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "detail": "invalid session"}


def test_presence_eviction_removes_participant_from_world(client: TestClient) -> None:
    user = _signin(client)
    sid = user["session_id"]
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r.status_code == 200

    with client.websocket_connect("/api/session/ws") as ws_a:
        ws_a.send_json({"type": "auth", "session_id": sid})

        with client.websocket_connect("/api/session/ws") as ws_b:
            ws_b.send_json({"type": "auth", "session_id": sid})

            evict = ws_a.receive_json()
            assert evict == {"type": "evicted", "reason": "takeover"}

    r = client.get("/api/parties/cream-terrazzo/observe")
    body = r.json()
    ids = [p["id"] for p in body["participants"]]
    assert sid not in ids
