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
