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


class PartyConfig(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    description: str
    theme: Theme
    zones: list[Zone]
    music: Music
    worldSize: WorldSize
    room: Room


class PartiesListResponse(BaseModel):
    parties: list[PartyConfig]
