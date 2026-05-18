from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import NoteValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


_SLUG_PATTERN = r"^[a-z0-9-]+$"
_MODULE_PATTERN = r"^[a-z0-9-]+$"
_NOTE_PATTERN = r"^[a-f0-9]+$"


class CreateNoteRequest(BaseModel):
    principal: Principal
    text: str
    color: str
    x: float
    y: float


class UpdateNoteRequest(BaseModel):
    principal: Principal
    text: str | None = None
    color: str | None = None
    x: float | None = None
    y: float | None = None


class DeleteNoteRequest(BaseModel):
    principal: Principal


def _map_world_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, ParticipantNotInPartyError):
        return HTTPException(status_code=409, detail=NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        return HTTPException(status_code=409, detail=envelope("not_in_range"))
    if isinstance(exc, PartyWorld.LimitReachedError):
        return HTTPException(status_code=409, detail=envelope("limit_reached"))
    if isinstance(exc, PartyWorld.NotAuthorError):
        return HTTPException(status_code=403, detail=envelope("not_author"))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=envelope("not_found"))
    if isinstance(exc, NoteValidationError):
        return HTTPException(
            status_code=400, detail=envelope("invalid_note", message=str(exc))
        )
    return HTTPException(status_code=500, detail=str(exc))


@router.post("/{slug}/modules/{module_id}/notes")
def create_note(
    body: CreateNoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.create_note(
            resolved.id, module_id, body.text, body.color, body.x, body.y
        )
    except Exception as exc:
        raise _map_world_errors(exc) from exc
    return {"note": ev.note.model_dump(), "cursor": world.cursor}


@router.patch("/{slug}/modules/{module_id}/notes/{note_id}")
def update_note(
    body: UpdateNoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    note_id: str = Path(pattern=_NOTE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.update_note(
            resolved.id,
            module_id,
            note_id,
            text=body.text,
            color=body.color,
            x=body.x,
            y=body.y,
        )
    except Exception as exc:
        raise _map_world_errors(exc) from exc
    return {"note": ev.note.model_dump(), "cursor": world.cursor}


@router.delete(
    "/{slug}/modules/{module_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_note(
    body: DeleteNoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    note_id: str = Path(pattern=_NOTE_PATTERN),
    store: Store = Depends(_store_dep),
) -> Response:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.delete_note(resolved.id, module_id, note_id)
    except Exception as exc:
        raise _map_world_errors(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
