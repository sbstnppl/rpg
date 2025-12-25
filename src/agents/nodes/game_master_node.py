"""GameMaster node for narrative generation.

This node generates the GM's narrative response to player input
using an LLM provider. Supports tool calling for dice rolls and NPC queries.

.. deprecated::
    This node is part of the LEGACY flow where the LLM decides what happens.
    The new System-Authority flow uses:
    - parse_intent_node → validate_actions_node → complication_oracle_node
    - execute_actions_node → narrator_node

    The legacy flow is retained for backward compatibility but may be removed
    in a future version. Use build_system_authority_graph() for new games.
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.agents.tools.gm_tools import GM_TOOLS
from src.agents.tools.executor import GMToolExecutor
from src.database.models.session import GameSession
from src.llm.factory import get_reasoning_provider
from src.llm.message_types import Message, MessageContent, MessageRole
from src.llm.audit_logger import set_audit_context
from src.managers.context_validator import ContextValidator


# Template path
TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "templates" / "game_master.md"


async def game_master_node(state: GameState) -> dict[str, Any]:
    """Generate GM narrative response.

    This is the default node function that expects _db and _game_session
    to be present in state.

    Args:
        state: Current game state with _db and _game_session.

    Returns:
        Partial state update with gm_response and routing info.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "gm_response": "Error: Missing database context.",
            "errors": ["Missing database session or game session in state"],
        }

    return await _generate_response(state)


def create_game_master_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a game master node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that generates GM response.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Generate GM narrative response.

        Args:
            state: Current game state.

        Returns:
            Partial state update with gm_response.
        """
        return await _generate_response(state)

    return node


async def _generate_response(state: GameState) -> dict[str, Any]:
    """Internal helper to generate GM response.

    Uses tool calling to let the GM invoke dice rolls and query NPC attitudes.

    Args:
        state: Current game state.

    Returns:
        Partial state update.
    """
    # Set audit context for logging
    session_id = state.get("session_id")
    turn_number = state.get("turn_number")
    set_audit_context(
        session_id=session_id,
        turn_number=turn_number,
        call_type="game_master",
    )

    # Load and format template
    template = _load_template()

    # Generate constraint context to prevent contradictions
    constraint_context = ""
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")
    if db is not None and game_session is not None:
        validator = ContextValidator(db, game_session)
        # Get entity keys from scene context (NPCs at location)
        entity_keys = state.get("entity_keys", [])
        constraint_context = validator.get_constraint_context(entity_keys)

    prompt = template.format(
        scene_context=state.get("scene_context", ""),
        player_input=state.get("player_input", ""),
        constraint_context=constraint_context,
    )

    # Get LLM provider and generate response with tools
    provider = get_reasoning_provider()
    messages = [Message.user(prompt)]

    # Setup tool executor if we have database context
    executor = None
    if db is not None and game_session is not None:
        # Pass current player location so spawn_storage/spawn_item know where to create things
        current_zone_key = state.get("player_location")
        executor = GMToolExecutor(db, game_session, current_zone_key=current_zone_key)

    # Track skill checks for interactive display
    skill_checks: list[dict[str, Any]] = []

    # Tool calling loop - allow multiple rounds of tool use
    # Accumulate text across rounds (narrative may come before tool calls)
    accumulated_text: list[str] = []
    max_tool_rounds = 5
    for _ in range(max_tool_rounds):
        if executor is not None:
            # Call with tools available
            response = await provider.complete_with_tools(
                messages=messages,
                tools=GM_TOOLS,
                max_tokens=2048,
                temperature=0.8,
            )
        else:
            # No tools available without DB context
            response = await provider.complete(
                messages=messages,
                max_tokens=2048,
                temperature=0.8,
            )

        # If no tool calls, we're done
        if not response.has_tool_calls:
            break

        # Build assistant message with both text content and tool_use blocks
        content_blocks: list[MessageContent] = []

        # Add text content if present (and accumulate for final response)
        if response.content:
            content_blocks.append(MessageContent(type="text", text=response.content))
            accumulated_text.append(response.content)

        # Add tool_use blocks for each tool call
        for tool_call in response.tool_calls:
            content_blocks.append(MessageContent(
                type="tool_use",
                tool_use_id=tool_call.id,
                tool_name=tool_call.name,
                tool_input=tool_call.arguments,
            ))

        # Add assistant message with all content blocks
        messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=tuple(content_blocks),
        ))

        for tool_call in response.tool_calls:
            if executor is not None:
                try:
                    result = executor.execute(tool_call.name, tool_call.arguments)
                    result_str = json.dumps(result)

                    # Track skill checks for interactive display
                    if tool_call.name == "skill_check" and "error" not in result:
                        skill_checks.append(result)

                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
            else:
                result_str = json.dumps({"error": "No database context for tool execution"})

            messages.append(Message.tool_result(tool_call.id, result_str))

    # Parse state changes from combined response
    # Include any text from tool-calling rounds plus the final response
    if response.content and response.content not in accumulated_text:
        accumulated_text.append(response.content)
    raw_response = "\n\n".join(accumulated_text)
    narrative, state_changes = parse_state_block(raw_response, return_narrative=True)

    # Build result from STATE block parsing (fallback approach)
    result = {
        "gm_response": narrative.strip(),
        "time_advance_minutes": state_changes.get("time_advance_minutes", 5),
        "location_changed": state_changes.get("location_changed", False),
        "player_location": state_changes.get("location_change") or state.get("player_location"),
        "combat_active": state_changes.get("combat_active", False),
        "skill_checks": skill_checks,  # For interactive dice display
    }

    # Merge tool-based state updates (takes precedence over STATE block parsing)
    # This is the new approach that replaces STATE block parsing
    if executor is not None and executor.pending_state_updates:
        for key, value in executor.pending_state_updates.items():
            result[key] = value

    # Add error info if response was empty
    if not narrative.strip():
        result["errors"] = result.get("errors", []) + [
            f"LLM returned empty response. finish_reason={response.finish_reason}"
        ]

    return result


def _load_template() -> str:
    """Load the GM prompt template.

    Returns:
        Template string.
    """
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text()

    # Fallback inline template
    return """# Game Master

