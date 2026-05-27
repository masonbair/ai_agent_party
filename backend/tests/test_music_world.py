from app.events import MusicChangedEvent, Event, Participant
from app.models import (
    PartyConfig,
    Room,
    Theme,
    Music,
    WorldSize,
)
from app.world import PartyWorld, MusicState, ParticipantNotInPartyError
from app.validation import MusicValidationError
import pytest


def _make_world() -> PartyWorld:
    party = PartyConfig(
        slug="t",
        name="T",
        description="",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="Music coming soon"),
        worldSize=WorldSize(width=400, height=300),
        room=Room(clipPath=None, border="1px solid #000", walls=[]),
        modules=[],
    )
    return PartyWorld(party)


def _join(w: PartyWorld, pid: str = "p1", kind: str = "agent") -> Participant:
    p = Participant(
        id=pid, kind=kind, username="U", color="#ff6b9d",
        x=10.0, y=10.0, joined_at=0.0,
    )
    w.join(p)
    return p


def test_music_changed_event_has_unified_actor_fields():
    ev = MusicChangedEvent(
        seq=1,
        track_id="lofi-loop",
        playing=True,
        volume=42,
        at=12345.0,
        actor_id="agent_x",
        actor_username="DJ",
        actor_kind="agent",
        room_wide=True,
    )
    assert ev.type == "music_changed"
    assert ev.track_id == "lofi-loop"
    assert ev.playing is True
    assert ev.volume == 42
    assert ev.actor_id == "agent_x"
    assert ev.room_wide is True


def test_music_changed_event_is_in_event_union():
    # Pydantic discriminator wiring sanity-check.
    assert MusicChangedEvent in Event.__args__  # type: ignore[attr-defined]


def test_initial_music_state_defaults():
    w = _make_world()
    assert isinstance(w.music, MusicState)
    assert w.music.track_id is None
    assert w.music.playing is False
    assert w.music.volume == 50
    assert w.music.since is None


def test_snapshot_includes_music_state():
    w = _make_world()
    snap = w.snapshot()
    assert "music" in snap
    assert snap["music"] == {
        "track_id": None,
        "playing": False,
        "volume": 50,
        "since": None,
    }
