import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app, get_store
from app.routes import agents as agents_routes
from app.routes import dm as dm_routes
from app.routes import inbox_ws as inbox_ws_routes
from app.routes import lighting as lighting_routes
from app.routes import music as music_routes
from app.routes import module_drawboard as module_drawboard_routes
from app.routes import module_notes as module_notes_routes
from app.routes import history as history_routes
from app.routes import parties as parties_routes
from app.routes import party_actions as party_actions_routes
from app.routes import reactions as reactions_routes
from app.routes import session as session_routes
from app.store import Store


def register_human(client, *, username: str = "Alice", color: str = "#ff6b9d") -> dict:
    """Register a human session and return a dict with session info + principal."""
    user = client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()
    return {
        **user,
        "principal": {"kind": "human", "id": user["session_id"]},
    }


def register_agent(client, *, username: str = "Bot", color: str = "#4ecdc4") -> dict:
    """Register an agent and return a dict with agent info + principal."""
    agent = client.post(
        "/api/agents", json={"username": username, "color": color}
    ).json()
    return {
        **agent,
        "principal": {"kind": "agent", "id": agent["agent_id"]},
    }


def join_party(client, principal_dict: dict, slug: str, *, x=None, y=None) -> dict:
    """Join a party and return the response body."""
    body: dict = {"principal": principal_dict["principal"]}
    if x is not None:
        body["x"] = x
    if y is not None:
        body["y"] = y
    resp = client.post(
        f"/api/parties/{slug}/join",
        json=body,
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()


@pytest.fixture
def store() -> Store:
    s = Store()
    s.db = db_module.init_db(":memory:")
    yield s
    db_module.close_db(s.db)


@pytest.fixture
def client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[session_routes._store_dep] = lambda: store
    app.dependency_overrides[parties_routes._store_dep] = lambda: store
    app.dependency_overrides[agents_routes._store_dep] = lambda: store
    app.dependency_overrides[party_actions_routes._store_dep] = lambda: store
    app.dependency_overrides[dm_routes._store_dep] = lambda: store
    app.dependency_overrides[inbox_ws_routes._store_dep] = lambda: store
    app.dependency_overrides[reactions_routes._store_dep] = lambda: store
    app.dependency_overrides[lighting_routes._store_dep] = lambda: store
    app.dependency_overrides[music_routes._store_dep] = lambda: store
    app.dependency_overrides[module_notes_routes._store_dep] = lambda: store
    app.dependency_overrides[module_drawboard_routes._store_dep] = lambda: store
    app.dependency_overrides[history_routes._store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
