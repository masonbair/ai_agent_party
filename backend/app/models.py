from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator

from app.validation import ALLOWED_COLORS, USERNAME_REGEX


class CreateSessionRequest(BaseModel):
    username: str
    color: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        if USERNAME_REGEX.fullmatch(v) is None:
            raise ValueError("username must be 2-20 letters/digits")
        return v

    @field_validator("color")
    @classmethod
    def _check_color(cls, v: str) -> str:
        if v not in ALLOWED_COLORS:
            raise ValueError("color must be one of the allowed swatches")
        return v


class User(BaseModel):
    session_id: str
    username: str
    color: str


class Zone(BaseModel):
    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    color: str
    labelColor: str
    borderColor: str


class Theme(BaseModel):
    floor: str
    accent: str


class Music(BaseModel):
    url: str | None
    label: str


class WorldSize(BaseModel):
    width: int
    height: int


class Wall(BaseModel):
    x: float
    y: float
    width: float
    height: float
    color: str


class Room(BaseModel):
    clipPath: str | None = None
    border: str
    borderRadius: int | None = None
    walls: list[Wall]


LightingPreset = Literal["day", "dusk", "night", "party"]


class StickyNoteModule(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    kind: Literal["stickynotes"] = "stickynotes"
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class DrawBoardModule(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    kind: Literal["drawboard"] = "drawboard"
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class LightingModule(BaseModel):
    id: Literal["lighting"] = "lighting"
    kind: Literal["lighting"] = "lighting"
    preset: LightingPreset = "day"


class FreeNotesModule(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    kind: Literal["freenotes"] = "freenotes"


PlacedModule = Union[StickyNoteModule, DrawBoardModule, FreeNotesModule]
Module = Annotated[
    Union[StickyNoteModule, DrawBoardModule, FreeNotesModule, LightingModule],
    Field(discriminator="kind"),
]


class PartyConfig(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    description: str
    theme: Theme
    zones: list[Zone]
    music: Music
    worldSize: WorldSize
    room: Room
    modules: list[Module] = Field(default_factory=list)


class Occupancy(BaseModel):
    humans: int
    agents: int
    total: int
    active_last_5min: int


class PartyListEntry(PartyConfig):
    occupancy: Occupancy


class PartiesListResponse(BaseModel):
    parties: list[PartyListEntry]


class PartyPreviewMusic(BaseModel):
    url: str | None
    label: str


class PartyPreviewChat(BaseModel):
    seq: int
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    text: str
    at: float


class PartyPreviewResponse(BaseModel):
    slug: str
    name: str
    description: str
    occupancy: Occupancy
    lighting: LightingPreset
    music: PartyPreviewMusic
    recent_chat: list[PartyPreviewChat]
