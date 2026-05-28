"""Push WebSocket: /api/parties/{slug}/observe/ws.

Handshake:
  - server accept()s
  - client sends {"type":"auth","principal":{"kind":..., "id":...}}
  - server validates -> sends {"type":"initial", ...} -> subscribes
  - on auth failure: server closes with code 4401, reason JSON
    {"error":"unauthorized"}

After subscribe:
  - server pushes per-event frames {"type":"event","event":{...},"cursor":N}
  - proximity_snapshot / proximity_left synthetic frames same as /observe
  - heartbeat: server sends {"type":"ping"} every 20s; client must
    reply {"type":"pong"} within 30s or socket closes

Multiple concurrent sockets per principal are permitted (one per tab/
agent process) — each gets its own cursor and proximity tracker.
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.dm import principal_key
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter()

HEARTBEAT_INTERVAL = 20.0  # seconds between pings
HEARTBEAT_TIMEOUT = 30.0   # seconds without pong before close


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


_UNAUTHORIZED_CODE = 4401


def _resolve_auth(store: Store, frame: object):
    if not isinstance(frame, dict) or frame.get("type") != "auth":
        return None, "invalid_auth_frame"
    raw = frame.get("principal")
    if not isinstance(raw, dict):
        return None, "invalid_principal"
    try:
        principal = Principal(**raw)
    except (ValidationError, TypeError):
        return None, "invalid_principal"
    try:
        resolved = resolve_principal(store, principal)
    except Exception:
        return None, "principal_unknown"
    return resolved, None


def _room_view(party) -> dict:
    w = party.worldSize
    return {
        "slug": party.slug,
        "name": party.name,
        "worldSize": {"width": w.width, "height": w.height},
        "zones": [
            {
                "id": z.id, "label": z.label,
                "x": z.x, "y": z.y, "width": z.width, "height": z.height,
                "centerX": (z.x + z.width / 2.0) / 100.0 * w.width,
                "centerY": (z.y + z.height / 2.0) / 100.0 * w.height,
            }
            for z in party.zones
        ],
        "walls": [
            {"x": wl.x, "y": wl.y, "width": wl.width, "height": wl.height}
            for wl in party.room.walls
        ],
        "music": party.music.label,
        "modules": [
            {
                "id": m.id, "kind": m.kind,
                **(
                    {"x": m.x, "y": m.y, "w": m.w, "h": m.h}
                    if m.kind in ("stickynotes", "drawboard") else {}
                ),
                **({"preset": m.preset} if m.kind == "lighting" else {}),
            }
            for m in party.modules
        ],
    }


async def _close_unauthorized(ws: WebSocket, reason: str = "unauthorized") -> None:
    payload = json.dumps({"error": reason})
    try:
        await ws.close(code=_UNAUTHORIZED_CODE, reason=payload)
    except Exception:
        pass


@router.websocket("/api/parties/{slug}/observe/ws")
async def observe_ws(
    websocket: WebSocket,
    slug: str,
    store: Store = Depends(_store_dep),
) -> None:
    party = store.get_party(slug)
    if party is None:
        await websocket.accept()
        await _close_unauthorized(websocket, reason="party_not_found")
        return

    await websocket.accept()
    try:
        frame = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception:
        await _close_unauthorized(websocket, reason="invalid_auth_frame")
        return

    resolved, reason = _resolve_auth(store, frame)
    if resolved is None:
        await _close_unauthorized(websocket, reason=reason or "unauthorized")
        return

    world = store.get_or_create_world(slug)
    assert world is not None
    if resolved.id not in world.participants:
        await _close_unauthorized(websocket, reason="not_in_party")
        return

    snap = world.snapshot()
    initial = {
        "type": "initial",
        "room": _room_view(party),
        "participants": snap["participants"],
        "modules": snap["modules"],
        "lighting": snap["lighting"],
        "active_reactions": snap["active_reactions"],
        "recent_chat": world.recent_chat(),
        "cursor": snap["cursor"],
    }
    await websocket.send_json(initial)

    hub = store.get_or_create_observer_hub(slug)
    assert hub is not None
    key = principal_key(resolved)
    hub.subscribe(
        websocket, principal_key=key, participant_id=resolved.id
    )

    last_pong = time.monotonic()

    async def _heartbeat() -> None:
        nonlocal last_pong
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    return
                if time.monotonic() - last_pong > HEARTBEAT_TIMEOUT:
                    try:
                        await websocket.close(code=1011, reason="pong_timeout")
                    except Exception:
                        pass
                    return
        except asyncio.CancelledError:
            return

    async def _read_loop() -> None:
        nonlocal last_pong
        try:
            while True:
                msg = await websocket.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "pong":
                    last_pong = time.monotonic()
        except WebSocketDisconnect:
            return
        except Exception:
            return

    hb = asyncio.create_task(_heartbeat())
    rl = asyncio.create_task(_read_loop())
    try:
        done, pending = await asyncio.wait(
            {hb, rl}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        for t in pending:
            try:
                await t
            except Exception:
                pass
    finally:
        hub.unsubscribe(websocket)
        try:
            await websocket.close()
        except Exception:
            pass
