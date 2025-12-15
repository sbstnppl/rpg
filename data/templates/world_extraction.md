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
Extract FULL character details for each NPC - they will be fully generated characters.

For each named entity:
- entity_key: lowercase with underscores (e.g., "grandmother_elara")
- display_name: How they should be addressed (e.g., "Grandmother Elara")
- entity_type: "npc", "monster", "animal", or "organization"
- relationship_to_player: "family", "friend", "colleague", "mentor", "enemy", "acquaintance"
- relationship_role: Specific role (e.g., "grandmother", "younger brother", "mentor", "employer")
- relationship_context: How they emotionally relate to player (e.g., "idolizes player", "protective of player", "secretly jealous")
- brief_description: What we know from backstory
- age: Estimated age (infer from context - parent ~25 years older, sibling within 10 years, etc.)
- gender: "male" or "female"
- occupation: Their job or role (e.g., "farmer", "blacksmith", "homemaker", "child")
- personality_traits: 3-5 traits including relationship-specific ones (e.g., ["protective", "hardworking", "proud of player"])
- brief_appearance: Physical description (hair, build, distinguishing features)
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
      "relationship_role": "grandmother",
      "relationship_context": "Raised the player, deeply protective, worries about their safety",
      "brief_description": "Player's grandmother, they live together",
      "age": 68,
      "gender": "female",
      "occupation": "retired herbalist",
      "personality_traits": ["nurturing", "wise", "protective", "occasionally stubborn", "proud of grandchild"],
      "brief_appearance": "silver hair in a bun, kind wrinkled face, warm brown eyes",
      "is_alive": true,
      "trust": 95,
      "liking": 90,
      "respect": 85
    }},
    {{
      "entity_key": "younger_brother_tom",
      "display_name": "Tom",
      "entity_type": "npc",
      "relationship_to_player": "family",
      "relationship_role": "younger brother",
      "relationship_context": "Idolizes the player, always wants to tag along, eager to learn from them",
      "brief_description": "Player's younger brother, always following them around",
      "age": 10,
      "gender": "male",
      "occupation": "child",
      "personality_traits": ["energetic", "curious", "looks up to player", "mischievous", "easily excited"],
      "brief_appearance": "similar features to player, gap-toothed smile, always dirty knees",
      "is_alive": true,
      "trust": 95,
      "liking": 95,
      "respect": 70
    }},
    {{
      "entity_key": "boss_janet",
      "display_name": "Janet",
      "entity_type": "npc",
      "relationship_to_player": "colleague",
      "relationship_role": "employer",
      "relationship_context": "Stern but fair, sees potential in the player",
      "brief_description": "Player's supervisor at the smithy",
      "age": 45,
      "gender": "female",
      "occupation": "master blacksmith",
      "personality_traits": ["stern", "fair", "skilled", "demanding", "secretly proud of apprentice"],
      "brief_appearance": "muscular arms, burn scars on hands, practical short hair",
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
