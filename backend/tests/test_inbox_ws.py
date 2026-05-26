from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.events import Participant
from app.inbox import InboxHub
from app.store import Store


class FakeSocket:
    def __init__(self, fail_on: int | None = None) -> None:
        self.sent: list[dict] = []
        self.closed = False
        self._fail_on = fail_on

    async def send_json(self, payload: dict) -> None:
        if self._fail_on is not None and len(self.sent) == self._fail_on:
            raise RuntimeError("simulated broken pipe")
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_publish_only_to_addressed_principal() -> None:
    hub = InboxHub()
    a, b = FakeSocket(), FakeSocket()
    hub.subscribe(a, "human:alice")
    hub.subscribe(b, "human:bob")
    hub.publish("human:alice", {"type": "dm", "msg": "hi"})
    await hub.drain()
    assert a.sent == [{"type": "dm", "msg": "hi"}]
    assert b.sent == []


@pytest.mark.asyncio
async def test_duplicate_subscribe_evicts_prior_socket() -> None:
    hub = InboxHub()
    old, new = FakeSocket(), FakeSocket()
    hub.subscribe(old, "human:alice")
    hub.subscribe(new, "human:alice")
    await hub.drain()
    assert old.closed
    assert old.sent == [{"type": "evicted", "reason": "takeover"}]
    hub.publish("human:alice", {"type": "dm", "x": 1})
    await hub.drain()
    assert new.sent == [{"type": "dm", "x": 1}]


@pytest.mark.asyncio
async def test_unsubscribe_clears_routing() -> None:
    hub = InboxHub()
    sock = FakeSocket()
    hub.subscribe(sock, "human:alice")
    hub.unsubscribe(sock, "human:alice")
    hub.publish("human:alice", {"type": "dm"})
    await hub.drain()
    assert sock.sent == []


def _seed_two_in_party(store: Store) -> tuple[str, str]:
    alice = store.create_session(username="Alice", color="#ff6b9d")
    bob = store.create_session(username="Bob", color="#9c27b0")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    for sid, name, color in (
        (alice.session_id, "Alice", "#ff6b9d"),
        (bob.session_id, "Bob", "#9c27b0"),
    ):
        world.join(
            Participant(
                id=sid,
                kind="human",
                username=name,
                color=color,
                x=0.0,
                y=0.0,
                joined_at=0.0,
            )
        )
    return alice.session_id, bob.session_id


def test_ws_auth_success_then_receive_dm(client: TestClient, store: Store) -> None:
    a_id, b_id = _seed_two_in_party(store)
    with client.websocket_connect("/api/inbox") as bob_ws:
        bob_ws.send_json(
            {"type": "auth", "principal": {"kind": "human", "id": b_id}}
        )
        # Alice sends a DM to Bob via HTTP.
        resp = client.post(
            "/api/dm/send",
            json={
                "principal": {"kind": "human", "id": a_id},
                "recipient": {"kind": "human", "id": b_id},
                "text": "hello bob",
            },
        )
        assert resp.status_code == 200, resp.text
        frame = bob_ws.receive_json()
        assert frame["type"] == "dm"
        assert frame["message"]["text"] == "hello bob"
        assert frame["message"]["sender_name"] == "Alice"


def test_ws_auth_error_on_bad_principal(client: TestClient) -> None:
    with client.websocket_connect("/api/inbox") as ws:
        ws.send_json(
            {"type": "auth", "principal": {"kind": "human", "id": "nope"}}
        )
        frame = ws.receive_json()
        assert frame["type"] == "auth_error"


def test_ws_takeover_evicts_old_socket(client: TestClient, store: Store) -> None:
    alice = store.create_session(username="Alice", color="#ff6b9d")
    with client.websocket_connect("/api/inbox") as first:
        first.send_json(
            {"type": "auth", "principal": {"kind": "human", "id": alice.session_id}}
        )
        with client.websocket_connect("/api/inbox") as second:
            second.send_json(
                {
                    "type": "auth",
                    "principal": {"kind": "human", "id": alice.session_id},
                }
            )
            frame = first.receive_json()
            assert frame == {"type": "evicted", "reason": "takeover"}
