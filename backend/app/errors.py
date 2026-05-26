"""Canonical error codes returned to API clients.

Every 422/401/409 response uses the envelope shape
`{"detail": {"error": "<code>", ...}}` (for codes with extra context)
or `{"detail": "<code>"}` for plain string codes. Keep this file as the
single source of truth so agent guides, tests, and route handlers stay
in lockstep.
"""

PRINCIPAL_UNKNOWN = "principal_unknown"
NOT_IN_PARTY = "not_in_party"
INVALID_COLOR = "invalid_color"
INVALID_CHAT_TEXT = "invalid_chat_text"
VALIDATION_ERROR = "validation_error"
SELF_DM = "self_dm"
RECIPIENT_UNKNOWN = "recipient_unknown"
DM_FORBIDDEN = "dm_forbidden"


def envelope(error: str, **extras: object) -> dict[str, object]:
    """Build a structured 422-style detail body: `{"error": code, ...extras}`."""
    return {"error": error, **extras}
