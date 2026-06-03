"""Expressive action endpoints: /gesture and /cosmetic.

Kept separate from reactions.py to avoid bloating that file.
Both endpoints use token-bucket rate limiting per actor.
"""
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, PARTY_NOT_FOUND, envelope, http_envelope
from app.rate_limit import RateLimitScope, TokenBucketRegistry
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import (
    ALLOWED_COSMETIC_EFFECTS,
    ALLOWED_GESTURES,
    CosmeticValidationError,
    GestureValidationError,
)
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")

_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _rate_limit_dep() -> TokenBucketRegistry:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world


def _enforce_rate_limit(
    registry: TokenBucketRegistry, scope: RateLimitScope, actor_id: str
) -> None:
    res = registry.try_consume(scope.value, actor_id=actor_id)
    if not res.ok:
        raise http_envelope(
            429,
            "rate_limited",
            message=f"too many {scope.value} actions",
            scope=scope.value,
            retry_after_ms=res.retry_after_ms,
        )


class GestureRequest(BaseModel):
    principal: Principal
    gesture: str


class CosmeticRequest(BaseModel):
    principal: Principal
    effect: str


@router.post("/{slug}/gesture")
def gesture(
    body: GestureRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
    rate_limit: TokenBucketRegistry = Depends(_rate_limit_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    _enforce_rate_limit(rate_limit, RateLimitScope.GESTURE, resolved.id)
    try:
        ev = world.gesture(resolved.id, body.gesture)
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except GestureValidationError as exc:
        raise http_envelope(
            422,
            "invalid_gesture",
            message=str(exc),
            allowed_gestures=list(ALLOWED_GESTURES),
        )
    return {
        "gesture": ev.gesture,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "event": ev.model_dump(),
    }


@router.post("/{slug}/cosmetic")
def cosmetic(
    body: CosmeticRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
    rate_limit: TokenBucketRegistry = Depends(_rate_limit_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    _enforce_rate_limit(rate_limit, RateLimitScope.COSMETIC, resolved.id)
    try:
        ev = world.cosmetic(resolved.id, body.effect)
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except CosmeticValidationError as exc:
        raise http_envelope(
            422,
            "invalid_cosmetic",
            message=str(exc),
            allowed_effects=list(ALLOWED_COSMETIC_EFFECTS),
        )
    return {
        "effect": ev.effect,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "event": ev.model_dump(),
    }
