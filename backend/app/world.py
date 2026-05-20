import sqlite3
import time
from typing import Callable

from app import db as db_module
from app.collision import Rect, inflate_walls, slide
from app.events import (
    ChatEvent,
    Event,
    JoinEvent,
    LeaveEvent,
    MoveEvent,
    Participant,
)
from app.models import PartyConfig
from app.validation import validate_chat_text


class ParticipantNotInPartyError(LookupError):
    pass


class PartyWorld:
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
            participant_id=participant_id,
            text=cleaned,
            at=at,
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

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
