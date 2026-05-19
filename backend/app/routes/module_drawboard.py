from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import StrokeValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
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


def _map_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, ParticipantNotInPartyError):
        return HTTPException(status_code=409, detail=NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        return HTTPException(status_code=409, detail=envelope("not_in_range"))
    if isinstance(exc, StrokeValidationError):
        return HTTPException(
            status_code=422, detail=envelope("invalid_stroke", message=str(exc))
        )
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=envelope("not_found"))
    return HTTPException(status_code=500, detail=str(exc))


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
    except Exception as exc:
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
    except Exception as exc:
        raise _map_errors(exc) from exc
    return result
