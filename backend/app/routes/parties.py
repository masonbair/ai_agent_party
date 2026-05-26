from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError

from app.errors import PARTY_NOT_FOUND, http_envelope
from app.models import PartiesListResponse, PartyConfig
from app.routes.party_actions import _room_view
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.get("", response_model=PartiesListResponse)
def list_parties(store: Store = Depends(_store_dep)) -> PartiesListResponse:
    return PartiesListResponse(parties=store.list_parties())


@router.get("/{slug}", response_model=PartyConfig)
def get_party(
    slug: str = Path(pattern=r"^[a-z0-9-]+$"),
    store: Store = Depends(_store_dep),
) -> PartyConfig:
    party = store.get_party(slug)
    if party is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return party


def _validate_ws_principal(store: Store, frame: object) -> Principal | None:
    if not isinstance(frame, dict) or frame.get("type") != "auth":
        return None
    raw = frame.get("principal")
    if not isinstance(raw, dict):
        return None
    try:
        principal = Principal(**raw)
    except ValidationError:
        return None
    try:
        resolve_principal(store, principal)
    except HTTPException:
        return None
    return principal


@router.websocket("/{slug}/ws")
async def party_ws(
    websocket: WebSocket,
    slug: str,
    store: Store = Depends(_store_dep),
) -> None:
    party = store.get_party(slug)
    if party is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()

    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()
        return

    principal = _validate_ws_principal(store, frame)
    if principal is None:
        await websocket.send_json({"type": "error", "detail": "invalid principal"})
        await websocket.close()
        return

    world = store.get_or_create_world(slug)
    hub = store.get_or_create_hub(slug)
    assert world is not None and hub is not None

    snap = world.snapshot()
    await websocket.send_json(
        {
            "type": "snapshot",
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
        }
    )

    principal_key = f"{principal.kind}:{principal.id}"
    hub.subscribe(websocket, principal_key=principal_key, participant_id=principal.id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(websocket, principal_key=principal_key)
