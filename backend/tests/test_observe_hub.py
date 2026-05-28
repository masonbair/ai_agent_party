from __future__ import annotations

import asyncio
import pytest

from app.events import Participant
from app.observer_hub import PartyObserverHub
from app.store import Store


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self, code: int | None = None) -> None:
        self.closed = True


def _seed(store: Store, name: str, x: float, y: float):
    sess = store.create_session(username=name, color="#ff6b9d")
    world = store.get_or_create_world("cream-terrazzo")
    assert world is not None
    world.join(
        Participant(
            id=sess.session_id, kind="human", username=name,
            color="#ff6b9d", x=x, y=y, joined_at=0.0,
        )
    )
    return sess.session_id, world


@pytest.mark.asyncio
async def test_subscribe_tracks_socket_and_cursor():
    store = Store()
    pid, world = _seed(store, "Alice", 100.0, 100.0)
    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid, participant_id=pid)
    assert sock in hub.sockets
    assert hub.cursor_of(sock) == world.cursor
    hub.teardown()


def test_store_returns_one_observer_hub_per_party():
    store = Store()
    hub1 = store.get_or_create_observer_hub("cream-terrazzo")
    hub2 = store.get_or_create_observer_hub("cream-terrazzo")
    assert hub1 is hub2
    assert store.get_or_create_observer_hub("nope") is None


@pytest.mark.asyncio
async def test_event_pushed_with_cursor_when_visible(monkeypatch):
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 110.0, 110.0)  # within radius

    # Spec #02 helper: returns True iff event is visible to observer.
    assert hasattr(world, "visible_to")

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    ev = world.chat(pid_b, "hello")
    await hub.drain()

    assert any(f.get("type") == "event" for f in sock.sent)
    pushed = [f for f in sock.sent if f.get("type") == "event"]
    assert pushed[-1]["cursor"] == ev.seq
    assert pushed[-1]["event"]["type"] == "chat"
    assert pushed[-1]["event"]["text"] == "hello"
    assert hub.cursor_of(sock) == ev.seq
    hub.teardown()


@pytest.mark.asyncio
async def test_event_not_pushed_when_out_of_proximity():
    store = Store()
    pid_a, world = _seed(store, "Alice", 0.0, 0.0)
    pid_b, _ = _seed(store, "Bob", 5000.0, 5000.0)  # far away

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    world.chat(pid_b, "hi from afar")
    await hub.drain()

    # No "event" frames should reach Alice for Bob's chat.
    event_frames = [f for f in sock.sent if f.get("type") == "event"]
    assert event_frames == []
    hub.teardown()


@pytest.mark.asyncio
async def test_multiple_sockets_per_principal_each_get_event():
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 110.0, 110.0)

    hub = PartyObserverHub(world)
    s1, s2 = FakeSocket(), FakeSocket()
    hub.subscribe(s1, principal_key="human:" + pid_a, participant_id=pid_a)
    hub.subscribe(s2, principal_key="human:" + pid_a, participant_id=pid_a)

    world.chat(pid_b, "hey both")
    await hub.drain()

    for s in (s1, s2):
        evs = [f for f in s.sent if f.get("type") == "event"]
        assert len(evs) == 1
        assert evs[0]["event"]["text"] == "hey both"
    hub.teardown()


@pytest.mark.asyncio
async def test_peer_entering_proximity_emits_snapshot():
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 9000.0, 9000.0)

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    # Bob walks into Alice's proximity radius.
    world.move(pid_b, 110.0, 110.0)
    await hub.drain()

    types = [f.get("type") for f in sock.sent]
    assert "proximity_snapshot" in types
    snap = next(f for f in sock.sent if f["type"] == "proximity_snapshot")
    assert snap["participant_id"] == pid_b


@pytest.mark.asyncio
async def test_peer_leaving_proximity_emits_left():
    store = Store()
    pid_a, world = _seed(store, "Alice", 100.0, 100.0)
    pid_b, _ = _seed(store, "Bob", 110.0, 110.0)

    hub = PartyObserverHub(world)
    sock = FakeSocket()
    hub.subscribe(sock, principal_key="human:" + pid_a, participant_id=pid_a)

    # Hub seeded with current snapshot of peers in proximity.
    state = hub.sockets[sock]
    state.in_proximity.add(pid_b)

    # Bob walks far away.
    world.move(pid_b, 9000.0, 9000.0)
    await hub.drain()

    types = [f.get("type") for f in sock.sent]
    assert "proximity_left" in types
    left = next(f for f in sock.sent if f["type"] == "proximity_left")
    assert left["participant_id"] == pid_b
