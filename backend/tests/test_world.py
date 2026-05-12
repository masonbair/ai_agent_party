import pytest

from app.events import ChatEvent, JoinEvent, LeaveEvent, MoveEvent, Participant
from app.parties_data import CREAM_TERRAZZO
from app.validation import ChatValidationError
from app.world import PartyWorld, ParticipantNotInPartyError


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


def test_new_world_has_zero_cursor() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    assert w.cursor == 0
    assert w.participants == {}


def test_join_adds_participant_and_emits_event() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    ev = w.join(_alice())
    assert isinstance(ev, JoinEvent)
    assert ev.seq == 1
    assert w.cursor == 1
    assert w.participants["s-alice"].username == "Alice"


def test_join_assigns_monotonic_seq() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    e1 = w.join(_alice())
    bob = _alice().model_copy(update={"id": "s-bob", "username": "Bob"})
    e2 = w.join(bob)
    assert (e1.seq, e2.seq) == (1, 2)


def test_leave_removes_participant_and_emits_event() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    ev = w.leave("s-alice")
    assert isinstance(ev, LeaveEvent)
    assert "s-alice" not in w.participants
    assert ev.seq == 2


def test_leave_unknown_raises() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    with pytest.raises(ParticipantNotInPartyError):
        w.leave("nope")


def test_move_updates_position_and_clamps_to_bounds() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    ev = w.move("s-alice", x=-50.0, y=99999.0)
    assert isinstance(ev, MoveEvent)
    assert ev.x == 0.0
    assert ev.y == CREAM_TERRAZZO.worldSize.height
    assert w.participants["s-alice"].x == 0.0


def test_move_unknown_raises() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    with pytest.raises(ParticipantNotInPartyError):
        w.move("nope", 0, 0)


def test_chat_emits_event_with_trimmed_text() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    ev = w.chat("s-alice", "  hello!  ")
    assert isinstance(ev, ChatEvent)
    assert ev.text == "hello!"
    assert ev.at > 0


def test_chat_rejects_invalid_text() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    with pytest.raises(ChatValidationError):
        w.chat("s-alice", "<script>")


def test_chat_unknown_participant_raises() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    with pytest.raises(ParticipantNotInPartyError):
        w.chat("nope", "hi")
