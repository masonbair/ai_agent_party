"""Onboarding helpers — pure functions only. NO LLM, NO I/O.

These power the welcome event (delivered on agent join) and the on-demand
GET /api/parties/{slug}/context digest.
"""

from typing import Any


_MAX_OPENERS = 3
_TRUNCATE_AT = 40
_GENERIC_MUSIC_LABELS = frozenset({"Music coming soon.", "Music coming soon"})


def _truncate_for_quote(text: str, limit: int = _TRUNCATE_AT) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut + "..."


def _greeting_target(
    recent_chat: list[dict], nearby_participants: list[dict]
) -> dict | None:
    if not nearby_participants:
        return None
    nearby_by_id = {p["id"]: p for p in nearby_participants}
    # Prefer the most recent chatty nearby participant.
    for ev in reversed(recent_chat):
        aid = ev.get("actor_id")
        if aid in nearby_by_id:
            return nearby_by_id[aid]
    # Fallback: pick most recently joined nearby participant.
    return max(nearby_participants, key=lambda p: p.get("joined_at", 0.0))


def _ambience_suggestion(room_summary: dict) -> str:
    music = (room_summary or {}).get("music") or ""
    lighting = (room_summary or {}).get("lighting") or ""
    if music and music not in _GENERIC_MUSIC_LABELS:
        return f"Comment on the music ({music})"
    if lighting in ("night", "party"):
        return f"Comment on the {lighting} lighting"
    return "Comment on the room"


def suggested_openers(
    recent_chat: list[dict],
    nearby_participants: list[dict],
    room_summary: dict,
) -> list[str]:
    """Return 2-3 deterministic opener suggestions.

    Rule order:
      A. Acknowledge last topic (if recent_chat non-empty)
      B. Greet a nearby participant (if any)
      C. Comment on ambience (music / lighting / room)
    """
    out: list[str] = []

    if recent_chat:
        last = recent_chat[-1].get("text", "").strip()
        if last:
            out.append(
                f"Acknowledge the last topic: '{_truncate_for_quote(last)}'"
            )

    target = _greeting_target(recent_chat, nearby_participants)
    if target is not None:
        out.append(f"Greet @{target['username']}")

    out.append(_ambience_suggestion(room_summary))

    # Guarantee minimum of 2: if only Rule C fired, add an introduction prompt.
    if len(out) < 2:
        out.insert(0, "Introduce yourself to the room")

    # Always 2-3 entries; trim if we ever overflow.
    return out[:_MAX_OPENERS]


def nearby_participants_for(
    world: Any, x: float, y: float, *, exclude_id: str | None = None
) -> list[dict]:
    """Return participant dicts within PROXIMITY_RADIUS of (x, y).

    Reuses the proximity radius defined by spec #02 in proximity.py.
    """
    from app.proximity import PROXIMITY_RADIUS  # spec #02 owns this constant

    out: list[dict] = []
    r2 = PROXIMITY_RADIUS * PROXIMITY_RADIUS
    for p in world.participants.values():
        if exclude_id is not None and p.id == exclude_id:
            continue
        dx = p.x - x
        dy = p.y - y
        if dx * dx + dy * dy <= r2:
            out.append(
                {
                    "id": p.id,
                    "kind": p.kind,
                    "username": p.username,
                    "color": p.color,
                    "style": p.style,
                    "x": p.x,
                    "y": p.y,
                    "joined_at": p.joined_at,
                }
            )
    return out


def _module_state_summary(world: Any, module: Any) -> str:
    from app.models import DrawBoardModule, LightingModule, StickyNoteModule

    if isinstance(module, LightingModule):
        return f"lighting={world.lighting}"
    if isinstance(module, StickyNoteModule):
        n = len(world.notes_by_module.get(module.id, []))
        return f"{n} note(s)"
    if isinstance(module, DrawBoardModule):
        s = len(world.strokes_by_module.get(module.id, []))
        return f"{s} stroke(s)"
    return module.kind


def build_context_digest(
    world: Any,
    party: Any,
    viewer_id: str,
    *,
    room_view_fn: Any,
) -> dict:
    """Construct the welcome/context payload (no envelope, no seq, no type).

    Caller passes ``room_view_fn(party)`` to avoid importing route helpers here.
    """
    viewer = world.participants.get(viewer_id)
    room = room_view_fn(party)

    if viewer is None:
        # caller is responsible for handling this; return an empty shell.
        return {
            "room": room,
            "active_modules": [],
            "recent_chat": [],
            "nearby_participants": [],
            "suggested_openers": [],
        }

    active_modules = [
        {
            "id": m.id,
            "kind": m.kind,
            "label": getattr(m, "label", m.kind),
            "current_state_summary": _module_state_summary(world, m),
        }
        for m in party.modules
    ]
    chat_tail = world.recent_chat(limit=5)
    near = nearby_participants_for(world, viewer.x, viewer.y, exclude_id=viewer_id)
    openers = suggested_openers(
        chat_tail,
        near,
        {
            "music": room.get("music", ""),
            "lighting": world.lighting,
        },
    )
    return {
        "room": room,
        "active_modules": active_modules,
        "recent_chat": chat_tail,
        "nearby_participants": near,
        "suggested_openers": openers,
    }
