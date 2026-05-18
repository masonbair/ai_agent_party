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


# --- Lighting (Task 6) ---


def test_set_lighting_updates_state_and_emits_event() -> None:
    from app.events import LightingChangedEvent

    w = _world_with_modules()
    _join_modules(w, "p1")
    ev = w.set_lighting("p1", "night")
    assert isinstance(ev, LightingChangedEvent)
    assert w.lighting == "night"
    assert ev.changed_by == "p1"


def test_set_lighting_rejects_unknown_preset() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1")
    with pytest.raises(ValueError):
        w.set_lighting("p1", "rainbow")


def test_set_lighting_requires_participant() -> None:
    w = _world_with_modules()
    with pytest.raises(ParticipantNotInPartyError):
        w.set_lighting("ghost", "day")


# --- Sticky notes (Task 7) ---

from app.events import NoteCreatedEvent, NoteDeletedEvent, NoteUpdatedEvent, StickyNote


def test_create_note_emits_event_and_stores_note() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    ev = w.create_note("p1", "sticky-1", "hi", "yellow", x=10, y=10)
    assert isinstance(ev, NoteCreatedEvent)
    assert ev.note.text == "hi"
    assert ev.note.author_id == "p1"
    assert ev.note.author_kind == "human"
    assert w.notes_by_module["sticky-1"][0].id == ev.note.id


def test_create_note_clamps_local_coordinates() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    ev = w.create_note("p1", "sticky-1", "hi", "yellow", x=-50, y=999)
    assert ev.note.x == 0.0 and ev.note.y == 160.0


def test_create_note_requires_being_in_zone() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=700, y=400)
    with pytest.raises(PartyWorld.NotInRangeError):
        w.create_note("p1", "sticky-1", "hi", "yellow", x=0, y=0)


def test_create_note_rejects_unknown_module() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    with pytest.raises(KeyError):
        w.create_note("p1", "sticky-nope", "hi", "yellow", x=0, y=0)


def test_create_note_enforces_per_user_limit() -> None:
    from app.validation import NOTES_PER_USER_MAX

    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    for i in range(NOTES_PER_USER_MAX):
        w.create_note("p1", "sticky-1", f"n{i}", "yellow", x=0, y=0)
    with pytest.raises(PartyWorld.LimitReachedError):
        w.create_note("p1", "sticky-1", "one too many", "yellow", x=0, y=0)


def test_update_note_only_author() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    _join_modules(w, "p2", x=200, y=140)
    ev = w.create_note("p1", "sticky-1", "hi", "yellow", x=0, y=0)
    upd = w.update_note("p1", "sticky-1", ev.note.id, text="bye")
    assert isinstance(upd, NoteUpdatedEvent)
    assert upd.note.text == "bye"
    with pytest.raises(PartyWorld.NotAuthorError):
        w.update_note("p2", "sticky-1", ev.note.id, text="hax")


def test_delete_note_only_author() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    _join_modules(w, "p2", x=200, y=140)
    ev = w.create_note("p1", "sticky-1", "hi", "yellow", x=0, y=0)
    with pytest.raises(PartyWorld.NotAuthorError):
        w.delete_note("p2", "sticky-1", ev.note.id)
    out = w.delete_note("p1", "sticky-1", ev.note.id)
    assert isinstance(out, NoteDeletedEvent)
    assert w.notes_by_module["sticky-1"] == []


# --- Drawboard strokes (Task 8) ---

from app.events import StrokeAddedEvent, StrokeDroppedEvent
from app.validation import STROKES_PER_BOARD_MAX


def test_add_stroke_emits_event_and_stores_stroke() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    raw = {"color": "#ff6b9d", "width": "med", "points": [{"x": 1, "y": 1}, {"x": 5, "y": 5}]}
    ev = w.add_stroke("p1", "draw-1", raw)
    assert isinstance(ev, StrokeAddedEvent)
    assert ev.stroke.author_id == "p1"
    assert w.strokes_by_module["draw-1"][0].id == ev.stroke.id


def test_add_stroke_requires_in_zone() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=10, y=10)
    raw = {"color": "#ff6b9d", "width": "med", "points": [{"x": 0, "y": 0}]}
    with pytest.raises(PartyWorld.NotInRangeError):
        w.add_stroke("p1", "draw-1", raw)


