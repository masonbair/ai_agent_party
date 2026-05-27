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
