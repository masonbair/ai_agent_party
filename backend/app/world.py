import time
import uuid
from typing import Callable

from app.collision import Rect, inflate_walls, slide
from app.events import (
    ChatEvent,
    Event,
    JoinEvent,
    LeaveEvent,
    MoveEvent,
    Participant,
    Reaction,
    LightingChangedEvent,
    BoardClearedEvent,
    NoteCreatedEvent,
    NoteDeletedEvent,
    NoteUpdatedEvent,
    ReactionEvent,
    VoteChangedEvent,
    StickyNote,
    Stroke,
    StrokeAddedEvent,
    StrokeDroppedEvent,
)
from app.models import (
    DrawBoardModule,
    LightingModule,
    PartyConfig,
    PlacedModule,
    StickyNoteModule,
)
from app.validation import (
    INTERACTION_MARGIN,
    NOTES_PER_USER_MAX,
    REACTION_LIFETIME_SECONDS,
    SLOT_OCCUPIED_RADIUS,
    STROKES_PER_BOARD_MAX,
    VOTE_TTL_SECONDS,
    validate_chat_text,
    validate_note_color,
    validate_note_text,
    validate_reaction_emoji,
    validate_stroke,
)

_LIGHTING_PRESETS = ("day", "dusk", "night", "party")


class ParticipantNotInPartyError(LookupError):
    pass


class NotInRangeError(LookupError):
    pass


class LimitReachedError(LookupError):
    pass


class NotAuthorError(LookupError):
    pass


