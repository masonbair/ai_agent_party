"""Token-bucket rate limiting for per-actor action scopes.

Each scope (chat, gesture, cosmetic) has its own bucket configuration.
Buckets are keyed by ``(scope, actor_id)`` and are independent across
both dimensions — draining one scope does not affect another, and
draining one actor's bucket does not affect any other actor.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


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
