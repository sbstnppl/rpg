"""Narrator node for the System-Authority architecture.

This node generates narrative prose from mechanical results.

Supports:
- Scene introductions
- LOOK action descriptions
- Chained turn results (multi-action sequences)
- Continuation prompts (asking player to continue after interrupt)
"""

from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.executor.subturn_processor import ChainedTurnResult
from src.llm.factory import get_gm_provider
from src.llm.message_types import Message, MessageRole
from src.narrator.narrator import ConstrainedNarrator


SCENE_INTRO_SYSTEM = """You are the Game Master for a fantasy RPG. Generate atmospheric narrative introductions.

Write in second person ("You are...", "You see..."). Be evocative and immersive.
Use American English (pants not trousers, color not colour, etc.).
Do NOT include any game mechanics, dice rolls, or meta-commentary.
"""

SCENE_INTRO_PROMPT = """Generate an atmospheric introduction for this scene.

SCENE CONTEXT:
{scene_context}

Write 3-5 paragraphs introducing this scene. Include:
- Description of the player character (who they are, what they look like, what they're wearing)
- How the character is feeling right now
- Description of the current location and atmosphere
- Any NPCs present and what they're doing
- Sensory details (sights, sounds, smells)
"""

LOOK_SYSTEM = """You are the Game Master for a fantasy RPG. Describe what the player sees when they look around.

Write in second person ("You see...", "You notice..."). Be concise but evocative.
Use American English (pants not trousers, color not colour, etc.).
Do NOT describe the player's feelings, clothing, or internal state - just what they observe.

CRITICAL - ONLY USE INFORMATION PROVIDED:
- You may ONLY mention items, NPCs, and locations that are explicitly listed in the scene context
- Do NOT invent furniture, objects, or details that aren't in the context
- If something isn't mentioned, it doesn't exist - don't add it
- Use general atmosphere words but NOT specific objects you made up

Do NOT include any game mechanics, dice rolls, or meta-commentary.
"""

LOOK_PROMPT = """Describe what the player sees when they look around.

SCENE CONTEXT:
{scene_context}

Write 2-3 short paragraphs describing:
- The location and its notable features (ONLY those mentioned above)
- Any people present and what they're doing (ONLY those mentioned above)
- Any visible items (ONLY those mentioned above)
- Available exits or directions (ONLY those mentioned above)

IMPORTANT: Only mention things EXPLICITLY listed in the scene context.
If no items are listed, don't mention any items.
If no people are listed, don't mention any people.
Use atmospheric language but do NOT invent specific objects.
"""


async def _generate_scene_intro(scene_context: str) -> str:
    """Generate a scene introduction using the LLM.

    Args:
        scene_context: Compiled scene context from ContextCompiler.

    Returns:
        Narrative introduction text.
    """
    try:
        llm = get_gm_provider()
        prompt = SCENE_INTRO_PROMPT.format(scene_context=scene_context)
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await llm.complete(messages, temperature=0.8, max_tokens=1000, system_prompt=SCENE_INTRO_SYSTEM)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        # Fallback if LLM fails
        return f"You find yourself in an unfamiliar place... (Error generating intro: {e})"


async def _generate_look_description(scene_context: str) -> str:
    """Generate a LOOK description using the LLM.

    This is shorter and more focused than scene_intro - just describes
    what the player sees, not their feelings or clothing.

    Args:
        scene_context: Compiled scene context from ContextCompiler.

    Returns:
        Brief description of visible surroundings.
    """
    try:
        llm = get_gm_provider()
        prompt = LOOK_PROMPT.format(scene_context=scene_context)
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await llm.complete(messages, temperature=0.7, max_tokens=500, system_prompt=LOOK_SYSTEM)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        # Fallback if LLM fails
        return f"You look around... (Error generating description: {e})"


def _is_look_action(turn_result: dict) -> bool:
    """Check if the turn result is a LOOK action that needs scene description."""
    executions = turn_result.get("executions", [])
    failed = turn_result.get("failed_actions", [])
    if len(executions) == 1 and not failed:
        action = executions[0].get("action", {})
        return action.get("type") == "look"
    return False


# Style configurations for narrative output
STYLE_CONFIGS = {
    "observe": {
        "max_tokens": 200,
        "instruction": "Write 2-4 sentences with sensory details about what the player perceives.",
    },
    "action": {
        "max_tokens": 150,
        "instruction": "Write 1-3 sentences focusing on the outcome and brief atmosphere.",
    },
    "dialogue": {
        "max_tokens": 300,
        "instruction": "Focus on NPC speech with direct quotes. Keep prose minimal, speech prominent.",
    },
    "combat": {
        "max_tokens": 100,
        "instruction": "Write 1-2 sentences: mechanical result + brief flavor.",
    },
    "emote": {
        "max_tokens": 50,
        "instruction": "Write just 1 sentence acknowledging the action.",
    },
    # Chained turns get slightly more tokens for multi-action sequences
    "chained": {
        "max_tokens": 250,
        "instruction": "Write 2-5 sentences describing the sequence of actions naturally, as one flowing narrative.",
    },
}


