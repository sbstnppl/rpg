# GM Unkeyed Entities in Responses

**Status:** Partially Fixed
**Priority:** Medium
**Detected:** 2025-12-27
**Partial Fix:** 2025-12-27 - Player equipment no longer triggers false positives
**Related Sessions:** E2E immersive test runs

## Problem Statement

The GM pipeline is outputting entity names without the required `[entity_key]` format. Instead of referencing entities like `[farmer_marcus]` or `[simple_tunic_001]`, the GM outputs plain text like "Marcus" or "Simple Tunic". This breaks entity grounding validation and prevents proper entity tracking in the game.

## Current Behavior

E2E test grounding validation errors:
```
grounding retry (1/3)
  ! Unkeyed: Simple Tunic
Grounding validation failed (attempt 1): 1 errors

grounding retry (1/3)
  ! Unkeyed: Marcus
Grounding validation failed (attempt 1): 1 errors

grounding retry (1/3)
  ! Unkeyed: Simple Tunic
  ! Unkeyed: Leather Boots
Grounding validation failed (attempt 1): 2 errors

grounding retry (3/3)
  ! Unkeyed: Belt Pouch
Grounding validation failed (attempt 3): 1 errors
Grounding validation failed after 2 retries, proceeding with response
```

The grounding validator catches these but:
1. Retries don't fix the issue (LLM keeps making same mistake)
2. After 3 retries, it proceeds anyway with unkeyed entities
3. This happens across multiple scenarios

## Expected Behavior

GM responses should use keyed format:
- `[farmer_marcus]` instead of "Marcus"
- `[simple_tunic_001]` instead of "Simple Tunic"
- `[leather_boots_001]` instead of "Leather Boots"

The grounding validator should rarely need to retry if the LLM is properly prompted.

## Investigation Notes

### Affected Scenarios (from E2E test)
- Dialog: Simple Greeting - "Simple Tunic" unkeyed
- Hunger: Eat Available Bread - "Marcus" repeatedly unkeyed
- Thirst: Drink Available Water - "Marcus" unkeyed
- Item: Pick Up From Ground - "Simple Tunic", "Leather Boots", "Wool Socks" unkeyed
- OOC: Check Game Time - "Simple Tunic", "Leather Belt", "Belt Pouch" unkeyed

### Pattern Observed
- Player equipment (tunic, boots, belt) frequently unkeyed
- NPC name "Marcus" frequently unkeyed
- Scene objects (bread, water) less frequently unkeyed

## Root Cause

**Two separate issues identified:**

1. **Player equipment false positives (FIXED)**
   - Grounding validator flagged player's worn items (tunic, boots, belt) as unkeyed mentions
   - Narrative like "You're wearing a simple tunic" doesn't need [key:text] format
   - This was a validator bug, not an LLM issue

2. **NPC names genuinely unkeyed (ONGOING)**
   - Local LLM (qwen3:32b) doesn't consistently use [key:text] format for NPCs
   - Says "Marcus" instead of "[farmer_marcus:Marcus]"
   - Grounding retry sends error feedback, but LLM often makes same mistake
   - This is a prompt/model instruction-following issue

## Proposed Solution

**Part 1 (IMPLEMENTED):** Skip player items in grounding validation
- Player inventory and equipped items are exempt from unkeyed mention checks
- Added `skip_player_items=True` parameter to `GroundingValidator`
- Narrative can naturally mention what player is wearing without [key:text]

**Part 2 (TODO):** Improve NPC key format compliance
- Strengthen prompt emphasis on [key:text] format for local LLMs
- Consider model-specific prompt tuning for qwen3
- May need different approach for local vs cloud models

## Implementation Details

**Part 1 Changes (grounding_validator.py):**
```python
class GroundingValidator:
    def __init__(
        self,
        manifest: GroundingManifest,
        skip_player_items: bool = True,  # NEW: skip player items by default
    ) -> None:
        self.skip_player_items = skip_player_items
        self._player_item_keys: set[str] = set()
        # ...

    def _build_name_index(self) -> None:
        # Build set of player item keys (inventory + equipped)
        if self.skip_player_items:
            self._player_item_keys = set(self.manifest.inventory.keys())
            self._player_item_keys.update(self.manifest.equipped.keys())
        # ...

    def _detect_unkeyed_mentions(self, text, keyed_refs) -> list[UnkeyedMention]:
        for key, entity in self.manifest.all_entities().items():
            # Skip player items - these can be mentioned naturally
            if self.skip_player_items and key in self._player_item_keys:
                continue
            # ... rest of detection logic
```

## Files Modified

- [x] `src/gm/grounding_validator.py` - Added `skip_player_items` parameter

## Files to Investigate (for Part 2)

- [ ] `src/gm/prompts.py` - System prompt [key:text] instructions
- [ ] `src/gm/context_builder.py` - Entity reference formatting
- [ ] Consider model-specific prompt variants

## Test Cases

- [ ] Narrator uses `[entity_key]` for all NPC references
- [ ] Narrator uses `[entity_key]` for all item references
- [ ] Narrator uses `[entity_key]` for player equipment mentions
- [ ] Grounding validator passes on first attempt (no retries needed)
- [ ] E2E scenarios pass without grounding errors

## Related Issues

- GM duplicate responses (related - may share root cause)
- Scene entity coverage in narrator context

## References

- Test output: `logs/gm_e2e/live.log`
- Test runner: `scripts/gm_e2e_immersive_runner.py`
- Grounding validator: `src/gm/grounding_validator.py`
