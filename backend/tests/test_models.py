import pytest
from pydantic import ValidationError

from app.models import CreateSessionRequest, PartyConfig, User, Zone


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
        x=25.0,
        y=25.0,
        width=40.0,
        height=36.0,
        color="rgba(255,107,157,0.25)",
        labelColor="#8b1a4a",
    )
    cfg = PartyConfig(
        slug="cream-terrazzo",
        name="Cream Terrazzo Lounge",
        description="A bright, friendly party.",
        theme={"floor": "cream", "accent": "#ff6b9d"},
        zones=[zone],
        music={"url": None, "label": "Music coming soon"},
        worldSize={"width": 800, "height": 500},
    )
    assert cfg.slug == "cream-terrazzo"
    assert cfg.zones[0].id == "dance"
