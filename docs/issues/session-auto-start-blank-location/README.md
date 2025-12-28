# Session Auto-Start Creates Blank Location

**Status:** Investigating
**Priority:** High
**Detected:** 2025-12-28
**Related Sessions:** 299

## Problem Statement

When starting a game session with `--auto` mode, the player is created but placed in a "starting_location" that doesn't actually exist in the database. This results in a completely blank environment with no NPCs, no items, no exits, and no location description. The player is stuck in a void with no way to interact with the world.

## Current Behavior

1. `python -m src.main game start --auto` creates a session with a player character
2. Player is assigned to "starting_location"
3. No actual location record exists in the `locations` table for this session
4. GM receives empty scene context and responds with meta-commentary instead of narrative

**Database evidence:**
```sql
-- Entities table shows only the player
SELECT entity_key, display_name, entity_type FROM entities WHERE session_id = 299;
-- Returns: test_hero | Test Hero | player

-- Locations table is empty
SELECT * FROM locations WHERE session_id = 299;
-- Returns: (0 rows)
```

**GM Response (breaking character):**
> "The current scene is an empty starting location with no description, no NPCs, no items, and no exits. You're in a 'blank slate' environment. Here's what you can do next..."

The GM also outputs numbered lists with tool names like `get_player_state`, `satisfy_need`, `move_to` - completely breaking immersion.

## Expected Behavior

1. `--auto` mode should create a proper starting location (tavern, village square, etc.)
2. The location should have:
   - A descriptive name and atmosphere
   - At least one NPC to interact with
   - Some items in the scene
   - At least one exit to another location
3. GM should narrate an immersive scene introduction, not meta-commentary

## Investigation Notes

From audit log `logs/llm/session_299/turn_001_20251228_102724_gm.md`:

The system prompt correctly instructs the GM on narrative style, but the scene context shows:
```
**Location**: starting_location
No description available.
**NPCs Present**: None
**Items**: None visible
**Exits**: None apparent
```

The GM correctly called `get_scene_details` tool which returned:
```json
{"location": {"key": "starting_location", "name": "starting_location", "description": "No description", "atmosphere": null}, "npcs": [], "items": [], "exits": []}
```

## Root Cause

The `game start --auto` command likely creates the player entity but doesn't trigger location/NPC/item generation. The auto-creation flow needs to also initialize the game world.

## Proposed Solution

The `--auto` flag should:
1. Create a default starting location (e.g., "Village Tavern")
2. Populate it with at least 1-2 NPCs (e.g., tavern keeper)
3. Add some items (tables, chairs, mugs, food)
4. Add at least one exit (to outside/street)

Alternatively, trigger the WorldMechanics or SceneBuilder to generate the initial scene.

## Implementation Details

<To be filled during implementation>

## Files to Modify

- [ ] `src/cli/commands/game.py` - The `start` command implementation
- [ ] `src/managers/` - Possibly LocationManager, NPCManager, ItemManager
- [ ] Possibly a new "world initialization" module

## Test Cases

- [ ] Test case 1: `game start --auto` creates at least one location
- [ ] Test case 2: Starting location has NPCs present
- [ ] Test case 3: Starting location has items visible
- [ ] Test case 4: Starting location has at least one exit
- [ ] Test case 5: First turn produces narrative response, not meta-commentary

## Related Issues

- GM character break patterns (separate issue - GM responding with tool names)

## References

- `logs/llm/session_299/turn_001_20251228_102724_gm.md` - Audit log showing blank scene
- `docs/gm-pipeline-e2e-testing.md` - Expected behaviors
