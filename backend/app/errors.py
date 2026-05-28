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
INVALID_REPLY_TO = "invalid_reply_to"
RATE_LIMITED = "rate_limited"
CANNOT_FOLLOW_SELF = "cannot_follow_self"
TARGET_NOT_IN_PARTY = "target_not_in_party"
NOT_FOLLOWING = "not_following"
PROPOSAL_NOT_FOUND = "proposal_not_found"
PROPOSAL_EXPIRED = "proposal_expired"
INVALID_VOTE = "invalid_vote"
INVALID_PROPOSAL_TEXT = "invalid_proposal_text"
INVALID_EXPIRY = "invalid_expiry"


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
    INVALID_REPLY_TO: "reply_to does not reference a known chat event.",
    RATE_LIMITED: "Chat rate limit exceeded.",
    CANNOT_FOLLOW_SELF: "You cannot follow yourself.",
    TARGET_NOT_IN_PARTY: "The follow target is not in this party.",
    NOT_FOLLOWING: "You are not following anyone.",
    PROPOSAL_NOT_FOUND: "No proposal exists with that id.",
    PROPOSAL_EXPIRED: "This proposal has already expired.",
    INVALID_VOTE: "Vote must be 'yes', 'no', or 'abstain'.",
    INVALID_PROPOSAL_TEXT: "Proposal text failed validation.",
    INVALID_EXPIRY: "expires_in_sec must be between 1 and 60 inclusive.",
}


def envelope(error: str, *, message: str | None = None, **extras: object) -> dict[str, object]:
    """Build a structured detail body: ``{"error": code, "message": ..., ...extras}``.

    `message` falls back to a sensible default when omitted.
    """
    msg = message if message is not None else _DEFAULT_MESSAGES.get(error, error)
    return {"error": error, "message": msg, **extras}


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
