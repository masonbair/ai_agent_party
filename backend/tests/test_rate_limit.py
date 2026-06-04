"""Unit tests for the token-bucket rate limiter."""
from app.rate_limit import BucketConfig, RateLimiter


def test_burst_allows_n_then_blocks() -> None:
    rl = RateLimiter(
        configs={
            "proximity": BucketConfig(burst=2, refill_seconds=3.0),
        },
        now=lambda: 0.0,
    )
    assert rl.try_consume("p", "alice", "proximity") == (True, 0)
    assert rl.try_consume("p", "alice", "proximity") == (True, 0)
    ok, retry_ms = rl.try_consume("p", "alice", "proximity")
    assert ok is False
    assert retry_ms == 3000  # full refill interval to next token


def test_refill_partial_after_some_time() -> None:
    t = {"now": 0.0}
    rl = RateLimiter(
        configs={"proximity": BucketConfig(burst=2, refill_seconds=3.0)},
        now=lambda: t["now"],
    )
    rl.try_consume("p", "alice", "proximity")
    rl.try_consume("p", "alice", "proximity")
    # 1.5s elapsed: half a token earned -> still blocked, ~1500ms left.
    t["now"] = 1.5
    ok, retry_ms = rl.try_consume("p", "alice", "proximity")
    assert ok is False
    assert 1400 <= retry_ms <= 1600


def test_full_refill_unblocks() -> None:
    t = {"now": 0.0}
    rl = RateLimiter(
        configs={"proximity": BucketConfig(burst=2, refill_seconds=3.0)},
        now=lambda: t["now"],
    )
    rl.try_consume("p", "alice", "proximity")
    rl.try_consume("p", "alice", "proximity")
    t["now"] = 3.0
    ok, retry_ms = rl.try_consume("p", "alice", "proximity")
    assert ok is True
    assert retry_ms == 0


def test_separate_buckets_per_scope() -> None:
    rl = RateLimiter(
        configs={
            "proximity": BucketConfig(burst=2, refill_seconds=3.0),
            "room": BucketConfig(burst=2, refill_seconds=8.0),
        },
        now=lambda: 0.0,
    )
    rl.try_consume("p", "alice", "proximity")
    rl.try_consume("p", "alice", "proximity")
    # proximity is dry but room is independent.
    ok, _ = rl.try_consume("p", "alice", "room")
    assert ok is True


def test_separate_buckets_per_actor_and_party() -> None:
    rl = RateLimiter(
        configs={"proximity": BucketConfig(burst=1, refill_seconds=3.0)},
        now=lambda: 0.0,
    )
    rl.try_consume("p1", "alice", "proximity")
    # alice in p1 is dry; bob in p1 is fresh; alice in p2 is fresh.
    assert rl.try_consume("p1", "bob", "proximity")[0] is True
    assert rl.try_consume("p2", "alice", "proximity")[0] is True
    assert rl.try_consume("p1", "alice", "proximity")[0] is False


def test_proximity_chat_allows_one_then_blocks_for_about_four_seconds():
    from app.rate_limit import RateLimiter, CHAT_BUCKETS

    t = {"now": 1000.0}
    rl = RateLimiter(configs=CHAT_BUCKETS, now=lambda: t["now"])

    ok, retry = rl.try_consume("cream-terrazzo", "actor-1", "proximity")
    assert ok is True and retry == 0

    # Immediate second message is blocked (no bursting).
    ok2, retry2 = rl.try_consume("cream-terrazzo", "actor-1", "proximity")
    assert ok2 is False
    assert 3500 <= retry2 <= 4000  # ~4s until next token

    # After 4s a token is available again.
    t["now"] += 4.0
    ok3, _ = rl.try_consume("cream-terrazzo", "actor-1", "proximity")
    assert ok3 is True
