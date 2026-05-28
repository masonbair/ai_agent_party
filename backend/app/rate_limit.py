"""Generic token-bucket rate limiter keyed by (party_slug, actor_id, scope).

Used by /chat (spec #03) and the batched /act endpoint (spec #10). Keep it
pure-Python and side-effect free except for in-memory state — no DB, no
async, no HTTP coupling. Routes call try_consume(...) and translate the
result into a 429 envelope themselves.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BucketConfig:
    burst: int
    refill_seconds: float


# Defaults committed to in docs/superpowers/plans/feature-backlog-2026-05-26/03-chat-enhancements.md
CHAT_BUCKETS: dict[str, BucketConfig] = {
    "proximity": BucketConfig(burst=2, refill_seconds=3.0),
    "room": BucketConfig(burst=2, refill_seconds=8.0),
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
