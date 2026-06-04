"""Integration tests for per-actor token-bucket cooldown on POST /chat."""
import pytest

from app.rate_limit import reset_chat_limiter_for_tests
from tests.conftest import join_party as _jp
from tests.conftest import register_agent as _ra

_SLUG = "cream-terrazzo"


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_chat_limiter_for_tests()
    yield
    reset_chat_limiter_for_tests()


def _post_chat(client, slug, agent, text, **kwargs):
    return client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": text, **kwargs},
    )


def test_burst_one_then_429(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    assert _post_chat(client, _SLUG, a, "one").status_code == 200
    r = _post_chat(client, _SLUG, a, "two")
    assert r.status_code == 429
    body = r.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["scope"] == "proximity"
    assert isinstance(body["retry_after_ms"], int)
    assert body["retry_after_ms"] > 0


def test_room_scope_uses_separate_bucket(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    # Drain proximity bucket.
    _post_chat(client, _SLUG, a, "one")
    assert _post_chat(client, _SLUG, a, "two").status_code == 429
    r = _post_chat(client, _SLUG, a, "room one", scope="room")
    assert r.status_code == 200  # room bucket independent
    r2 = _post_chat(client, _SLUG, a, "room two", scope="room")
    assert r2.status_code == 429
    assert r2.json()["detail"]["scope"] == "room"


def test_separate_buckets_per_actor(client) -> None:
    a = _ra(client, username="Alice")
    b = _ra(client, username="Bob", color="#ff6b9d")
    _jp(client, a, _SLUG)
    _jp(client, b, _SLUG)
    # Drain alice.
    _post_chat(client, _SLUG, a, "a1")
    assert _post_chat(client, _SLUG, a, "a2").status_code == 429
    # Bob unaffected.
    assert _post_chat(client, _SLUG, b, "b1").status_code == 200
