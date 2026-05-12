import pytest

from app.validation import ALLOWED_COLORS, USERNAME_REGEX


@pytest.mark.parametrize(
    "value",
    ["ab", "Alice42", "ZZZZZZZZZZZZZZZZZZZZ"],  # 2, mixed, 20 chars
)
def test_username_regex_accepts_valid(value: str) -> None:
    assert USERNAME_REGEX.fullmatch(value) is not None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a",
        "a" * 21,
        "has space",
        "bob; DROP TABLE",
        "<script>",
        "héllo",
        "bob-1",
    ],
)
def test_username_regex_rejects_invalid(value: str) -> None:
    assert USERNAME_REGEX.fullmatch(value) is None


def test_allowed_colors_has_twelve_distinct_swatches() -> None:
    assert len(ALLOWED_COLORS) == 12
    assert len(set(ALLOWED_COLORS)) == 12
    for c in ALLOWED_COLORS:
        assert c.startswith("#") and len(c) == 7
