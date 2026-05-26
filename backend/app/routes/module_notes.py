from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel

from app.errors import INVALID_NOTE, LIMIT_REACHED, NOT_AUTHOR, NOT_FOUND, NOT_IN_PARTY, NOT_IN_RANGE, PARTY_NOT_FOUND, http_envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import NoteValidationError, STICKY_COLOR_ALLOWLIST
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
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


_NoteErrors = (
    ParticipantNotInPartyError,
    PartyWorld.NotInRangeError,
    PartyWorld.LimitReachedError,
    PartyWorld.NotAuthorError,
    KeyError,
    NoteValidationError,
)


def _map_world_errors(exc: Exception) -> Exception:
    if isinstance(exc, ParticipantNotInPartyError):
        return http_envelope(409, NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        return http_envelope(409, NOT_IN_RANGE,
                             message="You are not within the module's interaction zone.")
    if isinstance(exc, PartyWorld.LimitReachedError):
        return http_envelope(409, LIMIT_REACHED,
                             message="You have reached the per-user note limit.")
    if isinstance(exc, PartyWorld.NotAuthorError):
        return http_envelope(403, NOT_AUTHOR,
                             message="Only the note's author can modify it.")
    if isinstance(exc, KeyError):
        return http_envelope(404, NOT_FOUND)
    if isinstance(exc, NoteValidationError):
        return http_envelope(
            422,
            INVALID_NOTE,
            message=str(exc),
            allowed_colors=list(STICKY_COLOR_ALLOWLIST),
        )
    return http_envelope(422, INVALID_NOTE, message=str(exc))


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
    except _NoteErrors as exc:
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
    except _NoteErrors as exc:
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
    except _NoteErrors as exc:
        raise _map_world_errors(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
