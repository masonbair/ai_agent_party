import time

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


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class PartyWorld:
    def __init__(self, party: PartyConfig) -> None:
        self._party = party
        self.participants: dict[str, Participant] = {}
        self._events: list[Event] = []

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
        return ev

    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        del self.participants[participant_id]
        ev = LeaveEvent(seq=self._next_seq(), participant_id=participant_id, at=time.time())
        self._events.append(ev)
        return ev

    def move(self, participant_id: str, x: float, y: float) -> MoveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        w = self._party.worldSize
        cx = _clamp(float(x), 0.0, float(w.width))
        cy = _clamp(float(y), 0.0, float(w.height))
        current = self.participants[participant_id]
        self.participants[participant_id] = current.model_copy(
            update={"x": cx, "y": cy}
        )
        ev = MoveEvent(seq=self._next_seq(), participant_id=participant_id, x=cx, y=cy, at=time.time())
        self._events.append(ev)
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
