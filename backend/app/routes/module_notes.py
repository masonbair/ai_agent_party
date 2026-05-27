from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.errors import INVALID_NOTE, LIMIT_REACHED, NOT_AUTHOR, NOT_FOUND, NOT_IN_PARTY, PARTY_NOT_FOUND, envelope, http_envelope, not_in_range_envelope
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import NoteValidationError, REACTION_EMOJI_ALLOWLIST, ReactionValidationError, STICKY_COLOR_ALLOWLIST
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


def _map_world_errors(
    exc: Exception,
    world: "PartyWorld | None" = None,
    module_id: str | None = None,
    actor_id: str | None = None,
) -> Exception:
    if isinstance(exc, ParticipantNotInPartyError):
        return http_envelope(409, NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        rect = (
            world.interaction_rect(module_id)
            if world is not None and module_id is not None
            else None
        )
        pos = (
            world.actor_position(actor_id)
            if world is not None and actor_id is not None
            else None
        )
        body = not_in_range_envelope(
            module_id=module_id or "",
            interaction_rect=rect or {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
            actor_position=pos or {"x": 0.0, "y": 0.0},
        )
        return HTTPException(status_code=409, detail=body)
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
        raise _map_world_errors(exc, world=world, module_id=module_id, actor_id=resolved.id) from exc
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
        raise _map_world_errors(exc, world=world, module_id=module_id, actor_id=resolved.id) from exc
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
        raise _map_world_errors(exc, world=world, module_id=module_id, actor_id=resolved.id) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ReactNoteRequest(BaseModel):
    principal: Principal
    emoji: str


@router.post("/{slug}/modules/{module_id}/notes/{note_id}/react")
def react_to_note(
    body: ReactNoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    note_id: str = Path(pattern=_NOTE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.react_to_note(resolved.id, module_id, note_id, body.emoji)
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except PartyWorld.NotInRangeError:
        rect = world.interaction_rect(module_id) or {
            "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0,
        }
        pos = world.actor_position(resolved.id) or {"x": 0.0, "y": 0.0}
        raise HTTPException(
            status_code=409,
            detail=not_in_range_envelope(
                module_id=module_id, interaction_rect=rect, actor_position=pos,
            ),
        )
    except KeyError:
        raise http_envelope(404, NOT_FOUND)
    except ReactionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_emoji",
                message=str(exc),
                allowed_emojis=list(REACTION_EMOJI_ALLOWLIST),
            ),
        )
    return {
        "emoji": ev.emoji,
        "note_id": ev.note_id,
        "module_id": ev.module_id,
        "cursor": world.cursor,
    }
