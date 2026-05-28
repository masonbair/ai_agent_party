"""Unit tests for action_dispatch helpers (no HTTP layer)."""
import pytest
from fastapi.testclient import TestClient

from app.action_dispatch import (
    _Chat,
    _Gesture,
    _Move,
    _React,
    _do_chat,
    _do_gesture,
    _do_move,
    _do_react,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world_with_human(client: TestClient) -> tuple:
    """Register a human session, join the party, return (world, principal dict)."""
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": principal},
    )
    # Grab world from test store.
    from app.main import app, get_store
    store = app.dependency_overrides.get(get_store)
    assert store is not None
    the_store = store()
    world = the_store.get_or_create_world("cream-terrazzo")
    return world, user["session_id"]


# ---------------------------------------------------------------------------
# _do_move tests
# ---------------------------------------------------------------------------


def test_do_move_returns_optimistic_shape(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    result = _do_move(world, pid, _Move(kind="move", x=100, y=120))
    assert result["x"] == 100
    assert result["y"] == 120
    assert "zone" in result
    assert "cursor" in result


def test_do_move_raises_when_not_in_party(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    world.leave(pid)
    from app.world import ParticipantNotInPartyError
    with pytest.raises(ParticipantNotInPartyError):
        _do_move(world, pid, _Move(kind="move", x=10, y=10))


# ---------------------------------------------------------------------------
# _do_chat tests
# ---------------------------------------------------------------------------


def test_do_chat_returns_optimistic_shape(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    result = _do_chat(world, pid, _Chat(kind="chat", text="hello"), slug="cream-terrazzo")
    assert "chat" in result
    assert "cursor" in result


def test_do_chat_raises_on_invalid_text(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    from app.validation import ChatValidationError
    with pytest.raises(ChatValidationError):
        _do_chat(
            world, pid, _Chat(kind="chat", text="<<bad>>"), slug="cream-terrazzo"
        )


def test_do_chat_raises_when_not_in_party(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    world.leave(pid)
    from app.world import ParticipantNotInPartyError
    with pytest.raises(ParticipantNotInPartyError):
        _do_chat(world, pid, _Chat(kind="chat", text="hello"), slug="cream-terrazzo")


# ---------------------------------------------------------------------------
# _do_react tests
# ---------------------------------------------------------------------------


def test_do_react_returns_optimistic_shape(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    result = _do_react(world, pid, _React(kind="react", emoji="👍"))
    assert "emoji" in result
    assert "expires_at" in result
    assert "cursor" in result


def test_do_react_raises_on_invalid_emoji(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    from app.validation import ReactionValidationError
    with pytest.raises(ReactionValidationError):
        _do_react(world, pid, _React(kind="react", emoji="🚀"))


def test_do_react_raises_when_not_in_party(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    world.leave(pid)
    from app.world import ParticipantNotInPartyError
    with pytest.raises(ParticipantNotInPartyError):
        _do_react(world, pid, _React(kind="react", emoji="👍"))


# ---------------------------------------------------------------------------
# _do_gesture tests
# ---------------------------------------------------------------------------


def test_do_gesture_returns_optimistic_shape(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    result = _do_gesture(world, pid, _Gesture(kind="gesture", gesture="wave"))
    assert "gesture" in result
    assert "expires_at" in result
    assert "cursor" in result


def test_do_gesture_raises_on_invalid_gesture(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    from app.validation import GestureValidationError
    with pytest.raises(GestureValidationError):
        _do_gesture(world, pid, _Gesture(kind="gesture", gesture="fly"))


def test_do_gesture_raises_when_not_in_party(client: TestClient) -> None:
    world, pid = _make_world_with_human(client)
    world.leave(pid)
    from app.world import ParticipantNotInPartyError
    with pytest.raises(ParticipantNotInPartyError):
        _do_gesture(world, pid, _Gesture(kind="gesture", gesture="wave"))
