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
