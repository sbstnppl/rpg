"""Offloaded rule content for minimal context mode.

These rule sections are moved out of the main system prompt
and made available via tools for on-demand retrieval.
This reduces base prompt size for local LLMs.
"""

# Rule content organized by category
RULE_CONTENT: dict[str, str] = {
    "needs": """## NEED SATISFACTION RULES

When calling satisfy_need, use these amounts:

| Need | Trigger Words | Tool Call |
|------|---------------|-----------|
| hunger | eat, meal, food | satisfy_need(need="hunger", amount=X, activity="...") |
| thirst | drink, water | satisfy_need(need="thirst", amount=X, activity="...") |
| stamina | rest, sit, nap | satisfy_need(need="stamina", amount=X, activity="...") |
| hygiene | bathe, wash | satisfy_need(need="hygiene", amount=X, activity="...") |
| comfort | relax, warm up | satisfy_need(need="comfort", amount=X, activity="...") |
| wellness | exercise, stretch | satisfy_need(need="wellness", amount=X, activity="...") |
| social_connection | chat, talk | satisfy_need(need="social_connection", amount=X, activity="...") |
| morale | celebrate, enjoy | satisfy_need(need="morale", amount=X, activity="...") |
| sense_of_purpose | accomplish task | satisfy_need(need="sense_of_purpose", amount=X, activity="...") |
| intimacy | hug, embrace | satisfy_need(need="intimacy", amount=X, activity="...") |

### Amount Guide

- **hunger**: 10=snack, 25=light meal, 40=full meal, 65=feast
- **thirst**: 8=sip, 25=drink, 45=large drink, 70=deeply
- **stamina**: 10=catch breath, 20=short rest, 40=long rest
- **hygiene**: 15=quick wash, 30=partial bath, 65=full bath
- **social_connection**: 10=brief chat, 22=conversation, 30=group activity, 45=deep bonding

IMPORTANT: Always call satisfy_need BEFORE narrating the action.""",
    "combat": """## COMBAT RULES

### Skill Checks
Use skill_check(skill, dc) when outcome is uncertain AND meaningful:
- USE for: sneaking, perception, climbing, persuading, searching, picking locks
- SKIP for: walking, looking around, basic conversation, familiar tasks

### Difficulty Classes (DC)
- 10 = Easy (obvious actions)
- 15 = Medium (hidden/tricky)
- 20 = Hard (well-concealed, challenging)
- 25 = Legendary (nearly impossible)

### Combat Actions
- **attack_roll**: Roll to hit in combat
- **damage_entity**: Apply damage after successful hit

### Combat Flow
1. Determine initiative if needed
2. Roll attack (attack_roll)
3. On hit, roll damage (damage_entity)
4. Narrate the result""",
    "time": """## TIME ESTIMATION

Estimate realistic time for actions:

| Action | Duration |
|--------|----------|
| Greeting/farewell | 1 minute |
| Brief observation | 1-2 minutes |
| Conversation | 2-10 minutes |
| Take/drop item | 1 minute |
| Eating snack | 5 minutes |
| Eating full meal | 15-30 minutes |
| Drinking | 1-5 minutes |
| Resting | 5-60 minutes |
| Local movement | 1-5 minutes |
| Travel (between areas) | 10 min to 4 hours |

Note: Greeting/farewell is social time, NOT movement time.""",
    "entity_format": """## ENTITY REFERENCE FORMAT

When mentioning entities in your narrative, use [key:text] format:

### Correct Examples
- "[marcus_001:Marcus] waves at you from behind the counter."
- "You pick up [sword_001:the iron sword]."
- "The [closet_001:closet] stands against the wall."

### Wrong (will fail validation)
- "Marcus waves at you." (missing [key:text])
- "You pick up the iron sword." (missing [key:text])
- "A random villager watches you." (entity not in scene)

### Creating New Entities
If you need to reference something NOT in the entity list:
1. First call create_entity tool to create it
2. Use the returned key in [key:text] format

Example:
- TOOL: create_entity(entity_type="item", name="ceramic cup")
- RETURNS: {entity_key: "ceramic_cup_001", ...}
- NARRATIVE: "You notice [ceramic_cup_001:a ceramic cup] on the table."

### Grounding Rules
- Only reference entities from ENTITY REFERENCES or that you create
- Check inventory before assuming player has items""",
    "examples": """## USAGE EXAMPLES

### Example 1: Eating (hunger)
PLAYER: "I eat some bread"
- TOOL: satisfy_need(need="hunger", amount=25, activity="eating bread")
- NARRATIVE: "You tear off a chunk of [bread_001:the crusty bread], savoring its warmth."

### Example 2: Socializing
PLAYER: "I chat with the merchant"
- TOOL: satisfy_need(need="social_connection", amount=22, activity="friendly conversation")
- NARRATIVE: "You exchange pleasantries with [merchant_001:the merchant]."

### Example 3: Taking an Item
PLAYER: "I pick up the iron key"
- TOOL: take_item(item_key="iron_key_001")
- NARRATIVE: "[iron_key_001:The cold metal key] feels heavy in your palm."

### Example 4: NPC Sharing Information
PLAYER: "Who are you?"
- TOOL: get_npc_attitude(from_entity="farmer_001", to_entity="player")
- TOOL: record_fact("entity", "farmer_001", "name", "Marcus")
- NARRATIVE: "'Name's Marcus,' [farmer_001:the man] says gruffly."

### Example 5: Looking Around
PLAYER: "I look around"
- No tools needed unless searching for something specific
- NARRATIVE: Describe visible entities using [key:text] format""",
    "storage": """## STORAGE CONTAINER RULES

Check the STORAGE CONTAINERS section in the scene:

### First Time Visit
If marked **[FIRST TIME]**:
- You may freely invent reasonable contents
- At familiar locations (player's home): include personal belongings
- At unfamiliar locations: may roll or decide what's there
- Use create_entity to create items you invent

### Revisit
If marked **[REVISIT]**:
- Reference ONLY the established contents
- Do NOT create new items
- Contents were established on first observation
- Only world events could change them

### Important
Questions about already-observed containers do NOT create new items:
- "Are there other clothes?" after describing chest -> Answer with what exists
- "I search the chest again" -> Same contents as before""",
    "items": """## ITEM HANDLING RULES

### Taking Items
When player takes/picks up/grabs an item:
- TOOL: take_item(item_key="...")
- Narrate the acquisition using [key:text] format
- The tool updates inventory - you just describe it

### Dropping Items
When player drops/puts down/discards an item:
- TOOL: drop_item(item_key="...")
- Narrate the item being set down

### Giving Items
When player gives an item to an NPC:
- TOOL: give_item(item_key="...", recipient_key="...")
- Narrate the exchange

### Observation vs Acquisition
- OBSERVING (finding, searching): Describe what's there, don't add to inventory
- ACQUIRING (taking, grabbing): Call take_item, add to inventory
- If ambiguous, describe and let player decide""",
    "npc_dialogue": """## NPC DIALOGUE RULES

### Before Any NPC Speech
Always call get_npc_attitude first:
- get_npc_attitude(from_entity="npc_key", to_entity="player_key")
- This tells you how the NPC feels about the player
- Adjust tone and willingness accordingly

### Recording New Information
When NPC shares new info, call record_fact:
- Name: record_fact("entity", "npc_key", "name", "Marcus")
- Job: record_fact("entity", "npc_key", "occupation", "blacksmith")
- Location info: record_fact("location", "loc_key", "description", "...")

### Narrating Speech
Narrate in third person with [key:text]:
- WRONG: "My name is Marcus" (you are NOT the NPC!)
- WRONG: "Marcus says hello" (missing [key:text])
- RIGHT: "[farmer_001:The farmer] scratches his beard. 'Name's Marcus,' he says."

The player never sees dialogue as if from the NPC directly - always narrated.""",
}

# Valid category names for validation
VALID_CATEGORIES = frozenset(RULE_CONTENT.keys())


def get_rule_content(category: str) -> str | None:
    """Get rule content for a category.

    Args:
        category: The rule category name.

    Returns:
        The rule content string, or None if category not found.
    """
    return RULE_CONTENT.get(category)


def get_all_categories() -> list[str]:
    """Get all available rule categories.

    Returns:
        List of category names.
    """
    return list(RULE_CONTENT.keys())