class PartyWorld:
    NotInRangeError = NotInRangeError
    LimitReachedError = LimitReachedError
    NotAuthorError = NotAuthorError

    def __init__(self, party: PartyConfig) -> None:
        self._party = party
        self.participants: dict[str, Participant] = {}
        self._events: list[Event] = []
        self._wall_rects: list[Rect] = inflate_walls(
            party.room.walls, party.worldSize
        )
        self._listeners: list[Callable[[Event], None]] = []
        self.lighting: str = "day"
        self.notes_by_module: dict[str, list[StickyNote]] = {}
        self.strokes_by_module: dict[str, list[Stroke]] = {}
        self.votes_by_module: dict[str, dict[str, float]] = {}
        self.active_reactions: dict[str, Reaction] = {}
        for m in party.modules:
            if isinstance(m, LightingModule):
                self.lighting = m.preset
            elif isinstance(m, StickyNoteModule):
                self.notes_by_module[m.id] = []
            elif isinstance(m, DrawBoardModule):
                self.strokes_by_module[m.id] = []
                self.votes_by_module[m.id] = {}

    def on_event(
        self, callback: Callable[[Event], None]
    ) -> Callable[[], None]:
        """Register a callback fired synchronously after each event is appended.

        Returns an ``unsubscribe`` callable that removes the callback.
        """
        self._listeners.append(callback)

        def _unsub() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return _unsub

    def _emit(self, event: Event) -> None:
        # Snapshot so a listener may unsubscribe itself during dispatch.
        for cb in list(self._listeners):
            try:
                cb(event)
            except Exception:
                # A misbehaving listener must never break world bookkeeping.
                pass

    @property
    def cursor(self) -> int:
        return len(self._events)

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    def _next_seq(self) -> int:
        return len(self._events) + 1

    def join(self, participant: Participant) -> JoinEvent:
        self.participants[participant.id] = participant
        ev = JoinEvent(seq=self._next_seq(), participant=participant, at=time.time())
        self._events.append(ev)
        self._emit(ev)
        return ev

    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        del self.participants[participant_id]
        ev = LeaveEvent(seq=self._next_seq(), participant_id=participant_id, at=time.time())
        self._events.append(ev)
        self._emit(ev)
        self._recompute_all_drawboard_votes(time.time())
        return ev

    def move(self, participant_id: str, x: float, y: float) -> MoveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        current = self.participants[participant_id]
        new_x, new_y = slide(
            (current.x, current.y),
            (float(x), float(y)),
            self._wall_rects,
            self._party.worldSize,
        )
        self.participants[participant_id] = current.model_copy(
            update={"x": new_x, "y": new_y}
        )
        ev = MoveEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            x=new_x,
            y=new_y,
            at=time.time(),
        )
        self._events.append(ev)
        self._emit(ev)
        self._recompute_all_drawboard_votes(time.time())
        return ev

    def chat(self, participant_id: str, text: str) -> ChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        cleaned = validate_chat_text(text)
        ev = ChatEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            text=cleaned,
            at=time.time(),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

    def react(self, participant_id: str, emoji: str) -> ReactionEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        cleaned = validate_reaction_emoji(emoji)
        now = time.time()
        expires_at = now + REACTION_LIFETIME_SECONDS
        self.active_reactions[participant_id] = Reaction(
            actor_id=participant_id, emoji=cleaned, expires_at=expires_at,
        )
        ev = ReactionEvent(
            seq=self._next_seq(),
            actor_id=participant_id,
            emoji=cleaned,
            expires_at=expires_at,
            at=now,
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

    def set_lighting(self, changed_by: str, preset: str) -> LightingChangedEvent:
        if changed_by not in self.participants:
            raise ParticipantNotInPartyError(changed_by)
        if preset not in _LIGHTING_PRESETS:
            raise ValueError(f"unknown lighting preset {preset!r}")
        self.lighting = preset
        ev = LightingChangedEvent(
            seq=self._next_seq(),
            preset=preset,
            changed_by=changed_by,
            at=time.time(),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

    def _require_placed(self, module_id: str) -> PlacedModule:
        m = self._placed_module(module_id)
        if m is None:
            raise KeyError(module_id)
        return m

    def _require_in_zone(self, participant_id: str, module_id: str) -> None:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        p = self.participants[participant_id]
        if not self.in_zone(module_id, p.x, p.y):
            raise NotInRangeError(module_id)

    def _clamp_local(
        self, m: PlacedModule, x: float, y: float
    ) -> tuple[float, float]:
        return (max(0.0, min(m.w, float(x))), max(0.0, min(m.h, float(y))))

    def create_note(
        self,
        participant_id: str,
        module_id: str,
        text: str,
        color: str,
        x: float,
        y: float,
    ) -> NoteCreatedEvent:
        m = self._require_placed(module_id)
        if not isinstance(m, StickyNoteModule):
            raise KeyError(f"module {module_id} is not stickynotes")
        self._require_in_zone(participant_id, module_id)
        cleaned_text = validate_note_text(text)
        cleaned_color = validate_note_color(color)
        notes = self.notes_by_module[module_id]
        own = sum(1 for n in notes if n.author_id == participant_id)
        if own >= NOTES_PER_USER_MAX:
            raise LimitReachedError(module_id)
        lx, ly = self._clamp_local(m, x, y)
        participant = self.participants[participant_id]
        note = StickyNote(
            id=uuid.uuid4().hex,
            module_id=module_id,
            author_id=participant_id,
            author_kind=participant.kind,
            text=cleaned_text,
            color=cleaned_color,
            x=lx,
            y=ly,
            created_at=time.time(),
        )
        notes.append(note)
        ev = NoteCreatedEvent(
            seq=self._next_seq(),
            module_id=module_id,
            note=note,
            at=note.created_at,
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

    def update_note(
        self,
        participant_id: str,
        module_id: str,
        note_id: str,
        *,
        text: str | None = None,
        color: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> NoteUpdatedEvent:
        m = self._require_placed(module_id)
        if not isinstance(m, StickyNoteModule):
            raise KeyError(module_id)
        self._require_in_zone(participant_id, module_id)
        notes = self.notes_by_module[module_id]
        for i, n in enumerate(notes):
            if n.id == note_id:
                if n.author_id != participant_id:
                    raise NotAuthorError(note_id)
                fields: dict = {}
                if text is not None:
                    fields["text"] = validate_note_text(text)
                if color is not None:
                    fields["color"] = validate_note_color(color)
                if x is not None or y is not None:
                    nx = n.x if x is None else x
                    ny = n.y if y is None else y
                    lx, ly = self._clamp_local(m, nx, ny)
                    fields["x"] = lx
                    fields["y"] = ly
                updated = n.model_copy(update=fields)
                notes[i] = updated
                ev = NoteUpdatedEvent(
                    seq=self._next_seq(),
                    module_id=module_id,
                    note=updated,
                    at=time.time(),
                )
                self._events.append(ev)
                self._emit(ev)
                return ev
        raise KeyError(note_id)

    def delete_note(
        self, participant_id: str, module_id: str, note_id: str
    ) -> NoteDeletedEvent:
        self._require_placed(module_id)
        self._require_in_zone(participant_id, module_id)
        notes = self.notes_by_module[module_id]
        for i, n in enumerate(notes):
            if n.id == note_id:
                if n.author_id != participant_id:
                    raise NotAuthorError(note_id)
                del notes[i]
                ev = NoteDeletedEvent(
                    seq=self._next_seq(),
                    module_id=module_id,
                    note_id=note_id,
                    at=time.time(),
                )
                self._events.append(ev)
                self._emit(ev)
                return ev
        raise KeyError(note_id)

    def _zone_population(self, module_id: str) -> list[str]:
        return [
            pid
            for pid, p in self.participants.items()
            if self.in_zone(module_id, p.x, p.y)
        ]

    def _prune_votes(self, module_id: str, now: float) -> None:
        votes = self.votes_by_module.get(module_id)
        if votes is None:
            return
        in_zone = set(self._zone_population(module_id))
        stale = [
            aid for aid, exp in votes.items()
            if exp <= now or aid not in in_zone
        ]
        for aid in stale:
            del votes[aid]

    def _tally_and_maybe_clear(
        self, module_id: str, voter_id: str | None, now: float
    ) -> dict:
        self._prune_votes(module_id, now)
        population = self._zone_population(module_id)
        votes = self.votes_by_module[module_id]
        active = len(votes)
        needed = (len(population) // 2) + 1 if population else 1
        if active > len(population) / 2 and active > 0:
            self.strokes_by_module[module_id] = []
            self.votes_by_module[module_id] = {}
            ev = BoardClearedEvent(
                seq=self._next_seq(),
                module_id=module_id,
                cleared_by=voter_id or "system",
                at=now,
            )
            self._events.append(ev)
            self._emit(ev)
            return {"votes": 0, "needed": 1, "cleared": True}
        ev = VoteChangedEvent(
            seq=self._next_seq(),
            module_id=module_id,
            votes=active,
            needed=needed,
            at=now,
        )
        self._events.append(ev)
        self._emit(ev)
        return {"votes": active, "needed": needed, "cleared": False}

    def vote_clear(self, participant_id: str, module_id: str) -> dict:
        m = self._require_placed(module_id)
        if not isinstance(m, DrawBoardModule):
            raise KeyError(module_id)
        self._require_in_zone(participant_id, module_id)
        now = time.time()
        self.votes_by_module[module_id][participant_id] = now + VOTE_TTL_SECONDS
        return self._tally_and_maybe_clear(module_id, participant_id, now)

    def _recompute_all_drawboard_votes(self, now: float) -> None:
        for module_id in list(self.votes_by_module.keys()):
            before = set(self.votes_by_module[module_id].keys())
            self._prune_votes(module_id, now)
            after = set(self.votes_by_module[module_id].keys())
            if before != after:
                self._tally_and_maybe_clear(module_id, voter_id=None, now=now)

    def add_stroke(
        self, participant_id: str, module_id: str, raw: dict
    ) -> StrokeAddedEvent:
        m = self._require_placed(module_id)
        if not isinstance(m, DrawBoardModule):
            raise KeyError(f"module {module_id} is not drawboard")
        self._require_in_zone(participant_id, module_id)
        cleaned = validate_stroke(raw, m.w, m.h)
        participant = self.participants[participant_id]
        stroke = Stroke(
            id=uuid.uuid4().hex,
            module_id=module_id,
            author_id=participant_id,
            author_kind=participant.kind,
            color=cleaned["color"],
            width=cleaned["width"],
            points=cleaned["points"],
            created_at=time.time(),
        )
        strokes = self.strokes_by_module[module_id]
        dropped: Stroke | None = None
        if len(strokes) >= STROKES_PER_BOARD_MAX:
            dropped = strokes.pop(0)
        strokes.append(stroke)
        ev = StrokeAddedEvent(
            seq=self._next_seq(),
            module_id=module_id,
            stroke=stroke,
            at=stroke.created_at,
        )
        self._events.append(ev)
        self._emit(ev)
        if dropped is not None:
            drop_ev = StrokeDroppedEvent(
                seq=self._next_seq(),
                module_id=module_id,
                stroke_id=dropped.id,
                at=time.time(),
            )
            self._events.append(drop_ev)
            self._emit(drop_ev)
        return ev

    def _placed_module(self, module_id: str) -> PlacedModule | None:
        for m in self._party.modules:
            if isinstance(m, (StickyNoteModule, DrawBoardModule)) and m.id == module_id:
                return m
        return None

    def in_zone(self, module_id: str, x: float, y: float) -> bool:
        m = self._placed_module(module_id)
        if m is None:
            return False
        margin = INTERACTION_MARGIN
        return (
            m.x - margin <= x <= m.x + m.w + margin
            and m.y - margin <= y <= m.y + m.h + margin
        )

    def approach_slots(self, module_id: str) -> list[tuple[float, float]]:
        m = self._placed_module(module_id)
        if m is None:
            return []
        margin = INTERACTION_MARGIN
        ix, iy = m.x - margin, m.y - margin
        iw, ih = m.w + 2 * margin, m.h + 2 * margin
        cx, cy = ix + iw / 2, iy + ih / 2
        wcx = self._party.worldSize.width / 2
        wcy = self._party.worldSize.height / 2
        dx, dy = wcx - cx, wcy - cy
        slots: list[tuple[float, float]] = []
        if abs(dx) >= abs(dy):
            edge_x = ix + iw if dx > 0 else ix
            for i in range(6):
                slots.append((edge_x, iy + ih * (i + 0.5) / 6))
        else:
            edge_y = iy + ih if dy > 0 else iy
            for i in range(6):
                slots.append((ix + iw * (i + 0.5) / 6, edge_y))
        return slots

    def slot_occupancy(
        self,
        module_id: str,
        positions: list[tuple[float, float]] | None = None,
    ) -> list[bool]:
        if positions is None:
            positions = [(p.x, p.y) for p in self.participants.values()]
        slots = self.approach_slots(module_id)
        r2 = SLOT_OCCUPIED_RADIUS ** 2
        out: list[bool] = []
        for sx, sy in slots:
            occupied = any(
                (px - sx) ** 2 + (py - sy) ** 2 <= r2 for px, py in positions
            )
            out.append(occupied)
        return out

    def derive_zone(self, x: float, y: float) -> str | None:
        w = self._party.worldSize
        if w.width == 0 or w.height == 0:
            return None
        px = (x / w.width) * 100.0
        py = (y / w.height) * 100.0
        for zone in self._party.zones:
            if (
                zone.x <= px <= zone.x + zone.width
                and zone.y <= py <= zone.y + zone.height
            ):
                return zone.id
        return None

    def _participant_dict(self, p: Participant) -> dict:
        return {
            "id": p.id,
            "kind": p.kind,
            "username": p.username,
            "color": p.color,
            "x": p.x,
            "y": p.y,
            "zone": self.derive_zone(p.x, p.y),
        }

    def _module_snapshot(self, m: PlacedModule) -> dict:
        margin = INTERACTION_MARGIN
        ir = {
            "x": m.x - margin,
            "y": m.y - margin,
            "w": m.w + 2 * margin,
            "h": m.h + 2 * margin,
        }
        slots = self.approach_slots(m.id)
        occ = self.slot_occupancy(m.id)
        slots_out = [
            {"x": x, "y": y, "occupied": o} for (x, y), o in zip(slots, occ)
        ]
        base: dict = {
            "id": m.id,
            "kind": m.kind,
            "x": m.x,
            "y": m.y,
            "w": m.w,
            "h": m.h,
            "interactionRect": ir,
            "approachSlots": slots_out,
        }
        if isinstance(m, StickyNoteModule):
            base["notes"] = [n.model_dump() for n in self.notes_by_module[m.id]]
        else:
            base["strokes"] = [
                s.model_dump() for s in self.strokes_by_module[m.id]
            ]
            now = time.time()
            self._prune_votes(m.id, now)
            population = self._zone_population(m.id)
            active = len(self.votes_by_module[m.id])
            needed = (len(population) // 2) + 1 if population else 1
            base["vote"] = {"votes": active, "needed": needed}
        return base

    def snapshot(self) -> dict:
        now = time.time()
        active_reactions = [
            r.model_dump()
            for r in self.active_reactions.values()
            if r.expires_at > now
        ]
        self.active_reactions = {
            aid: r
            for aid, r in self.active_reactions.items()
            if r.expires_at > now
        }
        placed = [
            m for m in self._party.modules
            if isinstance(m, (StickyNoteModule, DrawBoardModule))
        ]
        return {
            "participants": [
                self._participant_dict(p) for p in self.participants.values()
            ],
            "cursor": self.cursor,
            "lighting": self.lighting,
            "modules": [self._module_snapshot(m) for m in placed],
            "active_reactions": active_reactions,
        }

    def observe_since(self, since: int) -> dict:
        if since < 0:
            since = 0
        tail = self._events[since:]
        latest_move_by_pid: dict[str, MoveEvent] = {}
        latest_vote_by_module: dict[str, VoteChangedEvent] = {}
        out: list[dict] = []
        for ev in tail:
            if isinstance(ev, MoveEvent):
                latest_move_by_pid[ev.participant_id] = ev
                continue
            if isinstance(ev, VoteChangedEvent):
                latest_vote_by_module[ev.module_id] = ev
                continue
            if isinstance(ev, JoinEvent):
                out.append(
                    {
                        "type": "join",
                        "seq": ev.seq,
                        "participant": self._participant_dict(ev.participant),
                        "at": ev.at,
                    }
                )
            else:
                out.append(ev.model_dump())
        for mv in latest_move_by_pid.values():
            d = mv.model_dump()
            d["zone"] = self.derive_zone(mv.x, mv.y)
            out.append(d)
        for v in latest_vote_by_module.values():
            out.append(v.model_dump())
        out.sort(key=lambda e: e["seq"])
        return {"events": out, "cursor": self.cursor}
