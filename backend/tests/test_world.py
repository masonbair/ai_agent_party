import time

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


def test_derive_zone_returns_zone_id_when_inside() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    # DANCE zone is at x=6%..40%, y=8%..44% of an 800x500 world.
    # Point (200, 100) -> 25% x, 20% y -> inside DANCE.
    assert w.derive_zone(200.0, 100.0) == "dance"


def test_derive_zone_returns_none_outside_any_zone() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    # Point (1, 1) is at ~0.1% x and ~0.2% y - outside all zones.
    assert w.derive_zone(1.0, 1.0) is None


def test_snapshot_returns_participants_with_zone_and_cursor() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice().model_copy(update={"x": 200.0, "y": 100.0}))
    snap = w.snapshot()
    assert snap["cursor"] == 1
    assert len(snap["participants"]) == 1
    p = snap["participants"][0]
    assert p["id"] == "s-alice"
    assert p["zone"] == "dance"
    assert p["x"] == 200.0


def test_observe_since_returns_events_after_cursor() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())  # seq 1
    w.move("s-alice", 100, 100)  # seq 2
    result = w.observe_since(1)
    assert result["cursor"] == 2
    assert len(result["events"]) == 1
    assert result["events"][0]["type"] == "move"


def test_observe_since_returns_empty_when_caught_up() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    result = w.observe_since(1)
    assert result == {"events": [], "cursor": 1}


def test_observe_since_collapses_consecutive_moves_per_participant() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    for i in range(1, 11):
        w.move("s-alice", float(i * 10), float(i * 5))
    result = w.observe_since(1)
    move_events = [e for e in result["events"] if e["type"] == "move"]
    assert len(move_events) == 1
    assert move_events[0]["x"] == 100.0
    assert move_events[0]["y"] == 50.0
    assert move_events[0]["participant_id"] == "s-alice"


def test_observe_since_does_not_collapse_chat_or_join_or_leave() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    w.chat("s-alice", "hi")
    w.chat("s-alice", "hello")
    result = w.observe_since(1)
    chat_events = [e for e in result["events"] if e["type"] == "chat"]
    assert len(chat_events) == 2


def test_observe_since_adds_zone_to_move_events() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    w.move("s-alice", 200.0, 100.0)
    result = w.observe_since(1)
    move = next(e for e in result["events"] if e["type"] == "move")
    assert move["zone"] == "dance"


def test_observe_since_adds_zone_to_join_participant() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice().model_copy(update={"x": 200.0, "y": 100.0}))
    result = w.observe_since(0)
    join = next(e for e in result["events"] if e["type"] == "join")
    assert join["participant"]["zone"] == "dance"


def test_observe_since_collapses_per_participant_not_globally() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    bob = _alice().model_copy(update={"id": "s-bob", "username": "Bob"})
    w.join(bob)
    w.move("s-alice", 50, 50)
    w.move("s-bob", 60, 60)
    w.move("s-alice", 70, 70)
    result = w.observe_since(2)
    moves = [e for e in result["events"] if e["type"] == "move"]
    by_pid = {m["participant_id"]: m for m in moves}
    assert set(by_pid.keys()) == {"s-alice", "s-bob"}
    assert by_pid["s-alice"]["x"] == 70.0
    assert by_pid["s-bob"]["x"] == 60.0


def test_on_event_callback_is_invoked_on_append() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    received: list = []
    w.on_event(received.append)
    w.join(_alice())
    w.move("s-alice", 300.0, 200.0)
    move_events = [e for e in received if isinstance(e, MoveEvent)]
    assert len(move_events) == 1
    assert move_events[0].x == 300.0 and move_events[0].y == 200.0
    join_events = [e for e in received if isinstance(e, JoinEvent)]
    assert len(join_events) == 1


def test_on_event_supports_multiple_callbacks_and_unregister() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    a: list = []
    b: list = []
    unsub = w.on_event(a.append)
    w.on_event(b.append)
    w.join(_alice())
    assert len(a) == 1 and len(b) == 1
    unsub()
    bob = _alice().model_copy(update={"id": "s-bob", "username": "Bob"})
    w.join(bob)
    assert len(a) == 1  # unsubscribed
    assert len(b) == 2


