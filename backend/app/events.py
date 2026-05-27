from typing import Literal

from pydantic import BaseModel


class Participant(BaseModel):
    id: str
    kind: Literal["human", "agent"]
    username: str
    color: str
    x: float
    y: float
    joined_at: float


class Agent(BaseModel):
    agent_id: str
    username: str
    color: str


class JoinEvent(BaseModel):
    seq: int
    type: Literal["join"] = "join"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    x: float
    y: float
    zone: str | None = None
    at: float
    room_wide: bool = False


class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    actor_color: str | None = None
    at: float
    room_wide: bool = False


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    actor_color: str | None = None
    x: float
    y: float
    at: float
    room_wide: bool = False


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    actor_color: str | None = None
    text: str
    at: float
    room_wide: bool = False


class StickyNote(BaseModel):
    id: str
    module_id: str
    author_id: str
    author_kind: Literal["human", "agent"]
    text: str
    color: Literal["yellow", "pink", "blue", "green"]
    x: float
    y: float
    created_at: float


class Stroke(BaseModel):
    id: str
    module_id: str
    author_id: str
    author_kind: Literal["human", "agent"]
    color: str
    width: Literal["thin", "med", "thick"]
    points: list[dict]
    created_at: float


class Reaction(BaseModel):
    actor_id: str
    emoji: str
    expires_at: float


class ReactionEvent(BaseModel):
    seq: int
    type: Literal["reaction"] = "reaction"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    actor_color: str | None = None
    emoji: str
    expires_at: float
    at: float
    room_wide: bool = False


class LightingChangedEvent(BaseModel):
    seq: int
    type: Literal["lighting_changed"] = "lighting_changed"
    preset: Literal["day", "dusk", "night", "party"]
    changed_by: str
    at: float
    room_wide: bool = True  # lighting is a whole-room change


class NoteCreatedEvent(BaseModel):
    seq: int
    type: Literal["note_created"] = "note_created"
    module_id: str
    note: StickyNote
    at: float
    room_wide: bool = False


class NoteUpdatedEvent(BaseModel):
    seq: int
    type: Literal["note_updated"] = "note_updated"
    module_id: str
    note: StickyNote
    at: float
    room_wide: bool = False


class NoteDeletedEvent(BaseModel):
    seq: int
    type: Literal["note_deleted"] = "note_deleted"
    module_id: str
    note_id: str
    at: float
    room_wide: bool = False


class StrokeAddedEvent(BaseModel):
    seq: int
    type: Literal["stroke_added"] = "stroke_added"
    module_id: str
    stroke: Stroke
    at: float
    room_wide: bool = False


class StrokeDroppedEvent(BaseModel):
    seq: int
    type: Literal["stroke_dropped"] = "stroke_dropped"
    module_id: str
    stroke_id: str
    at: float
    room_wide: bool = False


class BoardClearedEvent(BaseModel):
    seq: int
    type: Literal["board_cleared"] = "board_cleared"
    module_id: str
    cleared_by: str
    at: float
    room_wide: bool = True  # visible to everyone — the board snaps clean


class VoteChangedEvent(BaseModel):
    seq: int
    type: Literal["vote_changed"] = "vote_changed"
    module_id: str
    votes: int
    needed: int
    at: float
    room_wide: bool = True  # tally visible to everyone watching the board


class ProposalCreatedEvent(BaseModel):
    seq: int
    type: Literal["proposal_created"] = "proposal_created"
    proposal_id: str
    text: str
    expires_at: float
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    actor_color: str | None = None
    room_wide: bool = True


class ProposalVoteEvent(BaseModel):
    seq: int
    type: Literal["proposal_vote"] = "proposal_vote"
    proposal_id: str
    vote: Literal["yes", "no", "abstain"]
    tallies: dict  # {"yes": int, "no": int, "abstain": int}
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    actor_color: str | None = None
    room_wide: bool = True


class ProposalResolvedEvent(BaseModel):
    seq: int
    type: Literal["proposal_resolved"] = "proposal_resolved"
    proposal_id: str
    text: str
    tallies: dict
    at: float
    room_wide: bool = True


class ProximitySnapshotEvent(BaseModel):
    """One-shot snapshot emitted to a specific requester when they enter
    proximity of a module's interactionRect or another participant.

    Server-side only: NEVER appended to ``PartyWorld._events`` because it is
    per-requester. Constructed on the fly inside ``observe_since_scoped`` and
    injected into that requester's event list.
    """

    seq: int  # mirrors the cursor at emit time so clients can sort/dedupe
    type: Literal["proximity_snapshot"] = "proximity_snapshot"
    at: float
    entered: dict  # {"kind": "module"|"participant", "id": "..."}
    # Populated when entered.kind == "module":
    module: dict | None = None  # full module snapshot (notes/strokes/vote)
    # Populated when entered.kind == "participant":
    recent_chat: list[dict] | None = None  # last N visible chats from them
    room_wide: bool = False


class ProximityLeftEvent(BaseModel):
    """One-shot leave event when the requester walks out of range of a
    participant or out of a module's interactionRect."""

    seq: int
    type: Literal["proximity_left"] = "proximity_left"
    at: float
    left: dict  # {"kind": "module"|"participant", "id": "..."}
    room_wide: bool = False


Event = (
    JoinEvent
    | LeaveEvent
    | MoveEvent
    | ChatEvent
    | ReactionEvent
    | LightingChangedEvent
    | NoteCreatedEvent
    | NoteUpdatedEvent
    | NoteDeletedEvent
    | StrokeAddedEvent
    | StrokeDroppedEvent
    | BoardClearedEvent
    | VoteChangedEvent
    | ProposalCreatedEvent
    | ProposalVoteEvent
    | ProposalResolvedEvent
    | ProximitySnapshotEvent
    | ProximityLeftEvent
)
