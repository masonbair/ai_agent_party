from fastapi import (
    APIRouter,
    Depends,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.errors import SESSION_NOT_FOUND, http_envelope
from app.models import CreateSessionRequest, User
from app.store import Store

router = APIRouter(prefix="/api/session")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.post("", response_model=User)
def create_session(
    body: CreateSessionRequest, store: Store = Depends(_store_dep)
) -> User:
    return store.create_session(username=body.username, color=body.color)


@router.get("/{session_id}", response_model=User)
def get_session(session_id: str, store: Store = Depends(_store_dep)) -> User:
    user = store.get_session(session_id)
    if user is None:
        raise http_envelope(404, SESSION_NOT_FOUND)
    return user


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, store: Store = Depends(_store_dep)) -> Response:
    if not store.delete_session(session_id):
        raise http_envelope(404, SESSION_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.websocket("/ws")
async def session_ws(
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

    if not isinstance(frame, dict) or frame.get("type") != "auth":
        await websocket.send_json({"type": "error", "detail": "invalid session"})
        await websocket.close()
        return

    session_id = frame.get("session_id")
    if not isinstance(session_id, str) or store.get_session(session_id) is None:
        await websocket.send_json({"type": "error", "detail": "invalid session"})
        await websocket.close()
        return

    hub = store.session_presence
    hub.subscribe(websocket, session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket, session_id)
