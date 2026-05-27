from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app import rate_limit
from app.errors import (
    INVALID_ACTION,
    INVALID_TRACK,
    INVALID_VOLUME,
    NOT_IN_PARTY,
    PARTY_NOT_FOUND,
    RATE_LIMITED_MUSIC,
    envelope,
    http_envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import (
    MUSIC_TRACK_ALLOWLIST,
    MusicValidationError,
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


class MusicRequest(BaseModel):
    principal: Principal
    track_id: str
    action: str  # validated in handler to return proper error code
    volume: int | None = None


_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _classify_error(exc: MusicValidationError) -> tuple[str, dict]:
    msg = str(exc)
    # Use more specific prefixes to avoid false matches (e.g. "set_volume" in
    # an "unknown action" message would falsely trigger INVALID_VOLUME).
    if "track_id" in msg or "unknown track" in msg:
        return INVALID_TRACK, {"allowed_tracks": list(MUSIC_TRACK_ALLOWLIST)}
    if "unknown action" in msg:
        return INVALID_ACTION, {}
    if "volume" in msg:
        return INVALID_VOLUME, {}
    return INVALID_ACTION, {}


@router.post("/{slug}/music")
def set_music(
    body: MusicRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    allowed = rate_limit.acquire(
        scope="music",
        principal_id=resolved.id,
        burst=2,
        refill_per_sec=0.2,  # 1 token per 5 seconds
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED_MUSIC,
                message="music cooldown: burst 2, refill 1 per 5s",
            ),
        )
    try:
        ev = world.set_music(
            resolved.id,
            action=body.action,
            track_id=body.track_id,
            volume=body.volume,
        )
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except MusicValidationError as exc:
        code, extras = _classify_error(exc)
        raise HTTPException(
            status_code=422,
            detail=envelope(code, message=str(exc), **extras),
        )
    return {
        "music": {
            "track_id": ev.track_id,
            "playing": ev.playing,
            "volume": ev.volume,
            "since": ev.at,
        },
        "cursor": world.cursor,
    }
