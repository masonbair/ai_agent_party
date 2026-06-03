import pytest

from app.validation import (
    INTERACTION_MARGIN,
    NOTES_PER_USER_MAX,
    NoteValidationError,
    REACTION_EMOJI_ALLOWLIST,
    REACTION_LIFETIME_SECONDS,
    ReactionValidationError,
    SLOT_OCCUPIED_RADIUS,
    STICKY_COLOR_ALLOWLIST,
    STICKY_TEXT_MAX,
    STROKE_MAX_POINTS,
    STROKE_WIDTH_ALLOWLIST,
    STROKES_PER_BOARD_MAX,
    StrokeValidationError,
    VOTE_TTL_SECONDS,
    validate_note_color,
    validate_note_text,
    validate_reaction_emoji,
    validate_stroke,
)


def test_reaction_allowlist_size_and_validate() -> None:
    assert len(REACTION_EMOJI_ALLOWLIST) == 12
    assert validate_reaction_emoji("❤️") == "❤️"
    with pytest.raises(ReactionValidationError):
        validate_reaction_emoji("💩")


def test_note_text_validation() -> None:
    assert validate_note_text("  hello  ") == "hello"
    with pytest.raises(NoteValidationError):
        validate_note_text("")
    with pytest.raises(NoteValidationError):
        validate_note_text("x" * (STICKY_TEXT_MAX + 1))
    with pytest.raises(NoteValidationError):
        validate_note_text("nope 🙂")


def test_note_color_validation() -> None:
    assert validate_note_color("yellow") == "yellow"
    with pytest.raises(NoteValidationError):
        validate_note_color("magenta")


def test_stroke_validation_clamps_and_rejects() -> None:
    pts = [{"x": 0, "y": 0}, {"x": 50, "y": 50}]
    s = validate_stroke(
        {"color": "#ff6b9d", "width": "med", "points": pts},
        board_w=100,
        board_h=100,
    )
    assert s["color"] == "#ff6b9d"
    assert s["width"] == "med"
    assert len(s["points"]) == 2

    s2 = validate_stroke(
        {
            "color": "#ff6b9d",
            "width": "thin",
            "points": [{"x": -5, "y": 200}, {"x": 150, "y": -10}],
        },
        board_w=100,
        board_h=100,
    )
    assert s2["points"] == [
        {"x": 0.0, "y": 100.0},
        {"x": 100.0, "y": 0.0},
    ]

    with pytest.raises(StrokeValidationError):
        validate_stroke(
            {"color": "rebeccapurple", "width": "med", "points": pts}, 100, 100
        )
    with pytest.raises(StrokeValidationError):
        validate_stroke(
            {"color": "#ff6b9d", "width": "huge", "points": pts}, 100, 100
        )
    big = [{"x": 0, "y": 0}] * (STROKE_MAX_POINTS + 1)
    with pytest.raises(StrokeValidationError):
        validate_stroke(
            {"color": "#ff6b9d", "width": "med", "points": big}, 100, 100
        )
    with pytest.raises(StrokeValidationError):
        validate_stroke(
            {"color": "#ff6b9d", "width": "med", "points": []}, 100, 100
        )


def test_module_constants_have_sane_values() -> None:
    assert INTERACTION_MARGIN > 0
    assert SLOT_OCCUPIED_RADIUS > 0
    assert VOTE_TTL_SECONDS > 0
    assert REACTION_LIFETIME_SECONDS > 0
    assert NOTES_PER_USER_MAX > 0
    assert STROKES_PER_BOARD_MAX > 0
    assert "thin" in STROKE_WIDTH_ALLOWLIST
    assert "yellow" in STICKY_COLOR_ALLOWLIST
