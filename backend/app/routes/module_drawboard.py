from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.errors import INVALID_STROKE, NOT_FOUND, NOT_IN_PARTY, NOT_IN_RANGE, PARTY_NOT_FOUND, http_envelope
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


def _map_errors(exc: Exception) -> Exception:
    if isinstance(exc, ParticipantNotInPartyError):
        return http_envelope(409, NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        return http_envelope(409, NOT_IN_RANGE,
                             message="You are not within the module's interaction zone.")
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
        raise _map_errors(exc) from exc
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
        raise _map_errors(exc) from exc
    return result
