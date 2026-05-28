"""GET /api/parties/{slug}/context — on-demand context digest for agents."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.errors import NOT_IN_PARTY, envelope
from app.onboarding import build_context_digest
from app.rate_limit import check_rate_limit
from app.routes.party_actions import _room_view
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter(prefix="/api/parties")

_CONTEXT_COOLDOWN_S = 5.0
RATE_LIMITED = "rate_limited"
_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.get("/{slug}/context")
def get_context(
    slug: str = Path(pattern=_SLUG_PATTERN),
    viewer_kind: str = Query(...),
    viewer_id: str = Query(...),
    store: Store = Depends(_store_dep),
) -> dict:
    party = store.get_party(slug)
    if party is None:
        raise HTTPException(status_code=404, detail=envelope("party_not_found"))
    world = store.get_or_create_world(slug)
    assert world is not None
    # Validate principal identity (raises 401 envelope on unknown).
    resolve_principal(store, Principal(kind=viewer_kind, id=viewer_id))
    if viewer_id not in world.participants:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    allowed, retry_after_ms = check_rate_limit(
        "context", f"{viewer_kind}:{viewer_id}", _CONTEXT_COOLDOWN_S
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED,
                message="Rate limit exceeded. Try again after the retry window.",
                retry_after_ms=int(retry_after_ms),
            ),
        )
    return build_context_digest(
        world, party, viewer_id=viewer_id, room_view_fn=_room_view
    )
