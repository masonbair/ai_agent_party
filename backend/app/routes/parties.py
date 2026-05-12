from fastapi import APIRouter, Depends, HTTPException, Path

from app.models import PartiesListResponse, PartyConfig
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.get("", response_model=PartiesListResponse)
def list_parties(store: Store = Depends(_store_dep)) -> PartiesListResponse:
    return PartiesListResponse(parties=store.list_parties())


@router.get("/{slug}", response_model=PartyConfig)
def get_party(
    slug: str = Path(pattern=r"^[a-z0-9-]+$"),
    store: Store = Depends(_store_dep),
) -> PartyConfig:
    party = store.get_party(slug)
    if party is None:
        raise HTTPException(status_code=404, detail="party not found")
    return party
