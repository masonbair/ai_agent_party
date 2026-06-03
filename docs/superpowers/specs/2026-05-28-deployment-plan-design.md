# Deployment Plan — openParty

**Date:** 2026-05-28
**Status:** Spec — no code changes
**Target hostname:** `party.masonbair.com`
**Budget ceiling:** ~$25/mo
**Priority:** Learning value > cost > ops ease

---

## Goal

Get the current openParty (FastAPI backend + Vite/React frontend, in-memory state) reachable at `https://party.masonbair.com` on always-on infrastructure that:

1. Stays under $25/mo today and after Phase 4 (DB + WebSockets) lands.
2. Teaches production-shaped patterns (containers, CI/CD, secrets, TLS, observability) without paying for enterprise infra.
3. Does not require re-architecting hosting when DB + realtime are added.

This spec covers deployment plumbing only. It does **not** cover the in-memory-to-DB migration, WebSocket implementation, rate limiting, or auth hardening. Each of those gets its own spec.

---

## Chosen stack

| Layer | Choice | Why |
|---|---|---|
| Backend host | **Fly.io** (Docker app, `shared-cpu-1x` 256 MB, always-on, single region) | Real Dockerfile + `fly.toml`, native WebSocket support, ~$3/mo, portable container (no lock-in). |
| Frontend host | **Cloudflare Pages** | Free, global CDN, PR previews, builds straight from the repo. |
| DNS + TLS | **Cloudflare** (registrar stays wherever masonbair.com lives; only DNS moves if not already there) | One control plane for DNS + TLS + Pages. Free. |
| CI/CD | **GitHub Actions** (backend) + **Cloudflare Pages built-in CI** (frontend) | Path-filtered workflows; tests gate backend deploys. |
| Future DB | **Fly Postgres** (or Neon for managed) | Same `DATABASE_URL` env var, swappable. |
| Future realtime | **Fly raw WS** via dedicated `api.party.masonbair.com` hostname | `_redirects` doesn't rewrite WS; subdomain bypass keeps it clean. |

Rejected alternatives:
- **Hetzner VPS + Docker Compose** — strong learning, slightly cheaper, but more sysadmin surface than the user wants right now.
- **Railway** — easier ops, but hides too much for the learning-first priority and runs ~$10–15/mo.
- **Cloud Run** — WebSocket caps + cold starts conflict with the polling-based `/observe` endpoint.

---

## Architecture

```
                    ┌──────────────────────────────┐
   users ──HTTPS──► │ party.masonbair.com          │
                    │ (Cloudflare DNS + TLS)       │
                    └──────────┬───────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
   ┌──────────▼──────────┐         ┌────────────▼──────────────┐
   │ Cloudflare Pages    │         │ Fly.io app (Docker)        │
   │ static React build  │         │ FastAPI / uvicorn          │
   │ from frontend/dist  │ ──API─► │ /api/*, /docs, /openapi    │
   │ /_redirects proxies │         │ shared-cpu-1x 256 MB       │
   │ /api/* to Fly       │         │ single region (iad)        │
   └─────────────────────┘         └───────────────────────────┘
                                         (later: Fly Postgres)
```

Two deployable artifacts, one repo. The frontend serves the SPA; `/api/*` is proxied (rewrite, not redirect) from Pages to the Fly app via `_redirects`, so the browser sees same-origin. No CORS config in FastAPI.

---

## Containerization (backend)

### Dockerfile (multi-stage, non-root)

```dockerfile
# ---- builder ----
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv pip install --system --no-cache -r pyproject.toml

# ---- runtime ----
FROM python:3.11-slim
WORKDIR /app
RUN useradd -m -u 1000 app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY backend/app ./app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

### fly.toml

```toml
app = "openparty-api"
primary_region = "iad"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "off"
  min_machines_running = 1

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    method = "GET"
    path = "/api/health"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

### Key constraints documented in-spec

- **`auto_stop_machines = off`**: the polling `/observe` endpoint makes cold-start latency unacceptable. Costs ~$2–3/mo more than scale-to-zero; matches the always-on requirement.
- **`--proxy-headers`**: Fly terminates TLS upstream; required so FastAPI sees real client IPs.
- **Single uvicorn worker**: `world.py` / `store.py` hold state in-process. Multiple workers would corrupt state. Re-enable `--workers 2` *only* after DB migration moves state out of process.
- **No volume today**: state is in-memory and resets on deploy. Acceptable for beta. Add a 1 GB volume only when Postgres lands on Fly.

