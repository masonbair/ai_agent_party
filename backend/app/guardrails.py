"""Content guardrails — blocklist-driven word masking."""

import re
from pathlib import Path

_BLOCKLIST_PATH = Path(__file__).parent / "blocklist.txt"


def _load_blocklist(path: Path) -> frozenset[str]:
    """Return lowercase, trimmed entries; skip blanks and '#' comment lines."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return frozenset()
    words = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        words.add(stripped.lower())
    return frozenset(words)


def _build_regex(words: frozenset[str]) -> re.Pattern | None:
    """Build a whole-word IGNORECASE regex from *words*, longest-first."""
    if not words:
        return None
    sorted_words = sorted(words, key=len, reverse=True)
    pattern = r"\b(" + "|".join(re.escape(w) for w in sorted_words) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


BLOCKLIST: frozenset[str] = _load_blocklist(_BLOCKLIST_PATH)
BLOCKLIST_REGEX: re.Pattern | None = _build_regex(BLOCKLIST)


def mask_blocked(text: str) -> tuple[str, bool]:
    """Replace each whole-word match with '*' * len(match). Returns (masked, was_masked)."""
    if BLOCKLIST_REGEX is None:
        return text, False
    was_masked = False

    def _replace(m: re.Match) -> str:
        nonlocal was_masked
        was_masked = True
        return "*" * len(m.group(0))

    masked = BLOCKLIST_REGEX.sub(_replace, text)
    return masked, was_masked


def contains_blocked(text: str) -> bool:
    """True if *text* contains any blocked word as a whole word."""
    if BLOCKLIST_REGEX is None:
        return False
    return BLOCKLIST_REGEX.search(text) is not None
