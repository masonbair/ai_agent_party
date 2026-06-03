import pytest

from app.validation import (
    ALLOWED_COLORS,
    USERNAME_REGEX,
    UsernameValidationError,
    validate_username,
)


@pytest.mark.parametrize(
    "value",
    [
        "ab",            # min length
        "Alice42",       # mixed alnum
        "ZZZZZZZZZZZZZZZZZZZZ",  # 20 chars
        "bob-1",         # punctuation now allowed
        "foo.bar",
        "a_b-c",
        "<script>",      # printable ASCII; rendered inert, not executed
    ],
)
def test_username_regex_accepts_valid(value: str) -> None:
    assert USERNAME_REGEX.fullmatch(value) is not None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a",
        "a" * 21,
        "has space",       # spaces stay out (keeps @mention parsing intact)
        "bob; DROP TABLE",  # rejected via the space, not the punctuation
        "héllo",           # non-ASCII out of scope
        "ab🙂",            # emoji out of scope
    ],
)
def test_username_regex_rejects_invalid(value: str) -> None:
    assert USERNAME_REGEX.fullmatch(value) is None


def test_validate_username_returns_value_when_valid() -> None:
    assert validate_username("foo.bar") == "foo.bar"


def test_validate_username_normalizes_lookalikes() -> None:
    # Fullwidth "ｂｏｂ" folds to ASCII "bob" before the charset check.
    assert validate_username("ｂｏｂ") == "bob"


@pytest.mark.parametrize("value", ["has space", "", "a", "ab🙂", "héllo"])
def test_validate_username_rejects_invalid(value: str) -> None:
    with pytest.raises(UsernameValidationError):
        validate_username(value)


def test_validate_username_rejects_blocked_word(monkeypatch) -> None:
    import app.guardrails as guardrails

    monkeypatch.setattr(guardrails, "BLOCKLIST", frozenset(["badword"]))
    monkeypatch.setattr(
        guardrails, "BLOCKLIST_REGEX", guardrails._build_regex(frozenset(["badword"]))
    )
    with pytest.raises(UsernameValidationError):
        validate_username("badword")


def test_allowed_colors_has_twelve_distinct_swatches() -> None:
    assert len(ALLOWED_COLORS) == 12
    assert len(set(ALLOWED_COLORS)) == 12
    for c in ALLOWED_COLORS:
        assert c.startswith("#") and len(c) == 7
