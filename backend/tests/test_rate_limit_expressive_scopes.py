from app.rate_limit import RateLimitScope, TokenBucketRegistry


def test_gesture_scope_exists():
    assert RateLimitScope.GESTURE.value == "gesture"


def test_cosmetic_scope_exists():
    assert RateLimitScope.COSMETIC.value == "cosmetic"


def test_gesture_default_config_burst_3_refill_one_per_two_seconds():
    reg = TokenBucketRegistry()
    reg.configure_defaults()  # spec #03 helper that registers all known scopes
    # 3 consumes should succeed back-to-back.
    for _ in range(3):
        res = reg.try_consume(RateLimitScope.GESTURE.value, actor_id="alice")
        assert res.ok
    # 4th immediately is denied.
    denied = reg.try_consume(RateLimitScope.GESTURE.value, actor_id="alice")
    assert not denied.ok
    # retry_after_ms is positive and <= 2000 (refill 1 per 2s).
    assert 0 < denied.retry_after_ms <= 2000


def test_cosmetic_default_config_burst_1_refill_one_per_ten_seconds():
    reg = TokenBucketRegistry()
    reg.configure_defaults()
    res = reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="alice")
    assert res.ok
    denied = reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="alice")
    assert not denied.ok
    assert 0 < denied.retry_after_ms <= 10_000


def test_buckets_are_independent_per_actor():
    reg = TokenBucketRegistry()
    reg.configure_defaults()
    reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="alice")
    bob = reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="bob")
    assert bob.ok


def test_gesture_bucket_independent_from_chat_bucket():
    reg = TokenBucketRegistry()
    reg.configure_defaults()
    # Drain gesture bucket.
    for _ in range(3):
        reg.try_consume(RateLimitScope.GESTURE.value, actor_id="alice")
    # Chat is still available.
    chat_res = reg.try_consume(RateLimitScope.CHAT.value, actor_id="alice")
    assert chat_res.ok
