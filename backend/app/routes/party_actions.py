import datetime as dt
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, Field

from app.action_dispatch import (
    Action,
    DispatchContext,
    _Chat,
    _Move,
    _act_dispatch,
    _do_chat,
    _do_move,
)
from app.action_queue import ActionQueueStore, NotOwnerError, QueueLimitError
from app.errors import (
    INVALID_CHAT_TEXT,
    INVALID_REPLY_TO,
    NOT_IN_PARTY,
    PARTY_NOT_FOUND,
    RATE_LIMITED,
    RECIPIENT_UNKNOWN,
    envelope,
    http_envelope,
)
from app.events import Participant
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import CHAT_ALLOWED_CHARS_REGEX, CHAT_MAX_LEN, ChatValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _queue_dep(request: Request) -> ActionQueueStore:  # pragma: no cover - overridden by tests
    return request.app.state.action_queue


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world


class JoinRequest(BaseModel):
    principal: Principal
    x: float | None = None
    y: float | None = None


class LeaveRequest(BaseModel):
    principal: Principal


class MoveRequest(BaseModel):
    principal: Principal
    x: float
    y: float


class ChatRequest(BaseModel):
    principal: Principal
    text: str
    to_id: str | None = None
    reply_to: int | None = None
    scope: Literal["proximity", "room"] = "proximity"


class ActRequest(BaseModel):
    principal: Principal
    actions: list[Action] = Field(min_length=1, max_length=5)


class QueueRequest(BaseModel):
    principal: Principal
    actions: list[Action] = Field(min_length=1, max_length=5)
    start_at: dt.datetime | None = None


class QueueCancelRequest(BaseModel):
    principal: Principal


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.post("/{slug}/join")
def join(
    body: JoinRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    party = store.get_party(slug)
    assert party is not None
    x = body.x if body.x is not None else party.worldSize.width / 2
    y = body.y if body.y is not None else party.worldSize.height / 2
    style: str | None = None
    if resolved.kind == "agent":
        agent = store.get_agent(resolved.id)
        style = agent.style if agent is not None else "reactive"
    participant = Participant(
        id=resolved.id,
        kind=resolved.kind,
        username=resolved.username,
        color=resolved.color,
        x=float(x),
        y=float(y),
        joined_at=time.time(),
        style=style,
    )
    world.join(participant)
    return {
        "participant": {
            "id": participant.id,
            "kind": participant.kind,
            "username": participant.username,
            "color": participant.color,
            "style": participant.style,
            "x": participant.x,
            "y": participant.y,
            "zone": world.derive_zone(participant.x, participant.y),
        },
        "cursor": world.cursor,
    }


@router.post("/{slug}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave(
    body: LeaveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> Response:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.leave(resolved.id)
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{slug}/move")
def move(
    body: MoveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        return _do_move(world, resolved.id, _Move(kind="move", x=body.x, y=body.y))
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)


@router.post("/{slug}/chat")
def chat(
    body: ChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    # Extra validations only the single endpoint needs (target/reply checks).
    if body.to_id is not None and body.to_id not in world.participants:
        raise HTTPException(
            status_code=404,
            detail=envelope(RECIPIENT_UNKNOWN, message="to_id not in party"),
        )
    if body.reply_to is not None and not world.has_chat_at_seq(body.reply_to):
        raise HTTPException(
            status_code=404,
            detail=envelope(
                INVALID_REPLY_TO,
                message="reply_to does not reference a known chat event",
            ),
        )
    action = _Chat(
        kind="chat",
        text=body.text,
        scope=body.scope,
        to_id=body.to_id,
        reply_to=body.reply_to,
    )
    from app.action_dispatch import _ChatCooldownError
    try:
        result = _do_chat(world, resolved.id, action, slug=slug)
    except _ChatCooldownError as exc:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED,
                message=str(exc),
                retry_after_ms=exc.retry_after_ms,
                scope=exc.scope,
            ),
        )
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                INVALID_CHAT_TEXT,
                message=str(exc),
                allowed_chars_regex=CHAT_ALLOWED_CHARS_REGEX,
                max_chars=CHAT_MAX_LEN,
            ),
        )
    # /chat single endpoint returns {"event": ..., "cursor": ...}
    # _do_chat returns {"chat": ev.model_dump(), "cursor": ...}
    # Translate for backwards compat.
    return {"event": result["chat"], "cursor": result["cursor"]}


@router.get("/{slug}/participants/{participant_id}")
def get_participant(
    slug: str = Path(pattern=_SLUG_PATTERN),
    participant_id: str = Path(...),
    store: Store = Depends(_store_dep),
) -> dict:
    """Resolve a participant by id, bypassing proximity scoping.

    Returns only the same public fields already visible in the
    proximity-scoped snapshot whenever the requester sees the target.
    """
    world = _world(store, slug)
    p = world.participants.get(participant_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail=envelope(NOT_IN_PARTY),
        )
    return {
        "id": p.id,
        "username": p.username,
        "color": p.color,
        "kind": p.kind,
        "x": p.x,
        "y": p.y,
        "zone": world.derive_zone(p.x, p.y),
        "facing": getattr(p, "facing", None),
    }


