"""Tests for `app.dm.send` — proximity gate, validation, fanout."""

from __future__ import annotations

import pytest

from app.dm import DmError, principal_key, send, thread_key
from app.dm_store import DmStore, query_thread_history
from app.events import Participant
from app.inbox import InboxHub
from app.routes.principal import Principal, ResolvedPrincipal
from app.store import Store
from app.validation import ChatValidationError


def _join(store: Store, slug: str, ident: str, kind: str, username: str) -> None:
    world = store.get_or_create_world(slug)
    assert world is not None
    world.join(
        Participant(
            id=ident,
            kind=kind,
            username=username,
            color="#ff6b9d",
            x=100.0,
            y=100.0,
            joined_at=0.0,
        )
    )


def _seed(store: Store) -> tuple[ResolvedPrincipal, Principal]:
    alice = store.create_session(username="Alice", color="#ff6b9d")
    bob = store.create_session(username="Bob", color="#9c27b0")
    sender = ResolvedPrincipal(
        id=alice.session_id, kind="human", username="Alice", color="#ff6b9d"
    )
    recipient = Principal(kind="human", id=bob.session_id)
    return sender, recipient


def test_thread_key_is_sorted_and_pipe_joined() -> None:
    a = "human:zzz"
    b = "agent:aaa"
    assert thread_key(a, b) == "agent:aaa|human:zzz"
    assert thread_key(b, a) == "agent:aaa|human:zzz"


def test_principal_key_lowercases_kind() -> None:
    assert principal_key({"kind": "HUMAN", "id": "x"}) == "human:x"


def test_send_happy_path_persists_and_publishes() -> None:
    store = Store()
    sender, recipient = _seed(store)
    _join(store, "cream-terrazzo", sender.id, "human", "Alice")
    _join(store, "cream-terrazzo", recipient.id, "human", "Bob")
    hub = store.inbox_hub
    published: list[tuple[str, dict]] = []
    hub.publish = lambda key, frame: published.append((key, frame))  # type: ignore[assignment]

    result = send(
        store=store,
        dm_store=store.dm_store,
        inbox_hub=hub,
        sender=sender,
        recipient=recipient,
        text="hello there",
    )
    assert result["thread_key"] == thread_key(
        principal_key(sender), principal_key(recipient)
    )
    rows = query_thread_history(store.dm_store, thread_key=result["thread_key"])
    assert len(rows) == 1
    assert rows[0]["text"] == "hello there"
    assert rows[0]["sender_name"] == "Alice"
    # Both inboxes notified
    keys_notified = {p[0] for p in published}
    assert keys_notified == {principal_key(sender), principal_key(recipient)}
    for _, frame in published:
        assert frame["type"] == "dm"
        assert frame["message"]["text"] == "hello there"


def test_send_self_dm_rejected() -> None:
    store = Store()
    sender, _ = _seed(store)
    self_recipient = Principal(kind="human", id=sender.id)
    with pytest.raises(DmError) as exc:
        send(
            store=store,
            dm_store=store.dm_store,
            inbox_hub=store.inbox_hub,
            sender=sender,
            recipient=self_recipient,
            text="hi me",
        )
    assert exc.value.code == "self_dm"
    assert exc.value.status == 400


def test_send_unknown_recipient_rejected() -> None:
    store = Store()
    sender, _ = _seed(store)
    bogus = Principal(kind="agent", id="not-a-real-agent")
    with pytest.raises(DmError) as exc:
        send(
            store=store,
            dm_store=store.dm_store,
            inbox_hub=store.inbox_hub,
            sender=sender,
            recipient=bogus,
            text="hi",
        )
    assert exc.value.code == "recipient_unknown"
    assert exc.value.status == 404


def test_send_succeeds_when_neither_participant_in_any_party() -> None:
    """DMs are cross-party: registered principals can message regardless of presence."""
    store = Store()
    sender, recipient = _seed(store)
    hub = store.inbox_hub
    published: list[tuple[str, dict]] = []
    hub.publish = lambda key, frame: published.append((key, frame))  # type: ignore[assignment]

    result = send(
        store=store,
        dm_store=store.dm_store,
        inbox_hub=hub,
        sender=sender,
        recipient=recipient,
        text="hi",
    )
    assert result["thread_key"] == thread_key(
        principal_key(sender), principal_key(recipient)
    )
    keys_notified = {p[0] for p in published}
    assert keys_notified == {principal_key(sender), principal_key(recipient)}


def test_send_across_parties_succeeds() -> None:
    """Sender and recipient in different parties — DM still delivers."""
    store = Store()
    sender, recipient = _seed(store)
    _join(store, "cream-terrazzo", sender.id, "human", "Alice")
    # Put the recipient in a separate world to exercise the old cross-party gate.
    from app.parties_data import CREAM_TERRAZZO
    from app.world import PartyWorld

    other_world = PartyWorld(CREAM_TERRAZZO)
    store._worlds["other-party"] = other_world  # type: ignore[attr-defined]
    other_world.join(
        Participant(
            id=recipient.id,
            kind="human",
            username="Bob",
            color="#9c27b0",
            x=0.0,
            y=0.0,
            joined_at=0.0,
        )
    )
    hub = store.inbox_hub
    published: list[tuple[str, dict]] = []
    hub.publish = lambda key, frame: published.append((key, frame))  # type: ignore[assignment]

    result = send(
        store=store,
        dm_store=store.dm_store,
        inbox_hub=hub,
        sender=sender,
        recipient=recipient,
        text="hi from another party",
    )
    rows = query_thread_history(store.dm_store, thread_key=result["thread_key"])
    assert len(rows) == 1
    assert rows[0]["text"] == "hi from another party"
    keys_notified = {p[0] for p in published}
    assert keys_notified == {principal_key(sender), principal_key(recipient)}


def test_send_invalid_text_raises_chat_validation_error() -> None:
    store = Store()
    sender, recipient = _seed(store)
    _join(store, "cream-terrazzo", sender.id, "human", "Alice")
    _join(store, "cream-terrazzo", recipient.id, "human", "Bob")
    with pytest.raises(ChatValidationError):
        send(
            store=store,
            dm_store=store.dm_store,
            inbox_hub=store.inbox_hub,
            sender=sender,
            recipient=recipient,
            text="   ",
        )
