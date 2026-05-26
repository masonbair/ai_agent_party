import pytest
from pydantic import ValidationError

from app.events import (
    Agent,
    ChatEvent,
    JoinEvent,
    LeaveEvent,
    MoveEvent,
    Participant,
)


def _participant() -> Participant:
    return Participant(
        id="abc123",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=100.0,
        y=200.0,
        joined_at=1715533200.0,
    )


def test_participant_requires_human_or_agent_kind() -> None:
    with pytest.raises(ValidationError):
        Participant(
            id="abc",
            kind="ghost",  # type: ignore[arg-type]
            username="Alice",
            color="#ff6b9d",
            x=0.0,
            y=0.0,
            joined_at=0.0,
        )


def test_join_event_carries_participant_and_seq() -> None:
    ev = JoinEvent(seq=1, participant=_participant(), at=1715533200.0)
    assert ev.type == "join"
    assert ev.seq == 1
    assert ev.participant.username == "Alice"


def test_leave_event_carries_participant_id() -> None:
    ev = LeaveEvent(seq=2, participant_id="abc123", at=1715533200.0)
    assert ev.type == "leave"


def test_move_event_carries_coords() -> None:
    ev = MoveEvent(seq=3, participant_id="abc123", x=10.0, y=20.0, at=1715533200.0)
    assert ev.type == "move"
    assert ev.x == 10.0


def test_chat_event_carries_text_and_at() -> None:
    ev = ChatEvent(seq=4, participant_id="abc123", text="hi", at=1715533200.0)
    assert ev.type == "chat"
    assert ev.text == "hi"


def test_agent_model_fields() -> None:
    agent = Agent(agent_id="x", username="Bot1", color="#ff6b9d")
    assert agent.agent_id == "x"


def test_event_union_includes_new_types() -> None:
    from app.events import Event

    args = getattr(Event, "__args__", ())
    names = {a.__name__ for a in args}
    for n in [
        "ReactionEvent",
        "LightingChangedEvent",
        "NoteCreatedEvent",
        "NoteUpdatedEvent",
        "NoteDeletedEvent",
        "StrokeAddedEvent",
        "StrokeDroppedEvent",
        "BoardClearedEvent",
        "VoteChangedEvent",
    ]:
        assert n in names, f"{n} missing from Event union"


def test_reaction_event_round_trip() -> None:
    from app.events import ReactionEvent

    ev = ReactionEvent(seq=1, actor_id="a", emoji="❤️", expires_at=2.0, at=1.0)
    dumped = ev.model_dump()
    assert dumped["type"] == "reaction"
    assert dumped["emoji"] == "❤️"


def test_vote_changed_event_payload() -> None:
    from app.events import VoteChangedEvent

    ev = VoteChangedEvent(seq=2, module_id="draw-1", votes=1, needed=2, at=1.0)
    d = ev.model_dump()
    assert d["type"] == "vote_changed"
    assert d["votes"] == 1
    assert d["needed"] == 2
