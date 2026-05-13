import pytest
from fastapi import HTTPException

from app.routes.principal import Principal, resolve_principal
from app.store import Store


def test_resolve_principal_returns_user_for_valid_human() -> None:
    s = Store()
    user = s.create_session(username="Alice", color="#ff6b9d")
    resolved = resolve_principal(
        s, Principal(kind="human", id=user.session_id)
    )
    assert resolved.id == user.session_id
    assert resolved.kind == "human"
    assert resolved.username == "Alice"


def test_resolve_principal_returns_participant_fields_for_valid_agent() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#4dd0e1")
    resolved = resolve_principal(s, Principal(kind="agent", id=a.agent_id))
    assert resolved.id == a.agent_id
    assert resolved.kind == "agent"
    assert resolved.color == "#4dd0e1"


def test_resolve_principal_401_for_unknown_human_id() -> None:
    s = Store()
    with pytest.raises(HTTPException) as exc:
        resolve_principal(s, Principal(kind="human", id="nope"))
    assert exc.value.status_code == 401


def test_resolve_principal_401_for_unknown_agent_id() -> None:
    s = Store()
    with pytest.raises(HTTPException) as exc:
        resolve_principal(s, Principal(kind="agent", id="nope"))
    assert exc.value.status_code == 401


def test_resolve_principal_401_when_kind_mismatches() -> None:
    s = Store()
    user = s.create_session(username="Alice", color="#ff6b9d")
    with pytest.raises(HTTPException) as exc:
        resolve_principal(s, Principal(kind="agent", id=user.session_id))
    assert exc.value.status_code == 401
