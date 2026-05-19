from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


class LightingRequest(BaseModel):
    principal: Principal
    preset: str


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.post("/{slug}/lighting")
def set_lighting(
    body: LightingRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.set_lighting(resolved.id, body.preset)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope("invalid_preset", message=str(exc)),
        )
    return {"preset": ev.preset, "cursor": world.cursor}
