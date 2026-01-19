# TODO: World Generation for Finn's Journey

## Phase 1: Core Locations
- [x] Create Millbrook village location with sub-locations
  - [x] Market Square
  - [x] The Dusty Flagon (tavern)
  - [x] Chapel of the Light
  - [x] Blacksmith's Forge
  - [x] The Old Mill (abandoned)
- [x] Create Brennan Farm
- [x] Create Watcher's Tower ruins
- [x] Create Greywood Forest with hidden Temple of Dawn Star
- [x] Add River Moss fishing area
- [x] Create road connections (East Road, South Road)

## Phase 2: NPCs and Schedules
- [x] Create Old Aldric (tavern storyteller)
  - [x] Define schedule (tavern evenings, home mornings)
  - [x] Add lore knowledge (ballads about star warriors)
- [x] Create Sister Maren (chapel keeper)
  - [x] Define schedule (chapel daily, market on market days)
  - [x] Add restricted lore knowledge (church records)
- [x] Create The Hermit (forest edge)
  - [x] Define mysterious behavior patterns
  - [x] Add deep lore knowledge (actual Starbound member)
- [x] Create Master Corin (traveling merchant)
  - [x] Define travel schedule (visits monthly)
  - [x] Add artifact collection mechanics
- [x] Create Henrik (blacksmith)
  - [x] Define schedule (forge during day)
  - [x] Practical character, no lore
- [x] Create Widow Brennan
  - [x] Add knowledge about Finn's mother
  - [x] Add protective behavior triggers
- [x] Create Tom (barkeep)
  - [x] Define schedule (tavern hours)
  - [x] Add knowledge about mysterious shield

## Phase 3: Lore and World Facts
- [x] Create SPV facts for Starbound Order history
- [x] Create SPV facts for Hollow Mountains legends
- [x] Create SPV facts for weakening seal omens
- [x] Create discoverable lore items (via knowledge_areas)
  - [x] Old Aldric's ballads
  - [x] Church records (Sister Maren)
  - [x] Hermit's true knowledge

## Phase 4: Artifacts and Items
- [x] Define Mother's Pendant properties
  - [x] Add hidden shrine key functionality
  - [x] Add Starbound resonance property
- [x] Create discoverable Starbound artifacts
  - [x] Dawn Star medallion (Temple of Dawn Star)
  - [x] Watcher's spyglass (Watcher's Tower)
  - [x] Binding seal fragment (shrine below well)
- [x] Create well key (held by Hermit)
- [x] Create tavern shield (ward artifact)

## Phase 5: Environmental Systems
- [ ] Set up weather tracking (late autumn currently)
- [x] Add omen event triggers (via facts)
  - [x] Livestock marks (random farm events)
  - [x] Nightmare reports (NPC dialogue)
  - [x] Unusual cold (weather modifier)
- [x] Create discoverable location triggers (via visibility settings)
  - [x] Temple entrance in Greywood (hidden)
  - [x] Shrine beneath well (hidden, requires pendant)
  - [x] Tower secret chamber

## Phase 6: Relationship and Trust
- [x] Configure NPC trust thresholds for lore revelation
  - [x] Aldric: Low threshold (loves an audience) - 20/50/80
  - [x] Sister Maren: High threshold (church secrets) - 20/60/80/95
  - [x] Hermit: Quest-based (must prove worthy) - 30/50/70/90/95
  - [x] Widow Brennan: Time-based (protective instincts) - 20/60/90
- [x] Add dialogue variations based on trust level (via knowledge_areas)

## Verification
- [ ] Play through first hour as Finn
- [ ] Verify all locations are accessible
- [ ] Verify NPC schedules work correctly
- [ ] Test lore discovery through normal play
- [ ] Confirm hidden elements aren't revealed too easily

## Completion
- [x] Create world data files
  - [x] `data/worlds/millbrook.yaml` - Zones, locations, connections
  - [x] `data/worlds/millbrook_npcs.json` - NPC definitions
  - [x] `data/worlds/millbrook_schedules.json` - NPC schedules
  - [x] `data/worlds/millbrook_items.json` - Item definitions
  - [x] `data/worlds/millbrook_facts.json` - World facts
- [x] Create extended world loader service
  - [x] `src/services/world_loader_extended.py`
  - [x] `src/schemas/world_template.py` extensions
- [x] Add CLI command (`rpg world load millbrook`)
- [x] Write tests (14 unit + 26 integration)
- [x] Update README.md status to "Awaiting Verification"
- [x] Create commit with `/commit`

## Implementation Summary

**Files Created:**
- `data/worlds/millbrook.yaml` - 9 zones, 18+ locations
- `data/worlds/millbrook_npcs.json` - 7 NPCs with full specs
- `data/worlds/millbrook_schedules.json` - Daily schedules for all NPCs
- `data/worlds/millbrook_items.json` - 6 items including 4 artifacts
- `data/worlds/millbrook_facts.json` - 20+ world facts
- `src/services/world_loader_extended.py` - Extended loader
- `tests/test_services/test_world_loader_extended.py` - Unit tests
- `tests/test_integration/test_millbrook_world.py` - Integration tests

**CLI Usage:**
```bash
rpg world load millbrook --session <session_id>
```