def _build_chained_turn_result(chained_result: dict) -> dict:
    """Build a turn_result dict from chained_turn_result for narrator.

    Converts the subturn-based structure into a format the narrator expects.

    Args:
        chained_result: ChainedTurnResult.to_dict() output.

    Returns:
        Dict with executions[] and failed_actions[] for narrator.
    """
    executions = []
    failed_actions = []

    for subturn in chained_result.get("subturns", []):
        execution = subturn.get("execution")
        validation = subturn.get("validation", {})
        action = subturn.get("action", {})

        if execution and execution.get("success"):
            executions.append({
                "action": action,
                "success": True,
                "outcome": execution.get("outcome", ""),
                "state_changes": execution.get("state_changes", []),
                "metadata": execution.get("metadata", {}),
            })
        elif not validation.get("valid", True):
            failed_actions.append({
                "action": action,
                "reason": validation.get("reason", "Unknown validation error"),
            })

    return {
        "executions": executions,
        "failed_actions": failed_actions,
    }


async def narrator_node(state: GameState) -> dict[str, Any]:
    """Generate narrative from turn result.

    Uses the ConstrainedNarrator to generate prose that includes
    all mechanical facts without contradicting them.

    Supports:
    - Scene introductions
    - LOOK descriptions
    - Chained turn results (multi-action sequences)
    - Continuation prompts (when chain was interrupted with OFFER_CHOICE)

    Args:
        state: Current game state with turn_result or chained_turn_result.

    Returns:
        Partial state update with gm_response.
    """
    # Handle scene requests (first turn intro, etc.)
    if state.get("is_scene_request"):
        scene_context = state.get("scene_context", "")
        if scene_context:
            narrative = await _generate_scene_intro(scene_context)
            return {"gm_response": narrative}
        return {"gm_response": "You find yourself in an unfamiliar place..."}

    # Check for chained turn result (multi-action processing)
    chained_result = state.get("chained_turn_result")
    turn_result = state.get("turn_result")

    # If we have a chained result, build turn_result from it
    if chained_result and chained_result.get("subturns"):
        turn_result = _build_chained_turn_result(chained_result)
        # Include any interrupting complication
        if chained_result.get("interrupting_complication"):
            turn_result["complication"] = chained_result["interrupting_complication"]

    if not turn_result or (not turn_result.get("executions") and not turn_result.get("failed_actions")):
        return {
            "gm_response": "Nothing happens.",
        }

    # Handle LOOK actions - generate brief scene description
    if _is_look_action(turn_result):
        scene_context = state.get("scene_context", "")
        if scene_context:
            narrative = await _generate_look_description(scene_context)
            return {"gm_response": narrative}
        return {"gm_response": "You look around but there's nothing particularly notable to see."}

    # Inject complication from state if not already in turn_result
    complication = state.get("complication")
    if complication and "complication" not in turn_result:
        turn_result = dict(turn_result)  # Make a copy
        turn_result["complication"] = complication

    scene_context = state.get("scene_context", "")
    ambient_flavor = state.get("ambient_flavor")

    # Check for constraints from failed narrative validation
    narrative_constraints = state.get("narrative_constraints", "")

    # Get narrative style for verbosity control
    # Use "chained" style if this was a multi-action turn
    narrative_style = state.get("narrative_style", "action")
    if chained_result and len(chained_result.get("subturns", [])) > 1:
        narrative_style = "chained"
    style_config = STYLE_CONFIGS.get(narrative_style, STYLE_CONFIGS["action"])

    # Use LLM-powered narrator for proper prose generation
    try:
        llm = get_gm_provider()
        narrator = ConstrainedNarrator(
            llm_provider=llm,
            max_tokens=style_config["max_tokens"],
        )
    except Exception:
        # Fallback to non-LLM narrator if provider unavailable
        narrator = ConstrainedNarrator()

    result = await narrator.narrate(
        turn_result=turn_result,
        scene_context=scene_context,
        ambient_flavor=ambient_flavor,
        stable_conditions=narrative_constraints,  # Include validation constraints if present
        style_instruction=style_config["instruction"],
    )

    # Collect any warnings
    errors = []
    if result.warnings:
        errors.extend(result.warnings)

    narrative = result.narrative

    # Append continuation prompt if chain was interrupted with OFFER_CHOICE
    continuation_prompt = state.get("continuation_prompt")
    if continuation_prompt and state.get("continuation_status") == "offer_choice":
        # Add the GM's question to the narrative
        narrative = f"{narrative}\n\n{continuation_prompt}"

    return {
        "gm_response": narrative,
        "errors": errors if errors else [],
    }


def create_narrator_node(
    db: Session,
    game_session: GameSession,
    llm_provider: Any = None,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create a narrator node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.
        llm_provider: Optional LLM provider for richer narration.

    Returns:
        Async node function that generates narrative.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Generate narrative from turn result.

        Args:
            state: Current game state.

        Returns:
            Partial state update with gm_response.
        """
        turn_result = state.get("turn_result")
        if not turn_result:
            return {"gm_response": "Nothing happens."}

        # Inject complication from state if not already in turn_result
        complication = state.get("complication")
        if complication and "complication" not in turn_result:
            turn_result = dict(turn_result)  # Make a copy
            turn_result["complication"] = complication

        scene_context = state.get("scene_context", "")
        ambient_flavor = state.get("ambient_flavor")

        narrator = ConstrainedNarrator(llm_provider=llm_provider)

        result = await narrator.narrate(
            turn_result=turn_result,
            scene_context=scene_context,
            ambient_flavor=ambient_flavor,
        )

        errors = []
        if result.warnings:
            errors.extend(result.warnings)

        return {
            "gm_response": result.narrative,
            "errors": errors if errors else [],
        }

    return node
