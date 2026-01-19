# GM Player Agency Over-Interpretation

**Status:** Done
**Priority:** High
**Detected:** 2025-12-25
**Related Sessions:** Gameplay testing session

## Problem Statement

The GM over-interprets player intent, taking actions the player didn't explicitly request. When player said "find some fresh, clean clothes", the GM automatically added clothes to inventory. The player only asked to FIND (search/look), not TAKE.

## Current Behavior

**Player input:** "I go back in and see if I find some fresh, clean clothes."

**GM response:**
- Found clothes in chest
- Added `clean_shirt_001` and `clean_breeches_001` to inventory
- Announced "Updated Inventory"

**Problem:** Player didn't say "pick up" or "take" - they just wanted to LOOK.

## Expected Behavior

**For "find clothes":**
> You step back into the cottage and find a wooden chest near the bed. Inside, you see a neatly folded linen shirt and a pair of clean breeches.

(Player then decides whether to take them)

**For "find clothes and put them on":**
> You find clean clothes in the chest. You change into the fresh linen shirt and breeches, dropping your dirty clothes on the floor.

(Full action chain executed as requested)

## Investigation Notes

- GM prompt line 19: "NEVER narrate actions the player didn't explicitly take"
- Parse intent may bridge vague input to concrete actions
- No clear boundary between SEARCH (describe) vs TAKE (acquire)
- Template line 233-238 specifies when to use acquire_item but doesn't restrict inference

## Root Cause

The system lacks a clear policy on:
1. What verbs imply taking vs. just looking
2. When to chain inferred actions vs. wait for explicit player choice
3. Boundary between helpful automation and agency violation

## Proposed Solution

**Principle:** Do exactly what the player says - no more, no less. Trust the LLM to understand natural language intent.

### Key Insight

The LLM already understands that "find clothes" is observation and "grab the sword" is acquisition. We don't need word lists - we just need to tell it to respect that distinction instead of being proactively helpful.

### The Fix

Add a "Player Agency" section to both GM prompts:

**Observation vs Acquisition:**
- Player describes OBSERVING (finding, looking, searching) → Describe what's there. Do NOT acquire.
- Player describes ACQUIRING (taking, grabbing) → Add to inventory.
- Ambiguous → Describe and let player decide.

**Chained actions are fine** - "find clothes and put them on" executes the full chain.
**Implicit acquisition is not** - "find clothes" alone only describes, doesn't acquire.

Ask yourself: Did the player explicitly say they want to take/acquire this item?

## Implementation Details

### Files Modified
- `src/gm/prompts.py` - Added PLAYER AGENCY section after INTENT ANALYSIS
- `data/templates/game_master.md` - Added Player Agency section after Important Rules

### Parse Intent
Verified - no changes needed. The parser already correctly distinguishes action types.

## Files Modified

- [x] `src/gm/prompts.py` - Added PLAYER AGENCY section
- [x] `data/templates/game_master.md` - Added Player Agency section
- [x] `src/agents/nodes/parse_intent_node.py` - Verified no auto-chaining (no changes needed)

## Test Cases

- [ ] "find clothes" → describes clothes, doesn't add to inventory
- [ ] "find and take clothes" → adds to inventory
- [ ] "look for a weapon" → describes available weapons
- [ ] "grab a weapon" → adds to inventory
- [ ] "go home and shower" → narrates journey/shower, events may happen

## Related Issues

- GM structured output format
- Item naming technical debt

## References

- `data/templates/game_master.md:19` - "NEVER narrate actions the player didn't explicitly take"
- `data/templates/game_master.md:233-238` - Item acquisition rules
- `src/agents/nodes/parse_intent_node.py` - Intent parsing
