"""Proximity primitives for the scoped observer (spec #02).

The genuinely standalone pieces of the proximity model live here so they can
be imported without pulling in the whole ``PartyWorld``:

- ``PROXIMITY_RADIUS`` / ``PROXIMITY_SNAPSHOT_CHAT_LIMIT`` constants
- ``within_proximity`` — plain Euclidean radius test
- ``ProximityTracker`` — per-requester memory of who/what was in range

The scoped-observe *methods* themselves stay on ``PartyWorld`` (in
``world.py``) because they reach into many of its internals; relocating them
would only leak that coupling across a module boundary.

``world.py`` re-exports ``PROXIMITY_RADIUS`` and ``within_proximity`` so
existing imports (e.g. ``from app.world import PROXIMITY_RADIUS`` in
``agent_guide.py``) keep working. Other specs MUST import the constant rather
than redefining it.
"""

import math

# Proximity radius in world units. See plan #02 for justification.
PROXIMITY_RADIUS = 180.0

# Max recent chats bundled into a participant-entry proximity_snapshot.
PROXIMITY_SNAPSHOT_CHAT_LIMIT = 5


def within_proximity(
    a: tuple[float, float], b: tuple[float, float]
) -> bool:
    """Return True if points ``a`` and ``b`` are within PROXIMITY_RADIUS.

    Plain Euclidean radius. Walls do NOT block — line-of-sight is explicitly
    out of scope for v1 (see ``docs/features/feature-backlog.md`` §6 Owner
    Additions, Open question).
    """
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy) <= PROXIMITY_RADIUS


class ProximityTracker:
    """Per-requester memory of which participants and modules they were in
    range of on their last ``observe_since_scoped`` call.

    Used to detect proximity entry (emit ``proximity_snapshot``) and
    proximity exit (emit ``proximity_left``). Owned by ``PartyWorld``,
    keyed by requester participant id, cleared on ``leave``.
    """

    def __init__(self) -> None:
        self.participants_in_range: set[str] = set()
        self.modules_in_rect: set[str] = set()
        # The cursor at the time of the last poll. Used to bound the
        # ``recent_chat`` slice in a participant-entry snapshot to chats
        # the requester hadn't yet seen.
        self.last_observed_cursor: int = 0

    def diff(
        self,
        participants_in_range: set[str],
        modules_in_rect: set[str],
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        """Compute entered/left sets relative to current state.

        Does NOT auto-commit — call ``commit()`` when you want to persist the
        new state so subsequent diffs start from the updated baseline.
        """
        entered_p = participants_in_range - self.participants_in_range
        left_p = self.participants_in_range - participants_in_range
        entered_m = modules_in_rect - self.modules_in_rect
        left_m = self.modules_in_rect - modules_in_rect
        return entered_p, left_p, entered_m, left_m

    def commit(
        self,
        participants_in_range: set[str],
        modules_in_rect: set[str],
        cursor: int,
    ) -> None:
        self.participants_in_range = set(participants_in_range)
        self.modules_in_rect = set(modules_in_rect)
        self.last_observed_cursor = cursor