### .dockerignore (must include)

```
frontend/
node_modules/
.git/
docs/
*.md
backend/tests/
.venv/
__pycache__/
```

### docker-compose.yml (dev parity)

A `docker-compose.yml` at repo root mirrors the Fly deployment shape: builds the Dockerfile, exposes 8000, runs the same `CMD`. Verifies "works in container" before deploy. Not used in production.

---

## Frontend hosting + routing

### Cloudflare Pages settings

| Setting | Value |
|---|---|
| Repository | (the openParty repo) |
| Production branch | `main` |
| Build command | `cd frontend && npm ci && npm run build` |
| Output directory | `frontend/dist` |
| Node version | 20.x (project-pinned via `.nvmrc` if present) |

PR previews fire automatically — useful for visual review on frontend changes.

### `frontend/public/_redirects`

```
/api/*  https://openparty-api.fly.dev/api/:splat  200
```

`200` is a rewrite (proxy), not a 301/302. URL bar stays on `party.masonbair.com`; the browser treats the API as same-origin. No CORS preflights.

### DNS at Cloudflare

| Type | Name | Target | Proxy |
|---|---|---|---|
| `CNAME` | `party` | `<pages-project>.pages.dev` | Proxied (orange cloud) |

The Fly hostname `openparty-api.fly.dev` is only used by Pages internally and (later) by the dedicated WS subdomain. Not user-facing.

### TLS

- `party.masonbair.com` — Cloudflare auto-issues + renews.
- `openparty-api.fly.dev` — Fly auto-issues + renews.
- End-to-end HTTPS; no plaintext leg.

---

## CI/CD

### Frontend

Handled entirely by Cloudflare Pages. Optionally add a separate GH Action to run `vitest` on PRs (`paths: ['frontend/**']`) so failing tests block merge. Not required for v1.

### Backend — `.github/workflows/deploy-backend.yml`

```yaml
name: deploy-backend
on:
  push:
    branches: [main]
    paths: ['backend/**', 'Dockerfile', 'fly.toml', '.github/workflows/deploy-backend.yml']
  pull_request:
    paths: ['backend/**']

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install uv && uv pip install --system -r backend/pyproject.toml
      - run: cd backend && pytest

  deploy:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

Notes:
- `paths:` filters prevent frontend-only PRs from triggering a Fly rebuild.
- `deploy` is gated by `needs: test`.
- `--remote-only` runs the Docker build on Fly's builders (faster, no runner cache to manage).
- Single secret to create: `FLY_API_TOKEN` (from `flyctl auth token`).

### Rollback

`flyctl releases list` then `flyctl deploy --image <previous-image-ref>`. Document in `docs/runbook.md` during Phase D5.

### Observability

- **Live logs:** `flyctl logs`.
- **Persisted logs:** add a Better Stack or Axiom free-tier log drain in Phase D5 if needed.
- **Healthcheck:** `/api/health` (exists). Fly auto-restarts on repeated failure.
- **Frontend:** Cloudflare Pages analytics (free).

---

## Forward path (deferred, but not blocked by this plan)

### Persistence

```
flyctl postgres create --name openparty-db --region iad --vm-size shared-cpu-1x --volume-size 1
flyctl postgres attach --app openparty-api openparty-db
```

Sets `DATABASE_URL` automatically. Code reads via env var. Once state is in Postgres:
- Re-enable `--workers 2` on uvicorn (256 MB still fits).
- Optional swap to **Neon** for fully managed Postgres (same `DATABASE_URL`, free tier).

Migration of `store.py` / `world.py` to SQLAlchemy + Alembic is a separate spec.

### WebSockets / SSE (Phase 4)

- Fly's HTTP service proxies WS upgrades natively — no `fly.toml` change.
- Cloudflare Pages `_redirects` does **not** rewrite WS upgrades.
- Add a second DNS record: `CNAME api.party → openparty-api.fly.dev`, proxied. Run `flyctl certs create api.party.masonbair.com`.
- Client connects to `wss://api.party.masonbair.com/ws`. HTTP API can still go through Pages for same-origin behavior.
- Cookies on `.party.masonbair.com` (parent domain) span both subdomains, if used. Token-in-localStorage is unaffected.
- Single machine = trivial in-process pub/sub for fan-out. Cross-machine fan-out (Upstash Redis via Fly Marketplace + `fly-replay`) only when scaling past one machine.

