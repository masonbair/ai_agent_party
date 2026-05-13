from dataclasses import dataclass

from app.models import Wall, WorldSize

# Avatar treated as a point + walls inflated by this radius.
# Keep in sync with AVATAR_RADIUS in frontend/src/hooks/useMovement.ts.
AVATAR_RADIUS = 14


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


def inflate_walls(walls: list[Wall], world: WorldSize) -> list[Rect]:
    rects: list[Rect] = []
    for w in walls:
        left = (w.x / 100.0) * world.width - AVATAR_RADIUS
        top = (w.y / 100.0) * world.height - AVATAR_RADIUS
        right = ((w.x + w.width) / 100.0) * world.width + AVATAR_RADIUS
        bottom = ((w.y + w.height) / 100.0) * world.height + AVATAR_RADIUS
        rects.append(Rect(left=left, top=top, right=right, bottom=bottom))
    return rects


def _is_blocked(x: float, y: float, rects: list[Rect]) -> bool:
    for r in rects:
        if r.left < x < r.right and r.top < y < r.bottom:
            return True
    return False


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def slide(
    from_pt: tuple[float, float],
    to_pt: tuple[float, float],
    rects: list[Rect],
    world: WorldSize,
) -> tuple[float, float]:
    fx, fy = from_pt
    tx, ty = to_pt
    nx, ny = tx, ty
    if _is_blocked(nx, ny, rects):
        if not _is_blocked(tx, fy, rects):
            ny = fy
        elif not _is_blocked(fx, ty, rects):
            nx = fx
        else:
            nx, ny = fx, fy
    nx = _clamp(nx, 0.0, float(world.width))
    ny = _clamp(ny, 0.0, float(world.height))
    return (nx, ny)