def test_on_event_listener_exception_does_not_break_world() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    received: list = []

    def bad(_ev):
        raise RuntimeError("boom")

    w.on_event(bad)
    w.on_event(received.append)
    ev = w.join(_alice())
    assert ev.seq == 1
    assert len(received) == 1


# --- Module state (Task 4) ---

from app.models import (
    DrawBoardModule,
    LightingModule,
    Music,
    PartyConfig,
    Room,
    StickyNoteModule,
    Theme,
    WorldSize,
)


def _world_with_modules() -> PartyWorld:
    cfg = PartyConfig(
        slug="t",
        name="t",
        description="",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=500),
        room=Room(border="1px solid", walls=[]),
        modules=[
            LightingModule(preset="dusk"),
            StickyNoteModule(id="sticky-1", x=80, y=60, w=240, h=160),
            DrawBoardModule(id="draw-1", x=480, y=60, w=320, h=200),
        ],
    )
    return PartyWorld(cfg)


def test_world_initialises_module_state_from_config() -> None:
    w = _world_with_modules()
    assert w.lighting == "dusk"
    assert "sticky-1" in w.notes_by_module and w.notes_by_module["sticky-1"] == []
    assert "draw-1" in w.strokes_by_module and w.strokes_by_module["draw-1"] == []
    assert w.votes_by_module["draw-1"] == {}
    assert w.active_reactions == {}


def test_in_zone_uses_interaction_margin() -> None:
    from app.validation import INTERACTION_MARGIN

    w = _world_with_modules()
    assert w.in_zone("sticky-1", 80 - INTERACTION_MARGIN + 0.1, 60)
    assert w.in_zone("sticky-1", 80 + 120, 60 + 80)
    assert not w.in_zone("sticky-1", 80 - INTERACTION_MARGIN - 1, 60)
    assert not w.in_zone("nonexistent", 0, 0)


def test_approach_slots_lie_on_interaction_edge() -> None:
    from app.validation import INTERACTION_MARGIN as M

    w = _world_with_modules()
    slots = w.approach_slots("sticky-1")
    assert len(slots) == 6
    for x, y in slots:
        assert 80 - M <= x <= 80 + 240 + M
        assert 60 - M <= y <= 60 + 160 + M


def test_slot_occupancy_uses_radius() -> None:
    from app.validation import SLOT_OCCUPIED_RADIUS

    w = _world_with_modules()
    slots = w.approach_slots("sticky-1")
    sx, sy = slots[0]
    occ = w.slot_occupancy("sticky-1", [(sx + SLOT_OCCUPIED_RADIUS - 1, sy)])
    assert occ[0] is True
    occ2 = w.slot_occupancy("sticky-1", [(sx + SLOT_OCCUPIED_RADIUS + 1, sy)])
    assert occ2[0] is False


# --- Reactions (Task 5) ---

from app.events import ReactionEvent
from app.validation import REACTION_LIFETIME_SECONDS


def _join_modules(w: PartyWorld, pid: str, x: float = 100, y: float = 100) -> None:
    w.join(Participant(
        id=pid, kind="human", username="u" + pid, color="#ff6b9d",
        x=x, y=y, joined_at=time.time(),
    ))


def test_react_emits_event_and_records_active_reaction() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1")
    ev = w.react("p1", "❤️")
    assert isinstance(ev, ReactionEvent)
    assert ev.emoji == "❤️"
    assert "p1" in w.active_reactions
    assert w.active_reactions["p1"].emoji == "❤️"
    assert abs((ev.expires_at - ev.at) - REACTION_LIFETIME_SECONDS) < 1e-6


def test_react_replaces_existing_reaction_same_actor() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1")
    w.react("p1", "❤️")
    w.react("p1", "🎉")
    assert w.active_reactions["p1"].emoji == "🎉"


def test_react_unknown_emoji_raises() -> None:
    from app.validation import ReactionValidationError

    w = _world_with_modules()
    _join_modules(w, "p1")
    with pytest.raises(ReactionValidationError):
        w.react("p1", "💩")


def test_react_unknown_actor_raises() -> None:
    w = _world_with_modules()
    with pytest.raises(ParticipantNotInPartyError):
        w.react("ghost", "❤️")
