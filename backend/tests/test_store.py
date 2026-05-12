import pytest

from app.store import Store


def test_create_session_returns_user_with_uuid() -> None:
    store = Store()
    user = store.create_session(username="Alice", color="#ff6b9d")
    assert user.username == "Alice"
    assert user.color == "#ff6b9d"
    assert len(user.session_id) >= 8


def test_get_session_returns_same_user() -> None:
    store = Store()
    created = store.create_session(username="Alice", color="#ff6b9d")
    fetched = store.get_session(created.session_id)
    assert fetched is not None
    assert fetched.session_id == created.session_id


def test_get_session_returns_none_for_unknown_id() -> None:
    store = Store()
    assert store.get_session("does-not-exist") is None


def test_delete_session_removes_user() -> None:
    store = Store()
    created = store.create_session(username="Alice", color="#ff6b9d")
    assert store.delete_session(created.session_id) is True
    assert store.get_session(created.session_id) is None


def test_delete_session_returns_false_for_unknown_id() -> None:
    store = Store()
    assert store.delete_session("does-not-exist") is False


def test_list_parties_returns_seeded_registry() -> None:
    store = Store()
    parties = store.list_parties()
    slugs = {p.slug for p in parties}
    assert "cream-terrazzo" in slugs


def test_get_party_returns_config_or_none() -> None:
    store = Store()
    assert store.get_party("cream-terrazzo") is not None
    assert store.get_party("does-not-exist") is None
