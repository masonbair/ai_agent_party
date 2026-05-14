import asyncio

import pytest

from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.realtime import PartyWorldHub
from app.world import PartyWorld


def _alice() -> Participant:
    return Participant(
        id="s-alice",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=400.0,
        y=250.0,
        joined_at=1715533200.0,
    )


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
async def test_hub_broadcasts_to_subscribers() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    sock = FakeSocket()
    hub.subscribe(sock)
    world.join(_alice())
    await asyncio.sleep(0)
    await hub.drain()
    assert len(sock.sent) == 1
    assert sock.sent[0]["type"] == "event"
    assert sock.sent[0]["event"]["type"] == "join"
    assert sock.sent[0]["cursor"] == 1


@pytest.mark.asyncio
async def test_hub_drops_misbehaving_subscriber() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    good, bad = FakeSocket(), FakeSocket(fail_on=0)
    hub.subscribe(good)
    hub.subscribe(bad)
    world.join(_alice())
    await hub.drain()
    assert bad.closed
    assert bad not in hub.subscribers
    assert good in hub.subscribers
    assert len(good.sent) == 1


@pytest.mark.asyncio
async def test_hub_unsubscribe_stops_delivery() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    sock = FakeSocket()
    hub.subscribe(sock)
    world.join(_alice())
    await hub.drain()
    assert len(sock.sent) == 1
    hub.unsubscribe(sock)
    world.move("s-alice", 100.0, 100.0)
    await hub.drain()
    assert len(sock.sent) == 1  # unchanged
