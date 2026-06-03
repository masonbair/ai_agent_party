import pytest

from app.validation import (
    CHAT_ALLOWED_CHARS_REGEX,
    CHAT_MAX_LEN,
    CHAT_TEXT_REGEX,
    ChatValidationError,
    validate_chat_text,
)
from tests.conftest import join_party as _jp
from tests.conftest import register_agent as _ra


def test_validate_chat_text_returns_trimmed_text() -> None:
    assert validate_chat_text("  hello world  ") == "hello world"


def test_validate_chat_text_allows_basic_punctuation() -> None:
    text = "Hi, it's me! How are you? I'm here - really."
    assert validate_chat_text(text) == text


def test_validate_chat_text_allows_expanded_punctuation() -> None:
    # The whole printable-ASCII punctuation set is now permitted, stored as-is.
    text = "cost is $5 (cheap!) @bob: a/b; c#d ~ e* [x] {y} \"q\""
    assert validate_chat_text(text) == text


def test_validate_chat_text_keeps_injection_strings_verbatim() -> None:
    # Safety lives in parameterized SQL + React escaping, not the charset.
    for payload in ("<script>alert(1)</script>", "'; DROP TABLE users;--"):
        assert validate_chat_text(payload) == payload


def test_validate_chat_text_rejects_empty() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("   ")


def test_validate_chat_text_rejects_non_ascii() -> None:
    # Emoji and non-Latin scripts remain out of scope.
    with pytest.raises(ChatValidationError):
        validate_chat_text("hello 🙂")


def test_validate_chat_text_rejects_too_long() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("a" * (CHAT_MAX_LEN + 1))


def test_chat_text_regex_matches_expected_alphabet() -> None:
    assert CHAT_TEXT_REGEX.fullmatch("Hi there.") is not None
    assert CHAT_TEXT_REGEX.fullmatch("nope$ {ok} @you") is not None
    assert CHAT_TEXT_REGEX.fullmatch("nope🙂") is None


def test_chat_allows_at_sign(client) -> None:
    agent = _ra(client)
    _jp(client, agent, "cream-terrazzo")
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": "hi @everyone"},
    )
    assert r.status_code == 200


def test_chat_422_body_includes_rules(client) -> None:
    agent = _ra(client)
    _jp(client, agent, "cream-terrazzo")
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": "emoji not allowed 🙂"},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["error"] == "invalid_chat_text"
    assert "allowed_chars_regex" in body
    assert body["max_chars"] == 65
    # The advertised regex accepts the expanded punctuation set.
    import re
    assert re.fullmatch(body["allowed_chars_regex"], "@bob: (hi) #1") is not None
