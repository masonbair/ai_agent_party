from fastapi import APIRouter, Depends, Path, Query

from app import db as db_module
from app.errors import INVALID_BEFORE_ID, INVALID_LIMIT, PARTY_NOT_FOUND, http_envelope
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.get("/{slug}/broadcast-history")
def broadcast_history(
    slug: str = Path(pattern=_SLUG_PATTERN),
    before_id: int | None = Query(default=None),
    limit: int = Query(default=50),
    store: Store = Depends(_store_dep),
) -> dict:
    if store.get_party(slug) is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    if limit < 1 or limit > db_module.MAX_HISTORY_LIMIT:
        raise http_envelope(400, INVALID_LIMIT)
    if before_id is not None and before_id < 1:
        raise http_envelope(400, INVALID_BEFORE_ID)
    assert store.db is not None, "db not initialized"
    rows = db_module.query_broadcast_history(
        store.db, slug, before_id=before_id, limit=limit
    )
    next_before = rows[-1]["id"] if len(rows) == limit else None
    return {"messages": rows, "next_before_id": next_before}
