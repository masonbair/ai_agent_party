"""Per-principal DM inbox fan-out.

Mirrors the shape of :class:`PartyWorldHub` / :class:`SessionPresenceHub`:
one socket per ``principal_key``; a second subscribe evicts the prior
socket with ``{type:"evicted","reason":"takeover"}``.

``publish(principal_key, frame)`` is called synchronously from the HTTP
route handler that wrote the DM. The frame is dispatched to the
subscribed socket if any; if no socket is subscribed for that principal
the publish is a no-op (the recipient will see the message via HTTP
history on next connect).
"""

from __future__ import annotations

import asyncio
from typing import Protocol


class SocketLike(Protocol):
    async def send_json(self, payload: dict) -> None: ...

    async def close(self) -> None: ...


class InboxHub:
    def __init__(self) -> None:
        self._by_principal: dict[str, SocketLike] = {}
        self._pending: list[asyncio.Task] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def _capture_loop(self) -> None:
        if self._loop is not None:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def subscribe(self, sock: SocketLike, principal_key: str) -> None:
        self._capture_loop()
        old = self._by_principal.get(principal_key)
        if old is not None and old is not sock:
            self._dispatch(self._send_evict_and_close(old))
        self._by_principal[principal_key] = sock

    def unsubscribe(self, sock: SocketLike, principal_key: str) -> None:
        if self._by_principal.get(principal_key) is sock:
            del self._by_principal[principal_key]

    def publish(self, principal_key: str, frame: dict) -> None:
        self._capture_loop()
        sock = self._by_principal.get(principal_key)
        if sock is None:
            return
        self._dispatch(self._send_or_drop(sock, principal_key, frame))

    async def _send_or_drop(
        self, sock: SocketLike, principal_key: str, frame: dict
    ) -> None:
        try:
            await sock.send_json(frame)
        except Exception:
            if self._by_principal.get(principal_key) is sock:
                del self._by_principal[principal_key]
            try:
                await sock.close()
            except Exception:
                pass

    async def _send_evict_and_close(self, sock: SocketLike) -> None:
        try:
            await sock.send_json({"type": "evicted", "reason": "takeover"})
        except Exception:
            pass
        try:
            await sock.close()
        except Exception:
            pass

    def _dispatch(self, coro) -> None:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None:
            self._pending.append(running.create_task(coro))
        elif self._loop is not None:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            coro.close()

    async def drain(self) -> None:
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        await asyncio.gather(*pending, return_exceptions=True)
