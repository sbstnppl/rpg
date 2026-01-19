# OOC Handling - Exits Query

**Status**: Awaiting Verification
**Priority**: LOW
**Discovered**: Session 347 Play Test (2026-01-18)
**Fixed**: 2026-01-19
**Verification**: 0/3
**Last Verified**: -

## Problem

When the player asks an out-of-character (OOC) question about available exits, the system returns an unhelpful generic response instead of providing the requested game state information.

### Observed Behavior

```
Player: ooc: what exits are available?
System: That's an out-of-character request. What would you like to know?
```

### Expected Behavior

```
Player: ooc: what exits are available?
System: [OOC] From the tavern, you can go to:
- North: Village Square
- East: Back Alley
- Stairs: Tavern Upper Floor
```

## Root Cause

The OOC handler detected the `ooc:` prefix but lacked logic to:
1. Parse the specific question type
2. Query game state for the answer
3. Format a helpful response

The original implementation was a placeholder that acknowledged OOC mode but didn't actually answer questions.

## Solution

**Fixed in commit `471dbf5`** (2026-01-19): Implemented `OOCHandler` class with keyword-based query routing.

### Changes Made

1. **Created `OOCHandler` class** (`src/world_server/quantum/ooc_handler.py`):
   - `OOCQueryType` enum for classifying queries (EXITS, TIME, INVENTORY, etc.)
   - `classify_query()` function with keyword matching
   - Handler methods for each query type

2. **Integrated into quantum pipeline** (`src/world_server/quantum/pipeline.py`):
   ```python
   # Before:
   return "That's an out-of-character request. What would you like to know?"

   # After:
   ooc_handler = OOCHandler()
   context = OOCContext(db=self.db, game_session=self.game_session, location_key=location_key)
   return ooc_handler.handle_query(intent_result.raw_input, context)
   ```

3. **Exits handler fully implemented**:
   - Queries location exits from spatial layout
   - Filters inaccessible exits
   - Formats response with directions and destinations

### Handler Implementation Status

| Handler | Status | Notes |
|---------|--------|-------|
| `_handle_exits()` | Complete | Queries location manager, formats exits list |
| `_handle_time()` | Stub | TODO: Query TimeState from database |
| `_handle_inventory()` | Stub | TODO: Implement when needed |
| `_handle_npcs()` | Stub | TODO: Implement when needed |
| `_handle_stats()` | Stub | TODO: Implement when needed |
| `_handle_location()` | Stub | Returns placeholder |
| `_handle_help()` | Complete | Lists available OOC commands |
| `_handle_unknown()` | Complete | LLM fallback for unrecognized queries |

### Test Coverage

24 tests added in `tests/test_world_server/test_quantum/test_ooc_handler.py`:
- Query classification (14 tests)
- Exits handler (4 tests)
- Handle query routing (2 tests)
- LLM fallback (3 tests)
- Context creation (1 test)

## Common OOC Questions

Players frequently ask these meta-questions:

| Question Type | Expected Answer |
|---------------|-----------------|
| "What exits are available?" | List of exits from current location |
| "What time is it?" | Current in-game time |
| "Who is here?" | List of NPCs/entities in location |
| "What do I have?" | Player inventory summary |
| "What are my stats?" | Player attributes and health |
| "What can I do?" | Available actions in context |
| "Where am I?" | Current location description |

## Files to Investigate

- OOC handler in quantum pipeline (location TBD)
- Intent classifier OOC detection
- Location manager for exits query

## Potential Solutions

### Option 1: Keyword-Based OOC Routing

Parse OOC questions for keywords and route to appropriate handlers:
```python
OOC_HANDLERS = {
    "exit": handle_exits_query,
    "time": handle_time_query,
    "inventory": handle_inventory_query,
    "who": handle_entities_query,
}
```

**Pros**: Fast, deterministic
**Cons**: May miss phrasing variations

### Option 2: LLM Classification of OOC Intent

Use LLM to classify what the OOC question is asking:
```python
ooc_intent = classify_ooc_intent(question)
# Returns: "QUERY_EXITS", "QUERY_TIME", "QUERY_INVENTORY", etc.
```

**Pros**: Handles natural language variations
**Cons**: Additional LLM call

### Option 3: Hybrid Approach

1. Check for exact keyword matches first (fast path)
2. Fall back to LLM classification for ambiguous queries
3. Final fallback: "I don't understand. Try: exits, time, inventory, stats"

## Recommended Approach

**Option 1 (Keyword-Based)** is sufficient for MVP. OOC queries are typically short and formulaic. LLM classification can be added later if needed.

## Related Issues

- `ooc-time-hallucination` - Related OOC handling issue
- `poor-narrative-ooc-response` - General OOC response quality

## Reproduction Steps

1. Start a game session
2. Input: "ooc: what exits are available?"
3. Observe unhelpful generic response

## Test Coverage

- [x] Test: OOC exits query returns location exits
- [ ] Test: OOC time query returns game time (handler is stub)
- [ ] Test: OOC inventory query returns player items (handler is stub)
- [x] Test: Unknown OOC query returns helpful error message (LLM fallback)
