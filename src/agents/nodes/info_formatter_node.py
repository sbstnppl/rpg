"""Info formatter node for direct factual responses.

This node bypasses the full narrator for simple queries, producing
concise (5-20 word) responses directly from the narrator_facts.

Used when response_mode="info" for queries like:
- "What color is my shirt?" -> "Light purple with brown stitching."
- "Am I hungry?" -> "Slightly hungry. You haven't eaten since yesterday."
- "Where am I?" -> "The farmhouse kitchen."

Note: INFO responses still extract items for deferred spawning, so when
the response mentions "bucket and washbasin", those items are registered
for later on-demand spawning when the player interacts with them.
"""

import logging
from typing import Any

from src.agents.state import GameState
from src.narrator.item_extractor import ItemExtractor, ItemImportance

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

    # Extract items from INFO response for deferred spawning
    # This allows items mentioned in INFO responses (like "bucket and washbasin")
    # to be spawned later when the player interacts with them
    deferred_items = await _extract_deferred_items(state, response)

    result: dict[str, Any] = {"gm_response": response}
    if deferred_items:
        result["deferred_items"] = deferred_items
        logger.debug(f"INFO mode deferred {len(deferred_items)} items for later spawning")

    return result


async def _extract_deferred_items(
    state: GameState,
    response: str,
) -> list[dict[str, Any]]:
    """Extract items from INFO response for deferred spawning.

    Args:
        state: Current game state.
        response: The INFO response text.

    Returns:
        List of deferred item dicts with name, context, location.
    """
    if not response or len(response) < 10:
        return []

    try:
        from src.llm.factory import get_extraction_provider

        llm_provider = get_extraction_provider()
        extractor = ItemExtractor(llm_provider=llm_provider)

        # Extract items from the response
        result = await extractor.extract(response)

        if not result or not result.items:
            return []

        # Get player location for context
        player_location = state.get("player_location", "unknown")

        # All items from INFO responses are deferred (not spawned immediately)
        # They'll be spawned on-demand when the player interacts with them
        deferred = []
        for item in result.items:
            # Skip items marked as REFERENCE (just talked about, not present)
            if item.importance == ItemImportance.REFERENCE:
                continue

            deferred.append({
                "name": item.name,
                "context": item.context or response[:100],
                "location": player_location,
            })

        return deferred

    except Exception as e:
        logger.warning(f"Failed to extract items from INFO response: {e}")
        return []