def _room_view(party) -> dict:
    w = party.worldSize
    return {
        "slug": party.slug,
        "name": party.name,
        "worldSize": {"width": w.width, "height": w.height},
        "zones": [
            {
                "id": z.id,
                "label": z.label,
                "x": z.x,
                "y": z.y,
                "width": z.width,
                "height": z.height,
                "centerX": (z.x + z.width / 2.0) / 100.0 * w.width,
                "centerY": (z.y + z.height / 2.0) / 100.0 * w.height,
            }
            for z in party.zones
        ],
        "walls": [
            {"x": wl.x, "y": wl.y, "width": wl.width, "height": wl.height}
            for wl in party.room.walls
        ],
        "music": party.music.label,
        "modules": [
            {
                "id": m.id,
                "kind": m.kind,
                **(
                    {"x": m.x, "y": m.y, "w": m.w, "h": m.h}
                    if m.kind in ("stickynotes", "drawboard")
                    else {}
                ),
                **({"preset": m.preset} if m.kind == "lighting" else {}),
            }
            for m in party.modules
        ],
    }


@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
    exclude_self: bool = False,
    principal_id: str | None = None,
    principal_kind: str | None = None,
    viewer_id: str | None = None,
    viewer_kind: str | None = None,
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    party = store.get_party(slug)
    assert party is not None

    # Support both old (principal_id/kind) and new (viewer_id/kind) param names.
    eff_id = viewer_id if viewer_id is not None else principal_id
    eff_kind = viewer_kind if viewer_kind is not None else principal_kind

    requester_id: str | None = None
    if eff_id is not None and eff_kind is not None:
        # Only scope if the requester is actually in the party.
        # If the principal is unknown/not joined, fall back to unscoped so
        # the lobby UI still works.
        if eff_id in world.participants:
            requester_id = eff_id

    if since is None:
        if requester_id is None:
            snap = world.snapshot()
        else:
            snap = world.scoped_snapshot(requester_id)
        body = {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "music": snap["music"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
            "active_proposals": world.active_proposals(),
        }
        if eff_id is not None:
            body["welcome"] = world.latest_welcome_for(eff_id)
        else:
            body["welcome"] = None
        return body
    if requester_id is None:
        payload = world.observe_since(since, viewer_id=viewer_id or eff_id)
    else:
        payload = world.observe_since_scoped(since, requester_id)
    if exclude_self and principal_id:
        payload["events"] = [
            e for e in payload["events"]
            if e.get("actor_id") != principal_id
        ]
    return payload


# ---------------------------------------------------------------------------
# Batched /act endpoint
# ---------------------------------------------------------------------------


@router.post("/{slug}/act")
async def act(
    body: ActRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    """Run an ordered list of 1-5 actions sequentially in one request.

    Actions execute in order. If action N fails (validation, cooldown, etc.)
    actions N+1..end are still attempted; each result is independent. The
    response is ``{"results": [...]}`` with one entry per submitted action —
    either the optimistic shape from the equivalent single endpoint or
    ``{"error": {"error": "...", "message": "..."}}`` (spec #01 envelope).

    Worst-case latency: 5 × ``wait.ms`` = up to 10 seconds. Callers should
    set a client-side timeout >= 12s when using ``wait`` in the batch.
    """
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    ctx = DispatchContext(
        world=world,
        principal_id=resolved.id,
        principal_username=resolved.username,
        principal_kind=resolved.kind,
        slug=slug,
    )
    results = await _act_dispatch(ctx, body.actions)
    return {"results": results}


# ---------------------------------------------------------------------------
# Server-side action queue routes
# ---------------------------------------------------------------------------


@router.post("/{slug}/queue")
async def queue_actions(
    body: QueueRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
    queue: ActionQueueStore = Depends(_queue_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    ctx = DispatchContext(
        world=world,
        principal_id=resolved.id,
        principal_username=resolved.username,
        principal_kind=resolved.kind,
        slug=slug,
    )
    try:
        qid, when = queue.schedule(
            ctx=ctx,
            actions=body.actions,
            start_at=body.start_at,
            runner=_act_dispatch,
        )
    except QueueLimitError:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                "queue_limit",
                message="max 3 pending queues per principal",
            ),
        )
    return {
        "queue_id": qid,
        "scheduled_for": dt.datetime.fromtimestamp(
            when, tz=dt.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }


@router.get("/{slug}/queue")
def list_queues(
    slug: str = Path(pattern=_SLUG_PATTERN),
    agent_id: str = "",
    queue: ActionQueueStore = Depends(_queue_dep),
) -> dict:
    return {"queues": queue.list_for(agent_id, slug)}


@router.delete("/{slug}/queue/{queue_id}", status_code=204)
def cancel_queue(
    body: QueueCancelRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    queue_id: str = Path(...),
    store: Store = Depends(_store_dep),
    queue: ActionQueueStore = Depends(_queue_dep),
) -> Response:
    resolved = resolve_principal(store, body.principal)
    try:
        ok = queue.cancel(queue_id, resolved.id)
    except NotOwnerError:
        raise HTTPException(
            status_code=403,
            detail=envelope(
                "not_owner",
                message="queue belongs to another principal",
            ),
        )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=envelope("queue_not_found", message=queue_id),
        )
    return Response(status_code=204)
