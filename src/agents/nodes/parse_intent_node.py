"""Parse intent node for the System-Authority architecture.

This node parses player input into structured actions using LLM classification
as the primary method, with pattern matching only for explicit /commands.

Includes:
- Continuation handling: If queued_actions exist and player says "yes", resume chain
- Soft action limit: Max 5 actions per turn to prevent runaway complexity
"""

import re
from typing import Any, Callable, Coroutine

from src.agents.state import GameState
from src.llm.factory import get_extraction_provider
from src.parser.intent_parser import IntentParser, SceneContext


# Maximum actions per turn (soft limit with friendly message)
MAX_ACTIONS_PER_TURN = 5

# Patterns for affirmative responses to continue queued actions
AFFIRMATIVE_PATTERNS = [
    r"^y(es)?$",
    r"^yeah$",
    r"^sure$",
    r"^ok(ay)?$",
    r"^continue$",
    r"^go on$",
    r"^proceed$",
    r"^do it$",
    r"^yep$",
    r"^yup$",
]
AFFIRMATIVE_RE = re.compile("|".join(AFFIRMATIVE_PATTERNS), re.IGNORECASE)

# Patterns for negative responses (decline continuation)
NEGATIVE_PATTERNS = [
    r"^n(o)?$",
    r"^nope$",
    r"^nah$",
    r"^stop$",
    r"^cancel$",
    r"^never ?mind$",
    r"^forget it$",
]
NEGATIVE_RE = re.compile("|".join(NEGATIVE_PATTERNS), re.IGNORECASE)

def _is_affirmative(text: str) -> bool:
    """Check if text is an affirmative response."""
    return bool(AFFIRMATIVE_RE.match(text.strip()))


def _is_negative(text: str) -> bool:
    """Check if text is a negative response."""
    return bool(NEGATIVE_RE.match(text.strip()))


async def parse_intent_node(state: GameState) -> dict[str, Any]:
    """Parse player input into structured actions.

    Uses the IntentParser with LLM to convert natural language into Action objects.

    Handles continuation flow:
    - If queued_actions exist and player input is affirmative, resume queued chain
    - If negative or new action, clear queue and process new input

    Args:
        state: Current game state with player_input and context.

    Returns:
        Partial state update with parsed_actions and ambient_flavor.
    """
    player_input = state.get("player_input", "")
    if not player_input:
        return {
            "parsed_actions": [],
            "ambient_flavor": None,
        }

    # Check for continuation flow first
    queued_actions = state.get("queued_actions")
    if queued_actions:
        # There are queued actions from a previous OFFER_CHOICE interrupt
        if _is_affirmative(player_input):
            # Player wants to continue with queued actions
            return {
                "parsed_actions": queued_actions,
                "ambient_flavor": None,
                "is_continuation": True,
                "queued_actions": None,  # Clear the queue
                "continuation_status": None,
            }
        elif _is_negative(player_input):
            # Player explicitly declined - clear queue, no action this turn
            return {
                "parsed_actions": [],
                "ambient_flavor": None,
                "is_continuation": False,
                "queued_actions": None,  # Clear the queue
                "continuation_status": None,
            }
        # Otherwise, treat as new input - clear queue and parse normally
        # (implicit decline by doing something else)

    # Clear any stale queue state if we're not continuing
    clear_queue = {"queued_actions": None, "continuation_status": None, "is_continuation": False}

    # Check for scene request (first turn intro, etc.)
    # These skip normal action parsing and go straight to narrator
    if player_input.startswith("[FIRST TURN") or player_input.startswith("[SCENE"):
        return {
            "parsed_actions": [],
            "ambient_flavor": None,
            "is_scene_request": True,
            "scene_request_type": "intro" if "FIRST TURN" in player_input else "description",
            **clear_queue,
        }

    # Build scene context from state for target resolution
    context = SceneContext(
        location_key=state.get("player_location", ""),
    )

    # Get LLM provider for intent classification
    try:
        llm_provider = get_extraction_provider()
    except Exception:
        llm_provider = None

    parser = IntentParser(llm_provider=llm_provider)

    try:
        parsed_intent = await parser.parse_async(player_input, context)

        # Convert actions to dicts for state serialization
        action_dicts = [
            {
                "type": action.type.value,
                "target": action.target,
                "indirect_target": action.indirect_target,
                "manner": action.manner,
                "parameters": action.parameters,
            }
            for action in parsed_intent.actions
        ]

        # Apply soft action limit
        warnings = []
        if len(action_dicts) > MAX_ACTIONS_PER_TURN:
            action_dicts = action_dicts[:MAX_ACTIONS_PER_TURN]
            warnings.append(
                f"Let's take it step by step. Processing the first {MAX_ACTIONS_PER_TURN} actions."
            )

        # response_mode is determined by DynamicActionPlanner for CUSTOM actions
        # via LLM call in subturn_processor_node, not here
        result = {
            "parsed_actions": action_dicts,
            "ambient_flavor": parsed_intent.ambient_flavor,
            **clear_queue,
        }

        if warnings:
            result["errors"] = warnings  # Shows as warning to player

        return result

    except Exception as e:
        return {
            "parsed_actions": [],
            "ambient_flavor": None,
            "errors": [f"Failed to parse intent: {str(e)}"],
            **clear_queue,
        }


def create_parse_intent_node() -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a parse intent node.

    Returns:
        Async node function that parses player input.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Parse player input into structured actions.

        Args:
            state: Current game state.

        Returns:
            Partial state update with parsed_actions and ambient_flavor.
        """
        player_input = state.get("player_input", "")
        if not player_input:
            return {
                "parsed_actions": [],
                "ambient_flavor": None,
            }

        # Build scene context from state for target resolution
        context = SceneContext(
            location_key=state.get("player_location", ""),
        )

        # Get LLM provider for intent classification
        try:
            llm_provider = get_extraction_provider()
        except Exception:
            llm_provider = None

        parser = IntentParser(llm_provider=llm_provider)

        try:
            parsed_intent = await parser.parse_async(player_input, context)

            action_dicts = [
                {
                    "type": action.type.value,
                    "target": action.target,
                    "indirect_target": action.indirect_target,
                    "manner": action.manner,
                    "parameters": action.parameters,
                }
                for action in parsed_intent.actions
            ]

            return {
                "parsed_actions": action_dicts,
                "ambient_flavor": parsed_intent.ambient_flavor,
            }

        except Exception as e:
            return {
                "parsed_actions": [],
                "ambient_flavor": None,
                "errors": [f"Failed to parse intent: {str(e)}"],
            }

    return node
