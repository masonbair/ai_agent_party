"""Action dispatch helpers for /act batched endpoint.

Extracts the core logic of each single-purpose action route into a
standalone helper function.  Both single endpoints and /act call
these helpers so validation, mutation, and cooldown logic stays in one
place.
"""
from __future__ import annotations

import asyncio
from typing import Literal, Union

from pydantic import BaseModel, Field

from app.errors import (
    INVALID_CHAT_TEXT,
    NOT_IN_PARTY,
    RATE_LIMITED,
    RECIPIENT_UNKNOWN,
    envelope,
)
from app.rate_limit import chat_limiter
from app.validation import (
    CHAT_ALLOWED_CHARS_REGEX,
    CHAT_MAX_LEN,
    ChatValidationError,
    ReactionValidationError,
)
from app.world import ParticipantNotInPartyError, PartyWorld


# ---------------------------------------------------------------------------
# Action models (discriminated union by `kind`)
# ---------------------------------------------------------------------------


class _Move(BaseModel):
    kind: Literal["move"]
    x: float
    y: float


class _Chat(BaseModel):
    kind: Literal["chat"]
    text: str
    scope: Literal["proximity", "room"] = "proximity"
    to_id: str | None = None
    reply_to: int | None = None


class _React(BaseModel):
    kind: Literal["react"]
    emoji: str


class _Gesture(BaseModel):
    kind: Literal["gesture"]
    gesture: str


class _Wait(BaseModel):
    kind: Literal["wait"]
    ms: int = Field(gt=0, le=2000)


Action = Union[_Move, _Chat, _React, _Gesture, _Wait]


# ---------------------------------------------------------------------------
# Dispatch context
# ---------------------------------------------------------------------------


class DispatchContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    world: PartyWorld
    principal_id: str
    principal_username: str
    principal_kind: str
    slug: str


# ---------------------------------------------------------------------------
# Per-action helpers
# ---------------------------------------------------------------------------


def _do_move(world: PartyWorld, principal_id: str, action: _Move) -> dict:
    """Move participant and return the optimistic payload.

    Includes the full ``event`` dict for backwards compatibility with spec #09.
    """
    ev = world.move(principal_id, action.x, action.y)  # raises ParticipantNotInPartyError
    return {
        "event": ev.model_dump(),
        "x": ev.x,
        "y": ev.y,
        "zone": world.derive_zone(ev.x, ev.y),
        "cursor": world.cursor,
    }


def _do_chat(
    world: PartyWorld, principal_id: str, action: _Chat, slug: str = ""
) -> dict:
    """Send chat and return the optimistic payload.

    Respects the same rate-limit bucket as the /chat single endpoint.
    Raises ChatCooldownError (encoded as an Exception) when the bucket is
    exhausted; raises ChatValidationError on bad text.
    """
    from app.world import PartyWorld  # noqa: F811 — already imported, safety reimport

    # Cooldown check via shared limiter.
    ok, retry_after_ms = chat_limiter().try_consume(slug, principal_id, action.scope)
    if not ok:
        raise _ChatCooldownError(
            f"chat cooldown: try again in {retry_after_ms} ms",
            retry_after_ms=retry_after_ms,
            scope=action.scope,
        )

    ev = world.chat(
        principal_id,
        action.text,
        to_id=action.to_id,
        reply_to=action.reply_to,
        scope=action.scope,
    )
    return {"chat": ev.model_dump(), "cursor": world.cursor}


def _do_react(world: PartyWorld, principal_id: str, action: _React) -> dict:
    """React with emoji and return the optimistic payload."""
    ev = world.react(principal_id, action.emoji)
    return {
        "emoji": ev.emoji,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }


def _do_gesture(world: PartyWorld, principal_id: str, action: _Gesture) -> dict:
    """Perform a gesture and return the optimistic payload."""
    ev = world.gesture(principal_id, action.gesture)
    return {
        "gesture": ev.gesture,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }


# ---------------------------------------------------------------------------
# Batch dispatcher
# ---------------------------------------------------------------------------


async def _act_dispatch(
    ctx: DispatchContext, actions: list[Action]
) -> list[dict]:
    """Run actions sequentially. Continue on error; collect per-action results.

    Each result is either the optimistic payload from the corresponding
    _do_* helper OR ``{"error": {"error": "<code>", "message": "..."}}``
    using the spec #01 envelope shape.
    """
    results: list[dict] = []
    for action in actions:
        try:
            if isinstance(action, _Move):
                results.append(_do_move(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _Chat):
                results.append(
                    _do_chat(ctx.world, ctx.principal_id, action, slug=ctx.slug)
                )
            elif isinstance(action, _React):
                results.append(_do_react(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _Gesture):
                results.append(_do_gesture(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _Wait):
                await asyncio.sleep(action.ms / 1000.0)
                results.append({"waited_ms": action.ms})
            else:  # pragma: no cover - exhaustive union
                results.append(
                    {"error": envelope("unknown_action_kind", message=str(action))}
                )
        except ParticipantNotInPartyError:
            results.append(
                {"error": envelope(NOT_IN_PARTY, message="not in party")}
            )
        except ChatValidationError as exc:
            results.append(
                {"error": envelope(INVALID_CHAT_TEXT, message=str(exc))}
            )
        except _ChatCooldownError as exc:
            results.append(
                {
                    "error": envelope(
                        "chat_cooldown",
                        message=str(exc),
                        retry_after_ms=exc.retry_after_ms,
                        scope=exc.scope,
                    )
                }
            )
        except ReactionValidationError as exc:
            results.append(
                {"error": envelope("invalid_reaction", message=str(exc))}
            )
        except Exception as exc:  # gesture/cosmetic validation + unknown
            results.append(
                {"error": envelope("action_failed", message=str(exc))}
            )
    return results


# ---------------------------------------------------------------------------
# Internal exceptions
# ---------------------------------------------------------------------------


class _ChatCooldownError(Exception):
    def __init__(self, message: str, *, retry_after_ms: int, scope: str) -> None:
        super().__init__(message)
        self.retry_after_ms = retry_after_ms
        self.scope = scope
