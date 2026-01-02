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

---

## grounding-hallucinated-ale-mug

**Resolved:** 2026-01-02 | **Priority:** Medium | **Related Sessions:** 324

**Problem:** Branch generator referenced entity keys (like `ale_mug_001`) that didn't exist in the database, causing grounding validation warnings.

**Solution:** Ref-based architecture assigns single-letter refs (A, B, C) to entities. LLM can only reference existing refs - invalid refs produce errors, not guessed items.

---

## narrative-state-desync-item-take

**Resolved:** 2026-01-02 | **Priority:** High | **Related Sessions:** 324

**Problem:** Narrative described taking items that were never created in database, causing state/narrative desync.

**Solution:** Ref-based architecture validates all entity refs before generating deltas. `RefDeltaTranslator` only creates TRANSFER_ITEM deltas for items that exist in the manifest.

---

## transfer-item-nonexistent-item

**Resolved:** 2026-01-02 | **Priority:** High | **Related Sessions:** 330

**Problem:** TRANSFER_ITEM deltas referenced hallucinated item keys that didn't exist, causing delta application failure.

**Solution:** Ref-based architecture requires refs to exist in manifest. Invalid refs produce clear errors instead of silent failures.

---

## quantum-branch-hallucinated-npc

**Resolved:** 2026-01-02 | **Priority:** High | **Related Sessions:** 330

**Problem:** Branch generator hallucinated NPC references (like `[innkeeper_mary:Mary]`) not in the scene manifest.

**Solution:** Ref-based architecture assigns refs only to NPCs present in the scene. LLM outputs refs (A, B, C) which are validated against the manifest.

---

## drinking-satisfy-thirst-need

**Resolved:** 2026-01-01 | **Priority:** Medium | **Related Sessions:** 317

**Problem:** Drinking actions didn't update the `thirst` need - narrative described satisfying drink but database state unchanged.

**Solution:** Updated `branch_generator.py` system prompt to document the `update_need` delta type. LLM now generates appropriate need satisfaction deltas for eating/drinking actions.

---

## narrative-time-mismatch

**Resolved:** 2026-01-01 | **Priority:** Medium | **Related Sessions:** 323, 326

**Problem:** At 20:18 (evening), narrative described "crisp morning air" and "early risers" - LLM ignored time context.

**Solution:** Added explicit time-of-day instruction to system prompt in `branch_generator.py`:
- Match all narrative to the TIME period (morning/afternoon/evening/night)
- Specific imagery guidance for each period
- Added `game_period` field to BranchContext

---

## npc-grounding-wrong-location

**Resolved:** 2026-01-01 | **Priority:** High | **Related Sessions:** 320, 321, 322

**Problem:** Player at `village_square` asked about "a merchant" but narrative referenced Old Tom (tavern innkeeper at wrong location). LLM hallucinated NPCs not in the manifest.

**Solution:**
- Strengthened prompt: "NPCs PRESENT AT THIS LOCATION: NONE" when empty
- Added NPC hallucination detection in `validation.py`
- Integrated `BranchValidator` into both cache hit and miss paths
- Fallback: "You look around but don't see anyone to talk to here."

---

## narrative-uses-entity-key-not-you

**Resolved:** 2026-01-02 | **Priority:** High | **Related Sessions:** 330

**Problem:** Narrative used player's entity key "test_hero" directly in prose instead of second-person "you" - e.g., "the shadow of test_hero" instead of "your shadow".

**Solution:** Ref-based architecture narrator prompt explicitly instructs: "The player: [player_key:you] (use 'you' as the display text)". All examples show proper usage.

---

## move-validation-wrong-manifest

**Resolved:** 2026-01-02 | **Priority:** High | **Related Sessions:** 326

**Problem:** MOVE actions were validated against the current location's manifest instead of the destination's manifest, causing false positive "NPC hallucination" errors for NPCs at the destination.

**Solution:** Obsolete in ref-based architecture - uses RefManifest with direct ref lookup, no manifest-based NPC validation. Non-ref-based pipeline uses `generation_manifest` for MOVE action validation.

---

## scene-context-wrong-location

**Resolved:** 2026-01-02 | **Priority:** High | **Related Sessions:** 324

**Problem:** After moving to a new location, "look around" described the previous location. Branch cache contained stale branches from the departure location.

**Solution:** Obsolete in ref-based architecture - generates fresh content each turn (`was_cache_hit=False`), no branch cache staleness. Recommended to use `--ref-based` flag.
