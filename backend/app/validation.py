import re

from app.guardrails import mask_blocked

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
# Allowed characters in chat text:
# letters, digits, spaces, the punctuation set .,!?'-, and @ for mentions.
# Owner is conservative on character expansion — do not add more without
# an explicit owner decision (see docs/features/feature-backlog.md §1).
CHAT_ALLOWED_CHARS_REGEX = r"^[A-Za-z0-9 .,!?'\-@]+$"
CHAT_TEXT_REGEX = re.compile(CHAT_ALLOWED_CHARS_REGEX)
RECENT_CHAT_LIMIT = 20


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
    cleaned, _ = mask_blocked(trimmed)
    return cleaned


REACTION_EMOJI_ALLOWLIST: tuple[str, ...] = (
    "❤️", "😂", "👀", "🎉", "👍", "👋",
    "🤔", "😮", "🔥", "✨", "😴", "🫶",
)

STICKY_TEXT_MAX = 140
STICKY_TEXT_REGEX = re.compile(r"^[A-Za-z0-9 .,!?'\-\n]+$")
STICKY_COLOR_ALLOWLIST: tuple[str, ...] = ("yellow", "pink", "blue", "green")

STROKE_MAX_POINTS = 200
STROKES_PER_BOARD_MAX = 500
STROKE_WIDTH_ALLOWLIST: tuple[str, ...] = ("thin", "med", "thick")

# Whiteboard markers need dark colors that the avatar swatch list does not
# carry. Strokes accept any avatar color plus these neutrals.
STROKE_COLOR_ALLOWLIST: tuple[str, ...] = ALLOWED_COLORS + (
    "#222222",  # marker black
    "#1a3a6e",  # dark blue
)

NOTES_PER_USER_MAX = 10
INTERACTION_MARGIN = 24.0
SLOT_OCCUPIED_RADIUS = 32.0
VOTE_TTL_SECONDS = 30.0
REACTION_LIFETIME_SECONDS = 1.0

# --- music module ---------------------------------------------------------

MUSIC_TRACK_ALLOWLIST: tuple[str, ...] = (
    "lofi-loop",
    "jazz-club",
    "synthwave",
    "ambient-1",
    "party-mix",
)

MUSIC_VOLUME_MIN = 0
MUSIC_VOLUME_MAX = 100

MUSIC_ACTIONS: tuple[str, ...] = ("play", "pause", "skip", "set_volume")


class MusicValidationError(ValueError):
    pass


def validate_music_track(track_id: str) -> str:
    if not isinstance(track_id, str) or not track_id:
        raise MusicValidationError("track_id is required")
    if track_id not in MUSIC_TRACK_ALLOWLIST:
        raise MusicValidationError(
            f"unknown track {track_id!r}; allowed={list(MUSIC_TRACK_ALLOWLIST)}"
        )
    return track_id


def validate_music_volume(volume: int) -> int:
    # bool is a subclass of int — reject explicitly so True/False can't slip in.
    if isinstance(volume, bool) or not isinstance(volume, int):
        raise MusicValidationError("volume must be an integer")
    if volume < MUSIC_VOLUME_MIN or volume > MUSIC_VOLUME_MAX:
        raise MusicValidationError(
            f"volume must be {MUSIC_VOLUME_MIN}..{MUSIC_VOLUME_MAX}"
        )
    return volume


def validate_music_action(action: str) -> str:
    if action not in MUSIC_ACTIONS:
        raise MusicValidationError(
            f"unknown action {action!r}; allowed={list(MUSIC_ACTIONS)}"
        )
    return action


class ReactionValidationError(ValueError):
    pass


class NoteValidationError(ValueError):
    pass


class StrokeValidationError(ValueError):
    pass


def validate_reaction_emoji(emoji: str) -> str:
    if emoji not in REACTION_EMOJI_ALLOWLIST:
        raise ReactionValidationError(f"emoji {emoji!r} not in allow-list")
    return emoji


def validate_note_text(text: str) -> str:
    trimmed = text.strip()
    if not trimmed:
        raise NoteValidationError("note text must not be empty")
    if len(trimmed) > STICKY_TEXT_MAX:
        raise NoteValidationError(f"note text exceeds {STICKY_TEXT_MAX} chars")
    if STICKY_TEXT_REGEX.fullmatch(trimmed) is None:
        raise NoteValidationError("note text contains disallowed characters")
    cleaned, _ = mask_blocked(trimmed)
    return cleaned


def validate_note_color(color: str) -> str:
    if color not in STICKY_COLOR_ALLOWLIST:
        raise NoteValidationError(f"color {color!r} not in allow-list")
    return color


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def validate_stroke(raw: dict, board_w: float, board_h: float) -> dict:
    if raw.get("color") not in STROKE_COLOR_ALLOWLIST:
        raise StrokeValidationError("stroke color not in allow-list")
    if raw.get("width") not in STROKE_WIDTH_ALLOWLIST:
        raise StrokeValidationError("stroke width not in allow-list")
    pts = raw.get("points") or []
    if not pts:
        raise StrokeValidationError("stroke must have at least one point")
    if len(pts) > STROKE_MAX_POINTS:
        raise StrokeValidationError(f"stroke exceeds {STROKE_MAX_POINTS} points")
    clamped = [
        {
            "x": _clamp(float(p["x"]), 0.0, board_w),
            "y": _clamp(float(p["y"]), 0.0, board_h),
        }
        for p in pts
    ]
    return {"color": raw["color"], "width": raw["width"], "points": clamped}


ALLOWED_GESTURES: tuple[str, ...] = (
    "wave", "point", "dance", "jump", "sit", "shiver", "bow", "nod",
)

ALLOWED_COSMETIC_EFFECTS: tuple[str, ...] = (
    "confetti", "sparkle", "lights_flash", "ping",
)

GESTURE_TTL_SECONDS = 2.0
COSMETIC_TTL_SECONDS = 3.0


class GestureValidationError(ValueError):
    pass


class CosmeticValidationError(ValueError):
    pass


def validate_gesture(gesture: str) -> str:
    if gesture not in ALLOWED_GESTURES:
        raise GestureValidationError(f"gesture {gesture!r} not in allow-list")
    return gesture


def validate_cosmetic_effect(effect: str) -> str:
    if effect not in ALLOWED_COSMETIC_EFFECTS:
        raise CosmeticValidationError(f"effect {effect!r} not in allow-list")
    return effect
