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


def _agent(client) -> dict:
    return client.post(
        "/api/agents", json={"username": "TestBot", "color": "#ff6b9d"}
    ).json()


def test_chat_allows_at_sign(client):
    agent = _agent(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]}},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": "hi @everyone"},
    )
    assert r.status_code == 200


def test_chat_422_body_includes_rules(client):
    agent = _agent(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]}},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": "no curly braces {bad}"},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["error"] == "invalid_chat_text"
    assert "allowed_chars_regex" in body
    assert body["max_chars"] == 65
    # The regex string must contain the @ now.
    assert "@" in body["allowed_chars_regex"]
