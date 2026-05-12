import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.routes import agents as agents_routes
from app.routes import parties as parties_routes
from app.routes import session as session_routes
from app.store import Store


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[session_routes._store_dep] = lambda: store
    app.dependency_overrides[parties_routes._store_dep] = lambda: store
    app.dependency_overrides[agents_routes._store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
