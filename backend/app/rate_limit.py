"""Token-bucket rate limiters.

Two implementations coexist here:

- ``RateLimiter`` (spec #03) is keyed by ``(party, actor, scope)`` and powers
  the /chat cooldown with per-scope burst/refill configs.
- ``TokenBucketRegistry`` (spec #05) is keyed by ``(scope, actor)`` and powers
  /gesture, /cosmetic, and any future per-actor scopes.

Both are pure-Python, in-memory, side-effect free. Routes call ``try_consume``
and translate the result into a 429 envelope themselves.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable


# -------- Spec #03: chat rate limiter --------------------------------------

@dataclass(frozen=True)
class BucketConfig:
    burst: int
    refill_seconds: float


# Deepened cooldown (2026-06-03): no bursting; ~1 message / 4s for proximity
# chat, slower for room-wide. Keeps crowded rooms readable.
CHAT_BUCKETS: dict[str, BucketConfig] = {
    "proximity": BucketConfig(burst=1, refill_seconds=4.0),
    "room": BucketConfig(burst=1, refill_seconds=8.0),
}


class RateLimiter:
    def __init__(
        self,
        configs: dict[str, BucketConfig],
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._configs = configs
        self._now = now
        # key -> (tokens_float, last_refill_timestamp)
        self._buckets: dict[tuple[str, str, str], tuple[float, float]] = {}

    def _key(self, party: str, actor: str, scope: str) -> tuple[str, str, str]:
        return (party, actor, scope)

    def try_consume(
        self, party: str, actor: str, scope: str
    ) -> tuple[bool, int]:
        """Attempt to consume one token. Returns (allowed, retry_after_ms).

        retry_after_ms is 0 when allowed, otherwise the ms until the next
        whole token refills.
        """
        cfg = self._configs.get(scope)
        if cfg is None:
            # Unknown scope is treated as always-allowed; callers should
            # validate scope before getting here.
            return (True, 0)
        now = self._now()
        key = self._key(party, actor, scope)
        tokens, last = self._buckets.get(key, (float(cfg.burst), now))
        # Refill: 1 token per refill_seconds, capped at burst.
        elapsed = max(0.0, now - last)
        tokens = min(float(cfg.burst), tokens + elapsed / cfg.refill_seconds)
        if tokens >= 1.0:
            tokens -= 1.0
            self._buckets[key] = (tokens, now)
            return (True, 0)
        # Not enough; tell the caller how long until 1 token refills.
        needed = 1.0 - tokens
        wait_seconds = needed * cfg.refill_seconds
        self._buckets[key] = (tokens, now)
        return (False, int(round(wait_seconds * 1000)))


_DEFAULT: RateLimiter | None = None


def chat_limiter() -> RateLimiter:
    """Process-wide singleton used by the /chat route."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = RateLimiter(configs=CHAT_BUCKETS)
    return _DEFAULT


def reset_chat_limiter_for_tests() -> None:
    """Tests must call this in setup to avoid state bleed across cases."""
    global _DEFAULT
    _DEFAULT = None


# -------- Spec #05: per-actor scope registry (gestures, cosmetics, etc.) ----

class RateLimitScope(StrEnum):
    CHAT = "chat"
    GESTURE = "gesture"
    COSMETIC = "cosmetic"


@dataclass
class ConsumeResult:
    ok: bool
    retry_after_ms: int = 0


@dataclass
class _BucketConfig:
    burst: int
    refill_per_second: float


@dataclass
class _BucketState:
    tokens: float
    last_refill: float = field(default_factory=time.time)


