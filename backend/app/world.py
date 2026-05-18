import time
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
    StickyNote,
    Stroke,
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
    SLOT_OCCUPIED_RADIUS,
    validate_chat_text,
)


class ParticipantNotInPartyError(LookupError):
    pass


class PartyWorld:
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

    def snapshot(self) -> dict:
        return {
            "participants": [
                self._participant_dict(p) for p in self.participants.values()
            ],
            "cursor": self.cursor,
        }

    def observe_since(self, since: int) -> dict:
        if since < 0:
            since = 0
        tail = self._events[since:]
        latest_move_by_pid: dict[str, MoveEvent] = {}
        out: list[dict] = []
        for ev in tail:
            if isinstance(ev, MoveEvent):
                latest_move_by_pid[ev.participant_id] = ev
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
            elif isinstance(ev, LeaveEvent):
                out.append(
                    {
                        "type": "leave",
                        "seq": ev.seq,
                        "participant_id": ev.participant_id,
                        "at": ev.at,
                    }
                )
            elif isinstance(ev, ChatEvent):
                out.append(
                    {
                        "type": "chat",
                        "seq": ev.seq,
                        "participant_id": ev.participant_id,
                        "text": ev.text,
                        "at": ev.at,
                    }
                )
        for pid, mv in latest_move_by_pid.items():
            out.append(
                {
                    "type": "move",
                    "seq": mv.seq,
                    "participant_id": pid,
                    "x": mv.x,
                    "y": mv.y,
                    "zone": self.derive_zone(mv.x, mv.y),
                    "at": mv.at,
                }
            )
        out.sort(key=lambda e: e["seq"])
        return {"events": out, "cursor": self.cursor}
