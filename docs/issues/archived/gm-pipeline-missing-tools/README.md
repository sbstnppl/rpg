# New GM Pipeline Missing Tools - Audit and Implementation

**Status:** Done
**Priority:** High
**Detected:** 2025-12-25
**Completed:** 2025-12-25
**Related Sessions:** 79, 80 (for context)

## Problem Statement

The new GM pipeline (`src/gm/`) has only 5 tools compared to 27 in the legacy pipeline (`src/agents/tools/gm_tools.py`). Critical functionality is missing: relationship tracking, needs satisfaction, quest management, and navigation. This makes the new pipeline unable to properly handle social interactions, character needs, and quest-based gameplay.

## Current Behavior

The new GM pipeline (`--pipeline=gm`) has these tools:
- `skill_check` - 2d10 dice rolls
- `attack_roll` - Combat attack rolls
- `damage_entity` - Apply damage
- `create_entity` - Create NPC/item/location
- `record_fact` - SPV pattern facts

When players perform actions like "eat food" or "talk to the bartender", the GM narrates it but:
- Hunger/thirst doesn't decrease (no `satisfy_need`)
- NPC relationships don't change (no `update_npc_attitude`)
- Quests can't be assigned (no quest tools)

## Expected Behavior

The GM should be able to mechanically track all significant state changes during gameplay:
- Eating/drinking satisfies hunger/thirst
- Conversations affect NPC relationships
- Quests can be assigned and completed
- NPCs can be properly managed in scenes

## Legacy Tools (27 total)

### Dice/Checks (3)
- `skill_check` - Present in new pipeline
- `attack_roll` - Present in new pipeline
- `roll_damage` - Merged into attack_roll

### Relationships (2) - **MISSING**
- `get_npc_attitude` - Query relationship dimensions
- `update_npc_attitude` - Modify trust/liking/respect/etc.

### Needs (3) - **MISSING**
- `satisfy_need` - Satisfy hunger/thirst/stamina/etc.
- `apply_stimulus` - Create cravings (food sight, rest opportunity)
- `mark_need_communicated` - Prevent repetitive narration

### Navigation (7) - **MISSING** (partial replacement via StateChange.MOVE)
- `check_route` - Travel route planning
- `start_travel` - Begin journey
- `move_to_zone` - Move to adjacent zone
- `check_terrain` - Terrain accessibility
- `discover_zone` - Mark zone discovered
- `discover_location` - Mark location discovered
- `view_map` - Examine map item

### Items (2) - **MISSING** (partial replacement via StateChange.TAKE/DROP)
- `acquire_item` - Pick up item with slot/weight validation
- `drop_item` - Drop or give item

### World Spawning (2) - **MISSING**
- `spawn_storage` - Create furniture/containers
- `spawn_item` - Create discoverable items

### State Management (4) - Handled differently
- `advance_time` - Now via `time_passed_minutes`
- `entity_move` - Now via StateChange.MOVE
- `start_combat` - Not in new pipeline
- `end_combat` - Not in new pipeline

### Quest Management (3) - **MISSING**
- `assign_quest` - Create new quest
- `update_quest` - Progress quest
- `complete_quest` - Finish quest

### World Facts (1) - Present
- `record_fact` - Present in new pipeline

### NPC Scene Management (2) - Partial replacement
- `introduce_npc` - Replaced by `create_entity` for NPCs
- `npc_leaves` - **MISSING**

## Investigation Notes

### New Pipeline Architecture
The new pipeline is intentionally simplified:
1. `gm_node` - Single LLM call with tool loop
2. `validator_node` - Validates response (logs only)
3. `applier_node` - Applies StateChanges

StateChanges handle some functionality:
- `StateChangeType.MOVE` - Player movement
- `StateChangeType.TAKE` - Pick up items
- `StateChangeType.DROP` - Drop items
- `StateChangeType.GIVE` - Transfer items
- `StateChangeType.EQUIP/UNEQUIP` - Equipment
- `StateChangeType.CONSUME` - Use consumables
- `StateChangeType.RELATIONSHIP` - Update relationships
- `StateChangeType.FACT` - Record facts
- `StateChangeType.TIME_SKIP` - Skip time
- `StateChangeType.DAMAGE` - Combat damage

### Key Question
Should tools be added to the GM, or should the LLM output StateChanges that the applier handles?

The legacy approach: GM calls tools directly during generation
The new approach: GM returns structured response, applier applies changes

