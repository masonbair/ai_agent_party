import time

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.events import Participant
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


class JoinRequest(BaseModel):
    principal: Principal
    x: float | None = None
    y: float | None = None


class LeaveRequest(BaseModel):
    principal: Principal


class MoveRequest(BaseModel):
    principal: Principal
    x: float
    y: float


class ChatRequest(BaseModel):
    principal: Principal
    text: str


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.post("/{slug}/join")
def join(
    body: JoinRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    party = store.get_party(slug)
    assert party is not None
    x = body.x if body.x is not None else party.worldSize.width / 2
    y = body.y if body.y is not None else party.worldSize.height / 2
    participant = Participant(
        id=resolved.id,
        kind=resolved.kind,
        username=resolved.username,
        color=resolved.color,
        x=float(x),
        y=float(y),
        joined_at=time.time(),
    )
    world.join(participant)
    return {
        "participant": {
            "id": participant.id,
            "kind": participant.kind,
            "username": participant.username,
            "color": participant.color,
            "x": participant.x,
            "y": participant.y,
            "zone": world.derive_zone(participant.x, participant.y),
        },
        "cursor": world.cursor,
    }


@router.post("/{slug}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave(
    body: LeaveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> Response:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.leave(resolved.id)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{slug}/move")
def move(
    body: MoveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.move(resolved.id, body.x, body.y)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    return {
        "x": ev.x,
        "y": ev.y,
        "zone": world.derive_zone(ev.x, ev.y),
        "cursor": world.cursor,
    }


@router.post("/{slug}/chat")
def chat(
    body: ChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.chat(resolved.id, body.text)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    except ChatValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"cursor": world.cursor}
