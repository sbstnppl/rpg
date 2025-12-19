"""Info formatter node for direct factual responses.

This node bypasses the full narrator for simple queries, producing
concise (5-20 word) responses directly from the narrator_facts.

Used when response_mode="info" for queries like:
- "What color is my shirt?" -> "Light purple with brown stitching."
- "Am I hungry?" -> "Slightly hungry. You haven't eaten since yesterday."
- "Where am I?" -> "The farmhouse kitchen."
"""

import logging
from typing import Any

from src.agents.state import GameState

logger = logging.getLogger(__name__)


async def info_formatter_node(state: GameState) -> dict[str, Any]:
    """Format INFO mode responses directly from state.

    Takes narrator_facts from dynamic_plans and formats them as concise answers.
    No LLM call, no prose generation - just direct formatting.

    Args:
        state: Current game state with dynamic_plans containing narrator_facts.

    Returns:
        Partial state update with gm_response.
    """
    # Get facts from dynamic plans
    dynamic_plans = state.get("dynamic_plans") or {}

    # Collect all narrator_facts from plans
    all_facts: list[str] = []
    for plan in dynamic_plans.values():
        if isinstance(plan, dict):
            facts = plan.get("narrator_facts", [])
            if facts:
                all_facts.extend(facts)

    # Also check turn_result for execution facts
    turn_result = state.get("turn_result")
    if turn_result:
        executions = turn_result.get("executions", [])
        for execution in executions:
            result = execution.get("result", {})
            facts = result.get("narrator_facts", [])
            if facts:
                all_facts.extend(facts)

    if not all_facts:
        # Fallback if no facts - shouldn't normally happen
        logger.warning("INFO mode with no narrator_facts, falling back")
        return {"gm_response": "You're not sure."}

    # Format as concise answer
    # Remove redundant phrases and clean up
    formatted_facts = []
    for fact in all_facts:
        # Remove "Player" prefix if present (e.g., "Player recalls that...")
        cleaned = fact
        if cleaned.lower().startswith("player "):
            # Transform "Player recalls that X" -> "X"
            cleaned = cleaned[7:]  # Remove "Player "

        # Handle common patterns that need cleanup
        lower = cleaned.lower()
        if lower.startswith("recalls that "):
            cleaned = cleaned[13:]
        elif lower.startswith("knows that "):
            cleaned = cleaned[11:]
        elif lower.startswith("remembers that "):
            cleaned = cleaned[15:]
        elif lower.startswith("sees that "):
            cleaned = cleaned[10:]
        elif lower.startswith("checks and finds "):
            cleaned = cleaned[17:]
        elif lower.startswith("is "):
            cleaned = "You are " + cleaned[3:]
        elif lower.startswith("has "):
            cleaned = "You have " + cleaned[4:]
        elif lower.startswith("their "):
            cleaned = "Your " + cleaned[6:]
        elif lower.startswith("the player's "):
            cleaned = "Your " + cleaned[12:]

        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        formatted_facts.append(cleaned)

    # Join facts into a concise response
    response = " ".join(formatted_facts)

    # Ensure proper punctuation
    if response and not response[-1] in ".!?":
        response += "."

    logger.debug(f"INFO mode response: {response[:100]}...")

    return {"gm_response": response}
