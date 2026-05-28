import pytest

from app.events import GestureEvent, Participant
from app.models import Music, PartyConfig, Room, Theme, WorldSize
from app.validation import GESTURE_TTL_SECONDS, GestureValidationError
from app.world import ParticipantNotInPartyError, PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t",
        description="",
        theme=Theme(floor="#fff", accent="#000"),
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=600),
        room=Room(border="1px solid", walls=[]),
        zones=[], modules=[],
    )
    return PartyWorld(party=party)


def _join(w: PartyWorld, pid: str = "p1") -> Participant:
    p = Participant(
        id=pid, kind="human", username="Alice", color="#ff6b9d",
        x=100.0, y=100.0, joined_at=0.0,
    )
    w.join(p)
    return p


def test_gesture_emits_event_with_actor_fields():
    w = _world()
    _join(w)
    ev = w.gesture("p1", "wave")
    assert isinstance(ev, GestureEvent)
    assert ev.gesture == "wave"
    assert ev.actor_id == "p1"
    assert ev.actor_username == "Alice"
    assert ev.actor_kind == "human"
    assert ev.expires_at == pytest.approx(ev.at + GESTURE_TTL_SECONDS, abs=0.05)


def test_gesture_event_room_wide_false_default():
    w = _world()
    _join(w)
    ev = w.gesture("p1", "wave")
    assert ev.room_wide is False  # proximity-scoped


def test_gesture_unknown_raises_validation_error():
    w = _world()
    _join(w)
    with pytest.raises(GestureValidationError):
        w.gesture("p1", "twerk")


def test_gesture_unknown_participant_raises():
    w = _world()
    with pytest.raises(ParticipantNotInPartyError):
        w.gesture("ghost", "wave")


def test_gesture_uses_unified_seq_counter():
    w = _world()
    _join(w)  # seq 1
    ev1 = w.gesture("p1", "wave")
    ev2 = w.gesture("p1", "bow")
    assert ev2.seq == ev1.seq + 1
