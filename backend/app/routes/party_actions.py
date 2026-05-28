import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.errors import (
    INVALID_CHAT_TEXT,
    INVALID_REPLY_TO,
    NOT_IN_PARTY,
    PARTY_NOT_FOUND,
    RATE_LIMITED,
    RECIPIENT_UNKNOWN,
    envelope,
    http_envelope,
)
from app.events import Participant
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import CHAT_ALLOWED_CHARS_REGEX, CHAT_MAX_LEN, ChatValidationError
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
    to_id: str | None = None
    reply_to: int | None = None
    scope: Literal["proximity", "room"] = "proximity"


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
        "event": ev.model_dump(),
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
    from app.rate_limit import chat_limiter
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    if body.to_id is not None and body.to_id not in world.participants:
        raise HTTPException(
            status_code=404,
            detail=envelope(RECIPIENT_UNKNOWN, message="to_id not in party"),
        )
    if body.reply_to is not None and not world.has_chat_at_seq(body.reply_to):
        raise HTTPException(
            status_code=404,
            detail=envelope(
                INVALID_REPLY_TO,
                message="reply_to does not reference a known chat event",
            ),
        )
    ok, retry_after_ms = chat_limiter().try_consume(slug, resolved.id, body.scope)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED,
                message=f"chat cooldown: try again in {retry_after_ms} ms",
                retry_after_ms=retry_after_ms,
                scope=body.scope,
            ),
        )
    try:
        ev = world.chat(
            resolved.id,
            body.text,
            to_id=body.to_id,
            reply_to=body.reply_to,
            scope=body.scope,
        )
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                INVALID_CHAT_TEXT,
                message=str(exc),
                allowed_chars_regex=CHAT_ALLOWED_CHARS_REGEX,
                max_chars=CHAT_MAX_LEN,
            ),
        )
    return {"event": ev.model_dump(), "cursor": world.cursor}


@router.get("/{slug}/participants/{participant_id}")
def get_participant(
    slug: str = Path(pattern=_SLUG_PATTERN),
    participant_id: str = Path(...),
    store: Store = Depends(_store_dep),
) -> dict:
    """Resolve a participant by id, bypassing proximity scoping.

    Returns only the same public fields already visible in the
    proximity-scoped snapshot whenever the requester sees the target.
    """
    world = _world(store, slug)
    p = world.participants.get(participant_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail=envelope(NOT_IN_PARTY),
        )
    return {
        "id": p.id,
        "username": p.username,
        "color": p.color,
        "kind": p.kind,
        "x": p.x,
        "y": p.y,
        "zone": world.derive_zone(p.x, p.y),
        "facing": getattr(p, "facing", None),
    }


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
    exclude_self: bool = False,
    principal_id: str | None = None,
    principal_kind: str | None = None,
    viewer_id: str | None = None,
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    party = store.get_party(slug)
    assert party is not None

    requester_id: str | None = None
    if principal_id is not None and principal_kind is not None:
        # Only scope if the requester is actually in the party.
        # If the principal is unknown/not joined, fall back to unscoped so
        # the lobby UI still works.
        if principal_id in world.participants:
            requester_id = principal_id

    if since is None:
        if requester_id is None:
            snap = world.snapshot()
        else:
            snap = world.scoped_snapshot(requester_id)
        return {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "music": snap["music"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
            "active_proposals": world.active_proposals(),
        }
    if requester_id is None:
        payload = world.observe_since(since, viewer_id=viewer_id)
    else:
        payload = world.observe_since_scoped(since, requester_id)
    if exclude_self and principal_id:
        payload["events"] = [
            e for e in payload["events"]
            if e.get("actor_id") != principal_id
        ]
    return payload
