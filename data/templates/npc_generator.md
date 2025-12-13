# NPC Character Generation

Generate comprehensive character data for an NPC in a **{setting}** game.

## NPC Context

- **Name**: {display_name}
- **Type**: {entity_type}
- **Description**: {description}
- **Personality Traits**: {personality_traits}
- **Current Activity**: {current_activity}
- **Current Location**: {current_location}

## Current Time

Day {game_day}, {game_time}

## Instructions

Generate a complete character profile for this NPC. All data should be internally consistent and appropriate for the setting.

### 1. Appearance

Generate all 12 appearance fields appropriate for:
- The setting ({setting})
- Their implied occupation/role
- Their described traits and context

Fields to populate:
- `age` (integer years)
- `age_apparent` (how old they look, e.g., "early 20s", "middle-aged")
- `gender` (string)
- `height` (string, e.g., "5'10\"", "tall", "short")
- `build` (string, e.g., "athletic", "stocky", "slim")
- `hair_color` (string)
- `hair_style` (string, e.g., "long wavy", "buzz cut")
- `eye_color` (string)
- `skin_tone` (string, e.g., "fair", "tan", "dark")
- `species` (string, e.g., "human", "half-elf", "dwarf")
- `distinguishing_features` (scars, tattoos, notable marks)
- `voice_description` (how they speak)

### 2. Background

Create a brief but meaningful backstory:
- `backstory`: 2-3 sentences explaining their current role and history
- `occupation`: Their primary occupation (use lowercase, e.g., "blacksmith", "guard")
- `occupation_years`: How long they've done this work
- `personality_notes`: Specific traits, quirks, and mannerisms for roleplay

### 3. Skills

Assign 3-5 skills relevant to their occupation and role. Use occupation skill templates as guidance:

{occupation_skills}

Proficiency levels:
- 10-30: Novice (basic understanding)
- 40-60: Journeyman (competent)
- 70-85: Expert (highly skilled)
- 90+: Master (exceptional, rare)

### 4. Inventory

Create contextual inventory appropriate for their role. Use occupation inventory templates as guidance:

{occupation_inventory}

Include:
- Tools of their trade
- Personal effects
- Clothing appropriate for their status/occupation
- Mark equipped items with `is_equipped: true` and appropriate `body_slot`

### 5. Initial Needs

Set context-aware starting values (0-100, higher = better):

Time-based considerations:
- Morning (6-9): Lower hunger (needs breakfast), higher energy
- Midday (11-14): Lower hunger (needs lunch)
- Evening (17-20): Lower hunger and energy
- Night (22-5): Very low energy

Occupation considerations:
- Service workers (innkeeper, cook): Better food/drink access
- Physical laborers: Lower energy, higher hunger/thirst
- Social roles: Higher social_connection

## Output

Return a JSON object matching the NPCGenerationResult schema:

```json
{{
  "entity_key": "{display_name}",
  "appearance": {{
    "age": ...,
    "age_apparent": "...",
    ...
  }},
  "background": {{
    "backstory": "...",
    "occupation": "...",
    "occupation_years": ...,
    "personality_notes": "..."
  }},
  "skills": [
    {{"skill_key": "...", "proficiency_level": ...}},
    ...
  ],
  "inventory": [
    {{"item_key": "...", "display_name": "...", "item_type": "...", ...}},
    ...
  ],
  "initial_needs": {{
    "hunger": ...,
    "thirst": ...,
    "energy": ...,
    ...
  }}
}}
```

Note: Preferences (social_tendency, drive_level, etc.) are generated automatically by the system using probability distributions - do not include them in the output.

Generate the NPC data now.
