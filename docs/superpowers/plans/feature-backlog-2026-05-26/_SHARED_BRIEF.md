# Shared Brief — Feature Backlog 2026-05-26 Planning Round

This brief is referenced by every plan in `docs/superpowers/plans/feature-backlog-2026-05-26/`. Each plan implements one slice of the feature backlog at `docs/features/feature-backlog.md`. The slices are designed to be non-overlapping so independent agents can execute them in parallel after the foundation specs (#01, #02) merge.

## Codebase map (backend)

- `backend/app/main.py` — FastAPI app + router mounting
- `backend/app/routes/`
  - `session.py`, `agents.py` — principal registration
  - `parties.py` — party listing/config
  - `party_actions.py` — `/observe`, `/join`, `/leave`, `/move`, `/chat`
  - `reactions.py` — `/react`
  - `lighting.py` — `/lighting` (template for new module endpoints)
  - `module_notes.py`, `module_drawboard.py` — note/stroke modules
  - `dm.py`, `inbox_ws.py`, `history.py` — DM + WS + broadcast history
  - `agent_guide.py` — markdown primer returned at `/api/agent-guide`
  - `principal.py` — shared principal resolution + 401/409 helpers
- `backend/app/world.py` — `PartyWorld`: participants, event log, helpers (`recent_chat(n)`, etc.)
- `backend/app/events.py` — Pydantic event models (`Join/Leave/Move/Chat/Reaction/...`) + `Participant`
- `backend/app/store.py` — in-memory `Store`
- `backend/app/models.py` — `PartyConfig`, `Zone`, `Wall`, `Room`
- `backend/app/validation.py` — regexes, allow-lists (colors, emojis, chat-text rules)
- `backend/app/errors.py` — error envelope helpers
- `backend/app/collision.py` — wall/avatar collision
- `backend/app/realtime.py` — WS frame helpers (chat broadcast frame)
- `backend/app/inbox.py`, `dm_store.py` — DM state
- `backend/app/session_presence.py` — multi-tab presence
- `backend/app/parties_data.py` — seed parties (`cream-terrazzo`)

## Test conventions

- Tests live under `backend/tests/` and `frontend/tests/`.
- `backend/tests/conftest.py` exposes `client`, `register_human`, `register_agent`, `join_party` helpers — use these instead of re-implementing.
- Pattern: one test file per feature area (e.g. `test_<feature>_route.py`, `test_<feature>_validation.py`).
- Use `pytest -x --tb=short` for the focused run.
- Frontend uses Vitest + React Testing Library; run with `npm test -- --run`.
- All new tests must be written **first** (TDD per the writing-plans skill).

## Existing plan format (reference)

See `docs/superpowers/plans/2026-05-20-agent-experience-improvements.md` for the established style:
- Header with Goal / Architecture / Tech Stack
- Spec → Task map
- File Structure (Create / Modify / Test, with exact paths)
- Numbered tasks, each broken into 2-5 minute checkbox steps
- Every step that touches code shows the full code
- Frequent commits (typically one commit per task)
- Final task is a manual smoke-test or docs-update closing the loop

## Shared decisions (do not redesign these)

1. **Owner kept the 65-char chat cap.** Do not raise it. UX rationale: ensure all messages fit on display without dominating.
2. **Proximity is the default for `/chat`** (defined in spec #02). Room-wide broadcast is opt-in (defined in spec #03 via either `scope: "room"` or a separate `/announce` endpoint — spec #03 owns the decision and commits to one).
3. **Event shape unification lives in spec #01.** Other specs adding new event types should follow the unified shape (`actor_id`, `actor_username`, `actor_kind` flat at top level; `actor_color` from spec #06 once merged).
4. **Standardized error envelope** is `{"detail": {"error": "<code>", "message": "<human-readable>", ...extra}}`. Spec #01 owns the sweep. New endpoints in other specs MUST use this shape from the start.
5. **Proximity radius** is a single constant `PROXIMITY_RADIUS` defined in `backend/app/world.py` by spec #02. Default: TBD by spec #02 (suggest ~180 world units — about 1.5× a zone diameter — but spec #02 owner picks the number). Other specs reference the constant; they do not redefine it.
6. **Proximity respects line-of-sight (walls) is OUT OF SCOPE for v1.** Plain radius only. Spec #02 documents this explicitly.
7. **`agent_id` remains the bearer credential.** Short-lived session tokens (P3) are out of scope for this backlog round.
8. **No frontend SDK in this round.** Spec #11 mentions it as a follow-up only.

## Cross-spec coordination

| Spec | Depends on | Notes |
|---|---|---|
| 01 event shape + errors | — | Foundation. Merge first. |
| 02 proximity model + scoped observer | 01 | Foundation. Merge second. |
| 03 chat enhancements | 01, 02 | Builds on proximity default + new event fields |
| 04 module chat + improvements | 01, 02 | Module-scoped chat reuses proximity helpers |
| 05 expressive actions | 01 | New event types use unified shape |
| 06 social primitives | 01 | Adds `actor_color` to events globally |
| 07 music module | 01 | New module mirrors lighting pattern |
| 08 discovery + lobby | — | Touches `/api/parties` only — independent |
| 09 push + optimistic | 01, 02 | New WS for agents; references unified events |
| 10 batched /act + queue | 01, 03 | Action queue respects chat cooldown contract |
| 11 agent onboarding | 01, 02 | Welcome event uses unified event shape; references context endpoint |

If your spec needs something another spec defines, REFERENCE the other spec (by filename) rather than re-defining it. Do not duplicate types or constants across specs.

## Output rules for plan authors

- Save your plan to the exact path your prompt assigns.
- Use the writing-plans skill format strictly (header, file structure, TDD tasks, full code in every step).
- Include a "Spec → Task" map even if the source is a backlog section, not a separate spec doc.
- Include a final task: update `backend/app/routes/agent_guide.py` if your changes affect agent behavior, and update `frontend/src/api/types.ts` if you added/changed types.
- Mark anything explicitly out of scope so it doesn't leak into other specs.
- Do not modify other plan files. Do not modify the feature backlog. Do not modify `_SHARED_BRIEF.md`.
