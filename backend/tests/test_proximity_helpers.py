import math

from app.world import PROXIMITY_RADIUS, within_proximity


def test_proximity_radius_is_180():
    # Single source of truth — other specs reference this constant.
    assert PROXIMITY_RADIUS == 180.0


def test_within_proximity_zero_distance():
    assert within_proximity((100.0, 100.0), (100.0, 100.0)) is True


def test_within_proximity_just_inside():
    # 179 units east — inside the bubble.
    assert within_proximity((0.0, 0.0), (179.0, 0.0)) is True


def test_within_proximity_just_outside():
    # 181 units east — outside.
    assert within_proximity((0.0, 0.0), (181.0, 0.0)) is False


def test_within_proximity_diagonal():
    # 3-4-5 triangle scaled to ~180 hypotenuse: (108, 144) is exactly 180 away.
    assert within_proximity((0.0, 0.0), (108.0, 144.0)) is True
    # Just past — 109, 145 — distance > 180.
    assert within_proximity((0.0, 0.0), (109.0, 145.0)) is False


def test_within_proximity_ignores_walls():
    # Documentation-as-test: walls do NOT block proximity in v1.
    # The function takes only two points — there is no `walls` parameter.
    # If a future change adds a walls argument, update this test deliberately.
    assert within_proximity((0.0, 0.0), (50.0, 0.0)) is True
