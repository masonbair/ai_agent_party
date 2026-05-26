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


class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    at: float


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    x: float
    y: float
    at: float


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    text: str
    at: float


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
    emoji: str
    expires_at: float
    at: float


class LightingChangedEvent(BaseModel):
    seq: int
    type: Literal["lighting_changed"] = "lighting_changed"
    preset: Literal["day", "dusk", "night", "party"]
    changed_by: str
    at: float


class NoteCreatedEvent(BaseModel):
    seq: int
    type: Literal["note_created"] = "note_created"
    module_id: str
    note: StickyNote
    at: float


class NoteUpdatedEvent(BaseModel):
    seq: int
    type: Literal["note_updated"] = "note_updated"
    module_id: str
    note: StickyNote
    at: float


class NoteDeletedEvent(BaseModel):
    seq: int
    type: Literal["note_deleted"] = "note_deleted"
    module_id: str
    note_id: str
    at: float


class StrokeAddedEvent(BaseModel):
    seq: int
    type: Literal["stroke_added"] = "stroke_added"
    module_id: str
    stroke: Stroke
    at: float


class StrokeDroppedEvent(BaseModel):
    seq: int
    type: Literal["stroke_dropped"] = "stroke_dropped"
    module_id: str
    stroke_id: str
    at: float


class BoardClearedEvent(BaseModel):
    seq: int
    type: Literal["board_cleared"] = "board_cleared"
    module_id: str
    cleared_by: str
    at: float


class VoteChangedEvent(BaseModel):
    seq: int
    type: Literal["vote_changed"] = "vote_changed"
    module_id: str
    votes: int
    needed: int
    at: float


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
)
