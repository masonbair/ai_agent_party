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
        and f["event"].get("actor_id") == "s-alice"
    ]
    assert len(leave_frames) == 1
    assert not any(
        f.get("type") == "event" and f.get("event", {}).get("type") == "leave"
        for f in a.sent
    )


@pytest.mark.asyncio
async def test_hub_unsubscribe_does_not_clear_replaced_slot() -> None:
    world = PartyWorld(CREAM_TERRAZZO)
    hub = PartyWorldHub(world)
    world.join(_alice())

    a = FakeSocket()
    b = FakeSocket()
    hub.subscribe(a, principal_key="human:s-alice", participant_id="s-alice")
    hub.subscribe(b, principal_key="human:s-alice", participant_id="s-alice")
    await hub.drain()

    hub.unsubscribe(a, principal_key="human:s-alice")

    assert hub._by_principal["human:s-alice"] is b
    assert b in hub.subscribers


from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _signin(client: TestClient, username: str, color: str) -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def test_second_ws_with_same_session_evicts_the_first(client: TestClient) -> None:
    user = _signin(client, "Alice", "#ff6b9d")
    sid = user["session_id"]
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r.status_code == 200

    with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws_a:
        ws_a.send_json({"type": "auth", "principal": {"kind": "human", "id": sid}})
        snap_a = ws_a.receive_json()
        assert snap_a["type"] == "snapshot"

        with client.websocket_connect("/api/parties/cream-terrazzo/ws") as ws_b:
            ws_b.send_json({"type": "auth", "principal": {"kind": "human", "id": sid}})
            snap_b = ws_b.receive_json()
            assert snap_b["type"] == "snapshot"

            evict_frame = ws_a.receive_json()
            assert evict_frame == {"type": "evicted", "reason": "takeover"}
            with pytest.raises(WebSocketDisconnect):
                ws_a.receive_json()
