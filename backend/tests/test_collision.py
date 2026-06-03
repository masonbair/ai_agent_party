from app.collision import AVATAR_RADIUS, Rect, inflate_walls, slide, separate, MIN_AVATAR_SEPARATION
from app.models import Wall, WorldSize


def _walls(*tuples: tuple[float, float, float, float]) -> list[Wall]:
    return [
        Wall(x=x, y=y, width=w, height=h, color="#000")
        for (x, y, w, h) in tuples
    ]


def test_inflate_walls_converts_percent_to_world_units_with_radius() -> None:
    world = WorldSize(width=800, height=500)
    walls = _walls((50.0, 0.0, 0.75, 30.0))
    rects = inflate_walls(walls, world)
    assert len(rects) == 1
    r = rects[0]
    assert r.left == 400.0 - AVATAR_RADIUS
    assert r.right == (50.0 + 0.75) / 100 * 800 + AVATAR_RADIUS
    assert r.top == 0.0 - AVATAR_RADIUS
    assert r.bottom == 150.0 + AVATAR_RADIUS


def test_slide_lets_unblocked_moves_through() -> None:
    rects: list[Rect] = []
    world = WorldSize(width=800, height=500)
    p = slide((100.0, 100.0), (200.0, 200.0), rects, world)
    assert p == (200.0, 200.0)


def test_slide_clamps_to_world_bounds() -> None:
    world = WorldSize(width=800, height=500)
    p = slide((100.0, 100.0), (-50.0, 600.0), [], world)
    assert p == (0.0, 500.0)


def test_slide_blocks_target_in_wall_but_keeps_from_position() -> None:
    world = WorldSize(width=800, height=500)
    rects = inflate_walls(_walls((50.0, 0.0, 0.75, 30.0)), world)
    p = slide((300.0, 100.0), (400.0, 100.0), rects, world)
    assert p == (300.0, 100.0)


def test_slide_slides_on_x_axis_when_only_y_is_blocked() -> None:
    world = WorldSize(width=800, height=500)
    rects = [Rect(left=200.0, top=50.0, right=400.0, bottom=300.0)]
    p = slide((150.0, 150.0), (300.0, 200.0), rects, world)
    assert p == (150.0, 200.0)


def test_slide_corner_block_returns_from_position() -> None:
    world = WorldSize(width=800, height=500)
    rects = [
        Rect(left=200.0, top=50.0, right=250.0, bottom=300.0),
        Rect(left=50.0, top=200.0, right=300.0, bottom=250.0),
    ]
    p = slide((150.0, 150.0), (225.0, 225.0), rects, world)
    assert p == (150.0, 150.0)


def test_separate_pushes_apart_overlapping_point():
    # Two avatars 10 units apart (< MIN_AVATAR_SEPARATION) push to >= min.
    moved = separate((100.0, 100.0), [(110.0, 100.0)], MIN_AVATAR_SEPARATION)
    dist = ((moved[0] - 110.0) ** 2 + (moved[1] - 100.0) ** 2) ** 0.5
    assert dist >= MIN_AVATAR_SEPARATION - 1e-6
    # Pushed away from the other avatar (to the left).
    assert moved[0] < 100.0


def test_separate_leaves_distant_point_untouched():
    moved = separate((100.0, 100.0), [(500.0, 500.0)], MIN_AVATAR_SEPARATION)
    assert moved == (100.0, 100.0)


def test_separate_handles_exact_overlap_deterministically():
    moved = separate((100.0, 100.0), [(100.0, 100.0)], MIN_AVATAR_SEPARATION)
    # Nudged by exactly one separation along +x; never NaN.
    assert moved == (100.0 + MIN_AVATAR_SEPARATION, 100.0)
