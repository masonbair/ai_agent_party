# Sign-In + First Party Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement CLAUDE.md steps 1–2: a sign-in page (username + favorite color) and a first party page (Cream Terrazzo Lounge) where the user's avatar moves via WASD and click-to-move, with a lobby between them and a FastAPI backend scaffolded for step 3.

**Architecture:** Two services. **Frontend**: Vite + React + TypeScript on `:5173`, proxies `/api/*` to backend. **Backend**: FastAPI on `:8000` with an in-memory `Store` class so step 3 can swap implementations without changing routes. Parties are config-driven (`PartyConfig` registry on both sides). Avatars render as absolute-positioned DOM divs; movement state lives in a `useMovement` hook driven by a `requestAnimationFrame` loop.

**Tech Stack:** React 18, TypeScript 5, Vite 5, React Router 6, vitest + React Testing Library, FastAPI, pydantic v2, pytest, httpx (for TestClient).

**Spec:** `docs/superpowers/specs/2026-05-12-signin-and-party-page-design.md`

---

## File Structure

**Backend** (`backend/`)
- `pyproject.toml` — project config, deps
- `app/__init__.py`
- `app/main.py` — FastAPI app, CORS, router includes
- `app/models.py` — pydantic `User`, `Zone`, `PartyConfig`, request/response models
- `app/validation.py` — `USERNAME_REGEX`, `ALLOWED_COLORS`
- `app/store.py` — `Store` class wrapping `SESSIONS` and `PARTIES` dicts
- `app/parties_data.py` — Python copy of cream-terrazzo party config
- `app/routes/__init__.py`
- `app/routes/session.py` — POST/GET/DELETE `/api/session`
- `app/routes/parties.py` — GET `/api/parties`, GET `/api/parties/{slug}`
- `tests/__init__.py`
- `tests/conftest.py` — TestClient fixture with fresh `Store`
- `tests/test_validation.py`
- `tests/test_session_routes.py`
- `tests/test_parties_routes.py`

**Frontend** (`frontend/`)
- `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`
- `src/main.tsx` — React entry
- `src/App.tsx` — Router
- `src/api/client.ts` — `apiGet`, `apiPost`, `apiDelete`, `ApiError`
- `src/api/types.ts` — TS types matching backend response shapes
- `src/parties/types.ts` — `Zone`, `PartyConfig`
- `src/parties/cream-terrazzo.ts`
- `src/parties/registry.ts`
- `src/pages/SignIn.tsx`
- `src/pages/Lobby.tsx`
- `src/pages/Party.tsx`
- `src/components/Avatar.tsx`
- `src/components/Zone.tsx`
- `src/components/PartySpace.tsx`
- `src/components/MusicPill.tsx`
- `src/hooks/useSession.ts`
- `src/hooks/useMovement.ts`
- `src/constants.ts` — `ALLOWED_COLORS`, `USERNAME_REGEX`
- `src/styles.css` — base + reset
- `tests/setup.ts`
- `tests/SignIn.test.tsx`
- `tests/Lobby.test.tsx`
- `tests/useMovement.test.ts`
- `tests/registry.contract.test.ts`

**Root**
- `README.md` (already exists — leave alone)
- `.gitignore` (already updated)

---

## Task 1: Backend project scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "ai-agent-party-backend"
version = "0.1.0"
description = "Backend for ai_agent_party"
requires-python = ">=3.11"
dependencies = [
  "fastapi==0.115.0",
  "uvicorn[standard]==0.30.6",
  "pydantic==2.9.2",
]

