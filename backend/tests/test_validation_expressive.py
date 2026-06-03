import pytest

from app.validation import (
    ALLOWED_COSMETIC_EFFECTS,
    ALLOWED_GESTURES,
    COSMETIC_TTL_SECONDS,
    CosmeticValidationError,
    GESTURE_TTL_SECONDS,
    GestureValidationError,
    validate_cosmetic_effect,
    validate_gesture,
)


def test_allowed_gestures_exact_set():
    assert ALLOWED_GESTURES == (
        "wave", "point", "dance", "jump", "sit", "shiver", "bow", "nod",
    )


def test_allowed_cosmetic_effects_exact_set():
    assert ALLOWED_COSMETIC_EFFECTS == (
        "confetti", "sparkle", "lights_flash", "ping",
    )


def test_gesture_ttl_default_two_seconds():
    assert GESTURE_TTL_SECONDS == 2.0


def test_cosmetic_ttl_default_three_seconds():
    assert COSMETIC_TTL_SECONDS == 3.0


def test_validate_gesture_accepts_each():
    for g in ALLOWED_GESTURES:
        assert validate_gesture(g) == g


def test_validate_gesture_rejects_unknown():
    with pytest.raises(GestureValidationError):
        validate_gesture("twerk")


def test_validate_gesture_rejects_empty():
    with pytest.raises(GestureValidationError):
        validate_gesture("")


def test_validate_cosmetic_accepts_each():
    for e in ALLOWED_COSMETIC_EFFECTS:
        assert validate_cosmetic_effect(e) == e


def test_validate_cosmetic_rejects_unknown():
    with pytest.raises(CosmeticValidationError):
        validate_cosmetic_effect("rain")
