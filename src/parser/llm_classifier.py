"""LLM-based intent classification for complex player inputs.

This module provides LLM-powered classification for player inputs that
don't match simple patterns. It uses structured output to ensure
reliable parsing of the LLM response.
"""

from pydantic import BaseModel, Field

from src.parser.action_types import Action, ActionType, ParsedIntent
from src.parser.intent_parser import SceneContext
from src.llm.base import LLMProvider
from src.llm.message_types import Message, MessageRole


class ClassifiedAction(BaseModel):
    """A single action classified by the LLM."""

    action_type: str = Field(
        description="The type of action. Must be one of: "
        "move, enter, exit, take, drop, give, use, equip, unequip, examine, "
        "open, close, attack, defend, flee, talk, ask, tell, trade, persuade, "
        "intimidate, search, rest, wait, sleep, eat, drink, craft, lockpick, "
        "sneak, climb, swim, look, inventory, status, custom"
    )
    target: str | None = Field(
        default=None,
        description="The primary target of the action (item, entity, or location). "
        "For CUSTOM queries ABOUT an entity (e.g., 'where is she?'), set this to the "
        "resolved entity the query is about.",
    )
    indirect_target: str | None = Field(
        default=None,
        description="Secondary target for two-target actions (e.g., recipient in 'give X to Y')",
    )
    manner: str | None = Field(
        default=None,
        description="How the action is performed (e.g., 'carefully', 'quickly', 'stealthily')",
    )


class ClassificationResult(BaseModel):
    """Result of LLM intent classification."""

    actions: list[ClassifiedAction] = Field(
        default_factory=list,
        description="List of mechanical actions identified in the input",
    )
    ambient_flavor: str | None = Field(
        default=None,
        description="Non-mechanical descriptive elements (mood, emotion, style)",
    )
    needs_clarification: bool = Field(
        default=False,
        description="Whether the input is too ambiguous to classify",
    )
    clarification_question: str | None = Field(
        default=None,
        description="Question to ask player if clarification is needed",
    )


CLASSIFIER_SYSTEM_PROMPT = """You are an intent classifier for a fantasy RPG game.
Your job is to identify the mechanical actions a player wants to perform from their natural language input.

Guidelines:
1. Extract mechanical actions that can be executed by the game system
2. Ignore flavor text that doesn't affect game state
3. Resolve ambiguous references using the scene context provided
4. If truly ambiguous, set needs_clarification=true and provide a clarification question
5. For pure roleplay statements with no action or query, return an empty actions list

IMPORTANT - Player Queries (classify as "custom"):
Questions directed at the GAME SYSTEM (not at NPCs) should be classified as "custom":

- Memory/Knowledge: "Do I know...?", "What do I remember about...?", "Have I heard of...?"
- Inventory/Equipment: "Do I have...?", "What am I wearing?", "What's in my bag?"
- Character State: "Am I hungry?", "How tired am I?", "Am I injured?"
- Perception: "What can I see?", "What is X wearing?", "Can I see any weapons?"
- Possibility: "Can I go...?", "Is the door locked?", "Is the path blocked?"
- Relationships: "Does X like me?", "Have I met this person?"
- Location: "Have I been here before?", "Do I know this place?"

These are NOT the same as:
- Questions TO NPCs -> use "ask" (e.g., "Ask the guard about the castle")
- Looking around -> use "look"
- Checking inventory explicitly -> use "inventory"

Action Types:
- Movement: move (go somewhere), enter (enter building/room), exit (leave current area)
- Items: take, drop, give, use, equip, unequip, examine, open, close
- Combat: attack, defend, flee
- Social: talk, ask (question TO an NPC), tell, trade, persuade, intimidate
- World: search, rest, wait, sleep
- Consumption: eat, drink
- Skills: craft, lockpick, sneak, climb, swim
- Meta: look (look around), inventory, status
- Custom: custom (freeform actions AND player queries to the game system)

Target Resolution:
- Use entity_key if the target matches an entity in the scene
- Use item_key if the target matches an item in the scene
- Use the player's words if no clear match exists

Reference Resolution (CRITICAL):
The context may include a "Reference Resolution Guide" section with pre-computed mappings.
Use this to resolve references accurately.

1. PRONOUNS (she/he/it/they/him/her/them):
   - FIRST check if there's a Reference Resolution Guide with a mapping for this pronoun
   - If a mapping exists (e.g., "him" → [entity_id]), use that mapping
   - If NO mapping exists AND multiple entities match the pronoun's gender:
     SET needs_clarification=true and provide a clarification_question listing the candidates
   - Example: Two males present with no pronoun guide → "talk to him" requires clarification

2. ANAPHORIC REFERENCES (the other one, the first, the second):
   - Use the Reference Resolution Guide if available
   - "the other one" typically refers to the contrasting entity in a pair
   - If ambiguous, set needs_clarification=true

3. DESCRIPTIVE REFERENCES (the tall merchant, the singing guy):
   - Match descriptors to entity attributes from Entity Mentions
   - Example: Entity has descriptor "singing" → "the singing guy" matches

IMPORTANT - Pronoun Clarification:
When processing pronouns like "him", "her", "them":
- If there is ONE entity of matching gender → resolve to that entity
- If there are MULTIPLE entities of matching gender AND no Resolution Guide mapping:
  → DO NOT guess, DO NOT pick the most recent
  → Set needs_clarification=true
  → Ask "Which [pronoun] do you mean: [list candidates]?"

Target setting:
- For resolved entities: target="entity_key" or target="[reference_id]"
- For unresolved/ambiguous: leave actions empty, set needs_clarification=true
"""


