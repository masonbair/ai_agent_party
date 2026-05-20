import time

import pytest

from app import db as db_module
from app.events import Participant
from app.parties_data import PARTY_REGISTRY
from app.world import PartyWorld


@pytest.fixture
def conn():
    c = db_module.init_db(":memory:")
    yield c
    db_module.close_db(c)


@pytest.fixture
def party():
    return next(iter(PARTY_REGISTRY.values()))


def _join(world: PartyWorld) -> Participant:
    p = Participant(
        id="sess-1",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=10.0,
        y=10.0,
        joined_at=time.time(),
    )
    world.join(p)
    return p


def test_chat_persists_row_with_call_args(party, conn):
    world = PartyWorld(party, db_conn=conn, party_slug=party.slug)
    _join(world)
    world.chat("sess-1", "hello there")
    rows = db_module.query_broadcast_history(conn, party.slug)
    assert len(rows) == 1
    r = rows[0]
    assert r["party_slug"] == party.slug
    assert r["sender_kind"] == "human"
    assert r["sender_id"] == "sess-1"
    assert r["sender_name"] == "Alice"
    assert r["text"] == "hello there"
    assert isinstance(r["at"], float) and r["at"] > 0


def test_chat_without_db_still_works(party):
    world = PartyWorld(party)  # no db_conn → in-memory only
    _join(world)
    ev = world.chat("sess-1", "no db here")
    assert ev.text == "no db here"


def test_chat_db_failure_aborts_emit(party, conn):
    # Close the connection so insert raises.
    conn.close()
    world = PartyWorld(party, db_conn=conn, party_slug=party.slug)
    _join(world)
    received = []
    world.on_event(lambda e: received.append(e))
    with pytest.raises(Exception):
        world.chat("sess-1", "boom")
    # No ChatEvent should have been emitted because persistence failed.
    assert all(getattr(e, "text", None) != "boom" for e in received)
