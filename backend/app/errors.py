"""Canonical error codes returned to API clients.

Every error response uses the envelope shape:

    {"detail": {"error": "<code>", "message": "<human>", ...extras}}

Use `http_envelope` to build the FastAPI HTTPException — never construct
HTTPException with a string `detail` directly.
"""
from fastapi import HTTPException


# Codes — one constant per error.
PRINCIPAL_UNKNOWN = "principal_unknown"
NOT_IN_PARTY = "not_in_party"
INVALID_COLOR = "invalid_color"
INVALID_CHAT_TEXT = "invalid_chat_text"
VALIDATION_ERROR = "validation_error"
SELF_DM = "self_dm"
RECIPIENT_UNKNOWN = "recipient_unknown"
DM_FORBIDDEN = "dm_forbidden"
PARTY_NOT_FOUND = "party_not_found"
SESSION_NOT_FOUND = "session_not_found"
AGENT_NOT_FOUND = "agent_not_found"
INVALID_LIMIT = "invalid_limit"
INVALID_BEFORE_ID = "invalid_before_id"
NOT_FOUND = "not_found"  # generic fall-back
METHOD_NOT_ALLOWED = "method_not_allowed"
UNAUTHORIZED = "unauthorized"
FORBIDDEN = "forbidden"
HTTP_ERROR = "http_error"
NOT_IN_RANGE = "not_in_range"
LIMIT_REACHED = "limit_reached"
NOT_AUTHOR = "not_author"
INVALID_PRESET = "invalid_preset"
INVALID_STROKE = "invalid_stroke"
INVALID_NOTE = "invalid_note"


# Default human-readable messages keyed by code. Routes may override.
_DEFAULT_MESSAGES: dict[str, str] = {
    PRINCIPAL_UNKNOWN: "The provided principal could not be resolved.",
    NOT_IN_PARTY: "You must join the party before performing this action.",
    INVALID_COLOR: "The provided color is not in the allow-list.",
    INVALID_CHAT_TEXT: "Chat text failed validation.",
    VALIDATION_ERROR: "Request body failed validation.",
    SELF_DM: "You cannot send a direct message to yourself.",
    RECIPIENT_UNKNOWN: "The DM recipient could not be resolved.",
    DM_FORBIDDEN: "You are not a participant in this thread.",
    PARTY_NOT_FOUND: "No party exists with that slug.",
    SESSION_NOT_FOUND: "No session exists with that id.",
    AGENT_NOT_FOUND: "No agent exists with that id.",
    INVALID_LIMIT: "The `limit` query parameter is out of range.",
    INVALID_BEFORE_ID: "The `before_id` query parameter is invalid.",
    NOT_FOUND: "The requested resource was not found.",
    METHOD_NOT_ALLOWED: "HTTP method not allowed for this route.",
    UNAUTHORIZED: "Authentication required.",
    FORBIDDEN: "Access denied.",
    HTTP_ERROR: "HTTP error.",
    NOT_IN_RANGE: "You are not within the module's interaction zone.",
    LIMIT_REACHED: "You have reached the per-user note limit.",
    NOT_AUTHOR: "Only the note's author can modify it.",
    INVALID_PRESET: "The lighting preset is not valid.",
    INVALID_STROKE: "The stroke failed validation.",
    INVALID_NOTE: "The note failed validation.",
}


def envelope(error: str, *, message: str | None = None, **extras: object) -> dict[str, object]:
    """Build a structured detail body: ``{"error": code, "message": ..., ...extras}``.

    `message` falls back to a sensible default when omitted.
    """
    msg = message if message is not None else _DEFAULT_MESSAGES.get(error, error)
    return {"error": error, "message": msg, **extras}


def not_in_range_envelope(
    module_id: str,
    interaction_rect: dict[str, float],
    actor_position: dict[str, float],
) -> dict[str, object]:
    """Structured 409 body for module endpoints that require the caller
    to stand inside the module's interactionRect.

    Includes the rect and the caller's current position so an agent can
    auto-walk to a valid spot on the next request.
    """
    return envelope(
        NOT_IN_RANGE,
        module_id=module_id,
        interactionRect=interaction_rect,
        actor_position=actor_position,
    )


def http_envelope(
    status_code: int,
    error: str,
    *,
    message: str | None = None,
    **extras: object,
) -> HTTPException:
    """Build a FastAPI ``HTTPException`` whose ``detail`` is the standard envelope."""
    return HTTPException(
        status_code=status_code,
        detail=envelope(error, message=message, **extras),
    )
