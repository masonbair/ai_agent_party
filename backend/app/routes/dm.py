from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ValidationError

from app.dm import DmError, principal_key, send
from app.dm_store import list_threads_for, query_thread_history
from app.errors import (
    DM_FORBIDDEN,
    INVALID_CHAT_TEXT,
    PRINCIPAL_UNKNOWN,
    RECIPIENT_UNKNOWN,
    http_envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError

router = APIRouter(prefix="/api/dm")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


class RecipientRef(BaseModel):
    kind: str
    id: str


class SendDmRequest(BaseModel):
    principal: Principal
    recipient: RecipientRef
    text: str


@router.post("/send")
def send_dm(
    body: SendDmRequest, store: Store = Depends(_store_dep)
) -> dict:
    sender = resolve_principal(store, body.principal)
    try:
        recipient = Principal(kind=body.recipient.kind, id=body.recipient.id)
    except ValidationError:
        raise http_envelope(404, RECIPIENT_UNKNOWN)
    try:
        return send(
            store=store,
            dm_store=store.dm_store,
            inbox_hub=store.inbox_hub,
            sender=sender,
            recipient=recipient,
            text=body.text,
        )
    except ChatValidationError as exc:
        raise http_envelope(422, INVALID_CHAT_TEXT, message=str(exc))
    except DmError as exc:
        raise http_envelope(exc.status, exc.code)


@router.get("/threads")
def list_threads(
    principal_kind: str = Query(...),
    principal_id: str = Query(...),
    store: Store = Depends(_store_dep),
) -> dict:
    try:
        principal = Principal(kind=principal_kind, id=principal_id)
    except ValidationError:
        raise http_envelope(401, PRINCIPAL_UNKNOWN)
    resolved = resolve_principal(store, principal)
    key = principal_key(resolved)
    return {"threads": list_threads_for(store.dm_store, principal_key=key)}


@router.get("/threads/{thread_key}/history")
def get_history(
    thread_key: str,
    principal_kind: str = Query(...),
    principal_id: str = Query(...),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    store: Store = Depends(_store_dep),
) -> dict:
    try:
        principal = Principal(kind=principal_kind, id=principal_id)
    except ValidationError:
        raise http_envelope(401, PRINCIPAL_UNKNOWN)
    resolved = resolve_principal(store, principal)
    key = principal_key(resolved)
    parts = thread_key.split("|")
    if len(parts) != 2 or key not in parts:
        raise http_envelope(403, DM_FORBIDDEN)
    messages = query_thread_history(
        store.dm_store,
        thread_key=thread_key,
        before_id=before_id,
        limit=limit,
    )
    return {"thread_key": thread_key, "messages": messages}
