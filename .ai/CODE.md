# CODE.md — Standardized Code Patterns

**Purpose:** Templates for the most common kinds of code written in this repo.
Before adding a new feature, find the template that matches the layer you're
working in and follow its shape. Deviate only when the feature genuinely
requires it — and say why in the PR.

Pairs with `CONVENTIONS.md` (principles) and `ARCHITECTURE.md` (layout) in this
same `.ai/` folder. This file is about **how to write it**; those files are
about **why**.

---

## Table of Contents

1. [Backend — FastAPI route](#1-backend--fastapi-route)
2. [Backend — Pydantic request/response model](#2-backend--pydantic-requestresponse-model)
3. [Backend — Validation (regex + enum)](#3-backend--validation-regex--enum)
4. [Backend — Principal-gated party action](#4-backend--principal-gated-party-action)
5. [Backend — Store mutation (in-memory)](#5-backend--store-mutation-in-memory)
6. [Backend — pytest route test](#6-backend--pytest-route-test)
7. [Frontend — API call via `client.ts`](#7-frontend--api-call-via-clientts)
8. [Frontend — Shared API type](#8-frontend--shared-api-type)
9. [Frontend — React page component](#9-frontend--react-page-component)
10. [Frontend — Component file splitting](#10-frontend--component-file-splitting)
11. [Frontend — Custom hook](#11-frontend--custom-hook)
12. [Frontend — Vitest + RTL component test](#12-frontend--vitest--rtl-component-test)
13. [HTTP error code conventions](#13-http-error-code-conventions)
14. [Naming conventions](#14-naming-conventions)

---

## 1. Backend — FastAPI route

Every route module lives in `backend/app/routes/<name>.py`, declares its own
`APIRouter` with a `prefix`, and gets `Store` through a `_store_dep` placeholder
that `main.py` overrides. Never import the live `Store` instance directly.

```python
# backend/app/routes/<name>.py
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.store import Store

router = APIRouter(prefix="/api/<name>")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


@router.get("/{thing_id}", response_model=Thing)
def get_thing(thing_id: str, store: Store = Depends(_store_dep)) -> Thing:
    thing = store.get_thing(thing_id)
    if thing is None:
        raise HTTPException(status_code=404, detail="thing not found")
    return thing
```

**Rules:**
- One router per module; mount it from `app/main.py`.
- 404 uses `detail="<resource> not found"` (lowercase).
- DELETE returns `204` via `Response(status_code=...)`.
- Path params that are slugs: `slug: str = Path(pattern=r"^[a-z0-9-]+$")`.
- Annotate return types. Use `response_model=` for typed JSON responses.
- No business logic inside the route — delegate to `store`, `world`, or
  helpers. Routes should read like a table of contents.

---

## 2. Backend — Pydantic request/response model

Request bodies are `BaseModel` subclasses defined inside the route module
(co-located with the endpoint that consumes them). Domain models (`Agent`,
`Participant`, `PartyConfig`) live in `app/events.py` or `app/models.py`.

```python
class CreateThingRequest(BaseModel):
    username: str
    color: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        if USERNAME_REGEX.fullmatch(v) is None:
            raise ValueError("username must be 2-20 letters/digits")
        return v
```

**Rules:**
- Request classes named `<Verb><Noun>Request` (e.g. `CreateAgentRequest`).
- Validators are private (`_check_*`) and import constants from
  `app/validation.py` — never inline a regex or color list.
- Pydantic auto-converts `ValueError` → HTTP 422. Don't raise `HTTPException`
  from a validator.

---

## 3. Backend — Validation (regex + enum)

Centralized in `app/validation.py`. Add new constants there; don't redefine
them at call sites.

```python
# app/validation.py
import re

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9]{2,20}$")
ALLOWED_COLORS: frozenset[str] = frozenset({"#ff6b9d", ...})
CHAT_TEXT_REGEX = re.compile(...)
CHAT_MAX_LEN = 280


class ChatValidationError(ValueError):
    """Raised when chat text fails validation."""
```

**Rules:**
- Compile regexes at module scope.
- Use `frozenset` for closed enumerations.
- Domain-specific errors subclass `ValueError` so Pydantic surfaces them
  cleanly; routes translate to HTTP codes via `except` blocks.

---

## 4. Backend — Principal-gated party action

Any action a human OR an agent can perform takes a `Principal` in the body and
resolves it through `routes/principal.py`. Mismatched/unknown principals →
`401`. Not-joined-to-party → `409`. Missing slug → `404`.

```python
class MoveRequest(BaseModel):
    principal: Principal
    x: float
    y: float


@router.post("/{slug}/move")
def move(
    body: MoveRequest,
    slug: str = Path(pattern=r"^[a-z0-9-]+$"),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)               # 404 if slug unknown
    resolved = resolve_principal(store, body.principal)  # 401 if invalid
    try:
        ev = world.move(resolved.id, body.x, body.y)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    return {"x": ev.x, "y": ev.y, "cursor": world.cursor}
```

**Rules:**
- Always order checks: slug → principal → state.
- Return the world `cursor` so observers can resume diffs.
- Never look up `store.get_session` / `store.get_agent` directly from a route —
  always go through `resolve_principal`.

---

## 5. Backend — Store mutation (in-memory)

All mutable state lives in `app/store.py` (`Store`) and `app/world.py`
(`PartyWorld`). Routes never hold state.

```python
# app/store.py
def register_agent(self, *, username: str, color: str) -> Agent:
    agent_id = uuid.uuid4().hex
    agent = Agent(agent_id=agent_id, username=username, color=color)
    self._agents[agent_id] = agent
    return agent

def delete_agent(self, agent_id: str) -> bool:
    return self._agents.pop(agent_id, None) is not None
```

**Rules:**
- Mutators return either the created object or a `bool` (success).
- Keyword-only args for anything that takes 2+ same-typed params.
- Never `print` / log inside store methods; raise typed exceptions.
- Tests for store live in `backend/tests/test_store*.py` and don't go through
  HTTP.

---

## 6. Backend — pytest route test

Tests use the `client` fixture from `backend/tests/conftest.py` (a
`TestClient` with a fresh `Store`).

```python
# backend/tests/test_<route>_routes.py
from fastapi.testclient import TestClient


def test_post_things_creates_and_returns(client: TestClient) -> None:
    r = client.post("/api/things", json={"username": "Bot1", "color": "#ff6b9d"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "Bot1"


def test_get_thing_404_for_unknown(client: TestClient) -> None:
    assert client.get("/api/things/unknown-id").status_code == 404
```

**Rules:**
- One assertion focus per test; name says what's verified.
- Cover at minimum: happy path, validation 422, missing 404, conflict 409,
  unauthorized 401 (when applicable).
- Write the test BEFORE the implementation and watch it fail (see
  `.ai/CONVENTIONS.md` §1).

---

## 7. Frontend — API call via `client.ts`

All HTTP goes through `frontend/src/api/client.ts`. Never call `fetch`
directly from a component or hook.

```ts
import { apiGet, apiPost, apiDelete, ApiError } from '../api/client';
import type { Agent } from '../api/types';

const agent = await apiPost<Agent>('/api/agents', { username, color });
const fetched = await apiGet<Agent>(`/api/agents/${agent.agent_id}`);
await apiDelete<void>(`/api/agents/${agent.agent_id}`);

// Error handling:
try {
  await apiGet(`/api/session/${id}`);
} catch (err) {
  if (err instanceof ApiError && err.status === 404) {
    // handle expected 404
  }
}
```

**Rules:**
- Always pass an explicit type parameter (`apiGet<Foo>(...)`).
- Catch `ApiError` and branch on `err.status` — never inspect message strings.
- Use `void` for 204 responses.

---

## 8. Frontend — Shared API type

Response shapes live in `frontend/src/api/types.ts` and mirror the backend's
JSON. Use snake_case field names because that's what the API returns
(`session_id`, `agent_id`) — do not camelCase them client-side.

```ts
// frontend/src/api/types.ts
export type Agent = {
  agent_id: string;
  username: string;
  color: string;
};
```

**Rules:**
- One `type` per concept; prefer `type` over `interface` for plain data.
- Mark optional fields with `?:` and nullable fields with `| null` to match
  the backend's Pydantic optionality.

---

## 9. Frontend — React page component

Pages live in `frontend/src/pages/`. Routing is done via `react-router-dom`
in `App.tsx`. Pages own their data fetching; presentational logic moves to
`components/`.

```tsx
// frontend/src/pages/Things.tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import type { Thing } from '../api/types';

export default function Things() {
  const [things, setThings] = useState<Thing[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiGet<{ things: Thing[] }>('/api/things')
      .then((r) => setThings(r.things))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) navigate('/');
      });
  }, [navigate]);

  if (things === null) return <p>Loading…</p>;
  return <ul>{things.map((t) => <li key={t.id}>{t.label}</li>)}</ul>;
}
```

**Rules:**
- Default export per page module; the file name is the page name.
- `null` state = loading; empty array = loaded-but-empty. Don't conflate them.
- Sizing via `clamp()` / `min()` / `aspect-ratio`. No media queries.

---

## 10. Frontend — Component file splitting

**One component per file. When in doubt, split.** Prefer many small component
files that compose together over one big file that does it all. Shorter files
are easier to read, test, locate in a diff, and reuse.

Look at how `PartySpace` is built: it doesn't render avatars, zones, or walls
itself — it imports `Avatar`, `Zone`, `Wall`, and `MusicPill` from
`components/` and composes them. That's the pattern.

**Split when any of these are true:**
- The file has more than one default export's worth of UI (two visually
  distinct widgets living together).
- A piece of the JSX is reused — or could plausibly be reused — elsewhere.
- A subsection has its own state, effects, or props it doesn't share with the
  outer component.
- The file is heading past ~150 lines of JSX (well before the project-wide
  300-line ceiling in `CONVENTIONS.md`).
- You catch yourself writing a comment like `{/* --- chat panel --- */}` to
  visually separate sections. That comment is telling you to extract a
  component.

**How to split:**

```tsx
// Before: pages/Party.tsx is 400 lines and renders the room, avatars,
// the chat panel, and the leave pill inline.

// After:
// pages/Party.tsx                 ← data fetching + layout only
// components/PartySpace.tsx       ← the 2D room
// components/Avatar.tsx           ← one avatar
// components/ChatPanel.tsx        ← the chat UI
// components/LeavePill.tsx        ← the corner pill
```

**Rules:**
- Components live in `frontend/src/components/<ComponentName>.tsx`, one per
  file, named after the file. Default export.
- A component's tightly-coupled subcomponents (used nowhere else) can stay
  as non-exported helpers in the same file — until they grow, then split.
- Co-locate the component's CSS module / styled block with the component
  file. Don't share style files across unrelated components.
- Props types go in the same file as the component. Promote to
  `api/types.ts` only when shared with API responses.

**Anti-patterns:**
- A 600-line `Party.tsx` with five `function SubThing()` declarations at
  the bottom.
- Splitting so aggressively that you have a `<Label>` component wrapping a
  single `<span>`. The point is clarity, not granularity for its own sake.

---

## 11. Frontend — Custom hook

Hooks live in `frontend/src/hooks/`. Each file exports ONE primary hook plus
any small helpers that belong to it (see `useSession.ts`).

```ts
// frontend/src/hooks/useThing.ts
import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';
import type { Thing } from '../api/types';

type State =
  | { status: 'loading' }
  | { status: 'ready'; thing: Thing }
  | { status: 'error' };

export function useThing(id: string): State {
  const [state, setState] = useState<State>({ status: 'loading' });
  useEffect(() => {
    apiGet<Thing>(`/api/things/${id}`)
      .then((thing) => setState({ status: 'ready', thing }))
      .catch(() => setState({ status: 'error' }));
  }, [id]);
  return state;
}
```

**Rules:**
- Model state as a discriminated union on `status` — no `loading: boolean`
  plus `data: T | null`.
- Hook names start with `use`. Helpers (e.g. `getStoredSessionId`) can be
  plain functions exported from the same file.

---

## 12. Frontend — Vitest + RTL component test

```tsx
// frontend/tests/Thing.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Thing from '../src/pages/Thing';

describe('Thing', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: '1' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
  });
  afterEach(() => vi.restoreAllMocks());

  it('renders the thing once loaded', async () => {
    render(
      <MemoryRouter><Routes><Route path="/" element={<Thing />} /></Routes></MemoryRouter>,
    );
    expect(await screen.findByText(/thing 1/i)).toBeInTheDocument();
  });
});
```

**Rules:**
- Mock `fetch` with `vi.spyOn(globalThis, 'fetch')`; restore in `afterEach`.
- Query by accessible role/label/text, not by class or test-id.
- Wrap in `MemoryRouter` whenever the component uses router hooks.

---

## 13. HTTP error code conventions

| Code | When |
|------|------|
| `200` | GET / POST that returns a body |
| `204` | DELETE / state-only mutation (no body) |
| `401` | Principal invalid or doesn't match claimed kind |
| `404` | Resource (slug, id) not found |
| `409` | Valid principal but wrong state (e.g. not joined to party) |
| `422` | Pydantic validation failure (regex, enum, missing field) |

Detail strings are lowercase, short, and stable: clients may match on them.

---

## 14. Naming conventions

- **Slugs:** `^[a-z0-9-]+$`
- **Usernames:** `^[A-Za-z0-9]{2,20}$`
- **IDs:** opaque hex from `uuid.uuid4().hex`. Don't parse them.
- **Backend files:** snake_case. **Frontend files:** PascalCase for
  components/pages, camelCase for hooks and utilities.
- **Tests:** `test_<module>.py` / `<Component>.test.tsx`. Test name says
  what's verified, not what's called: `test_get_agent_404_for_unknown`,
  not `test_get_agent_2`.

---

## When this doc is wrong

If a pattern here conflicts with code you're reading, the code is the source
of truth — update this doc in the same PR that drifts from it. A stale CODE.md
is worse than no CODE.md.
