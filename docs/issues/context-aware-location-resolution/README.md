# Context-Aware Location Resolution

**Status:** Awaiting Verification
**Priority:** Medium
**Affected Components:** `GMContextBuilder`, `GroundingManifest`, `BranchGenerator`
**Verification:** 0/3
**Last Verified:** -
**Fixed:** 2026-01-18

## Problem Statement

When a player types a location name like "well", the system needs to resolve it to an actual location key. The original fuzzy matching returned the **first database match** without considering context, leading to unexpected behavior.

### Example Scenario

The game world has multiple wells:
- `family_farm_well` - The Well at the family farm
- `city_well` - The City Well in the town square
- `village_well` - The Village Well in Millbrook

**Original Behavior:**
```
Player is at: city_market
Player types: "go to the well"

Result: Resolved to "family_farm_well" (first match in DB)
Expected: Should resolve to "city_well" (nearby/accessible)
```

This created confusion because:
1. The player expects to go to the obvious nearby well
2. Instead, they were teleported across the map to a random well
3. The game felt broken or illogical

## Solution Implemented

**Commit:** `58e0bfb` (2026-01-18)

The fix uses an **LLM-based approach** rather than the originally proposed scoring system. This is better because the LLM has full discourse awareness and can understand conversation context naturally.

### Approach: Let the LLM Decide

Instead of pre-resolving ambiguous locations with heuristics, we now:

1. **Find all matching locations** via `_get_candidate_locations()` in `GMContextBuilder`
2. **Include them in the manifest** as `candidate_locations` (distinct from `exits`)
3. **Provide recent conversation context** via `recent_events` in the branch generation prompt
4. **Let the LLM pick** the contextually appropriate location

This handles edge cases naturally through understanding rather than brittle heuristics.

### Files Changed

| File | Change |
|------|--------|
| `src/gm/context_builder.py` | Added `_get_candidate_locations()` method |
| `src/gm/grounding.py` | Added `candidate_locations` field to `GroundingManifest` |
| `src/world_server/quantum/branch_generator.py` | Include `recent_events` in prompt |
| `src/world_server/quantum/delta_postprocessor.py` | Accept `candidate_locations` as valid destinations |
| `src/world_server/quantum/validation.py` | Add fuzzy matching suggestions in error messages |
| `src/world_server/quantum/pipeline.py` | Pass candidate locations through pipeline |

### Tests Added

14 new tests covering:
- `tests/test_gm/test_context_builder.py` - Candidate location gathering
- `tests/test_gm/test_grounding.py` - Manifest with candidate locations

## Verification Scenarios

To verify this fix works correctly, test these scenarios:

### Scenario 1: Multiple Similar Locations
```
Setup: Game world with multiple wells (city_well, village_well, farm_well)
       Player at city_market
Test:  Type "go to the well"
Expected: Goes to city_well (nearby) not a random distant well
```

### Scenario 2: Discourse-Referenced Location
```
Setup: NPC mentions "the old well of life" in conversation
       Player hasn't visited that well before
Test:  Type "go to that well" or "I want to see that well"
Expected: Goes to the mentioned well, not a different one
```

### Scenario 3: Explicit vs Contextual
```
Setup: Multiple wells exist, NPC mentioned village_well
Test:  Type "go to the city well" (explicit)
Expected: Goes to city_well regardless of recent mentions
Test:  Type "go to the well" (contextual)
Expected: Goes to village_well (recently mentioned)
```

## Original Proposed Solution (Not Implemented)

The original plan proposed a scoring system in `fuzzy_match_location()`:
- +100 points for accessible locations
- +50 points for same parent location
- +30 points for recently mentioned
- etc.

This was **not implemented** because:
1. Heuristic scoring can still pick the wrong location in edge cases
2. The LLM already has discourse context and can reason about it
3. The LLM approach handles nuance (tone, intent) that rules cannot

## Related Issues

- Entity resolution has similar ambiguity (multiple NPCs named "John")
- Item resolution ("take the sword" when multiple swords exist)
- Pronoun resolution already uses DiscourseManager for context

## References

- Commit: `58e0bfb` - Implementation commit
- `src/managers/discourse_manager.py` - Tracks recent entity mentions
- `src/gm/context_builder.py` - Builds context including candidate locations
