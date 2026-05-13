from __future__ import annotations

from typing import Iterable, Protocol

from app.world import PartyWorld


class StoreLike(Protocol):
    def worlds(self) -> Iterable[PartyWorld]: ...


class SessionPresenceHub:
    """Tracks one live WebSocket per ``session_id``. Filled in by Task 2."""

    def __init__(self, store: StoreLike) -> None:
        self._store = store
