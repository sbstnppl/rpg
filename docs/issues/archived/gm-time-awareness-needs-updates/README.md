# GM Time Awareness & Needs Updates Issue

**Status:** Partially Done (validator disabled)
**Priority:** Medium
**Detected:** 2024-12-22
**Related Sessions:** 79, 80

## Problem Statement

Two related issues identified during gameplay testing:

1. **GM Lacks Time Awareness**: At 8 AM, the GM wrote "rinse off the dirt and sweat of the day's work" - implying evening after a full workday when it was actually early morning.

2. **Needs Not Updated After Actions**: Player washed themselves, but `/status` showed hygiene still at 41 (passable). The GM narrated the washing but didn't call the `satisfy_need` tool.

## Current Behavior

Before fix:
- GM response at 08:00: "The water feels refreshing as you rinse off the dirt and sweat of the day's work."
- After washing action, hygiene remained at 41

## Expected Behavior

- GM should use time-appropriate descriptions (at 8 AM, there's no "day's work" to wash off yet)
- After washing, hygiene should increase by ~30 points (partial_bath)

## Root Cause

1. **Time Awareness**: The GM template had no guidance about matching narrative descriptions to the current time of day.

2. **Needs Updates**: The `satisfy_need` tool existed but the GM wasn't reliably calling it. The prescriptive action tables in the template were also confusing - semantic understanding works better.

## Solution Implemented

### Part 1: Time Awareness (GM Template)
Added "## Time of Day Awareness" section with time-period table and explicit anti-patterns to avoid.

### Part 2: Semantic Needs Understanding (GM Template)
Replaced prescriptive action lists with semantic descriptions of what each of the 10 needs represents, what satisfies them, and what depletes them.

### Part 3: Cravings (GM Template)
Updated to reference the existing `apply_stimulus` tool for triggering cravings when stimuli are encountered.

### Part 4: Needs Validator Node (Post-Processing Fallback)
Created `needs_validator_node.py` that runs after `game_master_node` and:
- Scans GM response for action keywords (wash, eat, drink, etc.)
- Checks if `satisfy_need` was called (via `last_*_turn` fields)
- Auto-applies reasonable defaults if GM forgot

## Files Modified

| File | Changes |
|------|---------|
| `data/templates/game_master.md` | Added time awareness + semantic needs sections |
| `src/agents/nodes/needs_validator_node.py` | Created - fallback validation node |
| `src/agents/graph.py` | Added needs_validator to legacy graph flow |
| `src/gm/graph.py` | Added needs_validator to GM pipeline (active pipeline) |
| `tests/test_agents/test_needs_validator.py` | Created - 8 tests for validator |

## Test Cases

- [x] Keyword patterns match wash/bathe/eat/drink variants
- [x] Validator applies hygiene when GM forgets
- [x] Validator skips when GM already called tool
- [x] Validator handles multiple needs in one response
- [x] Validator returns empty for no keywords
- [x] Validator handles missing DB gracefully

## Post-Implementation Update

**Validator Disabled** (2024-12-22): The keyword-based needs validator was disabled because it produced too many false positives:
- "clean clothes" triggered hygiene (not washing)
- Idioms and past-tense references would trigger incorrectly

See `docs/IDEAS.md` for future approaches (LLM verification, tool call tracking).

Currently relying on GM prompt improvements only. The Time Awareness section and Semantic Needs descriptions remain active.

## Related Issues

- Uses existing `apply_stimulus` tool for cravings (no new tool needed)

## References

- `src/managers/needs.py` - NeedsManager and satisfaction catalogs
- `src/database/models/character_state.py` - CharacterNeeds model with `last_*_turn` tracking
