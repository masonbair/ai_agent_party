from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.errors import (
    CANNOT_FOLLOW_SELF,
    NOT_IN_PARTY,
    TARGET_NOT_IN_PARTY,
    envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")

_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    w = store.get_or_create_world(slug)
    if w is None:
        raise HTTPException(status_code=404, detail=envelope("party_not_found"))
    return w


class FollowRequest(BaseModel):
    principal: Principal
    target_id: str


class UnfollowRequest(BaseModel):
    principal: Principal


@router.post("/{slug}/follow")
def follow(
    body: FollowRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.follow(resolved.id, body.target_id)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    except PartyWorld.CannotFollowSelfError:
        raise HTTPException(
            status_code=400, detail=envelope(CANNOT_FOLLOW_SELF)
        )
    except PartyWorld.TargetNotInPartyError:
        raise HTTPException(
            status_code=404, detail=envelope(TARGET_NOT_IN_PARTY)
        )
    return {"target_id": body.target_id}


@router.post("/{slug}/unfollow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow(
    body: UnfollowRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> Response:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.unfollow(resolved.id)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
