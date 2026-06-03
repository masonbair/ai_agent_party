import asyncio

import pytest

from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.realtime import PartyWorldHub
from app.world import PartyWorld


def _p(pid: str, x: float, y: float) -> Participant:
    return Participant(
        id=pid, kind="human", username=pid, color="#ff6b9d",
        x=x, y=y, joined_at=1715533200.0,
    )


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


def _chat_frames(sock: FakeSocket) -> list[dict]:
    return [
        f["event"]
        for f in sock.sent
        if f.get("type") == "event" and f["event"].get("type") == "chat"
    ]


@pytest.mark.asyncio
async def test_in_range_subscriber_gets_full_chat():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 300.0, 300.0))
    world.join(_p("b", 320.0, 300.0))  # within PROXIMITY_RADIUS of a
    hub = PartyWorldHub(world)
    sock_b = FakeSocket()
    hub.subscribe(sock_b, principal_key="human:b", participant_id="b")

    world.chat("a", "hello neighbor")
    await hub.drain()

    frames = _chat_frames(sock_b)
    assert len(frames) == 1
    assert frames[0]["text"] == "hello neighbor"
    assert frames[0].get("ambient") in (False, None)


@pytest.mark.asyncio
async def test_out_of_range_subscriber_gets_ambient_only():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 100.0, 100.0))
    world.join(_p("c", 900.0, 700.0))  # far from a
    hub = PartyWorldHub(world)
    sock_c = FakeSocket()
    hub.subscribe(sock_c, principal_key="human:c", participant_id="c")

    world.chat("a", "secret nearby talk")
    await hub.drain()

    frames = _chat_frames(sock_c)
    assert len(frames) == 1
    assert frames[0]["ambient"] is True
    assert "text" not in frames[0] or frames[0]["text"] == ""
    assert frames[0]["actor_id"] == "a"  # so the client can place the puff


@pytest.mark.asyncio
async def test_room_wide_chat_reaches_everyone_with_text():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 100.0, 100.0))
    world.join(_p("c", 900.0, 700.0))
    hub = PartyWorldHub(world)
    sock_c = FakeSocket()
    hub.subscribe(sock_c, principal_key="human:c", participant_id="c")

    world.chat("a", "EVERYONE LISTEN", scope="room")
    await hub.drain()

    frames = _chat_frames(sock_c)
    assert len(frames) == 1
    assert frames[0]["text"] == "EVERYONE LISTEN"


@pytest.mark.asyncio
async def test_move_is_global_regardless_of_distance():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 100.0, 100.0))
    world.join(_p("c", 900.0, 700.0))
    hub = PartyWorldHub(world)
    sock_c = FakeSocket()
    hub.subscribe(sock_c, principal_key="human:c", participant_id="c")

    world.move("a", 120.0, 120.0)
    await hub.drain()

    moves = [
        f["event"] for f in sock_c.sent
        if f.get("type") == "event" and f["event"].get("type") == "move"
    ]
    assert len(moves) >= 1  # far-away movement still delivered
