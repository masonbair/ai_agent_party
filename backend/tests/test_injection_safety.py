"""Regression tests proving the real security boundary holds.

The character whitelists were loosened to printable ASCII, so SQL/JS-looking
payloads now pass validation. These tests assert that the actual defenses —
parameterized SQL in db.py and (on the frontend) React's auto-escaping —
keep such payloads inert. They are the durable guarantee against a future
change accidentally reintroducing a hole.
"""

import time

import pytest

from app import db as db_module
from app.events import Participant
from app.parties_data import PARTY_REGISTRY
from app.world import PartyWorld

SQLI_PAYLOAD = "'); DROP TABLE broadcast_messages;--"


@pytest.fixture
def conn():
    c = db_module.init_db(":memory:")
    yield c
    db_module.close_db(c)


@pytest.fixture
def party():
    return next(iter(PARTY_REGISTRY.values()))


def _join(world: PartyWorld) -> None:
    world.join(
        Participant(
            id="sess-1",
            kind="human",
            username="Alice",
            color="#ff6b9d",
            x=10.0,
            y=10.0,
            joined_at=time.time(),
        )
    )


def test_sqli_payload_stored_verbatim_and_table_survives(party, conn):
    world = PartyWorld(party, db_conn=conn, party_slug=party.slug)
    _join(world)

    # A SQL-injection-shaped message is accepted by the loosened charset...
    world.chat("sess-1", SQLI_PAYLOAD)

    # ...stored as a literal value (parameterized query — never executed)...
    rows = db_module.query_broadcast_history(conn, party.slug)
    assert [r["text"] for r in rows] == [SQLI_PAYLOAD]

    # ...and the table it tried to drop is still there and usable.
    world.chat("sess-1", "still here")
    rows = db_module.query_broadcast_history(conn, party.slug)
    assert [r["text"] for r in rows] == ["still here", SQLI_PAYLOAD]


def test_sqli_payload_through_chat_route(client, store):
    party_slug = next(iter(PARTY_REGISTRY))
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "agent", "id": a["agent_id"]}
    client.post(f"/api/parties/{party_slug}/join", json={"principal": principal})

    r = client.post(
        f"/api/parties/{party_slug}/chat",
        json={"principal": principal, "text": SQLI_PAYLOAD},
    )
    assert r.status_code == 200

    rows = db_module.query_broadcast_history(store.db, party_slug)
    assert [row["text"] for row in rows] == [SQLI_PAYLOAD]
