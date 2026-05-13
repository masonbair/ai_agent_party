from app.collision import AVATAR_RADIUS, Rect, inflate_walls, slide
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
