import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.routes.session import _store_dep
from app.store import Store


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[_store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
