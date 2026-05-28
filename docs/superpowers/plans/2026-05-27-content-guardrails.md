# Content Guardrails — Implementation Plan

**Goal:** Add a content guardrail layer that censors sensitive words in user-generated text, driven by a single source-of-truth wordlist file.

## Decisions (already made with the owner)

- **Scope:** party chat, direct messages, sticky notes, usernames.
- **Action on hit (chat / DM / sticky notes):** mask the matched word with `*` characters of equal length. Message still goes through.
- **Action on hit (usernames):** reject with 422 (asterisks aren't a usable username).
- **Matching:** whole-word, case-insensitive (`\b…\b`). No leetspeak normalization in this pass.
- **Source-of-truth file:** `backend/app/blocklist.txt` — one word per line, `#` for comments, blanks ignored. Loaded once at import.

## Files

**New:**
- `backend/app/blocklist.txt` — committed wordlist. Seed with a small starter set (~5 common profanities, plus 1–2 comment lines documenting the format).
- `backend/app/guardrails.py` — loader + matcher.
- `backend/tests/test_guardrails.py` — unit + integration tests.

**Edited:**
- `backend/app/validation.py` — call masker at the end of `validate_chat_text` and `validate_note_text`.
- `backend/app/models.py` — username field validator rejects entries containing a blocked word.
- `backend/app/routes/agents.py` — same username rejection for agent registration.
- `CLAUDE.md` — one-line note pointing at `blocklist.txt`.
- `backend/app/routes/agent_guide.py` — one-line note that chat may be masked.

## `guardrails.py` API

```python
BLOCKLIST: frozenset[str]                       # lowercase entries
BLOCKLIST_REGEX: re.Pattern | None              # \b(w1|w2|...)\b, IGNORECASE; None if empty

def mask_blocked(text: str) -> tuple[str, bool]:
    """Replace each whole-word match with '*' * len(match). Returns (masked, was_masked)."""

def contains_blocked(text: str) -> bool:
    """True if `text` contains any blocked word as a whole word."""

def _load_blocklist(path: Path) -> frozenset[str]:
    """Skip blanks and lines starting with '#'. Lowercase. Trim."""
```

Implementation notes:
- Build the regex with `re.escape` on each entry, joined with `|`, sorted longest-first so multi-word entries (if ever added) match before any substring of them.
- If `BLOCKLIST` is empty, `mask_blocked` returns `(text, False)` and `contains_blocked` returns `False`.
- Masking preserves the original case/punctuation around the match — only the matched span becomes asterisks.

## Tasks

### Task 1 — Core module, wordlist, and unit tests

Create:
- `backend/app/blocklist.txt` with a small starter set. Keep it boring and uncontroversial — `damn`, `hell`, `crap`, `shit`, `fuck` is fine. Two leading `#`-comment lines explaining the format.
- `backend/app/guardrails.py` per the API above.
- `backend/tests/test_guardrails.py` covering:
  - `mask_blocked` masks exact whole-word matches, case-insensitively.
  - `mask_blocked` does NOT match substrings (e.g., `"classic"` survives when `"ass"` is blocked — use a temporary blocklist override for this if `ass` isn't in the seed list).
  - Length-preserving masking (`"Damn!"` → `"****!"`).
  - Multiple hits in one string all get masked.
  - `was_masked` boolean returns correctly.
  - `contains_blocked` returns True/False appropriately.
  - Loader ignores `#` comments and blank lines, and lowercases entries.
  - Empty blocklist behavior: `mask_blocked` returns text unchanged, `was_masked=False`; `contains_blocked` returns False.

TDD: write the tests first, see them fail, implement, see them pass. Use `monkeypatch` or a module-level reload helper if you need to test alternate blocklists — do NOT mutate the global `BLOCKLIST` between tests in a way that leaks.

Run `python -m pytest backend/tests/test_guardrails.py -q` and confirm green before finishing.

### Task 2 — Wire masking into chat, DM, and sticky-note validators

Edit `backend/app/validation.py` so that `validate_chat_text` and `validate_note_text`, after their existing trim/charset/length checks pass, call `mask_blocked` and return the masked version. Import is `from app.guardrails import mask_blocked`.

Add integration tests (extend `test_guardrails.py` or add to an existing test file — your judgment):
- POST `/api/parties/{slug}/chat` with a message containing a blocked word: response body and the next `/observe` cursor diff both show the masked form.
- DM `POST` containing a blocked word: same — stored and broadcast message is masked.
- Sticky-note create and update both store the masked text.

Run the full backend test suite (`python -m pytest -q` from `backend/`). All 384 prior tests should still pass; new tests should pass.

### Task 3 — Reject usernames + docs

Edit:
- `backend/app/models.py` — in the session/username field validator (around line 15), after the existing `USERNAME_REGEX` check, call `contains_blocked(v)` and raise `ValueError("username contains disallowed word")` if True.
- `backend/app/routes/agents.py` — same change at the equivalent line (~23). Both surfaces must reject identically.
- `CLAUDE.md` — under the existing validation discussion, one short line: edit `backend/app/blocklist.txt` to manage the wordlist; restart picks up changes.
- `backend/app/routes/agent_guide.py` — one short sentence noting that chat/DM/sticky-note text may be masked server-side.

Tests (add to a sensible existing test file, e.g. `test_session.py` and `test_agents.py`):
- `POST /api/session` with a username containing a blocked word → 422.
- `POST /api/agents` with same → 422.
- Username with no blocked word still works (regression).

Run the full backend test suite. All tests pass.

## Out of scope

- Leetspeak / unicode-confusable normalization.
- Per-category severity, hot-reload, admin endpoints.
- Frontend client-side preview of masking.
