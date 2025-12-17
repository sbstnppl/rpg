"""Main intent parser for converting player input to structured actions.

This module provides the IntentParser class which is the primary interface
for parsing player input. It uses pattern matching for fast recognition
and falls back to LLM classification for complex inputs.
"""

from dataclasses import dataclass

from src.parser.action_types import Action, ActionType, ParsedIntent
from src.parser.patterns import parse_input as pattern_parse


@dataclass
class SceneContext:
    """Context about the current scene for parsing.

    This information helps the parser (especially the LLM classifier)
    understand what entities and actions are available.

    Attributes:
        location_key: Current location identifier
        location_name: Display name of current location
        entities_present: List of entity keys present (NPCs, monsters)
        entity_names: Mapping of entity_key -> display_name
        items_present: List of item keys visible in the scene
        item_names: Mapping of item_key -> display_name
        exits: Available exits/directions
        in_combat: Whether combat is active
        in_conversation: Whether in active dialogue with NPC
        conversation_partner: Entity key of conversation partner if any
    """

    location_key: str = ""
    location_name: str = ""
    entities_present: list[str] | None = None
    entity_names: dict[str, str] | None = None
    items_present: list[str] | None = None
    item_names: dict[str, str] | None = None
    exits: list[str] | None = None
    in_combat: bool = False
    in_conversation: bool = False
    conversation_partner: str | None = None


class IntentParser:
    """Parser for converting player input to structured actions.

    The parser uses a multi-stage approach:
    1. Pattern matching for explicit commands (/take, /go) - instant
    2. Pattern matching for natural language - instant
    3. LLM classification for complex/ambiguous input - async

    The pattern matching handles ~80% of typical player inputs instantly.
    The LLM fallback handles creative or complex phrasings.

    Example:
        parser = IntentParser()

        # Simple command - instant
        result = parser.parse("/take sword")
        # -> ParsedIntent(actions=[Action(type=TAKE, target="sword")])

        # Natural language - instant
        result = parser.parse("pick up the rusty sword carefully")
        # -> ParsedIntent(actions=[Action(type=TAKE, target="rusty sword", manner="carefully")])

        # Complex input - needs LLM
        result = await parser.parse_async(
            "I want to grab that shiny thing over there",
            context=scene_context
        )
    """

    def __init__(self, llm_provider=None):
        """Initialize the parser.

        Args:
            llm_provider: Optional LLM provider for complex inputs.
                          If not provided, complex inputs will be marked
                          as needing clarification.
        """
        self.llm_provider = llm_provider

    def parse(self, text: str, context: SceneContext | None = None) -> ParsedIntent:
        """Parse player input synchronously using pattern matching only.

        This is the fast path that handles most common inputs. For inputs
        that don't match any patterns, the result will have an empty
        actions list - call parse_async to use LLM classification.

        Args:
            text: Raw player input.
            context: Optional scene context (used for entity resolution).

        Returns:
            ParsedIntent with recognized actions.
        """
        intent = pattern_parse(text)

        # If we have context, try to resolve ambiguous targets
        if context and intent.actions:
            intent = self._resolve_targets(intent, context)

        return intent

    async def parse_async(
        self, text: str, context: SceneContext | None = None
    ) -> ParsedIntent:
        """Parse player input, falling back to LLM for complex inputs.

        Args:
            text: Raw player input.
            context: Scene context for LLM classification.

        Returns:
            ParsedIntent with recognized actions.
        """
        # Try pattern matching first
        intent = self.parse(text, context)

        # If we got actions, we're done
        if intent.actions or intent.needs_clarification:
            return intent

        # No patterns matched - try LLM classification
        if self.llm_provider and context:
            return await self._llm_classify(text, context)

        # No LLM available - mark as custom action
        return ParsedIntent(
            actions=[Action(type=ActionType.CUSTOM, parameters={"raw_input": text})],
            raw_input=text,
        )

    def _resolve_targets(
        self, intent: ParsedIntent, context: SceneContext
    ) -> ParsedIntent:
        """Try to resolve ambiguous targets using scene context.

        For example, if player says "talk to the guard" and there's an
        entity "town_guard" in the scene, resolve the target.

        Args:
            intent: Parsed intent with potentially ambiguous targets.
            context: Scene context with available entities/items.

        Returns:
            ParsedIntent with resolved targets where possible.
        """
        if not intent.actions:
            return intent

        resolved_actions = []
        for action in intent.actions:
            resolved = self._resolve_single_target(action, context)
            resolved_actions.append(resolved)

        return ParsedIntent(
            actions=resolved_actions,
            ambient_flavor=intent.ambient_flavor,
            raw_input=intent.raw_input,
            needs_clarification=intent.needs_clarification,
            clarification_prompt=intent.clarification_prompt,
        )

    def _resolve_single_target(
        self, action: Action, context: SceneContext
    ) -> Action:
        """Resolve target for a single action."""
        if not action.target:
            return action

        target_lower = action.target.lower()
        resolved_target = action.target
        resolved_indirect = action.indirect_target

        # Determine what to match against based on action type
        if action.category.value in ("item", "consumption"):
            # Match against items
            if context.item_names:
                for key, name in context.item_names.items():
                    if target_lower in name.lower() or target_lower in key.lower():
                        resolved_target = key
                        break
        elif action.category.value in ("social", "combat"):
            # Match against entities
            if context.entity_names:
                for key, name in context.entity_names.items():
                    if target_lower in name.lower() or target_lower in key.lower():
                        resolved_target = key
                        break

            # Also resolve indirect target for social actions
            if action.indirect_target and context.entity_names:
                indirect_lower = action.indirect_target.lower()
                for key, name in context.entity_names.items():
                    if indirect_lower in name.lower() or indirect_lower in key.lower():
                        resolved_indirect = key
                        break

        elif action.category.value == "movement":
            # Match against exits/locations
            if context.exits:
                for exit_name in context.exits:
                    if target_lower in exit_name.lower():
                        resolved_target = exit_name
                        break

        return Action(
            type=action.type,
            target=resolved_target,
            indirect_target=resolved_indirect,
            manner=action.manner,
            parameters=action.parameters,
        )

    async def _llm_classify(
        self, text: str, context: SceneContext
    ) -> ParsedIntent:
        """Use LLM to classify complex player input.

        Args:
            text: Player input that didn't match patterns.
            context: Scene context for the LLM.

        Returns:
            ParsedIntent from LLM classification.
        """
        from src.parser.llm_classifier import classify_intent

        return await classify_intent(text, context, self.llm_provider)
