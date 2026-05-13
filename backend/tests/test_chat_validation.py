import pytest

from app.validation import (
    CHAT_MAX_LEN,
    CHAT_TEXT_REGEX,
    ChatValidationError,
    validate_chat_text,
)


def test_validate_chat_text_returns_trimmed_text() -> None:
    assert validate_chat_text("  hello world  ") == "hello world"


def test_validate_chat_text_allows_basic_punctuation() -> None:
    text = "Hi, it's me! How are you? I'm here - really."
    assert validate_chat_text(text) == text


def test_validate_chat_text_rejects_empty() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("   ")


def test_validate_chat_text_rejects_disallowed_characters() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("hello <script>")


def test_validate_chat_text_rejects_too_long() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("a" * (CHAT_MAX_LEN + 1))


def test_chat_text_regex_matches_expected_alphabet() -> None:
    assert CHAT_TEXT_REGEX.fullmatch("Hi there.") is not None
    assert CHAT_TEXT_REGEX.fullmatch("nope$") is None
