from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import (
    INVALID_CHAT_TEXT,
    NOT_IN_PARTY,
    PARTY_NOT_FOUND,
    envelope,
    http_envelope,
    not_in_range_envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden in main + conftest
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world


_SLUG_PATTERN = r"^[a-z0-9-]+$"
_MODULE_PATTERN = r"^[a-z0-9-]+$"


class ModuleChatRequest(BaseModel):
    principal: Principal
    text: str


def _not_in_range(
    world: PartyWorld, module_id: str, actor_id: str
) -> HTTPException:
    rect = world.interaction_rect(module_id) or {
        "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0,
    }
    pos = world.actor_position(actor_id) or {"x": 0.0, "y": 0.0}
    return HTTPException(
        status_code=409,
        detail=not_in_range_envelope(
            module_id=module_id, interaction_rect=rect, actor_position=pos
        ),
    )


@router.post("/{slug}/modules/{module_id}/chat")
def post_module_chat(
    body: ModuleChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.module_chat(resolved.id, module_id, body.text)
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except PartyWorld.NotInRangeError:
        raise _not_in_range(world, module_id, resolved.id)
    except KeyError:
        raise http_envelope(404, "not_found")
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(INVALID_CHAT_TEXT, message=str(exc)),
        )
    return {"cursor": world.cursor, "module_id": module_id, "seq": ev.seq}


@router.get("/{slug}/modules/{module_id}/chat-history")
def get_module_chat_history(
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    return {
        "module_id": module_id,
        "events": world.module_chat_history(module_id),
    }
