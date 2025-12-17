"""Parse intent node for the System-Authority architecture.

This node parses player input into structured actions using LLM classification
as the primary method, with pattern matching only for explicit /commands.
"""

from typing import Any, Callable, Coroutine

from src.agents.state import GameState
from src.llm.factory import get_extraction_provider
from src.parser.intent_parser import IntentParser, SceneContext


async def parse_intent_node(state: GameState) -> dict[str, Any]:
    """Parse player input into structured actions.

    Uses the IntentParser with LLM to convert natural language into Action objects.

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

    # Check for scene request (first turn intro, etc.)
    # These skip normal action parsing and go straight to narrator
    if player_input.startswith("[FIRST TURN") or player_input.startswith("[SCENE"):
        return {
            "parsed_actions": [],
            "ambient_flavor": None,
            "is_scene_request": True,
            "scene_request_type": "intro" if "FIRST TURN" in player_input else "description",
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
