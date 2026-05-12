import pytest
from pydantic import ValidationError

from app.models import (
    CreateSessionRequest,
    PartyConfig,
    Room,
    User,
    Wall,
    Zone,
)


def test_create_session_request_accepts_valid() -> None:
    req = CreateSessionRequest(username="Alice42", color="#ff6b9d")
    assert req.username == "Alice42"
    assert req.color == "#ff6b9d"


@pytest.mark.parametrize(
    "username,color",
    [
        ("a", "#ff6b9d"),
        ("bob; DROP", "#ff6b9d"),
        ("Alice", "#000000"),  # not in ALLOWED_COLORS
        ("Alice", "not-a-color"),
    ],
)
def test_create_session_request_rejects_invalid(username: str, color: str) -> None:
    with pytest.raises(ValidationError):
        CreateSessionRequest(username=username, color=color)


def test_user_carries_session_id() -> None:
    user = User(session_id="abc", username="Alice", color="#ff6b9d")
    assert user.session_id == "abc"


def test_party_config_minimum_shape() -> None:
    zone = Zone(
        id="dance",
        label="DANCE",
        x=8.0,
        y=10.0,
        width=34.0,
        height=36.0,
        color="#ff6b9d",
        labelColor="#ffffff",
        borderColor="#8b1a4a",
    )
    cfg = PartyConfig(
        slug="cream-terrazzo",
        name="Cream Terrazzo Lounge",
        description="A bright, friendly party.",
        theme={"floor": "cream", "accent": "#ff6b9d"},
        zones=[zone],
        music={"url": None, "label": "Music coming soon"},
        worldSize={"width": 800, "height": 500},
        room={
            "clipPath": None,
            "border": "6px solid #8b6f47",
            "borderRadius": 12,
            "walls": [
                {"x": 50.0, "y": 0.0, "width": 0.75, "height": 30.0, "color": "#8b6f47"}
            ],
        },
    )
    assert cfg.slug == "cream-terrazzo"
    assert cfg.zones[0].borderColor == "#8b1a4a"
    assert cfg.room.border.startswith("6px")
    assert len(cfg.room.walls) == 1


def test_room_allows_no_walls_and_no_clip_path() -> None:
    room = Room(clipPath=None, border="2px solid black", walls=[])
    assert room.clipPath is None
    assert room.borderRadius is None
    assert room.walls == []


def test_room_accepts_clip_path_string() -> None:
    room = Room(
        clipPath="polygon(0 0, 100% 0, 100% 100%, 0 100%)",
        border="2px solid black",
        walls=[],
    )
    assert "polygon" in room.clipPath


def test_wall_validates_dimensions() -> None:
    w = Wall(x=10.0, y=20.0, width=5.0, height=0.75, color="#000000")
    assert w.x == 10.0
