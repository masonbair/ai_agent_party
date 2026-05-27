from app.events import NoteReactionEvent


def test_note_reaction_event_shape():
    ev = NoteReactionEvent(
        seq=1,
        module_id="freenotes-1",
        note_id="abc",
        emoji="🎉",
        at=1.0,
        actor_id="p",
        actor_username="alex",
        actor_kind="human",
    )
    assert ev.type == "note_reaction"
    assert ev.emoji == "🎉"


from app.events import Participant
from app.models import (
    FreeNotesModule,
    Music,
    PartyConfig,
    Room,
    Theme,
    WorldSize,
)
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t", description="t",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=500),
        room=Room(border="1px solid #000", walls=[]),
        modules=[FreeNotesModule(id="freenotes-1")],
    )
    return PartyWorld(party)


def test_react_to_note_increments_and_emits_event():
    world = _world()
    world.join(Participant(id="p1", kind="human", username="alex",
                           color="#ff6b9d", x=100.0, y=100.0, joined_at=0.0))
    note_ev = world.create_note("p1", "freenotes-1", "hi", "pink", 100.0, 100.0)
    note_id = note_ev.note.id
    ev = world.react_to_note("p1", "freenotes-1", note_id, "🎉")
    assert ev.type == "note_reaction"
    assert ev.emoji == "🎉"
    # Counter updated on the note record.
    notes = world.notes_by_module["freenotes-1"]
    assert notes[0].reactions == {"🎉": 1}


def test_react_to_note_unknown_emoji_raises():
    world = _world()
    world.join(Participant(id="p1", kind="human", username="alex",
                           color="#ff6b9d", x=100.0, y=100.0, joined_at=0.0))
    note_ev = world.create_note("p1", "freenotes-1", "hi", "pink", 100.0, 100.0)
    import pytest
    from app.validation import ReactionValidationError
    with pytest.raises(ReactionValidationError):
        world.react_to_note("p1", "freenotes-1", note_ev.note.id, "💩")
