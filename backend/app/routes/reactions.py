from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, PARTY_NOT_FOUND, http_envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import REACTION_EMOJI_ALLOWLIST, ReactionValidationError
from app.world import (
    ParticipantNotInPartyError,
    PartyWorld,
    ReactionTargetConflictError,
    ReactionTargetNotFoundError,
)

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world


class ReactRequest(BaseModel):
    principal: Principal
    emoji: str
    target_seq: int | None = None
    target_actor_id: str | None = None


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
        ev = world.react(
            resolved.id,
            body.emoji,
            target_seq=body.target_seq,
            target_actor_id=body.target_actor_id,
        )
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except ReactionTargetConflictError as exc:
        raise http_envelope(
            422,
            "invalid_reaction_target",
            message=str(exc),
        )
    except ReactionTargetNotFoundError as exc:
        raise http_envelope(
            404,
            "target_not_found",
            message=f"target {exc!s} does not exist",
        )
    except ReactionValidationError as exc:
        raise http_envelope(
            422,
            "invalid_emoji",
            message=str(exc),
            allowed_emojis=list(REACTION_EMOJI_ALLOWLIST),
        )
    return {
        "emoji": ev.emoji,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "target_seq": ev.target_seq,
        "target_actor_id": ev.target_actor_id,
    }
