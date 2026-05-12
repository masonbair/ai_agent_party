# Sign-In + First Party Page — Design Spec

**Date:** 2026-05-12
**Scope:** CLAUDE.md steps 1 and 2 (sign-in page, first party page with single-user movement)
**Out of scope:** Step 3 (AI agent action API), Step 4 (multiplayer/WebSockets), real DB persistence, actual music playback, avatar-to-avatar collision

---

## Goals

1. A sign-in page that captures a `username` (letters/numbers, 2–20 chars) and a favorite color (swatch picker).
2. A lobby page that lists available parties so more can be added later via config.
3. A first party page — **Cream Terrazzo Lounge** — with an open zoned canvas (no walls), where the signed-in user's avatar moves via WASD and click-to-move.
4. A backend (FastAPI) scaffolded with an in-memory store so step 3 (AI agent API) plugs in without route churn.
5. Party-as-template: adding a new party is "drop a new config object in the registry."

---

## Architecture

Two services run during development:

- **Frontend** — Vite + React + TypeScript, dev server on `:5173`. Proxies `/api/*` to the backend.
- **Backend** — FastAPI (Python), on `:8000`. In-memory storage only.

```
ai_agent_party/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── SignIn.tsx
│   │   │   ├── Lobby.tsx
│   │   │   └── Party.tsx
│   │   ├── parties/
│   │   │   ├── types.ts
│   │   │   ├── registry.ts
│   │   │   └── cream-terrazzo.ts
│   │   ├── components/
│   │   │   ├── Avatar.tsx
│   │   │   ├── Zone.tsx
│   │   │   └── PartySpace.tsx
│   │   ├── hooks/
│   │   │   ├── useMovement.ts
│   │   │   └── useSession.ts
│   │   ├── api/client.ts
│   │   └── App.tsx
│   └── tests/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── session.py
│   │   │   └── parties.py
│   │   ├── models.py
│   │   ├── store.py
│   │   └── validation.py
│   └── tests/
└── docs/superpowers/specs/
```

Each source file is expected to stay under the 200–300 line target from `.ai/CONVENTIONS.md`.

---

## Party Config — The Boilerplate

The `PartyConfig` type is the single abstraction that makes "add a new party" cheap.

```typescript
// frontend/src/parties/types.ts
export type Zone = {
  id: string;              // "dance"
  label: string;           // "DANCE"
  x: number; y: number;    // center, % of world (0-100)
  width: number; height: number;  // % of world
  color: string;           // rgba blob tint
  labelColor: string;
};

export type PartyConfig = {
  slug: string;            // "cream-terrazzo"
  name: string;            // "Cream Terrazzo Lounge"
  description: string;     // lobby card text
  theme: { floor: string; accent: string };
  zones: Zone[];
  music: { url: string | null; label: string };  // url=null => "music coming soon"
  worldSize: { width: number; height: number };  // logical units
};
```

`registry.ts` is `export const PARTIES: PartyConfig[] = [creamTerrazzo]`. The backend declares an equivalent pydantic model and its own hardcoded list. The frontend's local registry is only for type-safe authoring; **the API is the runtime source of truth**, and a cross-stack test enforces that the slug sets match.

### Cream Terrazzo Lounge (first party)

- **Floor:** cream `#f4ead5` background with subtle terrazzo speckle (radial-gradient dots).
- **Zones (3):** Dance (top-left, pink blob), Chill (top-right, teal blob), Snacks (bottom-center, amber blob). All soft, no borders — radial-gradient fade-out.
- **Music:** `url: null`, `label: "Music coming soon"` — renders a placeholder pill in the corner.
- **Avatar styling:** 24px circle, 2px white border, drop shadow. Username label centered above.

---

## Routes & User Flows

### Frontend routes
- `/` → `SignIn` (redirects to `/lobby` if a valid session exists in localStorage)
- `/lobby` → `Lobby`
- `/party/:slug` → `Party`

### Sign-in
1. Form: `username` text input, color swatch picker (12 fixed swatches).
2. Client-side validation: username matches `^[A-Za-z0-9]{2,20}$`; color must be one of the 12.
3. On submit: `POST /api/session { username, color }`.
4. Backend re-validates (pydantic), creates `User`, stores in `SESSIONS` dict keyed by a UUID, returns `{ session_id, username, color }`.
5. Frontend writes `session_id` to `localStorage`, navigates to `/lobby`.

### Lobby
1. `useSession` hook calls `GET /api/session/{id}`; on 404, clears localStorage and routes to `/`.
2. `GET /api/parties` → render one card per party (name, description, theme preview swatch).
3. Click card → `navigate('/party/:slug')`.

### Party
1. `useSession` check (same as lobby).
2. `GET /api/parties/:slug`; on 404, show a toast and route to `/lobby`.
3. `PartySpace` renders:
   - Floor `<div>` styled from `theme.floor`, sized to `worldSize`.
   - One `<Zone>` per `config.zones[]`.
   - One `<Avatar>` for the current user (only theirs — multiplayer is step 4).
   - Music placeholder pill (top-right corner).
   - "Leave party" button → `/lobby`.
