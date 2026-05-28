import pytest

from app.events import CosmeticEvent, Participant
from app.models import Music, PartyConfig, Room, Theme, WorldSize
from app.validation import COSMETIC_TTL_SECONDS, CosmeticValidationError
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


def _join(w: PartyWorld) -> Participant:
    p = Participant(
        id="p1", kind="agent", username="Maestro", color="#9c27b0",
        x=100.0, y=100.0, joined_at=0.0,
    )
    w.join(p)
    return p


def test_cosmetic_emits_event_with_actor_fields_and_room_wide_true():
    w = _world()
    _join(w)
    ev = w.cosmetic("p1", "confetti")
    assert isinstance(ev, CosmeticEvent)
    assert ev.effect == "confetti"
    assert ev.room_wide is True
    assert ev.actor_id == "p1"
    assert ev.actor_username == "Maestro"
    assert ev.actor_kind == "agent"
    assert ev.expires_at == pytest.approx(ev.at + COSMETIC_TTL_SECONDS, abs=0.05)


def test_cosmetic_unknown_raises():
    w = _world()
    _join(w)
    with pytest.raises(CosmeticValidationError):
        w.cosmetic("p1", "rain")


def test_cosmetic_unknown_participant_raises():
    w = _world()
    with pytest.raises(ParticipantNotInPartyError):
        w.cosmetic("ghost", "confetti")
