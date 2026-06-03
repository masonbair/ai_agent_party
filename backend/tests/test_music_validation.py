import pytest
from app.validation import (
    MUSIC_TRACK_ALLOWLIST,
    MUSIC_VOLUME_MIN,
    MUSIC_VOLUME_MAX,
    MusicValidationError,
    validate_music_track,
    validate_music_volume,
    validate_music_action,
)


def test_allowlist_contains_the_five_placeholder_ids():
    assert set(MUSIC_TRACK_ALLOWLIST) == {
        "lofi-loop",
        "jazz-club",
        "synthwave",
        "ambient-1",
        "party-mix",
    }


def test_validate_music_track_accepts_allowed():
    assert validate_music_track("lofi-loop") == "lofi-loop"


def test_validate_music_track_rejects_unknown():
    with pytest.raises(MusicValidationError) as exc:
        validate_music_track("rickroll")
    assert "unknown track" in str(exc.value)


def test_validate_music_track_rejects_empty():
    with pytest.raises(MusicValidationError):
        validate_music_track("")


def test_volume_bounds_constants():
    assert MUSIC_VOLUME_MIN == 0
    assert MUSIC_VOLUME_MAX == 100


@pytest.mark.parametrize("v", [0, 1, 50, 99, 100])
def test_validate_music_volume_accepts_range(v):
    assert validate_music_volume(v) == v


@pytest.mark.parametrize("v", [-1, 101, 200])
def test_validate_music_volume_rejects_out_of_range(v):
    with pytest.raises(MusicValidationError):
        validate_music_volume(v)


def test_validate_music_volume_rejects_non_int():
    with pytest.raises(MusicValidationError):
        validate_music_volume(50.5)  # type: ignore[arg-type]


def test_validate_music_volume_rejects_bool():
    # bool is a subclass of int in Python; we must reject it explicitly.
    with pytest.raises(MusicValidationError):
        validate_music_volume(True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "a", ["play", "pause", "skip", "set_volume"]
)
def test_validate_music_action_accepts_known(a):
    assert validate_music_action(a) == a


def test_validate_music_action_rejects_unknown():
    with pytest.raises(MusicValidationError):
        validate_music_action("stop")