4. `useMovement` hook owns `(x, y)` state:
   - **WASD:** keydown adds to a velocity vector. A rAF loop advances position each frame and clamps to world bounds.
   - **Click:** click on the floor sets a `target`. The same rAF loop lerps position toward the target.
   - **Interaction rule:** WASD keydown cancels the active click-target.

---

## API Contract

All endpoints under `/api`. Backend re-validates everything the frontend already validated.

| Method | Path | Body | Returns | Errors |
|---|---|---|---|---|
| `POST` | `/session` | `{ username, color }` | `{ session_id, username, color }` | `422` if invalid (pydantic) |
| `GET` | `/session/{id}` | — | `{ session_id, username, color }` | `404` if missing |
| `DELETE` | `/session/{id}` | — | `204` | `404` if missing |
| `GET` | `/parties` | — | `{ parties: PartyConfig[] }` | — |
| `GET` | `/parties/{slug}` | — | `PartyConfig` | `404` if unknown |

`:slug` path param is constrained server-side to `^[a-z0-9-]+$`.

### Backend storage
`backend/app/store.py` exposes a single `Store` class with `create_session`, `get_session`, `delete_session`, `list_parties`, `get_party`. Internal state:
- `SESSIONS: dict[str, User] = {}`
- `PARTIES: dict[str, PartyConfig] = {"cream-terrazzo": ...}`

Routes call `Store` methods only, so step 3 can swap the implementation (SQLite/Postgres) without changing routes.

### Frontend state
- `localStorage.session_id` is the only persisted piece. Username and color always come from `GET /session/{id}` so a backend restart safely logs everyone out.
- React Router for navigation.
- No global state manager — `useSession` + `useState` + the API client is enough.

---

## Validation & Security

| Layer | Check |
|---|---|
| Frontend form | `^[A-Za-z0-9]{2,20}$` on username; color must be one of the 12 swatches. Submit disabled until valid; inline error on bad input. |
| Backend pydantic | Same regex on `username`; `color` constrained to the allowed set. FastAPI returns `422`. |
| Slug routing | FastAPI path constraint `^[a-z0-9-]+$`. Unknown slug → 404 from `Store.get_party`. |

User-provided strings only flow into JSON responses and React text nodes, which auto-escape. No `dangerouslySetInnerHTML` anywhere. No SQL anywhere yet.

---

## Error Handling

- `useSession`: if `GET /session/{id}` returns 404, clear `localStorage.session_id` and redirect to `/`.
- API client wraps `fetch`, throws `ApiError(status, body)`. Pages render a small banner on failure (especially sign-in).
- `Party.tsx` on bad slug: toast "Party not found", redirect to `/lobby`.
- Movement is clamped to world bounds — visual cannot desync from logical state.

---

## Testing (TDD)

Per `.ai/CONVENTIONS.md`: write the failing test first, then minimal implementation.

| Area | Tool | What it asserts |
|---|---|---|
| Backend validation | pytest | `POST /session` rejects `"bob; DROP"`, `"a"` (too short), 21+ chars, empty color, unknown color. Accepts valid input. |
| Backend session lifecycle | pytest | Create → fetch → delete; 404 after delete. |
| Backend parties | pytest | `GET /parties` returns the registry; `GET /parties/cream-terrazzo` returns full config; unknown slug → 404. |
| Frontend SignIn | vitest + RTL | Submit disabled until valid; error shown for bad input; success navigates to `/lobby`. |
| Frontend Lobby | vitest + RTL | Renders one card per party from mocked API; click navigates to `/party/:slug`. |
| Frontend movement | vitest | `useMovement`: WASD moves, clamps at bounds, click sets target, WASD cancels active target. |
| Cross-stack contract | pytest or vitest | Slug set in TS `registry.ts` matches the slug set from `GET /api/parties`. |

---

## Decisions & Rationale

| Decision | Rationale |
|---|---|
| React + FastAPI | User-selected; sets up step 3 (AI agent API) cleanly. |
| In-memory store now, not SQLite | Smaller surface area for steps 1–2; `Store` class isolates it so step 3 can swap. |
| Lobby between sign-in and party | Scales cleanly when more parties are added without retrofitting a picker. |
| Party as `PartyConfig` registry | "Add a new party = add a config object" — user-stated requirement. |
| DOM divs (not canvas/SVG) | Simplest, AI-inspectable, fine for single-user step 2. Step 4 can re-evaluate. |
| Names always visible above avatars | Better for AI agents — no extra API call needed to map circle to identity. |
| Music deferred, placeholder UI | User-chosen; schema reserves the field so step 3+ can wire audio. |
| `session_id` in localStorage; user data from server | A backend restart cleanly logs everyone out without leaving stale data. |
