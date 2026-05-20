from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app import db as db_module
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
        raise HTTPException(status_code=404, detail="party not found")
    if limit < 1 or limit > db_module.MAX_HISTORY_LIMIT:
        raise HTTPException(status_code=400, detail="invalid limit")
    if before_id is not None and before_id < 1:
        raise HTTPException(status_code=400, detail="invalid before_id")
    assert store.db is not None, "db not initialized"
    rows = db_module.query_broadcast_history(
        store.db, slug, before_id=before_id, limit=limit
    )
    next_before = rows[-1]["id"] if len(rows) == limit else None
    return {"messages": rows, "next_before_id": next_before}
