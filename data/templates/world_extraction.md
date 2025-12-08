# World Extraction System Prompt

Analyze the character creation output and extract the complete world context for the game.

## Character Creation Output
{character_output}

## Character Summary
- Name: {character_name}
- Background: {character_background}

## Setting
{setting_name}

---

## Instructions

Extract ALL information from the character creation conversation to populate the game world.
Be thorough - every named person, place, or relationship becomes part of the persistent world.

### 1. Player Appearance (REQUIRED)

Extract complete physical description of the player character:

```json
{{
  "player_appearance": {{
    "age": 25,
    "age_apparent": "mid-twenties",
    "gender": "male",
    "height": "tall",
    "build": "athletic",
    "hair_color": "dark brown",
    "hair_style": "short and messy",
    "eye_color": "green",
    "skin_tone": "fair",
    "species": "human",
    "distinguishing_features": "scar above left eyebrow",
    "voice_description": "deep and calm"
  }}
}}
```

Use null for any field not mentioned. Infer reasonable values if clearly implied.

### 2. Shadow Entities (Named NPCs from Backstory)

Every named person, creature, or organization mentioned becomes a Shadow Entity.
These are entities that exist in the world but haven't appeared on-screen yet.

For each named entity:
- entity_key: lowercase with underscores (e.g., "grandmother_elara")
- display_name: How they should be addressed (e.g., "Grandmother Elara")
- entity_type: "npc", "monster", "animal", or "organization"
- relationship_to_player: "family", "friend", "colleague", "mentor", "enemy", "acquaintance"
- brief_description: What we know from backstory
- is_alive: true unless explicitly mentioned as deceased
- trust: 0-100 (family=90, close friend=80, acquaintance=30)
- liking: 0-100 (similar scaling)
- respect: 0-100 (based on relationship type)

Example:
```json
{{
  "shadow_entities": [
    {{
      "entity_key": "grandmother_elara",
      "display_name": "Grandmother Elara",
      "entity_type": "npc",
      "relationship_to_player": "family",
      "brief_description": "Player's grandmother, they live together",
      "is_alive": true,
      "trust": 95,
      "liking": 90,
      "respect": 85
    }},
    {{
      "entity_key": "boss_janet",
      "display_name": "Janet",
      "entity_type": "npc",
      "relationship_to_player": "colleague",
      "brief_description": "Player's supervisor at the smithy",
      "is_alive": true,
      "trust": 50,
      "liking": 40,
      "respect": 60
    }}
  ]
}}
```

### 3. Locations

Extract all locations mentioned in the backstory:

- location_key: lowercase with underscores
- display_name: Location name
- location_type: "home", "workplace", "town", "landmark", "shop", "tavern", etc.
- description: What we know about it
- is_player_home: true if this is where the player lives
- is_player_workplace: true if this is where the player works

Example:
```json
{{
  "locations": [
    {{
      "location_key": "players_cottage",
      "display_name": "The Cottage",
      "location_type": "home",
      "description": "Small cottage on the edge of town where player lives with grandmother",
      "is_player_home": true,
      "is_player_workplace": false
    }},
    {{
      "location_key": "blackstone_smithy",
      "display_name": "Blackstone Smithy",
      "location_type": "workplace",
      "description": "The town's blacksmith shop where player apprentices",
      "is_player_home": false,
      "is_player_workplace": true
    }}
  ]
}}
```

### 4. Starting Context

Determine the initial game state:

```json
{{
  "starting_context": {{
    "starting_location_key": "players_cottage",
    "time_of_day": "morning",
    "initial_activity": "just waking up",
    "opening_hook": "A messenger arrives with urgent news"
  }}
}}
```

### 5. World Scope Assessment

Analyze how embedded the player is in their community:

```json
{{
  "world_scope": {{
    "scope_level": "embedded",
    "scope_notes": "Player has family, workplace, and community ties"
  }}
}}
```

scope_level options:
- "isolated": Lone wanderer, no established connections
- "minimal": Few connections (1-2 named entities)
- "embedded": Part of community (3-5 named entities)
- "deeply_embedded": Many ties (6+ named entities)

---

## Output Format

Return ONLY valid JSON combining all sections:

```json
{{
  "player_appearance": {{ ... }},
  "shadow_entities": [ ... ],
  "locations": [ ... ],
  "starting_context": {{ ... }},
  "world_scope": {{ ... }}
}}
```

Do not include explanation or markdown formatting around the JSON.
Be thorough - missing named entities cannot be added later without breaking continuity.