[project.optional-dependencies]
dev = [
  "pytest==8.3.3",
  "httpx==0.27.2",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty `backend/app/__init__.py` and `backend/tests/__init__.py`**

Both files contain a single empty line.

- [ ] **Step 3: Create minimal `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="ai_agent_party")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Install and verify**

Run:
```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```
Expected: installs without error.

Run:
```bash
cd backend && source .venv/bin/activate && pytest -v
```
Expected: `no tests ran` (no failures).

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(backend): scaffold FastAPI project"
```

---

## Task 2: Validation rules

**Files:**
- Create: `backend/app/validation.py`
- Create: `backend/tests/test_validation.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_validation.py`:

```python
import pytest

from app.validation import ALLOWED_COLORS, USERNAME_REGEX


@pytest.mark.parametrize(
    "value",
    ["ab", "Alice42", "ZZZZZZZZZZZZZZZZZZZZ"],  # 2, mixed, 20 chars
)
def test_username_regex_accepts_valid(value: str) -> None:
    assert USERNAME_REGEX.fullmatch(value) is not None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a",
        "a" * 21,
        "has space",
        "bob; DROP TABLE",
        "<script>",
        "héllo",
        "bob-1",
    ],
)
def test_username_regex_rejects_invalid(value: str) -> None:
    assert USERNAME_REGEX.fullmatch(value) is None


def test_allowed_colors_has_twelve_distinct_swatches() -> None:
    assert len(ALLOWED_COLORS) == 12
    assert len(set(ALLOWED_COLORS)) == 12
    for c in ALLOWED_COLORS:
        assert c.startswith("#") and len(c) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.validation'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/validation.py`:

```python
import re

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9]{2,20}$")

ALLOWED_COLORS: tuple[str, ...] = (
    "#ff6b9d",  # pink
    "#9c27b0",  # purple
    "#4dd0e1",  # teal
    "#ffd54f",  # amber
    "#81c784",  # green
    "#ff8a65",  # coral
    "#7986cb",  # indigo
    "#f06292",  # rose
    "#4db6ac",  # mint
    "#ba68c8",  # violet
    "#ffb74d",  # orange
    "#a1887f",  # taupe
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_validation.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation.py backend/tests/test_validation.py
git commit -m "feat(backend): add username regex and color swatch list"
```

---

## Task 3: Models

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.models import CreateSessionRequest, PartyConfig, User, Zone


def test_create_session_request_accepts_valid() -> None:
    req = CreateSessionRequest(username="Alice42", color="#ff6b9d")
    assert req.username == "Alice42"
    assert req.color == "#ff6b9d"


@pytest.mark.parametrize(
    "username,color",
    [
        ("a", "#ff6b9d"),
        ("bob; DROP", "#ff6b9d"),
        ("Alice", "#000000"),  # not in ALLOWED_COLORS
        ("Alice", "not-a-color"),
    ],
)
def test_create_session_request_rejects_invalid(username: str, color: str) -> None:
    with pytest.raises(ValidationError):
        CreateSessionRequest(username=username, color=color)


def test_user_carries_session_id() -> None:
    user = User(session_id="abc", username="Alice", color="#ff6b9d")
    assert user.session_id == "abc"


def test_party_config_minimum_shape() -> None:
    zone = Zone(
        id="dance",
        label="DANCE",
        x=25.0,
        y=25.0,
        width=40.0,
        height=36.0,
        color="rgba(255,107,157,0.25)",
        labelColor="#8b1a4a",
    )
    cfg = PartyConfig(
        slug="cream-terrazzo",
        name="Cream Terrazzo Lounge",
        description="A bright, friendly party.",
        theme={"floor": "cream", "accent": "#ff6b9d"},
        zones=[zone],
        music={"url": None, "label": "Music coming soon"},
        worldSize={"width": 800, "height": 500},
    )
    assert cfg.slug == "cream-terrazzo"
    assert cfg.zones[0].id == "dance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/models.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.validation import ALLOWED_COLORS, USERNAME_REGEX


class CreateSessionRequest(BaseModel):
    username: str
    color: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        if USERNAME_REGEX.fullmatch(v) is None:
            raise ValueError("username must be 2-20 letters/digits")
        return v

    @field_validator("color")
    @classmethod
    def _check_color(cls, v: str) -> str:
        if v not in ALLOWED_COLORS:
            raise ValueError("color must be one of the allowed swatches")
        return v


class User(BaseModel):
    session_id: str
    username: str
    color: str


class Zone(BaseModel):
    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    color: str
    labelColor: str


class Theme(BaseModel):
    floor: str
    accent: str


class Music(BaseModel):
    url: str | None
    label: str


class WorldSize(BaseModel):
    width: int
    height: int


class PartyConfig(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    description: str
    theme: Theme
    zones: list[Zone]
    music: Music
    worldSize: WorldSize


class PartiesListResponse(BaseModel):
    parties: list[PartyConfig]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(backend): add pydantic models for sessions and parties"
```

---

## Task 4: Cream Terrazzo party data

**Files:**
- Create: `backend/app/parties_data.py`
- Create: `backend/tests/test_parties_data.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_parties_data.py`:

```python
from app.parties_data import CREAM_TERRAZZO


def test_cream_terrazzo_has_expected_slug_and_zones() -> None:
    assert CREAM_TERRAZZO.slug == "cream-terrazzo"
    zone_ids = {z.id for z in CREAM_TERRAZZO.zones}
    assert zone_ids == {"dance", "chill", "snacks"}


def test_cream_terrazzo_music_is_placeholder() -> None:
    assert CREAM_TERRAZZO.music.url is None
    assert "coming soon" in CREAM_TERRAZZO.music.label.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_parties_data.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/parties_data.py`:

```python
from app.models import Music, PartyConfig, Theme, WorldSize, Zone

CREAM_TERRAZZO = PartyConfig(
    slug="cream-terrazzo",
    name="Cream Terrazzo Lounge",
    description="A bright, friendly room with soft pastel zones.",
    theme=Theme(
        floor=(
            "#f4ead5 radial-gradient(circle 2px at 10% 20%, #c0a070 1px, transparent 2px), "
            "radial-gradient(circle 2px at 40% 60%, #a85d3a 1px, transparent 2px), "
            "radial-gradient(circle 2px at 70% 30%, #c0a070 1px, transparent 2px), "
            "radial-gradient(circle 2px at 85% 80%, #8b6f47 1px, transparent 2px), "
            "radial-gradient(circle 2px at 25% 85%, #c0a070 1px, transparent 2px)"
        ),
        accent="#ff6b9d",
    ),
    zones=[
        Zone(
            id="dance",
            label="DANCE",
            x=25.0,
            y=24.0,
            width=40.0,
            height=36.0,
            color="rgba(255,107,157,0.25)",
            labelColor="#8b1a4a",
        ),
        Zone(
            id="chill",
            label="CHILL",
            x=75.0,
            y=24.0,
            width=40.0,
            height=36.0,
            color="rgba(77,208,225,0.25)",
            labelColor="#00606e",
        ),
        Zone(
            id="snacks",
            label="SNACKS",
            x=50.0,
            y=76.0,
            width=40.0,
            height=36.0,
            color="rgba(255,167,38,0.30)",
            labelColor="#6b3a00",
        ),
    ],
    music=Music(url=None, label="Music coming soon"),
    worldSize=WorldSize(width=800, height=500),
)

PARTY_REGISTRY: dict[str, PartyConfig] = {CREAM_TERRAZZO.slug: CREAM_TERRAZZO}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_parties_data.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/parties_data.py backend/tests/test_parties_data.py
git commit -m "feat(backend): add Cream Terrazzo party config"
```

---

## Task 5: Store class

**Files:**
- Create: `backend/app/store.py`
- Create: `backend/tests/test_store.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_store.py`:

```python
import pytest

from app.store import Store


def test_create_session_returns_user_with_uuid() -> None:
    store = Store()
    user = store.create_session(username="Alice", color="#ff6b9d")
    assert user.username == "Alice"
    assert user.color == "#ff6b9d"
    assert len(user.session_id) >= 8


def test_get_session_returns_same_user() -> None:
    store = Store()
    created = store.create_session(username="Alice", color="#ff6b9d")
    fetched = store.get_session(created.session_id)
    assert fetched is not None
    assert fetched.session_id == created.session_id


def test_get_session_returns_none_for_unknown_id() -> None:
    store = Store()
    assert store.get_session("does-not-exist") is None


def test_delete_session_removes_user() -> None:
    store = Store()
    created = store.create_session(username="Alice", color="#ff6b9d")
    assert store.delete_session(created.session_id) is True
    assert store.get_session(created.session_id) is None


def test_delete_session_returns_false_for_unknown_id() -> None:
    store = Store()
    assert store.delete_session("does-not-exist") is False


def test_list_parties_returns_seeded_registry() -> None:
    store = Store()
    parties = store.list_parties()
    slugs = {p.slug for p in parties}
    assert "cream-terrazzo" in slugs


def test_get_party_returns_config_or_none() -> None:
    store = Store()
    assert store.get_party("cream-terrazzo") is not None
    assert store.get_party("does-not-exist") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.store'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/store.py`:

```python
import uuid

from app.models import PartyConfig, User
from app.parties_data import PARTY_REGISTRY


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, User] = {}
        self._parties: dict[str, PartyConfig] = dict(PARTY_REGISTRY)

    def create_session(self, username: str, color: str) -> User:
        session_id = uuid.uuid4().hex
        user = User(session_id=session_id, username=username, color=color)
        self._sessions[session_id] = user
        return user

    def get_session(self, session_id: str) -> User | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_parties(self) -> list[PartyConfig]:
        return list(self._parties.values())

    def get_party(self, slug: str) -> PartyConfig | None:
        return self._parties.get(slug)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_store.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/store.py backend/tests/test_store.py
git commit -m "feat(backend): add in-memory Store for sessions and parties"
```

---

## Task 6: Session routes

**Files:**
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/session.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_session_routes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.store import Store


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
```

Create `backend/tests/test_session_routes.py`:

```python
from fastapi.testclient import TestClient


def test_post_session_creates_and_returns_user(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "Alice", "color": "#ff6b9d"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "Alice"
    assert body["color"] == "#ff6b9d"
    assert isinstance(body["session_id"], str) and len(body["session_id"]) >= 8


def test_post_session_rejects_bad_username(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "a", "color": "#ff6b9d"})
    assert r.status_code == 422


def test_post_session_rejects_bad_color(client: TestClient) -> None:
    r = client.post("/api/session", json={"username": "Alice", "color": "#000000"})
    assert r.status_code == 422


def test_post_session_rejects_injection_like_username(client: TestClient) -> None:
    r = client.post(
        "/api/session", json={"username": "bob; DROP TABLE", "color": "#ff6b9d"}
    )
    assert r.status_code == 422


def test_get_session_returns_existing_user(client: TestClient) -> None:
    created = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    r = client.get(f"/api/session/{created['session_id']}")
    assert r.status_code == 200
    assert r.json()["username"] == "Alice"


def test_get_session_404_for_unknown(client: TestClient) -> None:
    r = client.get("/api/session/unknown-id")
    assert r.status_code == 404


def test_delete_session_204_then_404(client: TestClient) -> None:
    created = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    r = client.delete(f"/api/session/{created['session_id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/session/{created['session_id']}")
    assert r2.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_session_routes.py -v`
Expected: FAIL because `app.main` does not export `get_store` and `/api/session` does not exist.

- [ ] **Step 3: Create routes file and dependency**

Create `backend/app/routes/__init__.py` with a single empty line.

Create `backend/app/routes/session.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.models import CreateSessionRequest, User
from app.store import Store

router = APIRouter(prefix="/api/session")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.post("", response_model=User)
def create_session(
    body: CreateSessionRequest, store: Store = Depends(_store_dep)
) -> User:
    return store.create_session(username=body.username, color=body.color)


@router.get("/{session_id}", response_model=User)
def get_session(session_id: str, store: Store = Depends(_store_dep)) -> User:
    user = store.get_session(session_id)
    if user is None:
        raise HTTPException(status_code=404, detail="session not found")
    return user


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, store: Store = Depends(_store_dep)) -> Response:
    if not store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Wire the router into `main.py`**

Replace `backend/app/main.py` with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.include_router(session_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Note: `app.dependency_overrides[session_routes._store_dep] = get_store` makes the `_store_dep` placeholder resolve to the singleton in production. `Depends(_store_dep)` in `routes/session.py` captured the original function reference at import time, so we use that same reference (via `session_routes._store_dep`) as the override key. Tests override it again via `conftest.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_session_routes.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes backend/app/main.py backend/tests/conftest.py backend/tests/test_session_routes.py
git commit -m "feat(backend): add session routes and TestClient fixture"
```

---

## Task 7: Parties routes

**Files:**
- Create: `backend/app/routes/parties.py`
- Create: `backend/tests/test_parties_routes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_parties_routes.py`:

```python
from fastapi.testclient import TestClient


def test_list_parties_includes_cream_terrazzo(client: TestClient) -> None:
    r = client.get("/api/parties")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()["parties"]}
    assert "cream-terrazzo" in slugs


def test_get_party_returns_full_config(client: TestClient) -> None:
    r = client.get("/api/parties/cream-terrazzo")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "cream-terrazzo"
    assert {z["id"] for z in body["zones"]} == {"dance", "chill", "snacks"}
    assert body["music"]["url"] is None


def test_get_party_404_for_unknown_slug(client: TestClient) -> None:
    r = client.get("/api/parties/does-not-exist")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_parties_routes.py -v`
Expected: FAIL with 404 on `/api/parties` (route not registered yet).

- [ ] **Step 3: Create parties route**

Create `backend/app/routes/parties.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Path

from app.models import PartiesListResponse, PartyConfig
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.get("", response_model=PartiesListResponse)
def list_parties(store: Store = Depends(_store_dep)) -> PartiesListResponse:
    return PartiesListResponse(parties=store.list_parties())


@router.get("/{slug}", response_model=PartyConfig)
def get_party(
    slug: str = Path(pattern=r"^[a-z0-9-]+$"),
    store: Store = Depends(_store_dep),
) -> PartyConfig:
    party = store.get_party(slug)
    if party is None:
        raise HTTPException(status_code=404, detail="party not found")
    return party
```

- [ ] **Step 4: Wire into `main.py` (modify)**

Edit `backend/app/main.py` — add the `parties` import and registration. The full file becomes:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import parties as parties_routes
from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.dependency_overrides[parties_routes._store_dep] = get_store
app.include_router(session_routes.router)
app.include_router(parties_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Update `backend/tests/conftest.py` to override both deps. Replace its contents with:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
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
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: all previously-passing tests still pass; the 3 new ones pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/parties.py backend/app/main.py backend/tests/conftest.py backend/tests/test_parties_routes.py
git commit -m "feat(backend): add parties routes"
```

---

## Task 8: Frontend project scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/tests/setup.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "ai-agent-party-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.0",
    "typescript": "^5.5.4",
    "vite": "^5.4.6",
    "vitest": "^2.1.1"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": false,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
  },
});
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ai_agent_party</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/main.tsx`**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 7: Create placeholder `frontend/src/App.tsx`**

```tsx
export default function App() {
  return <div>ai_agent_party</div>;
}
```

- [ ] **Step 8: Create `frontend/src/styles.css`**

```css
* { box-sizing: border-box; }
html, body, #root { margin: 0; padding: 0; height: 100%; font-family: system-ui, sans-serif; }
button { font: inherit; cursor: pointer; }
```

- [ ] **Step 9: Create `frontend/tests/setup.ts`**

```typescript
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 10: Install and verify**

Run:
```bash
cd frontend && npm install
```
Expected: completes without error.

Run:
```bash
cd frontend && npm run build
```
Expected: builds without error.

Run:
```bash
cd frontend && npm test
```
Expected: `No test files found` — clean exit, no failures.

- [ ] **Step 11: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html frontend/src frontend/tests/setup.ts
git commit -m "feat(frontend): scaffold Vite + React + TypeScript project"
```

---

## Task 9: Constants and types

**Files:**
- Create: `frontend/src/constants.ts`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/parties/types.ts`

- [ ] **Step 1: Create `frontend/src/constants.ts`**

Keep this in sync with `backend/app/validation.py` — same regex, same swatch list.

```typescript
export const USERNAME_REGEX = /^[A-Za-z0-9]{2,20}$/;

export const ALLOWED_COLORS = [
  '#ff6b9d',
  '#9c27b0',
  '#4dd0e1',
  '#ffd54f',
  '#81c784',
  '#ff8a65',
  '#7986cb',
  '#f06292',
  '#4db6ac',
  '#ba68c8',
  '#ffb74d',
  '#a1887f',
] as const;

export type AllowedColor = (typeof ALLOWED_COLORS)[number];
```

- [ ] **Step 2: Create `frontend/src/api/types.ts`**

```typescript
export type User = {
  session_id: string;
  username: string;
  color: string;
};

export type Zone = {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  labelColor: string;
};

export type PartyConfig = {
  slug: string;
  name: string;
  description: string;
  theme: { floor: string; accent: string };
  zones: Zone[];
  music: { url: string | null; label: string };
  worldSize: { width: number; height: number };
};

export type PartiesListResponse = {
  parties: PartyConfig[];
};
```

- [ ] **Step 3: Create `frontend/src/parties/types.ts`**

This re-exports the API types so local-registry code uses the same shape.

```typescript
export type { PartyConfig, Zone } from '../api/types';
```

- [ ] **Step 4: Verify it type-checks**

Run: `cd frontend && npx tsc -b`
Expected: clean exit.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/constants.ts frontend/src/api/types.ts frontend/src/parties/types.ts
git commit -m "feat(frontend): add validation constants and shared types"
```

---

## Task 10: API client

**Files:**
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Create the client**

No test for this thin wrapper — it's exercised by component tests via `vi.fn()` mocks.

```typescript
export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API error ${status}`);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(path));
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(path, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}

export async function apiDelete<T>(path: string): Promise<T> {
  return handle<T>(await fetch(path, { method: 'DELETE' }));
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): add fetch wrapper with ApiError"
```

---

## Task 11: Cream Terrazzo frontend config + registry contract test

**Files:**
- Create: `frontend/src/parties/cream-terrazzo.ts`
- Create: `frontend/src/parties/registry.ts`
- Create: `frontend/tests/registry.contract.test.ts`

- [ ] **Step 1: Write the failing contract test**

Create `frontend/tests/registry.contract.test.ts`:

```typescript
import { describe, expect, it } from 'vitest';
import { PARTIES } from '../src/parties/registry';

describe('frontend party registry', () => {
  it('includes cream-terrazzo with the three named zones', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo');
    expect(ct).toBeDefined();
    const zoneIds = new Set(ct!.zones.map((z) => z.id));
    expect(zoneIds).toEqual(new Set(['dance', 'chill', 'snacks']));
  });

  it('marks music as a placeholder', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    expect(ct.music.url).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — module `../src/parties/registry` not found.

- [ ] **Step 3: Create the party config**

Create `frontend/src/parties/cream-terrazzo.ts`:

```typescript
import type { PartyConfig } from './types';

export const creamTerrazzo: PartyConfig = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room with soft pastel zones.',
  theme: {
    floor:
      '#f4ead5 radial-gradient(circle 2px at 10% 20%, #c0a070 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 40% 60%, #a85d3a 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 70% 30%, #c0a070 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 85% 80%, #8b6f47 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 25% 85%, #c0a070 1px, transparent 2px)',
    accent: '#ff6b9d',
  },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 25.0,
      y: 24.0,
      width: 40.0,
      height: 36.0,
      color: 'rgba(255,107,157,0.25)',
      labelColor: '#8b1a4a',
    },
    {
      id: 'chill',
      label: 'CHILL',
      x: 75.0,
      y: 24.0,
      width: 40.0,
      height: 36.0,
      color: 'rgba(77,208,225,0.25)',
      labelColor: '#00606e',
    },
    {
      id: 'snacks',
      label: 'SNACKS',
      x: 50.0,
      y: 76.0,
      width: 40.0,
      height: 36.0,
      color: 'rgba(255,167,38,0.30)',
      labelColor: '#6b3a00',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
};
```

Create `frontend/src/parties/registry.ts`:

```typescript
import type { PartyConfig } from './types';
import { creamTerrazzo } from './cream-terrazzo';

export const PARTIES: PartyConfig[] = [creamTerrazzo];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/parties/cream-terrazzo.ts frontend/src/parties/registry.ts frontend/tests/registry.contract.test.ts
git commit -m "feat(frontend): add Cream Terrazzo config and registry"
```

---

## Task 12: useSession hook

**Files:**
- Create: `frontend/src/hooks/useSession.ts`

This hook is consumed by Lobby and Party tests with mocked fetch, so no dedicated test is required for it.

- [ ] **Step 1: Create the hook**

```typescript
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import type { User } from '../api/types';

const STORAGE_KEY = 'session_id';

export function getStoredSessionId(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setStoredSessionId(id: string): void {
  localStorage.setItem(STORAGE_KEY, id);
}

export function clearStoredSessionId(): void {
  localStorage.removeItem(STORAGE_KEY);
}

type State =
  | { status: 'loading' }
  | { status: 'authed'; user: User }
  | { status: 'anon' };

export function useSession(): State {
  const [state, setState] = useState<State>({ status: 'loading' });
  const navigate = useNavigate();

  useEffect(() => {
    const id = getStoredSessionId();
    if (!id) {
      setState({ status: 'anon' });
      navigate('/', { replace: true });
      return;
    }
    apiGet<User>(`/api/session/${id}`)
      .then((user) => setState({ status: 'authed', user }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          clearStoredSessionId();
        }
        setState({ status: 'anon' });
        navigate('/', { replace: true });
      });
  }, [navigate]);

  return state;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useSession.ts
git commit -m "feat(frontend): add useSession hook with localStorage"
```

---

## Task 13: SignIn page

**Files:**
- Create: `frontend/src/pages/SignIn.tsx`
- Create: `frontend/tests/SignIn.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/SignIn.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignIn from '../src/pages/SignIn';

function renderSignIn() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<SignIn />} />
        <Route path="/lobby" element={<div>Lobby page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SignIn', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ session_id: 'sid-1', username: 'Alice', color: '#ff6b9d' }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('disables submit until input is valid', async () => {
    renderSignIn();
    const button = screen.getByRole('button', { name: /enter/i });
    expect(button).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/username/i), 'Alice');
    // Color not yet picked
    expect(button).toBeDisabled();

    await userEvent.click(screen.getAllByRole('radio')[0]);
    expect(button).toBeEnabled();
  });

  it('shows error for invalid username', async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), 'bob; DROP');
    expect(
      screen.getByText(/letters and numbers/i),
    ).toBeInTheDocument();
  });

  it('submits and navigates to lobby on success', async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), 'Alice');
    await userEvent.click(screen.getAllByRole('radio')[0]);
    await userEvent.click(screen.getByRole('button', { name: /enter/i }));

    expect(await screen.findByText(/lobby page/i)).toBeInTheDocument();
    expect(localStorage.getItem('session_id')).toBe('sid-1');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- SignIn`
Expected: FAIL — `SignIn` module not found.

- [ ] **Step 3: Implement `SignIn.tsx`**

Create `frontend/src/pages/SignIn.tsx`:

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiPost } from '../api/client';
import type { User } from '../api/types';
import { ALLOWED_COLORS, USERNAME_REGEX } from '../constants';
import { setStoredSessionId } from '../hooks/useSession';

export default function SignIn() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [color, setColor] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const usernameTouched = username.length > 0;
  const usernameValid = USERNAME_REGEX.test(username);
  const canSubmit = usernameValid && color !== null && !submitting;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setServerError(null);
    try {
      const user = await apiPost<User>('/api/session', { username, color });
      setStoredSessionId(user.session_id);
      navigate('/lobby');
    } catch (err) {
      const message =
        err instanceof ApiError ? 'Sign-in rejected. Check your input.' : 'Network error.';
      setServerError(message);
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 420, margin: '64px auto', padding: 24 }}>
      <h1>Welcome to ai_agent_party</h1>
      <form onSubmit={onSubmit}>
        <label htmlFor="username" style={{ display: 'block', marginTop: 16 }}>
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
          maxLength={20}
          style={{ width: '100%', padding: 8 }}
        />
        {usernameTouched && !usernameValid && (
          <p style={{ color: '#b00020', fontSize: 14 }}>
            Use 2–20 letters and numbers only.
          </p>
        )}

        <fieldset style={{ marginTop: 16, border: 'none', padding: 0 }}>
          <legend>Favorite color</legend>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
            {ALLOWED_COLORS.map((c) => (
              <label key={c} style={{ display: 'inline-flex' }}>
                <input
                  type="radio"
                  name="color"
                  value={c}
                  checked={color === c}
                  onChange={() => setColor(c)}
                  style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
                />
                <span
                  aria-hidden
                  style={{
                    display: 'block',
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: c,
                    outline: color === c ? '3px solid #333' : 'none',
                    outlineOffset: 2,
                    cursor: 'pointer',
                  }}
                />
              </label>
            ))}
          </div>
        </fieldset>

        {serverError && (
          <p role="alert" style={{ color: '#b00020' }}>
            {serverError}
          </p>
        )}

        <button type="submit" disabled={!canSubmit} style={{ marginTop: 24, padding: '8px 16px' }}>
          Enter
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 4: Wire SignIn into App.tsx**

Replace `frontend/src/App.tsx` with:

```tsx
import { Route, Routes } from 'react-router-dom';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SignIn />} />
    </Routes>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- SignIn`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SignIn.tsx frontend/tests/SignIn.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add SignIn page with validation"
```

---

## Task 14: Lobby page

**Files:**
- Create: `frontend/src/pages/Lobby.tsx`
- Create: `frontend/tests/Lobby.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/Lobby.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Lobby from '../src/pages/Lobby';

const sessionResponse = {
  session_id: 'sid-1',
  username: 'Alice',
  color: '#ff6b9d',
};

const partiesResponse = {
  parties: [
    {
      slug: 'cream-terrazzo',
      name: 'Cream Terrazzo Lounge',
      description: 'A bright, friendly room.',
      theme: { floor: '#f4ead5', accent: '#ff6b9d' },
      zones: [],
      music: { url: null, label: 'Music coming soon' },
      worldSize: { width: 800, height: 500 },
    },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Lobby', () => {
  beforeEach(() => {
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
      if (u.endsWith('/api/parties')) return jsonResponse(partiesResponse);
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders a card per party from the API', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<div>Party page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Cream Terrazzo Lounge/i)).toBeInTheDocument();
  });

  it('navigates to /party/:slug when a card is clicked', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<div>Party page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    const card = await screen.findByRole('button', { name: /cream terrazzo lounge/i });
    await userEvent.click(card);
    expect(await screen.findByText(/Party page/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- Lobby`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `Lobby.tsx`**

Create `frontend/src/pages/Lobby.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyConfig } from '../api/types';
import { useSession } from '../hooks/useSession';

export default function Lobby() {
  const session = useSession();
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyConfig[] | null>(null);

  useEffect(() => {
    if (session.status !== 'authed') return;
    apiGet<PartiesListResponse>('/api/parties')
      .then((res) => setParties(res.parties))
      .catch(() => setParties([]));
  }, [session.status]);

  if (session.status !== 'authed') return null;

  return (
    <main style={{ maxWidth: 900, margin: '40px auto', padding: 24 }}>
      <h1>Pick a party, {session.user.username}</h1>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 16,
          marginTop: 16,
        }}
      >
        {parties === null && <p>Loading parties…</p>}
        {parties?.map((p) => (
          <button
            key={p.slug}
            type="button"
            onClick={() => navigate(`/party/${p.slug}`)}
            style={{
              textAlign: 'left',
              padding: 16,
              border: `2px solid ${p.theme.accent}`,
              borderRadius: 12,
              background: '#fff',
            }}
          >
            <div
              style={{
                height: 80,
                borderRadius: 8,
                background: p.theme.floor,
                marginBottom: 12,
              }}
            />
            <strong>{p.name}</strong>
            <p style={{ margin: '4px 0 0', color: '#555' }}>{p.description}</p>
          </button>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Wire Lobby into App.tsx**

Replace `frontend/src/App.tsx` with:

```tsx
import { Route, Routes } from 'react-router-dom';
import Lobby from './pages/Lobby';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SignIn />} />
      <Route path="/lobby" element={<Lobby />} />
    </Routes>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- Lobby`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Lobby.tsx frontend/tests/Lobby.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Lobby page"
```

---

## Task 15: useMovement hook

**Files:**
- Create: `frontend/src/hooks/useMovement.ts`
- Create: `frontend/tests/useMovement.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/useMovement.test.ts`:

```typescript
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useMovement } from '../src/hooks/useMovement';

function setupRaf() {
  let frame = 0;
  const cbs = new Map<number, FrameRequestCallback>();
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    frame += 1;
    cbs.set(frame, cb);
    return frame;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => {
    cbs.delete(id);
  });
  return {
    tick(times = 1, ms = 16) {
      for (let i = 0; i < times; i++) {
        const next = cbs.size > 0 ? Math.min(...cbs.keys()) : null;
        if (next == null) return;
        const cb = cbs.get(next)!;
        cbs.delete(next);
        cb(performance.now() + ms * (i + 1));
      }
    },
  };
}

describe('useMovement', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('moves right when "d" is held', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 200 }),
    );

    const startX = result.current.position.x;
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
      raf.tick(3);
    });
    expect(result.current.position.x).toBeGreaterThan(startX);
  });

  it('clamps position at world bounds', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 100, worldHeight: 100, speed: 9999 }),
    );

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
      raf.tick(20);
    });
    expect(result.current.position.x).toBeLessThanOrEqual(100);
    expect(result.current.position.x).toBeGreaterThanOrEqual(0);
  });

  it('moves toward a click target', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 400 }),
    );

    act(() => {
      result.current.setTarget({ x: 700, y: 400 });
      raf.tick(5);
    });
    expect(result.current.position.x).toBeGreaterThan(0);
    expect(result.current.position.y).toBeGreaterThan(0);
  });

  it('cancels active target when a WASD key is pressed', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 100 }),
    );

    act(() => {
      result.current.setTarget({ x: 700, y: 400 });
      raf.tick(2);
    });
    const xAfterClickStart = result.current.position.x;

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
      window.dispatchEvent(new KeyboardEvent('keyup', { key: 'a' }));
      raf.tick(2);
    });
    // x should no longer be heading toward 700 — verify target was cleared
    expect(result.current.target).toBeNull();
    expect(result.current.position.x).toBeLessThanOrEqual(xAfterClickStart + 1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- useMovement`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `useMovement.ts`**

Create `frontend/src/hooks/useMovement.ts`:

```typescript
import { useEffect, useRef, useState } from 'react';

export type Point = { x: number; y: number };

type Options = {
  worldWidth: number;
  worldHeight: number;
  speed: number; // logical units per second
  start?: Point;
};

const KEY_TO_DIR: Record<string, Point> = {
  w: { x: 0, y: -1 },
  a: { x: -1, y: 0 },
  s: { x: 0, y: 1 },
  d: { x: 1, y: 0 },
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function useMovement(opts: Options) {
  const { worldWidth, worldHeight, speed } = opts;
  const [position, setPosition] = useState<Point>(
    opts.start ?? { x: worldWidth / 2, y: worldHeight / 2 },
  );
  const [target, setTargetState] = useState<Point | null>(null);

  const keysRef = useRef<Set<string>>(new Set());
  const targetRef = useRef<Point | null>(null);
  const posRef = useRef<Point>(position);
  const lastTimeRef = useRef<number | null>(null);

  posRef.current = position;
  targetRef.current = target;

  function setTarget(p: Point | null) {
    targetRef.current = p;
    setTargetState(p);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const key = e.key.toLowerCase();
      if (KEY_TO_DIR[key]) {
        keysRef.current.add(key);
        if (targetRef.current !== null) {
          targetRef.current = null;
          setTargetState(null);
        }
      }
    }
    function onKeyUp(e: KeyboardEvent) {
      keysRef.current.delete(e.key.toLowerCase());
    }
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  useEffect(() => {
    let rafId = 0;
    function loop(now: number) {
      const last = lastTimeRef.current;
      const dt = last == null ? 0 : (now - last) / 1000;
      lastTimeRef.current = now;

      let { x, y } = posRef.current;
      let moved = false;

      // WASD takes priority
      if (keysRef.current.size > 0) {
        let dx = 0;
        let dy = 0;
        for (const k of keysRef.current) {
          const dir = KEY_TO_DIR[k];
          dx += dir.x;
          dy += dir.y;
        }
        const len = Math.hypot(dx, dy);
        if (len > 0) {
          x += (dx / len) * speed * dt;
          y += (dy / len) * speed * dt;
          moved = true;
        }
      } else if (targetRef.current) {
        const t = targetRef.current;
        const dx = t.x - x;
        const dy = t.y - y;
        const dist = Math.hypot(dx, dy);
        if (dist < 1) {
          targetRef.current = null;
          setTargetState(null);
        } else {
          const step = Math.min(dist, speed * dt);
          x += (dx / dist) * step;
          y += (dy / dist) * step;
          moved = true;
        }
      }

      if (moved) {
        const next = {
          x: clamp(x, 0, worldWidth),
          y: clamp(y, 0, worldHeight),
        };
        posRef.current = next;
        setPosition(next);
      }
      rafId = requestAnimationFrame(loop);
    }
    rafId = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(rafId);
      lastTimeRef.current = null;
    };
  }, [worldWidth, worldHeight, speed]);

  return { position, target, setTarget };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- useMovement`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useMovement.ts frontend/tests/useMovement.test.ts
git commit -m "feat(frontend): add useMovement hook for WASD and click-to-move"
```

---

## Task 16: Avatar, Zone, MusicPill, PartySpace components

**Files:**
- Create: `frontend/src/components/Avatar.tsx`
- Create: `frontend/src/components/Zone.tsx`
- Create: `frontend/src/components/MusicPill.tsx`
- Create: `frontend/src/components/PartySpace.tsx`

These are pure presentational components driven by props. They're exercised by the Party page test in Task 17.

- [ ] **Step 1: Create `Avatar.tsx`**

```tsx
type Props = {
  username: string;
  color: string;
  x: number;
  y: number;
};

export default function Avatar({ username, color, x, y }: Props) {
  return (
    <div
      style={{
        position: 'absolute',
        left: x - 12,
        top: y - 12,
        width: 24,
        height: 24,
        pointerEvents: 'none',
        transition: 'left 80ms linear, top 80ms linear',
      }}
    >
      <div
        style={{
          position: 'absolute',
          bottom: 28,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 12,
          background: 'rgba(255,255,255,0.85)',
          padding: '1px 6px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
        }}
      >
        {username}
      </div>
      <div
        style={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          background: color,
          border: '2px solid white',
          boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Create `Zone.tsx`**

```tsx
import type { Zone as ZoneType } from '../api/types';

type Props = { zone: ZoneType; worldWidth: number; worldHeight: number };

export default function Zone({ zone, worldWidth, worldHeight }: Props) {
  const widthPx = (zone.width / 100) * worldWidth;
  const heightPx = (zone.height / 100) * worldHeight;
  const leftPx = (zone.x / 100) * worldWidth - widthPx / 2;
  const topPx = (zone.y / 100) * worldHeight - heightPx / 2;

  return (
    <div
      aria-label={`zone-${zone.id}`}
      style={{
        position: 'absolute',
        left: leftPx,
        top: topPx,
        width: widthPx,
        height: heightPx,
        background: `radial-gradient(ellipse at center, ${zone.color}, transparent 70%)`,
        borderRadius: '50%',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: '50%',
          transform: 'translateX(-50%)',
          color: zone.labelColor,
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: 1,
        }}
      >
        {zone.label}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `MusicPill.tsx`**

```tsx
type Props = { label: string };

export default function MusicPill({ label }: Props) {
  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        padding: '4px 10px',
        background: 'rgba(0,0,0,0.6)',
        color: '#fff',
        borderRadius: 999,
        fontSize: 12,
      }}
    >
      🎵 {label}
    </div>
  );
}
```

- [ ] **Step 4: Create `PartySpace.tsx`**

```tsx
import { useRef } from 'react';
import type { PartyConfig, User } from '../api/types';
import { useMovement } from '../hooks/useMovement';
import Avatar from './Avatar';
import MusicPill from './MusicPill';
import Zone from './Zone';

const SPEED = 220; // logical units / sec

type Props = { party: PartyConfig; user: User };

export default function PartySpace({ party, user }: Props) {
  const { width, height } = party.worldSize;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
  });
  const floorRef = useRef<HTMLDivElement>(null);

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect) return;
    setTarget({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }

  return (
    <div
      ref={floorRef}
      onClick={onClick}
      style={{
        position: 'relative',
        width,
        height,
        background: party.theme.floor,
        borderRadius: 16,
        overflow: 'hidden',
        margin: '24px auto',
        boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      {party.zones.map((z) => (
        <Zone key={z.id} zone={z} worldWidth={width} worldHeight={height} />
      ))}
      <Avatar username={user.username} color={user.color} x={position.x} y={position.y} />
      <MusicPill label={party.music.label} />
    </div>
  );
}
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: clean exit.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components
git commit -m "feat(frontend): add Avatar, Zone, MusicPill, PartySpace components"
```

---

## Task 17: Party page

**Files:**
- Create: `frontend/src/pages/Party.tsx`
- Create: `frontend/tests/Party.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/Party.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Party from '../src/pages/Party';

const sessionResponse = {
  session_id: 'sid-1',
  username: 'Alice',
  color: '#ff6b9d',
};

const partyResponse = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 25,
      y: 25,
      width: 40,
      height: 36,
      color: 'rgba(255,107,157,0.25)',
      labelColor: '#8b1a4a',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Party', () => {
  beforeEach(() => {
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
      if (u.endsWith('/api/parties/cream-terrazzo')) return jsonResponse(partyResponse);
      if (u.endsWith('/api/parties/unknown')) return jsonResponse({ detail: 'nope' }, 404);
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders party space, zones, avatar, and music placeholder', async () => {
    render(
      <MemoryRouter initialEntries={['/party/cream-terrazzo']}>
        <Routes>
          <Route path="/party/:slug" element={<Party />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText('zone-dance')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText(/music coming soon/i)).toBeInTheDocument();
  });

  it('redirects to /lobby when slug is unknown', async () => {
    render(
      <MemoryRouter initialEntries={['/party/unknown']}>
        <Routes>
          <Route path="/party/:slug" element={<Party />} />
          <Route path="/lobby" element={<div>Lobby page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/lobby page/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- Party`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `Party.tsx`**

Create `frontend/src/pages/Party.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PartySpace from '../components/PartySpace';
import { ApiError, apiGet } from '../api/client';
import type { PartyConfig } from '../api/types';
import { useSession } from '../hooks/useSession';

export default function Party() {
  const session = useSession();
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();
  const [party, setParty] = useState<PartyConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug || session.status !== 'authed') return;
    apiGet<PartyConfig>(`/api/parties/${slug}`)
      .then(setParty)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setError('Party not found');
          navigate('/lobby', { replace: true });
        } else {
          setError('Failed to load party');
        }
      });
  }, [slug, session.status, navigate]);

  if (session.status !== 'authed') return null;
  if (error && !party) return <p role="alert">{error}</p>;
  if (!party) return <p>Loading party…</p>;

  return (
    <main>
      <header style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>{party.name}</h1>
        <button type="button" onClick={() => navigate('/lobby')}>
          Leave party
        </button>
      </header>
      <PartySpace party={party} user={session.user} />
    </main>
  );
}
```

- [ ] **Step 4: Wire Party into App.tsx**

Replace `frontend/src/App.tsx` with:

```tsx
import { Route, Routes } from 'react-router-dom';
import Lobby from './pages/Lobby';
import Party from './pages/Party';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SignIn />} />
      <Route path="/lobby" element={<Lobby />} />
      <Route path="/party/:slug" element={<Party />} />
    </Routes>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- Party`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Party.tsx frontend/tests/Party.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Party page"
```

---

## Task 18: Full-stack manual verification

**Files:**
- None (manual verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: all tests pass.

- [ ] **Step 3: Type-check frontend**

Run: `cd frontend && npm run build`
Expected: builds without error.

- [ ] **Step 4: Boot the backend**

In one terminal:
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```
Expected: serves on `:8000`.

Hit `http://localhost:8000/api/health` — returns `{"status":"ok"}`.
Hit `http://localhost:8000/api/parties` — returns the Cream Terrazzo party.

- [ ] **Step 5: Boot the frontend**

In another terminal:
```bash
cd frontend && npm run dev
```
Expected: serves on `:5173`.

- [ ] **Step 6: Browser smoke test**

Open `http://localhost:5173`. Confirm in the browser:
- Sign-in form rejects "a" (too short), "bob; DROP" (non-alphanumeric).
- Submit becomes enabled once a valid username + a color swatch are picked.
- After submit, you land on `/lobby` with one card ("Cream Terrazzo Lounge").
- Clicking the card lands you on `/party/cream-terrazzo` with the cream floor, three pastel zones, your avatar at center, name label, and the "Music coming soon" pill.
- WASD moves the avatar smoothly. Clicking the floor moves it toward the target. Pressing W/A/S/D while moving toward a target cancels the target.
- The avatar is clamped to the floor bounds.
- Refresh keeps you signed in; restarting the backend kicks you to sign-in.

- [ ] **Step 7: Cross-stack contract verification**

The contract that frontend and backend party slugs stay aligned is enforced by two independent tests: `backend/tests/test_parties_data.py` asserts `CREAM_TERRAZZO.slug == "cream-terrazzo"`, and `frontend/tests/registry.contract.test.ts` asserts `PARTIES` contains `cream-terrazzo`. If a future party gets added to one side only, the corresponding test on the other side will need to be updated, which is the intended forcing function. No new test in this step — just confirm both already-passing tests are green from Steps 1 and 2.

- [ ] **Step 8: Final commit (if any uncommitted polish made)**

Run `git status`. If clean, you're done. Otherwise:

```bash
git add -A
git commit -m "chore: smoke test polish"
```

---

## Out of Scope (for reference)

These are intentionally not in this plan — they belong to later CLAUDE.md steps:

- Multiplayer / WebSockets (step 4)
- AI agent action API (move, chat) — step 3
- Real database persistence
- Actual music playback
- Avatar-to-avatar collision
- Multiple parties (config is ready; just add another `*.ts` + Python entry when desired)