### Custom domain swap (future `openparty.xyz` or similar)

- Add the new domain in Cloudflare → attach as a custom domain on the Pages project (Pages supports multiple).
- Add matching Fly cert if you want `api.openparty.xyz`.
- Keep `party.masonbair.com` as a 301 to the new domain for at least 6 months.

### Multi-region

Trivially `flyctl scale count 2 --region fra` *after* DB lands. Today, in-memory state makes multi-region actively wrong.

---

## Cost summary

| Item | Today | After Phase 4 |
|---|---|---|
| Fly backend (256 MB, always-on) | ~$3 | ~$3 |
| Fly Postgres tiny | — | $2–5 |
| Cloudflare Pages | $0 | $0 |
| Cloudflare DNS / TLS | $0 | $0 |
| Log drain (Better Stack / Axiom free tier) | $0 | $0 |
| **Total** | **~$3/mo** | **~$5–10/mo** |

Headroom to bump to `shared-cpu-2x` / 512 MB (~$7/mo) if memory pressure shows up. Comfortably inside the $25/mo ceiling.

---

## Phased rollout

Each phase is independently mergeable and ends with something demonstrable.

### Phase D1 — Containerize backend locally
- Write `Dockerfile`, `.dockerignore`, `docker-compose.yml`.
- Verify `docker compose up` serves the API on `localhost:8000`.
- **Exit:** all backend tests pass when run inside the container.

### Phase D2 — Deploy backend to Fly
- `flyctl launch` (skip generated `fly.toml`, use the one specified above).
- `flyctl deploy` manually.
- **Exit:** `https://openparty-api.fly.dev/api/health` → 200; `/docs` loads; a manual `POST /api/session` works.

### Phase D3 — Deploy frontend + wire DNS
- Connect repo to Cloudflare Pages with the build settings above.
- Commit `frontend/public/_redirects`.
- Add `party` CNAME at Cloudflare; attach `party.masonbair.com` as Pages custom domain.
- **Exit:** open `https://party.masonbair.com` in a browser, sign in, join the lobby, walk around. Full flow works end-to-end.

### Phase D4 — CI/CD
- Add `FLY_API_TOKEN` to GitHub repo secrets.
- Commit `.github/workflows/deploy-backend.yml`.
- Push a trivial backend change to verify the workflow runs tests + deploys.
- **Exit:** merging a backend PR to `main` deploys to Fly without human intervention; a frontend PR shows a Pages preview URL in the PR conversation.

### Phase D5 — Operational basics
- Document `flyctl logs`, rollback steps, secret rotation in `docs/runbook.md`.
- Add Cloudflare Pages analytics (one-click).
- Add `SECURITY.md` noting deferred items: rate limiting, bearer-token auth, avatar-vs-avatar collision, event-log trimming.
- Decide on log drain (Better Stack / Axiom) only if `flyctl logs` proves insufficient.
- **Exit:** the repo is hand-offable — a stranger could deploy + rollback from the docs alone.

---

## Explicitly out of scope for this spec

Each becomes its own spec when the time comes:

1. In-memory → Postgres migration (`store.py`, `world.py`, SQLAlchemy + Alembic, test strategy).
2. WebSocket / SSE implementation (Phase 4 multiplayer design already exists at `2026-05-12-phase4-multiplayer-design.md`).
3. Custom dedicated domain purchase + swap.
4. Rate limiting + bearer-token auth hardening.
5. Event-log trimming (per CLAUDE.md "Not Yet Implemented" — flagged because the 256 MB memory ceiling makes unbounded growth a real concern; monitor RSS and cut a spec if it approaches 200 MB).
6. Avatar-vs-avatar collision.

---

## Risks + open questions

- **`/observe` polling load on a 256 MB machine.** Unknown until real traffic. Mitigation: monitor RSS + request rate in Phase D5; bump to `shared-cpu-2x` / 512 MB at ~$7/mo if needed.
- **Single-region single-machine = no HA.** Acceptable for beta. Phase 4 + DB unlocks multi-machine; do not pursue earlier.
- **Cloudflare Pages → Fly proxy adds one hop of latency.** Typically <30 ms; same continent. If latency-sensitive endpoints emerge, expose them via `api.party.masonbair.com` directly (the same hostname planned for WS).
- **Single uvicorn worker is a real cap.** Don't lift it until DB migration removes in-process state. Document this in `fly.toml` as a comment so future-you doesn't "optimize" it back into corruption.
