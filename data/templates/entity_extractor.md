# Entity Extraction System Prompt

Analyze the following game interaction and extract entities, facts, and state changes.

## Game Master Response
{gm_response}

## Player Input
{player_input}

## Current Context
- Location: {player_location}

## Instructions

Extract the following from the GM response (only if present):

### 1. New Characters
Characters mentioned for the first time. For each:
- entity_key: lowercase with underscores (e.g., "bartender_bob")
- display_name: How they should be addressed
- entity_type: "npc", "monster", or "animal"
- description: Physical appearance if mentioned
- personality_traits: Observable traits
- current_activity: What they're doing
- current_location: Where they are

### 2. Items
Items that appeared or were interacted with. For each:
- item_key: lowercase with underscores
- display_name: Item name
- item_type: "weapon", "armor", "clothing", "consumable", "container", "misc"
- description: If mentioned
- owner_key: Entity key of owner
- action: "acquired", "dropped", "transferred", "equipped", "mentioned"

### 3. Facts
New information revealed about characters or world. For each:
- subject: Entity key or topic
- predicate: What aspect (e.g., "occupation", "lives_at", "knows_about")
- value: The information
- is_secret: true if GM-only information

### 4. Relationship Changes
Track attitude shifts between characters. **Always extract when NPCs interact with the player.**

**IMPORTANT**: When an NPC has a conversation with the player for the first time, create a "familiarity" change of +10 to +20 to establish the relationship exists.

Common patterns to extract:
- First meeting/conversation → familiarity +10 to +20
- NPC acts friendly/helpful → liking +5 to +15
- NPC shows generosity/kindness → liking +5 to +10, trust +5
- Player helps NPC → trust +5 to +15, respect +5 to +10
- Player is polite/respectful → respect +5 to +10
- NPC is impressed → respect +10 to +15
- Negative interactions → negative deltas

For each relationship change:
- from_entity: Entity key whose attitude changed (usually the NPC)
- to_entity: Entity key toward whom (usually "player" for player interactions, or use player's entity_key like "durgan_stonehammer")
- dimension: "trust", "liking", "respect", "romantic_interest", "fear", "familiarity"
- delta: -20 to +20 (positive for improvement, negative for worsening)
- reason: Brief explanation of why

### 5. Appointments
Commitments made for future. For each:
- description: What for
- day: Game day number
- time: Time of day
- location_key: Where
- participants: Entity keys

### 6. State Changes
- time_advance_minutes: Minutes that passed (infer from narrative)
- location_change: New location key if player moved (or null)

## Output

Return ONLY valid JSON matching the ExtractionResult schema. Do not include any explanation or markdown formatting around the JSON.
