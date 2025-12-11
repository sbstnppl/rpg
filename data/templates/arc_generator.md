# Relationship Arc Generator

Generate a custom relationship arc template for two characters in a **{setting}** RPG.

## Important: Arcs are Guidance, Not Scripts

The arc you generate serves as **GM inspiration**, not deterministic scripting:
- Player actions always determine actual outcomes
- Arcs suggest dramatic possibilities based on current trajectory
- Multiple endings must be possible - player choice decides which occurs
- The arc can be abandoned or shifted if player actions change the dynamic

## Characters

### Character 1: {entity1_name}
- **Type**: {entity1_type}
- **Description**: {entity1_description}
- **Personality**: {entity1_personality}
- **Occupation**: {entity1_occupation}

### Character 2: {entity2_name}
- **Type**: {entity2_type}
- **Description**: {entity2_description}
- **Personality**: {entity2_personality}
- **Occupation**: {entity2_occupation}

## Current Relationship State

| Dimension | Value | Interpretation |
|-----------|-------|----------------|
| Trust | {trust}/100 | {trust_interpretation} |
| Liking | {liking}/100 | {liking_interpretation} |
| Respect | {respect}/100 | {respect_interpretation} |
| Romantic Interest | {romantic}/100 | {romantic_interpretation} |
| Fear | {fear}/100 | {fear_interpretation} |
| Familiarity | {familiarity}/100 | {familiarity_interpretation} |

- **Times Met**: {meeting_count}
- **Relationship Duration**: {relationship_duration}
- **Recent Interactions**: {recent_interactions}

## Instructions

Create a unique relationship arc that:

1. **Fits the current dynamics** - Don't force incompatible arcs. If trust is high and liking is high, don't suggest a betrayal arc unless there's reason.

2. **Has 4-6 distinct phases** with clear progression:
   - Each phase should feel meaningfully different
   - Include specific milestones to watch for (not force)
   - Suggest dramatic scenes appropriate to the {setting} setting

3. **Provides multiple possible endings** - Include both positive and negative outcomes. The player's choices determine which occurs.

4. **Includes tension management** - Define what increases and decreases dramatic tension.

5. **Is setting-appropriate** - For {setting}, consider:
   - Fantasy: Honor, duty, magic, nobility, ancient grudges
   - Contemporary: Social media, careers, family expectations, legal issues
   - Sci-fi: Technology, alien cultures, corporate intrigue, distance/time

## Example Arc Types (for inspiration - create something unique)

- **enemies_to_lovers**: Initial hostility transforms to romance through forced cooperation
- **betrayal**: Trust-building leads to devastating betrayal when hidden agenda is revealed
- **redemption**: Antagonist influenced toward redemption through player's example
- **found_family**: Strangers become chosen family through shared hardship
- **student_surpasses_master**: Mentorship leads to role reversal
- **reluctant_alliance**: Enemies cooperate against greater threat, transforming relationship

## Output

Return a JSON object matching the GeneratedArcTemplate schema:

```json
{{
  "arc_type_name": "unique_arc_name",
  "arc_type_display": "Human Readable Name",
  "arc_description": "2-3 sentence description of what this arc represents",
  "phases": [
    {{
      "phase_key": "introduction",
      "phase_name": "Phase Name",
      "description": "What happens during this phase",
      "suggested_milestones": ["milestone_1", "milestone_2"],
      "suggested_scenes": ["Scene idea 1", "Scene idea 2"],
      "typical_duration_description": "Several encounters"
    }}
  ],
  "potential_endings": [
    "Positive ending possibility",
    "Negative ending possibility",
    "Bittersweet ending possibility"
  ],
  "tension_triggers": [
    "Event that increases tension",
    "Another tension trigger"
  ],
  "de_escalation_triggers": [
    "Event that could defuse tension",
    "Another de-escalation option"
  ],
  "setting_notes": "Setting-specific considerations",
  "why_this_arc": "Why this arc fits the current relationship"
}}
```

Generate the relationship arc now.
