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
        ev = JoinEvent(seq=self._next_seq(), participant=participant)
        self._events.append(ev)
        return ev

    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        del self.participants[participant_id]
        ev = LeaveEvent(seq=self._next_seq(), participant_id=participant_id)
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
        ev = MoveEvent(seq=self._next_seq(), participant_id=participant_id, x=cx, y=cy)
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
