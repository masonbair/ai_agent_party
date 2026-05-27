import sqlite3
import time
import uuid
from typing import Callable

from app import db as db_module
from app.collision import Rect, inflate_walls, slide
from app.proximity import (
    PROXIMITY_RADIUS,
    PROXIMITY_SNAPSHOT_CHAT_LIMIT,
    ProximityTracker,
    within_proximity,
)
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
    RECENT_CHAT_LIMIT,
    SLOT_OCCUPIED_RADIUS,
    STROKES_PER_BOARD_MAX,
    VOTE_TTL_SECONDS,
    validate_chat_text,
    validate_note_color,
    validate_note_text,
    validate_reaction_emoji,
    validate_stroke,
)

# ``PROXIMITY_RADIUS``, ``PROXIMITY_SNAPSHOT_CHAT_LIMIT``, ``within_proximity``
# and ``ProximityTracker`` are imported from ``app.proximity`` above and
# re-exported here so existing imports (e.g. ``from app.world import
# PROXIMITY_RADIUS``) keep working unchanged.

_LIGHTING_PRESETS = ("day", "dusk", "night", "party")


class ParticipantNotInPartyError(LookupError):
    pass


class PartyWorld:
    class NotInRangeError(LookupError):
        pass

    class LimitReachedError(LookupError):
        pass

    class NotAuthorError(LookupError):
        pass

    def __init__(
        self,
        party: PartyConfig,
        *,
        db_conn: sqlite3.Connection | None = None,
        party_slug: str | None = None,
    ) -> None:
        self._party = party
        self._db = db_conn
        self._party_slug = party_slug if party_slug is not None else party.slug
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
        # Last (active_votes, needed) emitted per drawboard. Used to suppress
        # duplicate vote_changed events when participants move without
        # changing the tally — and to detect population-only changes (someone
        # walked into / out of a board with a vote in flight) so the displayed
        # 'needed' updates without requiring a new vote.
        self._last_vote_state: dict[str, tuple[int, int]] = {}
        # Per-requester proximity tracking. Cleared on leave().
        self._proximity_trackers: dict[str, ProximityTracker] = {}
        # Position of the actor at the time each event was emitted, keyed by seq.
        # Only populated for chat/reaction events; move events carry x/y already.
        # NOTE: grows unbounded like ``_events`` — pruning is unsafe while
        # multiple observers hold different cursors, so it is deferred to the
        # event-log trimming work (see CLAUDE.md "Not Yet Implemented").
        self._actor_pos_at_seq: dict[int, tuple[float, float]] = {}
        for m in party.modules:
            if isinstance(m, LightingModule):
                self.lighting = m.preset
            elif isinstance(m, StickyNoteModule):
                self.notes_by_module[m.id] = []
            elif isinstance(m, DrawBoardModule):
                self.strokes_by_module[m.id] = []
                self.votes_by_module[m.id] = {}
                self._last_vote_state[m.id] = (0, 1)

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

    def _actor_fields(self, participant_id: str) -> dict:
        p = self.participants.get(participant_id)
        if p is None:
            return {}
        return {
            "actor_id": p.id,
            "actor_username": p.username,
            "actor_kind": p.kind,
        }

    def join(self, participant: Participant) -> JoinEvent:
        self.participants[participant.id] = participant
        ev = JoinEvent(
            seq=self._next_seq(),
            actor_id=participant.id,
            actor_username=participant.username,
            actor_kind=participant.kind,
            x=participant.x,
            y=participant.y,
            zone=self.derive_zone(participant.x, participant.y),
            at=time.time(),
        )
        self._events.append(ev)
        self._emit(ev)
        self._recompute_all_drawboard_votes(time.time())
        return ev

    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        actor = self._actor_fields(participant_id)
        del self.participants[participant_id]
        self._proximity_trackers.pop(participant_id, None)
        ev = LeaveEvent(seq=self._next_seq(), at=time.time(), **actor)
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
            x=new_x,
            y=new_y,
            at=time.time(),
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._emit(ev)
        self._recompute_all_drawboard_votes(time.time())
        return ev

    def chat(self, participant_id: str, text: str) -> ChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        cleaned = validate_chat_text(text)
        at = time.time()
        sender = self.participants[participant_id]
        if self._db is not None:
            # Persist FIRST so a DB failure raises and no live bubble is emitted.
            db_module.insert_broadcast(
                self._db,
                party_slug=self._party_slug,
                sender_kind=sender.kind,
                sender_id=sender.id,
                sender_name=sender.username,
                text=cleaned,
                at=at,
            )
        ev = ChatEvent(
            seq=self._next_seq(),
            text=cleaned,
            at=time.time(),
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._actor_pos_at_seq[ev.seq] = (sender.x, sender.y)
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
        p = self.participants[participant_id]
        ev = ReactionEvent(
            seq=self._next_seq(),
            emoji=cleaned,
            expires_at=expires_at,
            at=now,
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._actor_pos_at_seq[ev.seq] = (p.x, p.y)
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

    def interaction_rect(self, module_id: str) -> dict[str, float] | None:
        m = self._placed_module(module_id)
        if m is None:
            return None
        margin = INTERACTION_MARGIN
        return {
            "x": m.x - margin,
            "y": m.y - margin,
            "w": m.w + 2 * margin,
            "h": m.h + 2 * margin,
        }

    def actor_position(self, participant_id: str) -> dict[str, float] | None:
        p = self.participants.get(participant_id)
        if p is None:
            return None
        return {"x": p.x, "y": p.y}

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
            raise PartyWorld.NotInRangeError(module_id)

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
            raise PartyWorld.LimitReachedError(module_id)
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
                    raise PartyWorld.NotAuthorError(note_id)
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
                    raise PartyWorld.NotAuthorError(note_id)
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
            cleared_ev = BoardClearedEvent(
                seq=self._next_seq(),
                module_id=module_id,
                cleared_by=voter_id or "system",
                at=now,
            )
            self._events.append(cleared_ev)
            self._emit(cleared_ev)
            post_needed = (len(population) // 2) + 1 if population else 1
            tally_ev = VoteChangedEvent(
                seq=self._next_seq(),
                module_id=module_id,
                votes=0,
                needed=post_needed,
                at=now,
            )
            self._events.append(tally_ev)
            self._emit(tally_ev)
            self._last_vote_state[module_id] = (0, post_needed)
            return {"votes": 0, "needed": post_needed, "cleared": True}
        state = (active, needed)
        if self._last_vote_state.get(module_id) != state:
            self._last_vote_state[module_id] = state
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
        # Always re-tally after movement / join / leave: the displayed needed
        # depends on in-zone population, and the dedupe inside
        # _tally_and_maybe_clear keeps this from emitting duplicate events.
        for module_id in list(self.votes_by_module.keys()):
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

    def _participants_visible_to(self, requester_id: str) -> list[dict]:
        """Project participants the requester can see (within radius).

        Includes the requester themselves — they need their own avatar in the
        snapshot. (``_participants_in_range_for`` excludes self, since it feeds
        the proximity diff, which is about *others* entering/leaving range.)
        """
        req = self.participants.get(requester_id)
        if req is None:
            return []
        out: list[dict] = []
        for p in self.participants.values():
            if p.id == requester_id or within_proximity(
                (req.x, req.y), (p.x, p.y)
            ):
                out.append(self._participant_dict(p))
        return out

    def _modules_in_rect_for(self, requester_id: str) -> set[str]:
        req = self.participants.get(requester_id)
        if req is None:
            return set()
        out: set[str] = set()
        for m in self._party.modules:
            if isinstance(m, (StickyNoteModule, DrawBoardModule)):
                if self.in_zone(m.id, req.x, req.y):
                    out.add(m.id)
        return out

    def _participants_in_range_for(self, requester_id: str) -> set[str]:
        req = self.participants.get(requester_id)
        if req is None:
            return set()
        return {
            p.id
            for p in self.participants.values()
            if p.id != requester_id and within_proximity(
                (req.x, req.y), (p.x, p.y)
            )
        }

    def _module_stub(self, full: dict) -> dict:
        """Strip live state from a module the requester is not inside.

        Keeps placement / approachSlots so agents can navigate toward it, but
        omits ``notes``/``strokes``/``vote`` so distant module state stays
        hidden (fixes the noteboard-at-distance bug).
        """
        return {
            k: v for k, v in full.items()
            if k not in ("notes", "strokes", "vote")
        }

    def scoped_snapshot(self, requester_id: str) -> dict:
        """``snapshot()`` filtered to what the requester can see.

        Also seeds the proximity tracker so subsequent ``observe_since_scoped``
        polls start from the correct baseline (rather than treating everything
        as a fresh "entry").
        """
        base = self.snapshot()
        base["participants"] = self._participants_visible_to(requester_id)
        in_rect = self._modules_in_rect_for(requester_id)
        base["modules"] = [
            m if m["id"] in in_rect else self._module_stub(m)
            for m in base["modules"]
        ]
        # Seed tracker so the next ?since= poll doesn't re-fire snapshot events
        # for participants/modules already visible in this snapshot.
        tracker = self._proximity_trackers.setdefault(
            requester_id, ProximityTracker()
        )
        tracker.commit(
            participants_in_range=self._participants_in_range_for(requester_id),
            modules_in_rect=in_rect,
            cursor=self.cursor,
        )
        return base

    def _participant_recent_chat(
        self, participant_id: str, limit: int
    ) -> list[dict]:
        """Return up to ``limit`` most-recent chats from ``participant_id``,
        oldest-first.

        Deliberately NOT filtered by the requester's cursor: the requester may
        never have seen these chats if they were out of range when they were
        sent, so a proximity-entry snapshot catches them up on all recent
        messages from the participant they just walked up to.
        """
        out: list[dict] = []
        for ev in reversed(self._events):
            if (
                isinstance(ev, ChatEvent)
                and ev.actor_id == participant_id
            ):
                out.append(ev.model_dump())
                if len(out) >= limit:
                    break
        out.reverse()
        return out

    def observe_since_scoped(self, since: int, requester_id: str) -> dict:
        """``observe_since`` filtered to what the requester can see.

        Composed of two concerns, each in its own helper:
        - ``_scoped_event_tail`` — the real events since ``since``, filtered
          and coalesced to what the requester can see.
        - ``_proximity_transition_events`` — synthetic ``proximity_snapshot`` /
          ``proximity_left`` events for whoever entered/left range this poll.
        """
        if since < 0:
            since = 0
        req = self.participants.get(requester_id)
        if req is None:
            # Requester left mid-poll — return unscoped tail.
            return self.observe_since(since)

        tracker = self._proximity_trackers.setdefault(
            requester_id, ProximityTracker()
        )

        out = self._scoped_event_tail(self._events[since:], req)

        transitions, now_participants, now_modules = (
            self._proximity_transition_events(requester_id, tracker)
        )
        out.extend(transitions)

        out.sort(key=lambda e: e["seq"])

        # Update tracker AFTER diff so subsequent polls start from new state.
        tracker.commit(
            participants_in_range=now_participants,
            modules_in_rect=now_modules,
            cursor=self.cursor,
        )

        return {"events": out, "cursor": self.cursor}

    def _scoped_event_tail(
        self, tail: list[Event], req: Participant
    ) -> list[dict]:
        """Filter + coalesce real events to what ``req`` can see.

        Moves coalesce to the actor's latest position; votes coalesce per
        module; chat/reaction are scoped by the actor's position when emitted;
        module events require the requester to be in the module's rect; leaves
        always pass; ``room_wide`` events bypass all proximity filters.
        """
        latest_move_by_pid: dict[str, MoveEvent] = {}
        latest_vote_by_module: dict[str, VoteChangedEvent] = {}
        out: list[dict] = []
        req_pos = (req.x, req.y)

        for ev in tail:
            room_wide = getattr(ev, "room_wide", False)

            if isinstance(ev, MoveEvent):
                # Coalesce to latest, scope by actor's final move position.
                if room_wide or within_proximity(req_pos, (ev.x, ev.y)):
                    latest_move_by_pid[ev.actor_id] = ev
                continue

            if isinstance(ev, VoteChangedEvent):
                # room_wide by default — still coalesce.
                latest_vote_by_module[ev.module_id] = ev
                continue

            if isinstance(ev, (ChatEvent, ReactionEvent)):
                if not room_wide:
                    pos = self._actor_pos_at_seq.get(ev.seq)
                    if pos is None or not within_proximity(req_pos, pos):
                        continue
                out.append(ev.model_dump())
                continue

            if isinstance(
                ev,
                (NoteCreatedEvent, NoteUpdatedEvent, NoteDeletedEvent,
                 StrokeAddedEvent, StrokeDroppedEvent),
            ):
                # Module-scoped events: only delivered if requester is inside
                # the module's interactionRect right now.
                if self.in_zone(ev.module_id, req.x, req.y):
                    out.append(ev.model_dump())
                continue

            if isinstance(ev, JoinEvent):
                if within_proximity(req_pos, (ev.x, ev.y)):
                    out.append(ev.model_dump())
                continue

            if isinstance(ev, LeaveEvent):
                # Always deliver leave so requester can clean up local state —
                # clients can ignore unknown ids.
                out.append(ev.model_dump())
                continue

            # Default: room_wide or unrecognized → pass through.
            if room_wide:
                out.append(ev.model_dump())

        for mv in latest_move_by_pid.values():
            d = mv.model_dump()
            d["zone"] = self.derive_zone(mv.x, mv.y)
            out.append(d)
        for v in latest_vote_by_module.values():
            out.append(v.model_dump())
        return out

    def _proximity_transition_events(
        self, requester_id: str, tracker: ProximityTracker
    ) -> tuple[list[dict], set[str], set[str]]:
        """Build one-shot proximity_snapshot/proximity_left events for whoever
        entered or left the requester's range since the last poll.

        Returns ``(events, now_participants, now_modules)`` so the caller can
        commit the tracker without recomputing the in-range sets.

        Synthetic ``seq`` values are derived from the current cursor purely to
        order these events after the real tail within THIS poll's response.
        They are ephemeral — never written to the real event log — so they
        carry no cross-poll meaning (a caveat to revisit under concurrency).
        """
        now_participants = self._participants_in_range_for(requester_id)
        now_modules = self._modules_in_rect_for(requester_id)
        entered_p, left_p, entered_m, left_m = tracker.diff(
            now_participants, now_modules
        )
        out: list[dict] = []
        synthetic_seq = self.cursor
        now_ts = time.time()

        for module_id in sorted(entered_m):
            m = self._placed_module(module_id)
            if m is None:
                continue
            synthetic_seq += 1
            out.append(
                {
                    "type": "proximity_snapshot",
                    "seq": synthetic_seq,
                    "at": now_ts,
                    "entered": {"kind": "module", "id": module_id},
                    "module": self._module_snapshot(m),
                    "recent_chat": None,
                    "room_wide": False,
                }
            )
        for other_id in sorted(entered_p):
            synthetic_seq += 1
            out.append(
                {
                    "type": "proximity_snapshot",
                    "seq": synthetic_seq,
                    "at": now_ts,
                    "entered": {"kind": "participant", "id": other_id},
                    "module": None,
                    "recent_chat": self._participant_recent_chat(
                        other_id, limit=PROXIMITY_SNAPSHOT_CHAT_LIMIT
                    ),
                    "room_wide": False,
                }
            )
        for module_id in sorted(left_m):
            synthetic_seq += 1
            out.append(
                {
                    "type": "proximity_left",
                    "seq": synthetic_seq,
                    "at": now_ts,
                    "left": {"kind": "module", "id": module_id},
                    "room_wide": False,
                }
            )
        for other_id in sorted(left_p):
            synthetic_seq += 1
            out.append(
                {
                    "type": "proximity_left",
                    "seq": synthetic_seq,
                    "at": now_ts,
                    "left": {"kind": "participant", "id": other_id},
                    "room_wide": False,
                }
            )
        return out, now_participants, now_modules

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

    def recent_chat(self, limit: int = RECENT_CHAT_LIMIT) -> list[dict]:
        out: list[dict] = []
        for ev in reversed(self._events):
            if isinstance(ev, ChatEvent):
                out.append(ev.model_dump())
                if len(out) >= limit:
                    break
        out.reverse()
        return out

    def observe_since(self, since: int) -> dict:
        if since < 0:
            since = 0
        tail = self._events[since:]
        latest_move_by_actor: dict[str, MoveEvent] = {}
        latest_vote_by_module: dict[str, VoteChangedEvent] = {}
        out: list[dict] = []
        for ev in tail:
            if isinstance(ev, MoveEvent):
                latest_move_by_actor[ev.actor_id] = ev
                continue
            if isinstance(ev, VoteChangedEvent):
                latest_vote_by_module[ev.module_id] = ev
                continue
            out.append(ev.model_dump())
        for mv in latest_move_by_actor.values():
            d = mv.model_dump()
            d["zone"] = self.derive_zone(mv.x, mv.y)
            out.append(d)
        for v in latest_vote_by_module.values():
            out.append(v.model_dump())
        out.sort(key=lambda e: e["seq"])
        return {"events": out, "cursor": self.cursor}
