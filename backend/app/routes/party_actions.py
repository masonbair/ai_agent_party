import time

from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel

from app.errors import INVALID_CHAT_TEXT, NOT_IN_PARTY, PARTY_NOT_FOUND, http_envelope
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
        raise http_envelope(404, PARTY_NOT_FOUND)
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
    style: str | None = None
    if resolved.kind == "agent":
        agent = store.get_agent(resolved.id)
        style = agent.style if agent is not None else "reactive"
    participant = Participant(
        id=resolved.id,
        kind=resolved.kind,
        username=resolved.username,
        color=resolved.color,
        x=float(x),
        y=float(y),
        joined_at=time.time(),
        style=style,
    )
    world.join(participant)
    return {
        "participant": {
            "id": participant.id,
            "kind": participant.kind,
            "username": participant.username,
            "color": participant.color,
            "style": participant.style,
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
        raise http_envelope(409, NOT_IN_PARTY)
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
        raise http_envelope(409, NOT_IN_PARTY)
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
        raise http_envelope(409, NOT_IN_PARTY)
    except ChatValidationError as exc:
        raise http_envelope(422, INVALID_CHAT_TEXT, message=str(exc))
    return {"cursor": world.cursor}


def _room_view(party) -> dict:
    w = party.worldSize
    return {
        "slug": party.slug,
        "name": party.name,
        "worldSize": {"width": w.width, "height": w.height},
        "zones": [
            {
                "id": z.id,
                "label": z.label,
                "x": z.x,
                "y": z.y,
                "width": z.width,
                "height": z.height,
                "centerX": (z.x + z.width / 2.0) / 100.0 * w.width,
                "centerY": (z.y + z.height / 2.0) / 100.0 * w.height,
            }
            for z in party.zones
        ],
        "walls": [
            {"x": wl.x, "y": wl.y, "width": wl.width, "height": wl.height}
            for wl in party.room.walls
        ],
        "music": party.music.label,
        "modules": [
            {
                "id": m.id,
                "kind": m.kind,
                **(
                    {"x": m.x, "y": m.y, "w": m.w, "h": m.h}
                    if m.kind in ("stickynotes", "drawboard")
                    else {}
                ),
                **({"preset": m.preset} if m.kind == "lighting" else {}),
            }
            for m in party.modules
        ],
    }


@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
    principal_id: str | None = None,
    principal_kind: str | None = None,
    viewer_id: str | None = None,
    viewer_kind: str | None = None,
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    party = store.get_party(slug)
    assert party is not None

    # Support both old (principal_id/kind) and new (viewer_id/kind) param names.
    eff_id = viewer_id if viewer_id is not None else principal_id
    eff_kind = viewer_kind if viewer_kind is not None else principal_kind

    requester_id: str | None = None
    if eff_id is not None and eff_kind is not None:
        # Only scope if the requester is actually in the party.
        # If the principal is unknown/not joined, fall back to unscoped so
        # the lobby UI still works.
        if eff_id in world.participants:
            requester_id = eff_id

    if since is None:
        if requester_id is None:
            snap = world.snapshot()
        else:
            snap = world.scoped_snapshot(requester_id)
        body = {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
        }
        if eff_id is not None:
            body["welcome"] = world.latest_welcome_for(eff_id)
        else:
            body["welcome"] = None
        return body
    if requester_id is None:
        return world.observe_since(since, viewer_id=eff_id)
    return world.observe_since_scoped(since, requester_id)
