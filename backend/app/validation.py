import re

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9]{2,20}$")

ALLOWED_COLORS: tuple[str, ...] = (
    "#ff6b9d",  # pink
    "#9c27b0",  # purple
    "#4dd0e1",  # teal
    "#ffd54f",  # amber
    "#81c784",  # green
    "#ff8a65",  # coral
    "#7986cb",  # indigo
    "#f06292",  # rose
    "#4db6ac",  # mint
    "#ba68c8",  # violet
    "#ffb74d",  # orange
    "#a1887f",  # taupe
)

CHAT_MAX_LEN = 65
CHAT_TEXT_REGEX = re.compile(r"^[A-Za-z0-9 .,!?'\-]+$")


class ChatValidationError(ValueError):
    pass


def validate_chat_text(text: str) -> str:
    trimmed = text.strip()
    if not trimmed:
        raise ChatValidationError("chat text must not be empty")
    if len(trimmed) > CHAT_MAX_LEN:
        raise ChatValidationError(f"chat text exceeds {CHAT_MAX_LEN} chars")
    if CHAT_TEXT_REGEX.fullmatch(trimmed) is None:
        raise ChatValidationError("chat text contains disallowed characters")
    return trimmed
