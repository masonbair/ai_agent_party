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
    participant: Participant
    at: float


class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    participant_id: str
    at: float


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    participant_id: str
    x: float
    y: float
    at: float


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    participant_id: str
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


Event = JoinEvent | LeaveEvent | MoveEvent | ChatEvent