Currently the new pipeline has tools for dice rolls (immediate feedback needed) and entity creation (LLM needs key back), but uses StateChanges for state mutations.

## Root Cause

Intentional simplification - the new pipeline was designed to be minimal, but critical tools were not migrated.

## Solution Implemented

Implemented a **consistent architecture**:
- **StateChanges** for all state mutations (needs, movement, relationships)
- **Tools** only when GM needs immediate feedback (queries, dice, entity creation)

### StateChange Enhancements
1. Renamed `CONSUME` to `SATISFY_NEED` for clarity
2. Extended `SATISFY_NEED` to handle activities (sleeping, bathing) not just item consumption
3. Extended `MOVE` to handle NPC movement (not just player)

### New Tools Added (10 total)
1. `get_npc_attitude` - Query NPC relationship before generating dialogue
2. `assign_quest` - Create and assign a new quest
3. `update_quest` - Advance quest to next stage
4. `complete_quest` - Mark quest as completed/failed
5. `create_task` - Add a goal/reminder for the player
6. `complete_task` - Mark task as done
7. `create_appointment` - Schedule a meeting with NPC
8. `complete_appointment` - Mark appointment as kept/missed/cancelled
9. `apply_stimulus` - Create cravings when describing tempting scenes
10. `mark_need_communicated` - Prevent repetitive need narration (stub)

### Existing Tools Extended
- `create_entity` - Added `entity_type: "storage"` for creating containers/furniture

### Final Tool Count
- Before: 5 tools
- After: 15 tools (plus StateChanges handling needs/relationships/movement)

## Proposed Solution (Original)

### Tier 1: Critical (Must Have)
These tools require immediate LLM feedback or are essential for gameplay:

1. **satisfy_need** - Needs system doesn't work without it
2. **update_npc_attitude** - Social interactions meaningless without it
3. **get_npc_attitude** - GM needs to know relationship to roleplay NPC

### Tier 2: Important (Should Have)
Essential for full gameplay but workaroundable:

4. **assign_quest** / **update_quest** / **complete_quest** - Quest system
5. **spawn_storage** / **spawn_item** - World building (or extend `create_entity`)
6. **npc_leaves** - Scene management

### Tier 3: Nice to Have
Could be handled via StateChanges or are edge cases:

7. Navigation tools - May not need if zones not used
8. `apply_stimulus` - Craving system is secondary
9. `mark_need_communicated` - Can add later

### Alternative: Extend StateChanges
Instead of adding all tools, could extend the StateChange system:
- `StateChangeType.NEED_CHANGE` - For satisfy_need
- `StateChangeType.QUEST_START/PROGRESS/COMPLETE`
- etc.

This keeps tool count low but requires GM to output structured state changes.

## Implementation Details

### Option A: Add Tools (Simpler)
Copy tool definitions from `src/agents/tools/gm_tools.py` to `src/gm/tools.py`, implementing execution in `GMTools.execute_tool()`.

### Option B: Extend StateChanges (Cleaner Architecture)
Add new StateChangeTypes and handle in `applier.py`.

### Recommendation
Start with Option A for Tier 1 tools (satisfy_need, update_npc_attitude, get_npc_attitude) since they need immediate feedback. Evaluate Option B for Tier 2+.

## Files to Modify

- [ ] `src/gm/tools.py` - Add tool definitions and execution
- [ ] `src/gm/gm_node.py` - Update tool list
- [ ] `src/gm/schemas.py` - Add any new schemas
- [ ] `src/gm/prompts.py` - Update system prompt if needed
- [ ] `tests/test_gm/` - Add tests for new tools

## Test Cases

- [ ] Eating food satisfies hunger via satisfy_need
- [ ] Talking to NPC updates relationship via update_npc_attitude
- [ ] GM can query NPC attitude before deciding response
- [ ] Quest can be assigned and completed
- [ ] Items can be spawned in scene

## Related Issues

- See `docs/gm-pipeline-e2e-testing.md` for testing guide
- Legacy tools: `src/agents/tools/gm_tools.py`
- Legacy executor: `src/agents/tools/executor.py`

## References

- `src/gm/tools.py` - Current tool definitions (5 tools)
- `src/agents/tools/gm_tools.py` - Legacy tool definitions (27 tools)
- `src/gm/applier.py` - StateChange handling
- `src/gm/schemas.py` - GMResponse and StateChange schemas
- `src/managers/needs.py` - NeedsManager for satisfy_need
- `src/managers/relationship_manager.py` - For update_npc_attitude
