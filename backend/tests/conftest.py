import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app, get_store
from app.routes import agents as agents_routes
from app.routes import lighting as lighting_routes
from app.routes import module_drawboard as module_drawboard_routes
from app.routes import module_notes as module_notes_routes
from app.routes import history as history_routes
from app.routes import parties as parties_routes
from app.routes import party_actions as party_actions_routes
from app.routes import reactions as reactions_routes
from app.routes import session as session_routes
from app.store import Store


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
    app.dependency_overrides[reactions_routes._store_dep] = lambda: store
    app.dependency_overrides[lighting_routes._store_dep] = lambda: store
    app.dependency_overrides[module_notes_routes._store_dep] = lambda: store
    app.dependency_overrides[module_drawboard_routes._store_dep] = lambda: store
    app.dependency_overrides[history_routes._store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
