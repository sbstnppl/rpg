"""Constrained Narrator node for Scene-First Architecture.

This node invokes SceneNarrator to generate constrained narration:
- Uses only entities from the NarratorManifest
- Outputs [key] format for entity references
- Retries on validation failure
- Falls back to safe narration if needed

This node runs AFTER resolve_references_node.
"""

from typing import Any, TYPE_CHECKING

from src.agents.state import GameState

if TYPE_CHECKING:
    pass


async def constrained_narrator_node(state: GameState) -> dict[str, Any]:
    """Generate constrained narration for the scene.

    This node:
    1. Gets the NarratorManifest with valid entities
    2. Determines narration type from context
    3. Invokes SceneNarrator with retry/fallback
    4. Returns display text and raw output

    Args:
        state: Current game state with narrator_manifest and actions.

    Returns:
        Partial state update with gm_response.
    """
    # Import here to avoid circular imports
    from src.llm.factory import get_extraction_provider
    from src.narrator.scene_narrator import SceneNarrator
    from src.world.schemas import NarrationContext, NarrationType, NarratorManifest

    # Handle clarification directly if needed (can work without manifest)
    if state.get("needs_clarification"):
        clarification_prompt = state.get("clarification_prompt")
        if clarification_prompt:
            return {
                "gm_response": clarification_prompt,
            }
        else:
            return {
                "gm_response": "Could you be more specific about who or what you mean?",
            }

    # Handle INFO mode responses (direct factual answers, bypass SceneNarrator)
    # INFO responses come from narrator_facts and don't need [key:text] format
    if state.get("response_mode") == "info":
        dynamic_plans = state.get("dynamic_plans") or {}
        all_facts: list[str] = []
        for plan in dynamic_plans.values():
            if isinstance(plan, dict):
                facts = plan.get("narrator_facts", [])
                if facts:
                    all_facts.extend(facts)
        if all_facts:
            return {
                "gm_response": " ".join(all_facts),
            }

    # Get narrator manifest
    narrator_manifest_dict = state.get("narrator_manifest")
    if narrator_manifest_dict is None:
        return {
            "gm_response": "You look around but see nothing notable.",
            "errors": ["No narrator manifest for narration"],
        }

    narrator_manifest = NarratorManifest.model_validate(narrator_manifest_dict)

    # Determine narration type
    narration_type = _determine_narration_type(state)

    # Build narration context
    context = _build_narration_context(state)

    # Try to get LLM provider
    try:
        llm_provider = get_extraction_provider()
    except Exception:
        llm_provider = None

    # Initialize narrator
    narrator = SceneNarrator(
        manifest=narrator_manifest,
        llm_provider=llm_provider,
        max_retries=3,
        temperature=0.7,
    )

    try:
        result = await narrator.narrate(
            narration_type=narration_type,
            context=context,
        )

        # Log validation status but don't fail - the output is still usable
        if not result.validation_passed:
            import logging
            logging.getLogger(__name__).warning(
                "Narrator validation did not pass, but output is usable"
            )

        return {
            "gm_response": result.display_text,
            # Store raw output for validation node
            "_narrator_raw_output": result.raw_output,
            "_narrator_validation_passed": result.validation_passed,
        }

    except Exception as e:
        return {
            "gm_response": f"You are in {narrator_manifest.location_display}.",
            "errors": [f"Narration failed: {str(e)}"],
        }


def _determine_narration_type(state: GameState):
    """Determine narration type from game state.

    Args:
        state: Current game state.

    Returns:
        NarrationType for this turn.
    """
    from src.world.schemas import NarrationType

    # Check for clarification needed
    if state.get("needs_clarification"):
        return NarrationType.CLARIFICATION

    # Check for scene entry
    if state.get("just_entered_location") or state.get("location_changed"):
        return NarrationType.SCENE_ENTRY

    # Check for action result
    parsed_actions = state.get("parsed_actions") or []
    if parsed_actions:
        # Check for dialogue actions
        for action in parsed_actions:
            action_type = action.get("type", "").upper()
            if action_type in ("TALK", "SAY", "ASK"):
                return NarrationType.DIALOGUE
        return NarrationType.ACTION_RESULT

    # Default to scene entry for scene requests
    if state.get("is_scene_request"):
        return NarrationType.SCENE_ENTRY

    return NarrationType.SCENE_ENTRY


def _build_narration_context(state: GameState):
    """Build narration context from game state.

    Args:
        state: Current game state.

    Returns:
        NarrationContext for narration.
    """
    from src.world.schemas import NarrationContext

    player_input = state.get("player_input", "")

    # Build player action dict from parsed actions or input
    parsed_actions = state.get("parsed_actions") or []
    player_action = None
    if parsed_actions:
        # Use first parsed action
        player_action = parsed_actions[0]
    elif player_input:
        # Wrap player input in a dict for context
        player_action = {"raw_input": player_input}

    # Get action result if available
    action_result = None
    turn_result = state.get("turn_result")
    if turn_result:
        action_result = turn_result

    # Get clarification prompt if needed
    clarification_prompt = None
    if state.get("needs_clarification"):
        clarification_prompt = state.get("clarification_prompt")

    return NarrationContext(
        player_action=player_action,
        action_result=action_result,
        clarification_prompt=clarification_prompt,
        previous_errors=[],  # Will be set by retry logic
    )