def _build_classifier_prompt(text: str, context: SceneContext) -> str:
    """Build the classification prompt with scene context."""
    parts = [f'Player input: "{text}"', "", "Scene Context:"]

    parts.append(f"- Location: {context.location_name or context.location_key}")

    if context.entities_present and context.entity_names:
        entity_list = [
            f"{key} ({context.entity_names.get(key, key)})"
            for key in context.entities_present
        ]
        parts.append(f"- Entities present: {', '.join(entity_list)}")
    else:
        parts.append("- Entities present: none")

    if context.items_present and context.item_names:
        item_list = [
            f"{key} ({context.item_names.get(key, key)})"
            for key in context.items_present
        ]
        parts.append(f"- Items visible: {', '.join(item_list)}")
    else:
        parts.append("- Items visible: none")

    if context.exits:
        parts.append(f"- Exits: {', '.join(context.exits)}")

    if context.in_combat:
        parts.append("- Status: IN COMBAT")

    if context.in_conversation:
        parts.append(f"- Status: In conversation with {context.conversation_partner}")

    if context.recent_mentions:
        parts.append("")
        parts.append("Recent Conversation:")
        parts.append(context.recent_mentions)

    parts.append("")
    parts.append("Classify the player's intent. Extract mechanical actions only.")

    return "\n".join(parts)


def _action_type_from_string(type_str: str) -> ActionType:
    """Convert string action type to ActionType enum."""
    type_map = {
        "move": ActionType.MOVE,
        "enter": ActionType.ENTER,
        "exit": ActionType.EXIT,
        "take": ActionType.TAKE,
        "drop": ActionType.DROP,
        "give": ActionType.GIVE,
        "use": ActionType.USE,
        "equip": ActionType.EQUIP,
        "unequip": ActionType.UNEQUIP,
        "examine": ActionType.EXAMINE,
        "open": ActionType.OPEN,
        "close": ActionType.CLOSE,
        "attack": ActionType.ATTACK,
        "defend": ActionType.DEFEND,
        "flee": ActionType.FLEE,
        "talk": ActionType.TALK,
        "ask": ActionType.ASK,
        "tell": ActionType.TELL,
        "trade": ActionType.TRADE,
        "persuade": ActionType.PERSUADE,
        "intimidate": ActionType.INTIMIDATE,
        "search": ActionType.SEARCH,
        "rest": ActionType.REST,
        "wait": ActionType.WAIT,
        "sleep": ActionType.SLEEP,
        "eat": ActionType.EAT,
        "drink": ActionType.DRINK,
        "craft": ActionType.CRAFT,
        "lockpick": ActionType.LOCKPICK,
        "sneak": ActionType.SNEAK,
        "climb": ActionType.CLIMB,
        "swim": ActionType.SWIM,
        "look": ActionType.LOOK,
        "inventory": ActionType.INVENTORY,
        "status": ActionType.STATUS,
        "custom": ActionType.CUSTOM,
    }
    return type_map.get(type_str.lower(), ActionType.CUSTOM)


async def classify_intent(
    text: str,
    context: SceneContext,
    provider: LLMProvider,
) -> ParsedIntent:
    """Classify player intent using LLM.

    Args:
        text: Player input that didn't match patterns.
        context: Scene context for disambiguation.
        provider: LLM provider for classification.

    Returns:
        ParsedIntent with classified actions.
    """
    prompt = _build_classifier_prompt(text, context)

    messages = [Message.user(prompt)]

    response = await provider.complete_structured(
        messages=messages,
        response_schema=ClassificationResult,
        temperature=0.0,  # Deterministic for classification
        max_tokens=500,
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
    )

    # Parse the result
    if response.parsed_content is None:
        # Fallback if structured parsing failed
        return ParsedIntent(
            actions=[Action(type=ActionType.CUSTOM, parameters={"raw_input": text})],
            raw_input=text,
        )

    # Handle both dict (from API) and Pydantic model (from tests)
    if isinstance(response.parsed_content, dict):
        result = ClassificationResult(**response.parsed_content)
    else:
        result = response.parsed_content

    # Convert to our action types
    actions = []
    for classified in result.actions:
        action_type = _action_type_from_string(classified.action_type)

        # Include raw_input and resolved_target in parameters for CUSTOM actions
        # so the planner can use the pronoun-resolved target
        if action_type == ActionType.CUSTOM:
            params = {"raw_input": text}
            # If the classifier resolved a pronoun to a specific target, include it
            if classified.target:
                params["resolved_target"] = classified.target
        else:
            params = {}

        action = Action(
            type=action_type,
            target=classified.target,
            indirect_target=classified.indirect_target,
            manner=classified.manner,
            parameters=params,
        )
        actions.append(action)

    return ParsedIntent(
        actions=actions,
        ambient_flavor=result.ambient_flavor,
        raw_input=text,
        needs_clarification=result.needs_clarification,
        clarification_prompt=result.clarification_question,
    )
