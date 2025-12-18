"""Narrative validation node for post-narration checking.

This node validates that the narrator didn't hallucinate items, NPCs,
or locations that don't exist in the game state. If validation fails,
it can trigger re-narration with stricter constraints.
"""

import logging
from typing import Any

from src.agents.state import GameState
from src.narrator.narrative_validator import NarrativeValidator


logger = logging.getLogger(__name__)

# Maximum number of re-narration attempts
MAX_RETRY_COUNT = 2


async def narrative_validator_node(state: GameState) -> dict[str, Any]:
    """Validate narrative against known game state.

    Checks that the narrator didn't invent items, NPCs, or locations.
    If validation fails and we haven't exceeded retry limit, signals
    for re-narration with stricter constraints.

    Args:
        state: Current game state with gm_response.

    Returns:
        Partial state update with validation result and routing signal.
    """
    narrative = state.get("gm_response", "")
    retry_count = state.get("narrative_retry_count", 0)

    # Skip validation for scene intros (they use different constraints)
    if state.get("is_scene_request"):
        logger.debug("Skipping validation for scene request")
        return {
            "narrative_validation_result": {"is_valid": True},
        }

    # Skip validation if no narrative
    if not narrative:
        logger.debug("Skipping validation - no narrative")
        return {
            "narrative_validation_result": {"is_valid": True},
        }

    # Gather context for validation
    # Get spawned items from this turn
    spawned_items = state.get("spawned_items") or []

    # Get items at location from turn_result metadata if available
    # This is populated by the dynamic planner during state gathering
    items_at_location: list[dict[str, Any]] = []
    npcs_present: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    equipped: list[dict[str, Any]] = []

    # Try to extract from dynamic_plans metadata
    dynamic_plans = state.get("dynamic_plans") or {}
    for plan in dynamic_plans.values():
        if isinstance(plan, dict):
            # Look for relevant_state if stored in plan
            relevant_state = plan.get("_relevant_state", {})
            if relevant_state:
                items_at_location = relevant_state.get("items_at_location", [])
                npcs_present = relevant_state.get("npcs_present", [])
                inventory = relevant_state.get("inventory", [])
                equipped = relevant_state.get("equipped", [])
                break

    # Build validator
    validator = NarrativeValidator(
        items_at_location=items_at_location,
        npcs_present=npcs_present,
        available_exits=[],  # Not critical for validation
        spawned_items=spawned_items,
        inventory=inventory,
        equipped=equipped,
    )

    result = validator.validate(narrative)

    if not result.is_valid:
        logger.warning(
            "Narrative validation failed: hallucinated_items=%s",
            result.hallucinated_items,
        )

        if retry_count < MAX_RETRY_COUNT:
            # Need re-narration
            logger.info(
                "Triggering re-narration (attempt %d/%d)",
                retry_count + 1,
                MAX_RETRY_COUNT,
            )
            return {
                "narrative_validation_result": {
                    "is_valid": False,
                    "hallucinated_items": result.hallucinated_items,
                    "hallucinated_npcs": result.hallucinated_npcs,
                },
                "narrative_retry_count": retry_count + 1,
                "narrative_constraints": validator.get_constraint_prompt(),
                "_route_to_narrator": True,  # Signal for conditional routing
            }
        else:
            # Max retries exceeded, log warning but continue
            logger.error(
                "Max re-narration attempts exceeded, proceeding with potentially "
                "invalid narrative. Hallucinated items: %s",
                result.hallucinated_items,
            )
            return {
                "narrative_validation_result": {
                    "is_valid": False,
                    "hallucinated_items": result.hallucinated_items,
                    "max_retries_exceeded": True,
                },
                "errors": [
                    f"Narrative validation failed after {MAX_RETRY_COUNT} retries. "
                    f"Hallucinated items: {result.hallucinated_items}"
                ],
            }

    # Validation passed
    logger.debug("Narrative validation passed")
    return {
        "narrative_validation_result": {
            "is_valid": True,
        },
    }
