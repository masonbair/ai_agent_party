from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.dm import principal_key
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter()


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _resolve_auth(store: Store, frame: object):
    if not isinstance(frame, dict) or frame.get("type") != "auth":
        return None, "invalid_auth_frame"
    raw = frame.get("principal")
    if not isinstance(raw, dict):
        return None, "invalid_principal"
    try:
        principal = Principal(**raw)
    except ValidationError:
        return None, "invalid_principal"
    try:
        resolved = resolve_principal(store, principal)
    except Exception:
        return None, "principal_unknown"
    return resolved, None


@router.websocket("/api/inbox")
async def inbox_ws(
    websocket: WebSocket,
    store: Store = Depends(_store_dep),
) -> None:
    await websocket.accept()
    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()
        return

    resolved, reason = _resolve_auth(store, frame)
    if resolved is None:
        await websocket.send_json({"type": "auth_error", "reason": reason})
        await websocket.close()
        return

    key = principal_key(resolved)
    hub = store.inbox_hub
    hub.subscribe(websocket, key)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket, key)
