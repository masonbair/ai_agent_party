from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.events import Participant
from app.store import Store


def _seed_alice(store: Store) -> str:
    sess = store.create_session(username="Alice", color="#ff6b9d")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    world.join(
        Participant(
            id=sess.session_id, kind="human", username="Alice",
            color="#ff6b9d", x=200.0, y=200.0, joined_at=0.0,
        )
    )
    return sess.session_id


def test_ws_handshake_returns_initial_snapshot(client: TestClient, store: Store):
    pid = _seed_alice(store)
    with client.websocket_connect("/api/parties/cream-terrazzo/observe/ws") as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": pid}})
        frame = ws.receive_json()
        assert frame["type"] == "initial"
        assert frame["room"]["slug"] == "cream-terrazzo"
        assert isinstance(frame["participants"], list)
        assert any(p["id"] == pid for p in frame["participants"])
        assert isinstance(frame["modules"], list)
        assert isinstance(frame["recent_chat"], list)
        assert isinstance(frame["cursor"], int)


def test_ws_unknown_principal_closes_4401(client: TestClient):
    with client.websocket_connect(
        "/api/parties/cream-terrazzo/observe/ws"
    ) as ws:
        ws.send_json(
            {"type": "auth", "principal": {"kind": "human", "id": "nope"}}
        )
        with pytest.raises(Exception) as exc_info:
            ws.receive_json()
        from starlette.websockets import WebSocketDisconnect as SWD
        assert isinstance(exc_info.value, SWD)
        assert exc_info.value.code == 4401


def test_ws_malformed_auth_frame_closes_4401(client: TestClient):
    with client.websocket_connect(
        "/api/parties/cream-terrazzo/observe/ws"
    ) as ws:
        ws.send_json({"type": "garbage"})
        with pytest.raises(Exception) as exc_info:
            ws.receive_json()
        from starlette.websockets import WebSocketDisconnect as SWD
        assert isinstance(exc_info.value, SWD)
        assert exc_info.value.code == 4401


def test_ws_unknown_slug_closes_4401(client: TestClient):
    with client.websocket_connect(
        "/api/parties/no-such-party/observe/ws"
    ) as ws:
        with pytest.raises(Exception) as exc_info:
            ws.receive_json()
        from starlette.websockets import WebSocketDisconnect as SWD
        assert isinstance(exc_info.value, SWD)
        assert exc_info.value.code == 4401


def test_ws_emits_ping_after_interval(client: TestClient, store: Store, monkeypatch):
    # Shrink interval so the test is fast.
    from app.routes import observe_ws as obs
    monkeypatch.setattr(obs, "HEARTBEAT_INTERVAL", 0.05)
    monkeypatch.setattr(obs, "HEARTBEAT_TIMEOUT", 1.0)

    pid = _seed_alice(store)
    with client.websocket_connect(
        "/api/parties/cream-terrazzo/observe/ws"
    ) as ws:
        ws.send_json({"type": "auth", "principal": {"kind": "human", "id": pid}})
        _initial = ws.receive_json()
        # Within 0.5s we should see at least one ping.
        seen_ping = False
        for _ in range(20):
            frame = ws.receive_json()
            if frame.get("type") == "ping":
                seen_ping = True
                ws.send_json({"type": "pong"})
                break
        assert seen_ping


def test_ws_closes_when_pong_overdue(client: TestClient, store: Store, monkeypatch):
    from app.routes import observe_ws as obs
    monkeypatch.setattr(obs, "HEARTBEAT_INTERVAL", 0.05)
    monkeypatch.setattr(obs, "HEARTBEAT_TIMEOUT", 0.1)

    pid = _seed_alice(store)
    from starlette.websockets import WebSocketDisconnect as SWD
    with pytest.raises(SWD):
        with client.websocket_connect(
            "/api/parties/cream-terrazzo/observe/ws"
        ) as ws:
            ws.send_json({"type": "auth", "principal": {"kind": "human", "id": pid}})
            _initial = ws.receive_json()
            # Never reply to ping. The server should drop us.
            for _ in range(50):
                ws.receive_json()
