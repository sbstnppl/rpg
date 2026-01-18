# LLM Hallucinates NPCs Not in Scene Manifest

**Status:** Awaiting Verification
**Priority:** High
**Detected:** 2026-01-18
**Fixed:** 2026-01-18 (regression fix applied)
**Related Sessions:** 346, 347

## Problem Statement

When the player tries to interact with generic entities mentioned in the narrative (e.g., "patrons" in a tavern), the LLM branch generator creates entities that don't exist in the scene manifest. The grounding validator correctly catches these, but the player gets a confusing error message instead of a graceful fallback.

## Original Behavior

**Player input:** "try to listen in on the conversation of the patrons at the corner table"

**Error output:**
```
Branch validation: variant:failure:delta - Delta[2]: Entity 'laborer_1' not found
Branch validation: variant:failure:delta - Delta[3]: Entity 'laborer_2' not found
Branch validation: variant:critical_success:grounding - Invalid entity key: [laborer_1:Unshaven Laborer]
Branch validation: variant:critical_success:grounding - Invalid entity key: [laborer_2:Bearded Laborer]
Branch validation: variant:critical_failure:delta - Delta[4]: Entity 'laborer_1' not found
Branch validation: variant:critical_failure:delta - Delta[5]: Entity 'laborer_2' not found

"You try, but something doesn't seem quite right..."

Error: Validation errors: Delta[2]: Entity 'laborer_1' not found...
```

The narrative earlier mentioned "a few early patrons" as flavor text, but these are not actual entities in the manifest.

## Root Cause

Two issues:
1. **Narrator uses plain prose** for NPCs (e.g., "patrons") instead of `[key:display]` format
2. **No CREATE_ENTITY deltas** emitted for ambient NPCs mentioned in narrative

## Solution Implemented

### Part 1: Require Grounded NPC References in Narrative

Updated `branch_generator.py` system prompt to require all NPC mentions use `[key:display]` format AND emit corresponding `CREATE_ENTITY` deltas.

**New prompt section (lines 277-289):**
```
INVARIANT FOR AMBIENT NPCs:
If your narrative describes NPCs in the scene (patrons, travelers, guards, etc.), you MUST:
1. Use [key:display] format for ALL NPC references (e.g., [patron_01:a weathered farmer])
2. Generate a create_entity delta for each new NPC
```

### Part 2: Auto-Create NPCs from Grounded References

Extended `DeltaPostProcessor` with `_inject_missing_npc_creates()` method that:
1. Parses narrative for `[npc_key:display]` patterns
2. Auto-injects `CREATE_ENTITY` deltas for keys matching NPC_KEY_HINTS
3. Includes location_key from manifest for proper placement

**NPC key hints recognized:**
- patron, traveler, stranger, guard, merchant
- villager, farmer, laborer, beggar, servant
- worker, visitor, customer, guest, passerby

## Files Modified

- [x] `src/world_server/quantum/branch_generator.py` - Added INVARIANT FOR AMBIENT NPCs section
- [x] `src/world_server/quantum/delta_postprocessor.py` - Added NPC_KEY_HINTS, `_inject_missing_npc_creates()`
- [x] `tests/test_world_server/test_quantum/test_delta_postprocessor.py` - Added TestInjectMissingNPCCreates

## Test Coverage

New tests in `TestInjectMissingNPCCreates`:
- [x] NPCs in [key:display] format auto-created
- [x] Existing NPCs not duplicated
- [x] Multiple NPCs created
- [x] Non-NPC keys not created as NPCs
- [x] Pending creates not duplicated
- [x] Created NPCs include location_key
- [x] Empty/None narrative handled
- [x] Various NPC key hints recognized
- [x] Same NPC mentioned multiple times creates only one

## Related Issues

- `docs/issues/narrative-state-desync-items/` - Similar issue with item creation (already fixed with same pattern)

## References

- `src/world_server/quantum/branch_generator.py` - System prompt with NPC invariant
- `src/world_server/quantum/delta_postprocessor.py` - NPC auto-creation logic
- `src/gm/grounding_validator.py` - Validates entity references

---

## Regression Notes (2026-01-18, Session 347)

The fix doesn't work consistently. On "look around" in session 347:

```
Branch validation: variant:success:grounding - Invalid entity key: [patron_01:a weathered farmer]
Branch validation: variant:success:grounding - Invalid entity key: [patron_02:a grizzled cartwright]
```

**Investigation needed:**
- Is `_inject_missing_npc_creates()` being called before grounding validation?
- Are the injected create_entity deltas being processed in the right order?
- Does grounding validation run on original vs post-processed deltas?

The DeltaPostProcessor clarification says LLM wants to create the NPCs, but validation still fails.

### Root Cause Found

The execution order was:
1. `branch_generator.generate_branch()` calls `DeltaPostProcessor.process_async()`
2. `_inject_missing_npc_creates()` creates CREATE_ENTITY deltas for NPCs like `patron_01`
3. Branch returned with fixed deltas containing the new entity keys
4. `BranchValidator(generation_manifest)` created with **original manifest**
5. Grounding validation fails - `patron_01` not in `manifest.contains_key()`

The `GroundingManifest` has an `additional_valid_keys` field designed for exactly this purpose, but it wasn't being populated with the injected keys.

### Regression Fix (2026-01-18)

**File:** `src/world_server/quantum/pipeline.py`

After `generate_branch()` returns but before `BranchValidator` is created, extract CREATE_ENTITY target keys and add them to the manifest:

```python
# Add entity keys from injected CREATE_ENTITY deltas to manifest
for variant in branch.variants.values():
    for delta in variant.state_deltas:
        if delta.delta_type == DeltaType.CREATE_ENTITY:
            generation_manifest.additional_valid_keys.add(delta.target_key)
```

Applied in two locations:
- Main path (after line 895)
- Retry path (after line 970, inside `except RegenerationNeeded`)

**Tests added:** `TestCreateEntityKeyInjection` in `test_pipeline.py` (4 tests)
