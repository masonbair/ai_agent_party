from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import INVALID_STROKE, NOT_FOUND, NOT_IN_PARTY, PARTY_NOT_FOUND, http_envelope, not_in_range_envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import (
    STROKE_COLOR_ALLOWLIST,
    STROKE_WIDTH_ALLOWLIST,
    StrokeValidationError,
)
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world


_SLUG_PATTERN = r"^[a-z0-9-]+$"
_MODULE_PATTERN = r"^[a-z0-9-]+$"


class StrokeRequest(BaseModel):
    principal: Principal
    color: str
    width: str
    points: list[dict]


class ClearRequest(BaseModel):
    principal: Principal


_DrawErrors = (
    ParticipantNotInPartyError,
    PartyWorld.NotInRangeError,
    StrokeValidationError,
    KeyError,
)


def _map_errors(
    exc: Exception,
    world: "PartyWorld | None" = None,
    module_id: str | None = None,
    actor_id: str | None = None,
) -> Exception:
    if isinstance(exc, ParticipantNotInPartyError):
        return http_envelope(409, NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        rect = (
            world.interaction_rect(module_id)
            if world is not None and module_id is not None
            else None
        )
        pos = (
            world.actor_position(actor_id)
            if world is not None and actor_id is not None
            else None
        )
        body = not_in_range_envelope(
            module_id=module_id or "",
            interaction_rect=rect or {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
            actor_position=pos or {"x": 0.0, "y": 0.0},
        )
        return HTTPException(status_code=409, detail=body)
    if isinstance(exc, StrokeValidationError):
        return http_envelope(
            422,
            INVALID_STROKE,
            message=str(exc),
            allowed_colors=list(STROKE_COLOR_ALLOWLIST),
            allowed_widths=list(STROKE_WIDTH_ALLOWLIST),
        )
    return http_envelope(404, NOT_FOUND)


@router.post("/{slug}/modules/{module_id}/strokes")
def add_stroke(
    body: StrokeRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    raw = {"color": body.color, "width": body.width, "points": body.points}
    try:
        ev = world.add_stroke(resolved.id, module_id, raw)
    except _DrawErrors as exc:
        raise _map_errors(exc, world=world, module_id=module_id, actor_id=resolved.id) from exc
    return {"stroke": ev.stroke.model_dump(), "cursor": world.cursor}


@router.post("/{slug}/modules/{module_id}/clear")
def clear_board(
    body: ClearRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        result = world.vote_clear(resolved.id, module_id)
    except _DrawErrors as exc:
        raise _map_errors(exc, world=world, module_id=module_id, actor_id=resolved.id) from exc
    return result
