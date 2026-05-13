import asyncio

import pytest

from app.session_presence import SessionPresenceHub


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


class FakeStore:
    def worlds(self):
        return []


@pytest.mark.asyncio
async def test_presence_hub_evicts_prior_socket_for_same_session_id() -> None:
    hub = SessionPresenceHub(FakeStore())
    a = FakeSocket()
    b = FakeSocket()

    hub.subscribe(a, "sid-1")
    hub.subscribe(b, "sid-1")

    await hub.drain()
    assert {"type": "evicted", "reason": "takeover"} in a.sent
    assert a.closed is True
    assert hub._by_session["sid-1"] is b


@pytest.mark.asyncio
async def test_presence_hub_unsubscribe_does_not_clear_replaced_slot() -> None:
    hub = SessionPresenceHub(FakeStore())
    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.subscribe(b, "sid-1")
    await hub.drain()

    hub.unsubscribe(a, "sid-1")

    assert hub._by_session["sid-1"] is b


@pytest.mark.asyncio
async def test_presence_hub_clean_unsubscribe_clears_slot() -> None:
    hub = SessionPresenceHub(FakeStore())
    a = FakeSocket()
    hub.subscribe(a, "sid-1")
    hub.unsubscribe(a, "sid-1")
    assert "sid-1" not in hub._by_session
