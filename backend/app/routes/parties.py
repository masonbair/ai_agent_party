import time

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
from app.models import (
    Occupancy,
    PartiesListResponse,
    PartyConfig,
    PartyListEntry,
    PartyPreviewChat,
    PartyPreviewMusic,
    PartyPreviewResponse,
)
from app.occupancy import compute_occupancy
from app.routes.party_actions import _room_view
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.get("", response_model=PartiesListResponse)
def list_parties(store: Store = Depends(_store_dep)) -> PartiesListResponse:
    now = time.time()
    entries: list[PartyListEntry] = []
    for party in store.list_parties():
        world = store.get_world(party.slug)
        if world is None:
            occ = Occupancy(humans=0, agents=0, total=0, active_last_5min=0)
        else:
            occ = Occupancy(**compute_occupancy(world, now=now))
        entries.append(
            PartyListEntry(**party.model_dump(), occupancy=occ)
        )
    return PartiesListResponse(parties=entries)


@router.get("/{slug}/preview", response_model=PartyPreviewResponse)
def preview_party(
    slug: str = Path(pattern=r"^[a-z0-9-]+$"),
    store: Store = Depends(_store_dep),
) -> PartyPreviewResponse:
    party = store.get_party(slug)
    if party is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    world = store.get_world(slug)
    now = time.time()
    if world is None:
        occ = Occupancy(humans=0, agents=0, total=0, active_last_5min=0)
        lighting = "day"
        recent: list[PartyPreviewChat] = []
    else:
        occ = Occupancy(**compute_occupancy(world, now=now))
        lighting = world.lighting
        raw_chats = world.recent_chat(limit=5)
        recent = []
        for c in raw_chats:
            actor_username = c.get("actor_username")
            if not actor_username:
                p = world.participants.get(c.get("actor_id") or c.get("participant_id", ""))
                actor_username = p.username if p else ""
            recent.append(
                PartyPreviewChat(
                    seq=c["seq"],
                    actor_id=c.get("actor_id") or c.get("participant_id", ""),
                    actor_username=actor_username,
                    actor_kind=c.get("actor_kind", "human"),
                    text=c["text"],
                    at=c["at"],
                )
            )
    music_url = party.music.url
    music_label = party.music.label
    if world is not None:
        world_music = getattr(world, "music_state", None)
        if isinstance(world_music, dict):
            music_url = world_music.get("url", music_url)
            music_label = world_music.get("label", music_label)
    music = PartyPreviewMusic(url=music_url, label=music_label)
    return PartyPreviewResponse(
        slug=party.slug,
        name=party.name,
        description=party.description,
        occupancy=occ,
        lighting=lighting,
        music=music,
        recent_chat=recent,
    )


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
