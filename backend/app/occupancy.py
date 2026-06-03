"""Compute a public occupancy summary for a PartyWorld.

Used by:
- ``GET /api/parties`` (per-entry ``occupancy``)
- ``GET /api/parties/{slug}/preview`` (top-level ``occupancy``)

"active in the last 5 minutes" is derived from the world's event log: any
participant currently in the room who has produced a ``join``, ``move``,
``chat``, or ``reaction`` event with ``at >= now - 300``. We intentionally
do NOT consult walls / proximity here — this is a coarse room-wide stat.
"""
from __future__ import annotations

from app.events import ChatEvent, JoinEvent, MoveEvent, ReactionEvent
from app.world import PartyWorld

ACTIVE_WINDOW_SECONDS = 300.0


def compute_occupancy(world: PartyWorld, *, now: float) -> dict:
    humans = 0
    agents = 0
    for p in world.participants.values():
        if p.kind == "human":
            humans += 1
        elif p.kind == "agent":
            agents += 1
    total = humans + agents

    if total == 0:
        return {"humans": 0, "agents": 0, "total": 0, "active_last_5min": 0}

    threshold = now - ACTIVE_WINDOW_SECONDS
    present_ids = set(world.participants.keys())
    active: set[str] = set()
    # Walk events newest-first; bail once we cross the threshold.
    for ev in reversed(world.events):
        if ev.at < threshold:
            break
        actor_id: str | None = None
        if isinstance(ev, JoinEvent):
            actor_id = ev.actor_id
        elif isinstance(ev, (MoveEvent, ChatEvent)):
            actor_id = ev.actor_id
        elif isinstance(ev, ReactionEvent):
            actor_id = ev.actor_id
        if actor_id is not None and actor_id in present_ids:
            active.add(actor_id)
        if len(active) == total:
            break

    return {
        "humans": humans,
        "agents": agents,
        "total": total,
        "active_last_5min": len(active),
    }
