"""DM business logic — pure functions called by the HTTP route layer.

``send`` performs the proximity gate and writes to the in-memory store.
Helpers ``principal_key`` and ``thread_key`` are reused by the WS route
and the frontend contract test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.dm_store import DmStore, insert_dm
from app.routes.principal import Principal, ResolvedPrincipal
from app.validation import ChatValidationError, validate_chat_text


@dataclass
class DmError(Exception):
    """Raised when ``send`` cannot deliver. ``code`` is the canonical error."""

    code: str
    status: int = 409


def principal_key(principal: ResolvedPrincipal | Principal | dict) -> str:
    if isinstance(principal, dict):
        kind = principal["kind"]
        ident = principal["id"]
    else:
        kind = principal.kind
        ident = principal.id
    return f"{kind.lower()}:{ident}"


def thread_key(a: str, b: str) -> str:
    lo, hi = sorted([a, b])
    return f"{lo}|{hi}"


def send(
    store,
    dm_store: DmStore,
    inbox_hub,
    sender: ResolvedPrincipal,
    recipient: Principal,
    text: str,
) -> dict[str, Any]:
    cleaned = validate_chat_text(text)  # raises ChatValidationError
    sender_key = principal_key(sender)
    recipient_key = principal_key(recipient)
    if sender_key == recipient_key:
        raise DmError("self_dm", status=400)
    if not store.principal_exists(recipient):
        raise DmError("recipient_unknown", status=404)
    sender_world = store.world_of(sender_key)
    recipient_world = store.world_of(recipient_key)
    if sender_world is None:
        raise DmError("not_present", status=409)
    if recipient_world is None:
        raise DmError("recipient_not_present", status=409)
    if sender_world != recipient_world:
        raise DmError("not_co_located", status=409)
    tk = thread_key(sender_key, recipient_key)
    at = time.time()
    mid = insert_dm(
        dm_store,
        thread_key=tk,
        sender_kind=sender.kind,
        sender_id=sender.id,
        sender_name=sender.username,
        text=cleaned,
        at=at,
    )
    frame = {
        "type": "dm",
        "thread_key": tk,
        "sender_color": sender.color,
        "message": {
            "id": mid,
            "sender_kind": sender.kind,
            "sender_id": sender.id,
            "sender_name": sender.username,
            "text": cleaned,
            "at": at,
        },
    }
    inbox_hub.publish(sender_key, frame)
    if recipient_key != sender_key:
        inbox_hub.publish(recipient_key, frame)
    return {"message_id": mid, "at": at, "thread_key": tk}


__all__ = [
    "ChatValidationError",
    "DmError",
    "principal_key",
    "send",
    "thread_key",
]
