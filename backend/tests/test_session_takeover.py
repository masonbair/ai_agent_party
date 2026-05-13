import asyncio

import pytest

from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.realtime import PartyWorldHub
from app.world import PartyWorld


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


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


@pytest.mark.asyncio
async def test_hub_evicts_prior_socket_for_same_principal_key() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    world.join(_alice())  # so leave() during eviction is valid

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, principal_key="human:s-alice", participant_id="s-alice")
    hub.subscribe(b, principal_key="human:s-alice", participant_id="s-alice")

    await hub.drain()
    assert {"type": "evicted", "reason": "takeover"} in a.sent
    assert a.closed is True
    assert a not in hub.subscribers
    assert b in hub.subscribers
    assert hub._by_principal["human:s-alice"] is b


@pytest.mark.asyncio
async def test_hub_eviction_broadcasts_leave_event_to_others() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    world.join(_alice())

    observer = FakeSocket()
    hub.subscribe(observer, principal_key="human:observer", participant_id="observer")
    await hub.drain()
    observer.sent.clear()

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, principal_key="human:s-alice", participant_id="s-alice")
    hub.subscribe(b, principal_key="human:s-alice", participant_id="s-alice")
    await hub.drain()

    leave_frames = [
        f for f in observer.sent
        if f.get("type") == "event"
        and f.get("event", {}).get("type") == "leave"
        and f["event"].get("participant_id") == "s-alice"
    ]
    assert len(leave_frames) == 1
    assert not any(
        f.get("type") == "event" and f.get("event", {}).get("type") == "leave"
        for f in a.sent
    )
