"""Resolve References node for Scene-First Architecture.

This node resolves player references to entity keys:
- Exact key matches
- Display name matches
- Pronoun resolution
- Descriptor matching

When ambiguous, sets needs_clarification and provides candidates.

This node runs AFTER persist_scene_node.
"""

from typing import Any, TYPE_CHECKING

from src.agents.state import GameState

if TYPE_CHECKING:
    pass


async def resolve_references_node(state: GameState) -> dict[str, Any]:
    """Resolve player references to entity keys.

    This node:
    1. Gets parsed actions with target references
    2. Uses ReferenceResolver to match targets to entities
    3. Returns resolved actions or sets clarification needed

    Args:
        state: Current game state with parsed_actions and narrator_manifest.

    Returns:
        Partial state update with resolved_actions or clarification info.
    """
    # Import here to avoid circular imports
    from src.resolver.reference_resolver import ReferenceResolver
    from src.world.schemas import NarratorManifest

    # Get narrator manifest
    narrator_manifest_dict = state.get("narrator_manifest")
    if narrator_manifest_dict is None:
        return {
            "resolved_actions": None,
            "needs_clarification": False,
            "errors": ["No narrator manifest for reference resolution"],
        }

    narrator_manifest = NarratorManifest.model_validate(narrator_manifest_dict)

    # Get parsed actions
    parsed_actions = state.get("parsed_actions") or []
    if not parsed_actions:
        # No actions to resolve - this might be a scene-only request
        return {
            "resolved_actions": [],
            "needs_clarification": False,
        }

    # Initialize resolver
    resolver = ReferenceResolver(narrator_manifest)

    resolved_actions = []
    clarification_needed = False
    clarification_prompt = None
    clarification_candidates = None

    for action in parsed_actions:
        action_copy = dict(action)
        target = action.get("target")

        if target:
            # Resolve the target reference
            result = resolver.resolve(target)

            if result.resolved and result.entity:
                # Successfully resolved
                action_copy["resolved_target_key"] = result.entity.key
                action_copy["resolved_target_name"] = result.entity.display_name
            elif result.ambiguous and result.candidates:
                # Ambiguous - need clarification
                clarification_needed = True
                candidate_names = [c.display_name for c in result.candidates]
                clarification_prompt = (
                    f'Which "{target}" do you mean: {", ".join(candidate_names)}?'
                )
                clarification_candidates = [c.model_dump() for c in result.candidates]
                # Mark action as unresolved
                action_copy["resolution_failed"] = True
                action_copy["resolution_reason"] = "ambiguous"
            else:
                # Not found in scene
                action_copy["resolution_failed"] = True
                action_copy["resolution_reason"] = "not_found"

        # Also resolve indirect_target if present
        indirect_target = action.get("indirect_target")
        if indirect_target:
            result = resolver.resolve(indirect_target)

            if result.resolved and result.entity:
                action_copy["resolved_indirect_key"] = result.entity.key
                action_copy["resolved_indirect_name"] = result.entity.display_name
            elif result.ambiguous and result.candidates:
                if not clarification_needed:
                    clarification_needed = True
                    candidate_names = [c.display_name for c in result.candidates]
                    clarification_prompt = (
                        f'Which "{indirect_target}" do you mean: {", ".join(candidate_names)}?'
                    )
                    clarification_candidates = [c.model_dump() for c in result.candidates]
                action_copy["indirect_resolution_failed"] = True
                action_copy["indirect_resolution_reason"] = "ambiguous"
            else:
                action_copy["indirect_resolution_failed"] = True
                action_copy["indirect_resolution_reason"] = "not_found"

        resolved_actions.append(action_copy)

    return {
        "resolved_actions": resolved_actions,
        "needs_clarification": clarification_needed,
        "clarification_prompt": clarification_prompt,
        "clarification_candidates": clarification_candidates,
    }
