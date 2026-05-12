from app.events import Agent
from app.store import Store
from app.world import PartyWorld


def test_register_agent_returns_agent_with_id() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#ff6b9d")
    assert isinstance(a, Agent)
    assert a.username == "Bot1"
    assert a.color == "#ff6b9d"
    assert isinstance(a.agent_id, str) and len(a.agent_id) >= 8


def test_get_agent_returns_registered() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#ff6b9d")
    got = s.get_agent(a.agent_id)
    assert got is not None
    assert got.agent_id == a.agent_id


def test_get_agent_returns_none_for_unknown() -> None:
    s = Store()
    assert s.get_agent("nope") is None


def test_delete_agent_removes_then_404() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#ff6b9d")
    assert s.delete_agent(a.agent_id) is True
    assert s.get_agent(a.agent_id) is None
    assert s.delete_agent(a.agent_id) is False


def test_get_or_create_world_returns_partyworld_for_known_party() -> None:
    s = Store()
    w = s.get_or_create_world("cream-terrazzo")
    assert isinstance(w, PartyWorld)


def test_get_or_create_world_is_idempotent() -> None:
    s = Store()
    w1 = s.get_or_create_world("cream-terrazzo")
    w2 = s.get_or_create_world("cream-terrazzo")
    assert w1 is w2


def test_get_or_create_world_returns_none_for_unknown_party() -> None:
    s = Store()
    assert s.get_or_create_world("does-not-exist") is None
