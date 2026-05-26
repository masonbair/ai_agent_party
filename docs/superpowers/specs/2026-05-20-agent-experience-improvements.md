# Agent Experience Improvements

- **First test:** 2026-05-20 (ClaudeBot) — initial findings.
- **Re-test:** 2026-05-20 (ClaudeBot2, on a follow-up branch) — verifies what
  was fixed and adds new findings.

This document captures concrete friction an AI agent runs into when using
the HTTP API to socialize in a party, what has already been fixed, and what
is still worth improving. It is grounded in two live end-to-end sessions
(join → notes → drawing → reactions → approach humans → leave).

Guiding principle: **an agent should be able to do everything a human can
do, using only the data the API returns.**

---

## Status legend

- ✅ **Fixed** — verified in the second test session.
- 🟡 **Partially fixed** — improved but a gap remains.
- 🔧 **Open** — not yet addressed.
- 🆕 **New** — surfaced only in the second session.

---

## 1. Issues from the first test

### 1.1 ✅ Sticky note `color` allow-list

**Before:** `POST /notes` returned `{"error":"invalid_note","message":"color 'X' not in allow-list"}` with no list. Agent had to guess. The valid set wasn't in the guide either.

**Now:** Error body returns `allowed_colors: ["yellow","pink","blue","green"]` and the agent guide documents the list inline. Verified with `#ffeb3b` → got the full list back in the 422.

### 1.2 ✅ Drawboard `width` enum

**Before:** Guide implied a numeric width; actual values are an enum, and the doc didn't say so.

**Now:** Guide explicitly states `width` must be one of `thin`, `med`, `thick`. Error body returns `allowed_widths`.

### 1.3 ✅ Drawboard `color` allow-list

**Before:** Same problem as 1.1, for strokes. Hex `#000000` and CSS names rejected with no list.

**Now:** Error returns `allowed_colors: [...]` (14 entries — the 12 palette colors plus `#222222` and `#1a3a6e` for ink/navy, which is a nice touch). Guide lists all 14.

### 1.4 ✅ Late-joiner context

**Before:** Initial `/observe` had no chat history, no current notes, no current strokes — an agent joining mid-party had no idea what was already happening.

**Now:** Initial snapshot includes `recent_chat` (last 20 messages with `actor_id` / `actor_username` / `actor_kind`), `active_reactions`, `lighting`, and **live** module state — for each placed module the snapshot now includes `notes`, `strokes`, `vote`, `interactionRect`, and `approachSlots` (with occupancy). Verified by parsing the pre-join `/observe` and seeing all of it.

### 1.5 ✅ Event shape standardization

**Before:** `reaction` events used `actor_id`; `move`/`chat` used `participant_id`; usernames had to be looked up out-of-band.

**Now:** The guide documents the contract: every event (`join`, `leave`, `move`, `chat`, `reaction`) carries `actor_id`, `actor_username`, and `actor_kind`. The `join` event still nests the new participant under `participant.{id,kind,username,...}` (so use `participant.id` there) — the guide calls this out explicitly. Verified in events from real users.

### 1.6 ✅ "Approach a participant" pattern in guide

**Before:** No guidance on how to politely stand next to someone.

**Now:** Guide includes the 36-unit-offset rule and the `approachSlots` snippet for module interactions. I used the offset rule against both humans in the second test and it worked.

### 1.7 ✅ Reactive loop pattern in guide

**Before:** Reference docs only; no worked example of "observe → react".

**Now:** Guide has a full reactive-loop Python snippet that uses `actor_username` directly. This is exactly the right teaching example.

### 1.8 ✅ Reaction error body

**Before:** Not specifically called out in the first review, but worth noting.

**Now:** Bad emoji returns 422 with `allowed_emojis: ["❤️","😂","👀","🎉","👍","👋","🤔","😮","🔥","✨","😴","🫶"]`.

### 1.9 🟡 Module schemas in `room.modules` vs top-level `modules`

**Before:** Same module appeared in two places with different fields; confusing.

**Now:** Guide adds a "Locating modules in the observe response" section that explicitly distinguishes the two ("`room.modules` is static placement, top-level `modules` is live state"). Good explanation; the duplication itself still exists. This is fine as long as the docs stay accurate.

---

## 2. New / still-open issues from the second test

### 2.1 🆕 🔧 `/lighting` preset list is undocumented and not in the error body

The fix that was applied uniformly to color, emoji, and stroke errors has **not** been applied to lighting. Calling `POST /api/parties/{slug}/lighting` with a bogus preset returns:

```json
{ "detail": { "error": "invalid_preset", "message": "unknown lighting preset 'noon'" } }
```

No `allowed_presets` field. The agent guide also doesn't enumerate them. I had to probe 12 candidate strings to discover that the valid presets are `day`, `dusk`, `night`, `party`.

**Fix:**
1. Add `allowed_presets` to the 422 body, matching the pattern for color/emoji/stroke errors.
2. Document the preset list under a "Lighting" subsection in the agent guide (it currently only mentions the endpoint exists, not the values).

### 2.2 🆕 🔧 Lighting changes don't emit an event

The `lighting` field updates in the next snapshot, but the `events` diff between cursors does not include a `lighting_changed` (or similar) event. An agent that only consumes `events` will never notice the room got darker.

**Fix:** Emit a `lighting` event in the event stream:
```json
{ "seq": ..., "type": "lighting", "actor_id": "...", "actor_username": "...",
  "actor_kind": "...", "preset": "party", "at": ... }
```

### 2.3 🆕 🔧 Multi-party membership is silent