class TokenBucketRegistry:
    """Registry of per-(scope, actor_id) token buckets.

    Usage::

        reg = TokenBucketRegistry()
        reg.configure_defaults()
        result = reg.try_consume("gesture", actor_id="agent-42")
        if not result.ok:
            # back off for result.retry_after_ms milliseconds
    """

    def __init__(self) -> None:
        self._configs: dict[str, _BucketConfig] = {}
        self._buckets: dict[tuple[str, str], _BucketState] = {}

    def configure(
        self,
        scope: str,
        *,
        burst: int,
        refill_per_second: float,
    ) -> None:
        """Register (or update) a scope's bucket parameters."""
        self._configs[scope] = _BucketConfig(
            burst=burst,
            refill_per_second=refill_per_second,
        )

    def configure_defaults(self) -> None:
        """Register all known scopes with their default parameters."""
        self.configure(RateLimitScope.CHAT.value, burst=10, refill_per_second=2.0)
        self.configure(
            RateLimitScope.GESTURE.value,
            burst=3,
            refill_per_second=0.5,  # 1 token per 2 seconds
        )
        self.configure(
            RateLimitScope.COSMETIC.value,
            burst=1,
            refill_per_second=0.1,  # 1 token per 10 seconds
        )

    def _refill(self, state: _BucketState, config: _BucketConfig) -> None:
        now = time.time()
        elapsed = now - state.last_refill
        state.tokens = min(
            config.burst,
            state.tokens + elapsed * config.refill_per_second,
        )
        state.last_refill = now

    def try_consume(self, scope: str, *, actor_id: str) -> ConsumeResult:
        """Attempt to consume one token from the bucket for ``(scope, actor_id)``.

        Returns a ``ConsumeResult`` with ``ok=True`` on success or
        ``ok=False`` with a ``retry_after_ms`` hint on failure.
        """
        config = self._configs.get(scope)
        if config is None:
            # Unknown scope — allow through (fail open).
            return ConsumeResult(ok=True)

        key = (scope, actor_id)
        state = self._buckets.get(key)
        if state is None:
            state = _BucketState(tokens=float(config.burst))
            self._buckets[key] = state

        self._refill(state, config)

        if state.tokens >= 1.0:
            state.tokens -= 1.0
            return ConsumeResult(ok=True)

        # How long until we have 1 token again.
        deficit = 1.0 - state.tokens
        wait_seconds = deficit / config.refill_per_second
        retry_after_ms = max(1, int(wait_seconds * 1000))
        return ConsumeResult(ok=False, retry_after_ms=retry_after_ms)
"""Token-bucket rate limiter (in-memory, per principal+scope).

Designed to be shared across route modules without copying. Each (scope,
principal_id) pair gets its own bucket. Buckets are stored in the module-level
``_buckets`` dict so tests can clear them between runs.

Usage::

    from app import rate_limit

    allowed = rate_limit.acquire(
        scope="music",
        principal_id=user_id,
        burst=2,
        refill_per_sec=0.2,  # 1 token per 5 seconds
    )
    if not allowed:
        raise HTTPException(status_code=429, ...)
"""

import threading


def _now() -> float:
    """Return current time in seconds. Overridable in tests via monkeypatch."""
    import time
    return time.time()


class RateLimited(Exception):
    """Raised by callers that prefer exception-style over bool-return."""


# ``_buckets[key] = [tokens: float, last_refill_ts: float]``
_buckets: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def acquire(
    scope: str,
    principal_id: str,
    *,
    burst: int,
    refill_per_sec: float,
) -> bool:
    """Try to consume one token from the bucket for (scope, principal_id).

    Returns True if a token was available (request allowed), False if the
    bucket is empty (request should be rate-limited with 429).

    ``burst``          — maximum tokens the bucket can hold (initial fill).
    ``refill_per_sec`` — tokens added per second (fractional OK).
    """
    key = (scope, principal_id)
    now = _now()
    with _lock:
        if key not in _buckets:
            # First call: start with a full bucket minus the token we're about
            # to consume.
            _buckets[key] = [float(burst) - 1.0, now]
            return True

        tokens, last_ts = _buckets[key]
        elapsed = now - last_ts
        tokens = min(float(burst), tokens + elapsed * refill_per_sec)

        if tokens < 1.0:
            _buckets[key] = [tokens, now]
            return False

        _buckets[key] = [tokens - 1.0, now]
        return True
"""Per-principal rate-limit helper.

If spec #03 lands with its own implementation, this module can be replaced or
extended — the public API is just ``check_rate_limit``.
"""

import time

_LAST_HIT: dict[tuple[str, str], float] = {}


def _now() -> float:
    return time.time()


def check_rate_limit(
    bucket: str, key: str, interval_s: float
) -> tuple[bool, float]:
    """Return (allowed, retry_after_ms).

    On allowed=True the call is recorded; on False the existing window remains.
    """
    now = _now()
    last = _LAST_HIT.get((bucket, key))
    if last is None or now - last >= interval_s:
        _LAST_HIT[(bucket, key)] = now
        return True, 0.0
    retry_after_ms = (interval_s - (now - last)) * 1000.0
    return False, retry_after_ms
