import pytest

from app.events import Participant
from app.models import Music, PartyConfig, Room, Theme, WorldSize
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t",
        description="",
        theme=Theme(floor="#fff", accent="#000"),
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=2000, height=2000),
        room=Room(border="1px solid", walls=[]),
        zones=[], modules=[],
    )
    return PartyWorld(party=party)


def _join(w: PartyWorld) -> Participant:
    p = Participant(
        id="p1", kind="human", username="Alice", color="#ff6b9d",
        x=500.0, y=500.0, joined_at=0.0,
    )
    w.join(p)
    return p


@pytest.mark.parametrize("dx,dy,expected", [
    (0, -10, "up"),
    (0, 10, "down"),
    (-10, 0, "left"),
    (10, 0, "right"),
    (-10, -10, "up-left"),
    (10, -10, "up-right"),
    (-10, 10, "down-left"),
    (10, 10, "down-right"),
])
def test_move_derives_facing_for_each_octant(dx, dy, expected):
    w = _world()
    p = _join(w)
    ev = w.move("p1", p.x + dx, p.y + dy)
    assert ev.facing == expected
    assert w.participants["p1"].facing == expected


def test_move_zero_delta_retains_previous_facing():
    w = _world()
    p = _join(w)
    # Initial move sets facing to "right".
    w.move("p1", p.x + 10, p.y)
    assert w.participants["p1"].facing == "right"
    # Same-position move retains.
    ev = w.move("p1", p.x + 10, p.y)
    assert ev.facing == "right"
    assert w.participants["p1"].facing == "right"


def test_initial_participant_facing_defaults_to_down():
    w = _world()
    p = _join(w)
    # Before any move, facing should be the default.
    assert p.facing == "down"
    assert w.participants["p1"].facing == "down"


def test_observe_participant_includes_facing():
    w = _world()
    _join(w)
    w.move("p1", 510.0, 510.0)
    snap = w.snapshot()
    me = next(p for p in snap["participants"] if p["id"] == "p1")
    assert me["facing"] == "down-right"
