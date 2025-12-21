# Context-Aware Location Resolution

**Status:** Planned
**Priority:** Medium
**Affected Components:** `LocationManager.fuzzy_match_location()`, `ActionValidator._validate_move()`

## Problem Statement

When a player types a location name like "well", the system needs to resolve it to an actual location key. Currently, the fuzzy matching returns the **first database match** without considering context, which can lead to unexpected behavior.

### Example Scenario

The game world has multiple wells:
- `family_farm_well` - The Well at the family farm
- `city_well` - The City Well in the town square
- `village_well` - The Village Well in Millbrook

**Current Behavior:**
```
Player is at: city_market
Player types: "go to the well"

Result: Resolves to "family_farm_well" (first match in DB)
Expected: Should resolve to "city_well" (nearby/accessible)
```

This creates confusion because:
1. The player expects to go to the obvious nearby well
2. Instead, they're teleported across the map to a random well
3. The game feels broken or illogical

## Current Implementation

Location: `src/managers/location_manager.py` - `fuzzy_match_location()`

```python
def fuzzy_match_location(self, location_text: str) -> Location | None:
    # 1. Exact key match
    # 2. Display name match (case-insensitive)
    # 3. Normalized text match (removes "the_" prefix)
    # 4. Partial match - PROBLEM HERE:
    for loc in all_locations:
        if normalized in loc.location_key:
            return loc  # Returns FIRST match, not best match!
```

The partial matching (step 4) iterates through all locations and returns the first one containing the search term. Database order is not deterministic or context-aware.

## Proposed Solution

Implement a scoring system that considers multiple factors to find the **best** match, not just the first match.

### Resolution Priority (Highest to Lowest)

1. **Accessible Locations** (can walk there directly)
   - Check `spatial_layout.exits` from current location
   - Score: +100 points

2. **Same Parent Location** (sibling locations)
   - If player is at `city_market`, prefer `city_well` over `farm_well`
   - Both share parent `city`
   - Score: +50 points

3. **Child of Current Location**
   - If player is at `city`, prefer `city_well` (child) over `farm_well`
   - Score: +40 points

4. **Recently Mentioned** (discourse context)
   - Location mentioned in last 5 turns of conversation
   - Score: +30 points

5. **Same Region/Area**
   - Locations sharing a common ancestor within 2 levels
   - Score: +20 points

6. **Exact Name Match**
   - Display name matches exactly (case-insensitive)
   - Score: +10 points

7. **Partial Key Match**
   - Location key contains search term
   - Score: +5 points

### Implementation Approach

```python
def fuzzy_match_location(
    self,
    location_text: str,
    current_location: str | None = None,  # NEW: context
    recent_mentions: list[str] | None = None,  # NEW: discourse
) -> Location | None:
    """Match location text with context awareness.

    Args:
        location_text: The location text from player input.
        current_location: Player's current location key (for proximity).
        recent_mentions: Location keys mentioned in recent turns.

    Returns:
        Best matching Location based on context scoring.
    """
    candidates = self._find_all_matching_locations(location_text)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Score each candidate
    scored = []
    for loc in candidates:
        score = self._calculate_location_score(
            loc, current_location, recent_mentions
        )
        scored.append((score, loc))

    # Return highest scoring match
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
```

### Ambiguity Handling

When multiple locations have similar scores (within 10 points), the system should:

1. **Ask for clarification** if scores are too close:
   ```
   Player: "go to the well"
   GM: "Which well do you mean? The City Well is nearby,
        or do you mean The Well at the family farm?"
   ```

2. **Provide disambiguation hints** in the response:
   ```
   Player: "go to the well"
   GM: "You head to the City Well in the town square."
   (Clarifies WHICH well was chosen)
   ```

## Files to Modify

1. **`src/managers/location_manager.py`**
   - Add `current_location` parameter to `fuzzy_match_location()`
   - Implement `_calculate_location_score()` helper
   - Implement `_find_all_matching_locations()` helper

2. **`src/validators/action_validator.py`**
   - Pass current player location to fuzzy matcher
   - Handle ambiguity (multiple high-scoring matches)

3. **`src/agents/nodes/resolve_references_node.py`**
   - Consider adding location resolution alongside entity resolution
   - Could use DiscourseManager for recent mentions

4. **`src/resolver/reference_resolver.py`** (if exists)
   - Unified resolution for both entities and locations

## Testing Scenarios

### Test Case 1: Prefer Accessible Location
```
Setup: Player at city_market, exits include city_well
Input: "go to well"
Expected: Resolves to city_well (accessible)
```

### Test Case 2: Prefer Sibling Location
```
Setup: Player at city_tavern, no direct exit to well
       city_tavern and city_well share parent "city"
Input: "go to well"
Expected: Resolves to city_well (same parent)
```

### Test Case 3: Recently Mentioned
```
Setup: GM just said "You notice the old village well across the square"
Input: "go to the well"
Expected: Resolves to village_well (recently mentioned)
```

### Test Case 4: Ambiguity Clarification
```
Setup: Player at crossroads between city and farm
       Both city_well and farm_well are equidistant
Input: "go to well"
Expected: Asks "Which well?" with options
```

## Related Issues

- Entity resolution has similar ambiguity (multiple NPCs named "John")
- Item resolution ("take the sword" when multiple swords exist)
- Pronoun resolution already uses DiscourseManager for context

## References

- `src/managers/discourse_manager.py` - Tracks recent entity mentions
- `src/resolver/reference_resolver.py` - Entity resolution patterns
- `docs/scene-first-architecture/` - Architecture context
