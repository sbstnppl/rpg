# TODO: OOC Handling - Exits Query

## Investigation ✓

- [x] Locate OOC handler code in quantum pipeline
- [x] Understand current OOC detection and routing
- [x] Identify where to add query handlers

**Completed**: Commit `471dbf5` (2026-01-19)

## Implementation Tasks

### Phase 1: Exits Query ✓

- [x] Implement `handle_exits_query()` function
- [x] Query location manager for current location exits
- [x] Format response with exit directions and destinations
- [x] Wire into OOC handler

**Completed**: Full exits handler with inaccessibility filtering

### Phase 2: Additional Queries (Stubs Only)

- [ ] Implement `handle_time_query()` - current game time
  - Stub exists, TODO: Query TimeState from database
- [ ] Implement `handle_inventory_query()` - player items
  - Stub exists, returns placeholder
- [ ] Implement `handle_entities_query()` - NPCs in location
  - Stub exists, returns placeholder
- [ ] Implement `handle_stats_query()` - player attributes
  - Stub exists, returns placeholder

### Phase 3: Help System ✓

- [x] Add OOC help command listing available queries
- [x] Improve error message for unknown OOC queries (LLM fallback)
- [x] Consider "ooc: help" as explicit help trigger

## Notes

Priority: LOW - Quality of life improvement, not blocking gameplay

The core infrastructure (OOCHandler, query classification, routing) is complete.
Remaining work is implementing the stub handlers as needed.
