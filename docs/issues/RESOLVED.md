# Resolved Issues

This file summarizes issues that have been fixed and are no longer active. Original issue directories have been archived for historical reference.

---

## gm-hallucinates-inconsistent-narrative

**Resolved:** 2025-12-29 | **Priority:** Medium | **Related Sessions:** 301

**Problem:** GM generated narrative contradicting established facts - wrong NPCs, fabricated events, meta-questions at end of responses.

**Solution:** Implemented validation layer in `src/world_server/quantum/validation.py`:
- `NarrativeConsistencyValidator` - checks NPC refs, detects fabricated events, flags meta-questions
- `DeltaValidator` - validates state delta consistency
- `BranchValidator` - validates entire branches before caching

**Tests:** 53 unit tests in `tests/test_world_server/test_quantum/test_validation.py`

---

## gm-crashes-record-fact-wrong-params

**Resolved:** 2025-12-29 | **Priority:** High | **Related Sessions:** 301

**Problem:** GM crashed with TypeError when LLM called `record_fact` with hallucinated/missing parameters, leaving game in error state.

**Solution:** Added validation in `src/gm/tools.py` (lines 946-963):
- Validate required parameters before calling record_fact
- Return helpful error with missing params list
- Wrapped call in try/catch for graceful handling
- Applied same protection to create_entity tool

---

## gm-calls-nonexistent-move-to-tool

**Resolved:** 2025-12-29 | **Priority:** High | **Related Sessions:** 301

**Problem:** GM called non-existent `move_to` tool for player movement, causing disconnect between narrative and game state.

**Solution:** Implemented `move_to` tool in `src/gm/tools.py` (lines 2208-2260):
- Accepts destination (location key or display name) and travel method
- Fuzzy matches existing locations or auto-creates new ones
- Calculates realistic travel time based on distance
- Updates player location in database

---

## gm-repeats-response-after-tool-error

**Resolved:** 2025-12-29 | **Priority:** High | **Related Sessions:** 301

**Problem:** After tool error + grounding retry, GM repeated previous turn's response instead of addressing current player input.

**Solution:** Fixed in `src/gm/gm_node.py`:
- Added `_current_player_input` and `_current_turn_number` instance variables (lines 310-311)
- Store player input at start of run() method (lines 550-552)
- Include explicit turn number and player input in retry messages (lines 732-735, 823-824)

---

## gm-unkeyed-entities (Partial)

**Partial Fix:** 2025-12-27 | **Priority:** Medium

**Problem:** GM outputting entity names without required `[entity_key:text]` format, breaking grounding validation.

**Part 1 (FIXED):** Player equipment false positives
- Grounding validator was flagging player's worn items (tunic, boots, belt) as unkeyed
- Added `skip_player_items=True` parameter to `GroundingValidator` in `src/gm/grounding_validator.py`

**Part 2 (ONGOING):** NPC names still occasionally unkeyed with local LLM (qwen3:32b)
- See active issue tracking for Part 2 if work continues

---

## create-entity-invalid-item-type

**Resolved:** 2026-01-01 | **Priority:** High | **Related Sessions:** 314

**Problem:** CREATE_ENTITY delta with `entity_type: "item"` failed because "item" is not a valid `entitytype` enum value. Items should be created in `items` table, not `entities` table.

**Solution:** Modified `_apply_single_delta` in `collapse.py` to detect item types and route to `ItemManager.create_item()` instead of `EntityManager.create_entity()`.

---

## delta-transfer-item-not-found

**Resolved:** 2026-01-01 | **Priority:** High | **Related Sessions:** 323

**Problem:** TRANSFER_ITEM deltas referenced hallucinated item keys (e.g., `ale_mug_001`) that didn't exist in the database.

**Solution:**
- Fixed validation naming mismatch (`from/to` vs `from_entity_key/to_entity_key`)
- Added item existence check in validation
- Removed hardcoded example key from prompt that LLM was copying

---

## narrative-wrong-location

**Resolved:** 2026-01-01 | **Priority:** High | **Related Sessions:** 323

**Problem:** After moving to a new location, narrative still described the previous location because manifest was built for departure location instead of destination.

**Solution:** In `_generate_sync`, detect MOVE actions and build manifest for `action.target_key` (destination) instead of current location.

---

## player-location-update-movement

**Resolved:** 2026-01-01 | **Priority:** High | **Related Sessions:** 326

**Problem:** UPDATE_LOCATION delta used invented location keys (e.g., `rusty_tankard`) instead of exact manifest keys (e.g., `village_tavern`).

**Solution:**
- Strengthened system prompt with explicit instruction to use exact exit keys
- Upgraded validation severity from WARNING to ERROR for invalid exit keys
- Added runtime validation in collapse.py to check location exists before applying
