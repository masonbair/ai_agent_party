import time

import pytest

from app.events import Agent, ChatEvent, MoveEvent, Participant
from app.models import PartyConfig
from app.occupancy import compute_occupancy
from app.parties_data import PARTY_REGISTRY
from app.world import PartyWorld


def _world() -> PartyWorld:
    party: PartyConfig = list(PARTY_REGISTRY.values())[0]
    return PartyWorld(party, party_slug=party.slug)


def _human(id_: str, x: float = 100.0) -> Participant:
    return Participant(id=id_, kind="human", username=f"h_{id_}", color="#ff6b9d", x=x, y=100.0, joined_at=time.time())


def _agent(id_: str, x: float = 110.0) -> Participant:
    return Participant(id=id_, kind="agent", username=f"a_{id_}", color="#ff6b9d", x=x, y=100.0, joined_at=time.time())


def test_empty_room():
    w = _world()
    occ = compute_occupancy(w, now=time.time())
    assert occ == {"humans": 0, "agents": 0, "total": 0, "active_last_5min": 0}


def test_mixed_population_idle_default():
    # New joiners count toward active (they have a recent join event).
    w = _world()
    w.join(_human("h1"))
    w.join(_agent("a1"))
    w.join(_agent("a2"))
    occ = compute_occupancy(w, now=time.time())
    assert occ == {"humans": 1, "agents": 2, "total": 3, "active_last_5min": 3}


def test_active_last_5min_counts_only_recent_actors():
    w = _world()
    w.join(_human("h1"))
    w.join(_human("h2"))
    # Backdate h2 by writing a stale move directly.
    # h1 will produce a fresh move; h2 stays idle.
    w.move("h1", 120.0, 100.0)
    now = time.time()
    # Rewrite h2's join timestamp into the past so they look idle.
    for ev in w._events:
        if getattr(ev, "actor_id", None) == "h2":
            object.__setattr__(ev, "at", now - 600.0)
    occ = compute_occupancy(w, now=now)
    assert occ["humans"] == 2
    assert occ["total"] == 2
    assert occ["active_last_5min"] == 1  # only h1 acted in last 5min


def test_active_only_counts_participants_currently_in_room():
    # A participant who left should not count, even with a recent event.
    w = _world()
    w.join(_human("h1"))
    w.join(_human("h2"))
    w.leave("h2")
    occ = compute_occupancy(w, now=time.time())
    assert occ["humans"] == 1
    assert occ["total"] == 1
    assert occ["active_last_5min"] == 1