def test_add_stroke_validation_errors_propagate() -> None:
    from app.validation import StrokeValidationError

    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    with pytest.raises(StrokeValidationError):
        w.add_stroke("p1", "draw-1", {"color": "rebeccapurple", "width": "med", "points": [{"x": 0, "y": 0}]})


def test_add_stroke_evicts_oldest_at_cap() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    raw = {"color": "#ff6b9d", "width": "thin", "points": [{"x": 0, "y": 0}]}
    first_id = w.add_stroke("p1", "draw-1", raw).stroke.id
    for _ in range(STROKES_PER_BOARD_MAX - 1):
        w.add_stroke("p1", "draw-1", raw)
    assert len(w.strokes_by_module["draw-1"]) == STROKES_PER_BOARD_MAX
    received: list = []
    unsub = w.on_event(received.append)
    w.add_stroke("p1", "draw-1", raw)
    unsub()
    dropped = [e for e in received if isinstance(e, StrokeDroppedEvent)]
    assert len(dropped) == 1
    assert dropped[0].stroke_id == first_id
    assert all(s.id != first_id for s in w.strokes_by_module["draw-1"])
    assert len(w.strokes_by_module["draw-1"]) == STROKES_PER_BOARD_MAX


# --- Vote-to-clear (Task 9) ---

from app.events import BoardClearedEvent, VoteChangedEvent


def test_solo_vote_clears_immediately() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    raw = {"color": "#ff6b9d", "width": "thin", "points": [{"x": 0, "y": 0}]}
    w.add_stroke("p1", "draw-1", raw)
    received: list = []
    unsub = w.on_event(received.append)
    result = w.vote_clear("p1", "draw-1")
    unsub()
    assert result["cleared"] is True
    assert w.strokes_by_module["draw-1"] == []
    assert any(isinstance(e, BoardClearedEvent) for e in received)
    assert w.votes_by_module["draw-1"] == {}


def test_two_voters_need_both() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    _join_modules(w, "p2", x=620, y=180)
    w.add_stroke("p1", "draw-1", {"color": "#ff6b9d", "width": "thin", "points": [{"x": 0, "y": 0}]})
    r1 = w.vote_clear("p1", "draw-1")
    assert r1["cleared"] is False
    assert r1["votes"] == 1 and r1["needed"] == 2
    r2 = w.vote_clear("p2", "draw-1")
    assert r2["cleared"] is True
    assert w.strokes_by_module["draw-1"] == []


def test_vote_dropped_when_voter_walks_away() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    _join_modules(w, "p2", x=620, y=180)
    w.vote_clear("p1", "draw-1")
    w.move("p1", x=10, y=10)
    assert "p1" not in w.votes_by_module["draw-1"]
    r = w.vote_clear("p2", "draw-1")
    assert r["cleared"] is True


def test_expired_vote_does_not_count() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    _join_modules(w, "p2", x=620, y=180)
    w.vote_clear("p1", "draw-1")
    w.votes_by_module["draw-1"]["p1"] = time.time() - 1
    r = w.vote_clear("p2", "draw-1")
    assert r["cleared"] is False
    assert r["votes"] == 1 and r["needed"] == 2


def test_vote_changed_event_emitted_on_progress() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=640, y=160)
    _join_modules(w, "p2", x=620, y=180)
    received: list = []
    unsub = w.on_event(received.append)
    w.vote_clear("p1", "draw-1")
    unsub()
    vc = [e for e in received if isinstance(e, VoteChangedEvent)]
    assert vc and vc[-1].votes == 1 and vc[-1].needed == 2


# --- Snapshot includes modules (Task 10) ---


def test_snapshot_includes_module_state() -> None:
    w = _world_with_modules()
    _join_modules(w, "p1", x=200, y=140)
    w.create_note("p1", "sticky-1", "hi", "yellow", x=0, y=0)
    snap = w.snapshot()
    assert snap["lighting"] == "dusk"
    assert snap["active_reactions"] == []
    mods = {m["id"]: m for m in snap["modules"]}
    assert mods["sticky-1"]["kind"] == "stickynotes"
    assert len(mods["sticky-1"]["notes"]) == 1
    assert mods["sticky-1"]["interactionRect"]["w"] == 240 + 2 * 24
    assert len(mods["sticky-1"]["approachSlots"]) == 6
    assert mods["draw-1"]["strokes"] == []
    assert mods["draw-1"]["vote"]["votes"] == 0
