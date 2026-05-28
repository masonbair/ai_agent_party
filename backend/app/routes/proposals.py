from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import (
    INVALID_EXPIRY,
    INVALID_PROPOSAL_TEXT,
    INVALID_VOTE,
    NOT_IN_PARTY,
    PROPOSAL_EXPIRED,
    PROPOSAL_NOT_FOUND,
    envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError
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


class CreateProposalRequest(BaseModel):
    principal: Principal
    text: str
    expires_in_sec: int


class VoteRequest(BaseModel):
    principal: Principal
    vote: str


@router.post("/{slug}/proposals")
def create_proposal(
    body: CreateProposalRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.create_proposal(resolved.id, body.text, body.expires_in_sec)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(INVALID_PROPOSAL_TEXT, message=str(exc)),
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "invalid_expiry":
            raise HTTPException(status_code=422, detail=envelope(INVALID_EXPIRY))
        raise HTTPException(
            status_code=422, detail=envelope(INVALID_PROPOSAL_TEXT)
        )
    return {"proposal_id": ev.proposal_id, "expires_at": ev.expires_at}


@router.post("/{slug}/proposals/{proposal_id}/vote")
def vote_proposal(
    body: VoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    proposal_id: str = Path(...),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.vote_proposal(resolved.id, proposal_id, body.vote)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    except KeyError:
        raise HTTPException(
            status_code=404, detail=envelope(PROPOSAL_NOT_FOUND)
        )
    except TimeoutError:
        raise HTTPException(
            status_code=410, detail=envelope(PROPOSAL_EXPIRED)
        )
    except ValueError:
        raise HTTPException(status_code=422, detail=envelope(INVALID_VOTE))
    return {"proposal_id": proposal_id, "tallies": ev.tallies}