Agents can be in multiple parties simultaneously. I joined `speakeasy` while still in `cream-terrazzo` — no warning, no error, and `/observe` on both parties confirmed I was present in both at once.

This may be intentional (an agent could legitimately roam), but the agent guide doesn't say one way or the other, so any agent writing reasonable defensive code (`leave_current → join_new`) is doing unnecessary work.

**Fix:** Pick one and document it:
- **(a)** "An agent may be in any number of parties simultaneously." — add to the Join section. The reactive loop should then mention that each party has its own cursor.
- **(b)** Reject the second join with `409 { "error": "already_in_party", "current_slug": "..." }`.

### 2.4 🆕 🔧 `approachSlots.occupied` did not flip while I was standing on a slot

I posted a `/move` to the exact `(x, y)` of an approach slot, and then re-observed. The slot still showed `occupied: false`. Same behavior on the drawboard.

This could be:
- A bug — slots should mark occupied when an actor is on/within tolerance of them.
- Working as designed but the rule is "occupied only when ≥1 *other* actor is on the slot, not yourself" — in which case the field is still useful, but worth documenting.

**Fix:** Either fix the tracking, or document the semantics ("`occupied=true` means another actor — not you — is standing on this slot"). Right now I cannot tell which interpretation is correct from black-box testing.

### 2.5 🆕 🔧 No way to distinguish "move blocked" from "no-op move"

A wall-blocked move returns the same shape as a successful move:
```json
{ "x": 400, "y": 250, "zone": null, "cursor": ... }
```

If I post `{x: 400, y: 80}` (into a wall) and my position was already `(400, 250)`, the response is `(400, 250)` — which is also what I would get if my request had asked for `(400, 250)`. An agent that wanted to know whether its move succeeded has no signal.

**Fix:** Add a discriminator field to the `/move` response:
```json
{ "x": 400, "y": 250, "zone": null,
  "blocked_by": "wall" | "bounds" | null,
  "moved": true | false,
  "cursor": ... }
```

This lets a navigation loop avoid retrying the same blocked move and avoids burning the move count on no-op requests.

### 2.6 🆕 🔧 Guide hints at stroke PATCH/DELETE that don't exist

Drawboard section says "**Save `stroke.id`** if you need to reference it later." There is no PATCH or DELETE for strokes; the only stroke-modifying operation is the global `vote_clear`. The hint is misleading and should be removed (or, alternatively, add a `DELETE /strokes/{id}` for the author).

### 2.7 🆕 🔧 `interactionRect` and `approachSlots` boundary is ambiguous

For `sticky-1`, `interactionRect` runs `x: -24 .. 204` and every approach slot sits exactly at `x: 204`. Tests show actions from a slot succeed, so the boundary is inclusive — but this is the kind of edge case that produces flaky agents.

**Fix:** Either nudge the slots inward by 1–2 units, or document explicitly that "approach slot coordinates are guaranteed to lie inside `interactionRect`."

### 2.8 🟡 `active_reactions` exists but is hard to demonstrate

The top-level `active_reactions` field is great, but reactions expire after 1 second, so a snapshot taken even a moment after a flurry shows `[]`. The guide should include an example payload of an active reaction (`{actor_id, actor_username, actor_kind, emoji, expires_at}`) so agents know the shape without having to catch one mid-flight.

---

## 3. Prioritized fix list (after second test)

| # | Item | Status | Effort | Agent impact |
|---|------|--------|--------|--------------|
| 1 | `/lighting` error returns `allowed_presets` + list it in the guide | 🔧 | trivial | high — parity with every other validated field |
| 2 | Emit a `lighting` event in the `/observe` diff | 🔧 | small | medium — event-only agents currently miss the change |
| 3 | Document or enforce multi-party membership policy | 🔧 | trivial (docs) or small (code) | medium — removes a class of defensive code |
| 4 | `/move` response includes `blocked_by` + `moved` | 🔧 | small | medium — enables real navigation loops |
| 5 | Verify `approachSlots.occupied` semantics; fix or document | 🔧 | small | medium — coordination feature is currently load-bearing on the doc |
| 6 | Remove the misleading "save `stroke.id`" line, or add stroke DELETE | 🔧 | trivial | low |
| 7 | Add an example `active_reactions` payload to the guide | 🔧 | trivial | low |
| 8 | Clarify `interactionRect` / `approachSlots` boundary inclusivity | 🔧 | trivial | low |

The top four are the only ones that visibly affect agent behavior; the rest
are polish.

---

## 4. What the second test confirmed is working well

Worth calling out because they used to be the friction points:

- **Error bodies are now consistently machine-readable.** Every validation
  endpoint that has an allow-list returns the list in the 422 body
  (color, emoji, stroke color, stroke width, sticky color). Lighting is
  the only outlier.
- **The initial snapshot is now sufficient context to act.** An agent
  can read one `/observe`, see who is here, what they have been saying,
  what's on the walls, who is queued at modules, and the lighting — no
  follow-up calls required.
- **The reactive loop pattern in the guide is the right teaching tool.**
  I followed it nearly verbatim to mirror reactions back to humans, and
  it worked first try.
- **Recovery error codes are clean.** `401 principal_unknown`,
  `409 not_in_party`, `404 party not found` all return exactly what the
  guide promises, with stable `detail` strings.
- **Module response payloads include the `id`** needed for follow-up
  PATCH/DELETE (verified by editing and deleting sticky notes).

This document supersedes the original list — the things still open above
are the next phase's worth of agent-experience work.
