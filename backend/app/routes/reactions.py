from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import REACTION_EMOJI_ALLOWLIST, ReactionValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


class ReactRequest(BaseModel):
    principal: Principal
    emoji: str


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.post("/{slug}/react")
def react(
    body: ReactRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.react(resolved.id, body.emoji)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except ReactionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_emoji",
                message=str(exc),
                allowed_emojis=list(REACTION_EMOJI_ALLOWLIST),
            ),
        )
    return {"emoji": ev.emoji, "expires_at": ev.expires_at, "cursor": world.cursor}
