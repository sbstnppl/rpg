"""Validate Narrator node for Scene-First Architecture.

This node validates the narrator output against the manifest:
- Checks all [key] references are valid
- Detects unkeyed entity mentions
- Routes back to narrator on failure or to persistence on success

This node runs AFTER constrained_narrator_node.
"""

from typing import Any, TYPE_CHECKING

from src.agents.state import GameState

if TYPE_CHECKING:
    pass


# Maximum validation retries before using fallback
MAX_VALIDATION_RETRIES = 2


async def validate_narrator_node(state: GameState) -> dict[str, Any]:
    """Validate narrator output against manifest.

    This node:
    1. Gets the raw narrator output
    2. Validates [key] references against manifest
    3. Routes back to narrator on failure or proceeds on success

    Args:
        state: Current game state with narrator output and manifest.

    Returns:
        Partial state update with validation result or routing flag.
    """
    # Import here to avoid circular imports
    from src.narrator.validator import NarratorValidator
    from src.world.schemas import NarratorManifest

    # Get narrator manifest
    narrator_manifest_dict = state.get("narrator_manifest")
    if narrator_manifest_dict is None:
        # No manifest to validate against - skip validation
        return {
            "narrative_validation_result": {
                "valid": True,
                "skipped": True,
                "reason": "No manifest",
            },
        }

    narrator_manifest = NarratorManifest.model_validate(narrator_manifest_dict)

    # Get raw narrator output
    raw_output = state.get("_narrator_raw_output")
    if raw_output is None:
        # No raw output - use gm_response
        raw_output = state.get("gm_response", "")

    # Check if validation already passed in narrator
    if state.get("_narrator_validation_passed"):
        return {
            "narrative_validation_result": {
                "valid": True,
                "references": [],
            },
        }

    # Get current retry count
    retry_count = state.get("narrative_retry_count", 0)

    # Initialize validator
    validator = NarratorValidator(narrator_manifest)

    try:
        validation_result = validator.validate(raw_output)

        if validation_result.valid:
            return {
                "narrative_validation_result": {
                    "valid": True,
                    "references": validation_result.references,
                },
            }

        # Validation failed
        if retry_count < MAX_VALIDATION_RETRIES:
            # Route back to narrator for retry
            error_messages = validation_result.error_messages
            return {
                "narrative_validation_result": {
                    "valid": False,
                    "errors": error_messages,
                },
                "narrative_retry_count": retry_count + 1,
                "narrative_constraints": "\n".join(error_messages),
                "_route_to_narrator": True,  # Signal to route back
            }
        else:
            # Max retries exceeded - accept current output (it's still usable)
            import logging
            logging.getLogger(__name__).info(
                f"Narrator validation soft-failed after {retry_count} retries, accepting output"
            )
            return {
                "narrative_validation_result": {
                    "valid": False,
                    "accepted_with_errors": True,
                    "errors": validation_result.error_messages,
                },
                # Don't add to errors - the output is still usable
            }

    except Exception as e:
        return {
            "narrative_validation_result": {
                "valid": False,
                "error": str(e),
            },
            "errors": [f"Narrator validation error: {str(e)}"],
        }