{scene_context}

{constraint_context}

## Player Input
{player_input}

Respond with narrative. End with:
---STATE---
time_advance_minutes: [number]
location_change: [location or none]
combat_initiated: [true/false]"""


def parse_state_block(
    text: str,
    return_narrative: bool = False,
) -> dict[str, Any] | tuple[str, dict[str, Any]]:
    """Parse the ---STATE--- block from GM response.

    Args:
        text: Full GM response text.
        return_narrative: If True, also return narrative portion.

    Returns:
        State dict, or tuple of (narrative, state_dict) if return_narrative.
    """
    defaults = {
        "time_advance_minutes": 5,
        "location_changed": False,
        "location_change": None,
        "combat_active": False,
    }

    # Split on state block marker
    if "---STATE---" not in text:
        if return_narrative:
            return text, defaults
        return defaults

    parts = text.split("---STATE---", 1)
    narrative = parts[0].strip()
    state_text = parts[1].strip() if len(parts) > 1 else ""

    result = defaults.copy()

    # Parse time_advance_minutes
    time_match = re.search(r"time_advance_minutes:\s*(\d+)", state_text)
    if time_match:
        result["time_advance_minutes"] = int(time_match.group(1))

    # Parse location_change
    loc_match = re.search(r"location_change:\s*(\S+)", state_text)
    if loc_match:
        loc_value = loc_match.group(1).lower()
        if loc_value not in ("none", "null", ""):
            result["location_change"] = loc_value
            result["location_changed"] = True

    # Parse combat_initiated
    combat_match = re.search(r"combat_initiated:\s*(true|false)", state_text, re.IGNORECASE)
    if combat_match:
        result["combat_active"] = combat_match.group(1).lower() == "true"

    if return_narrative:
        return narrative, result
    return result
