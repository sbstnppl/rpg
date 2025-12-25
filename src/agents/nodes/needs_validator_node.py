"""Needs validator node - catches missed needs updates after GM narration.

This node runs after game_master_node and checks if the GM's narrative
describes actions that should have updated character needs. If the GM
forgot to call satisfy_need, this node applies reasonable defaults.

This is a FALLBACK mechanism - the GM should call the tools, this catches misses.
"""

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.character_state import CharacterNeeds
from src.database.models.session import GameSession
from src.managers.needs import NeedsManager, estimate_base_satisfaction

logger = logging.getLogger(__name__)

# Keyword patterns for detecting need-affecting actions in narrative
# Uses word boundaries to avoid false positives (e.g., "water" in "waterfall")
NEED_KEYWORDS: dict[str, list[str]] = {
    "hygiene": [
        r"\bwash\w*\b",  # wash, washed, washing
        r"\bbathe\w*\b",  # bathe, bathed, bathing
        r"\bbath\b",
        r"\brinse\w*\b",
        r"\bclean\w*\b",  # clean, cleaned, cleaning (in context)
        r"\bscrub\w*\b",
        r"\bshower\w*\b",
        r"\bsplash\w*\b",  # splashing water on face
    ],
    "hunger": [
        r"\beat\w*\b",  # eat, eating, eats
        r"\bate\b",  # past tense
        r"\bfood\b",
        r"\bmeal\b",
        r"\bsnack\w*\b",
        r"\bbreakfast\b",
        r"\blunch\b",
        r"\bdinner\b",
        r"\bsupper\b",
        r"\bchew\w*\b",
        r"\bswallow\w*\b",
        r"\bbite\b",
    ],
    "thirst": [
        r"\bdrink\w*\b",  # drink, drinking, drinks
        r"\bdrank\b",  # past tense
        r"\bale\b",
        r"\bwine\b",
        r"\btea\b",
        r"\bwater\b",  # drinking water specifically
        r"\bgulp\w*\b",
        r"\bsip\w*\b",
        r"\bquaff\w*\b",
    ],
    "stamina": [
        r"\brest\w*\b",  # rest, rested, resting
        r"\brelax\w*\b",
        r"\bsit\s+down\b",
        r"\bcatch\w*\s+breath\b",
        r"\blie\s+down\b",
        r"\blying\s+down\b",
    ],
    "social_connection": [
        r"\btalk\w*\b",  # talk, talked, talking
        r"\bchat\w*\b",
        r"\bconversat\w*\b",  # conversation, conversing
        r"\bdiscuss\w*\b",
        r"\bconfide\w*\b",
        r"\bheart-to-heart\b",
    ],
}

# Map needs to their "last action" turn tracking field
NEED_TURN_FIELDS: dict[str, str] = {
    "hygiene": "last_bath_turn",
    "hunger": "last_meal_turn",
    "thirst": "last_drink_turn",
    "stamina": "last_sleep_turn",  # rest also uses sleep tracking
    "social_connection": "last_social_turn",
}

# Default action types for auto-applying updates
DEFAULT_ACTION_TYPES: dict[str, str] = {
    "hygiene": "partial_bath",  # ~30 points
    "hunger": "light_meal",  # ~22 points
    "thirst": "drink",  # ~30 points
    "stamina": "short_rest",  # ~30 points
    "social_connection": "conversation",  # ~25 points
}


async def needs_validator_node(state: GameState) -> dict[str, Any]:
    """Validate that GM called satisfy_need when narrating need-affecting actions.

    Scans the GM response for keywords suggesting needs were satisfied
    (washing, eating, drinking, etc.) and checks if the corresponding
    satisfy_need tool was called by checking last_*_turn fields.

    If keywords are found but the need wasn't updated this turn,
    applies a reasonable default update.

    Args:
        state: Current game state with gm_response and DB context.

    Returns:
        Dict with validation_results and any auto-applied updates.
    """
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")
    gm_response: str | None = state.get("gm_response")
    player_id: int | None = state.get("player_id")
    turn_number: int = state.get("turn_number", 1)

    # Skip if missing context
    if db is None or game_session is None:
        return {}

    if not gm_response or not player_id:
        return {}

    # Get player entity
    from src.managers.entity_manager import EntityManager

    entity_manager = EntityManager(db, game_session)
    player = entity_manager.get_player()
    if not player:
        return {}

    # Get current needs
    needs_manager = NeedsManager(db, game_session)
    needs = needs_manager.get_or_create_needs(player.id)

    # Scan response for keywords and check if updates were applied
    auto_applied: list[dict[str, Any]] = []
    response_lower = gm_response.lower()

    for need_name, patterns in NEED_KEYWORDS.items():
        # Check if any keyword matches
        keyword_found = False
        matched_keyword = ""
        for pattern in patterns:
            match = re.search(pattern, response_lower)
            if match:
                keyword_found = True
                matched_keyword = match.group()
                break

        if not keyword_found:
            continue

        # Check if this need was already updated this turn
        turn_field = NEED_TURN_FIELDS.get(need_name)
        if turn_field:
            last_turn = getattr(needs, turn_field, None)
            if last_turn == turn_number:
                # GM already called the tool this turn - skip
                logger.debug(
                    f"Needs validator: {need_name} already updated this turn "
                    f"(keyword '{matched_keyword}' found)"
                )
                continue

        # Need wasn't updated but action was narrated - apply default
        action_type = DEFAULT_ACTION_TYPES.get(need_name, "basic")
        base_amount = estimate_base_satisfaction(need_name, action_type, "basic")

        old_value = getattr(needs, need_name, 50)
        new_needs = needs_manager.satisfy_need(
            entity_id=player.id,
            need_name=need_name,
            amount=base_amount,
            turn=turn_number,
        )
        new_value = getattr(new_needs, need_name, old_value)

        logger.info(
            f"Needs validator auto-applied: {need_name} +{base_amount} "
            f"({old_value} -> {new_value}) [keyword: '{matched_keyword}']"
        )

        auto_applied.append({
            "need": need_name,
            "keyword": matched_keyword,
            "action_type": action_type,
            "amount": base_amount,
            "old_value": old_value,
            "new_value": new_value,
        })

    result: dict[str, Any] = {}

    if auto_applied:
        result["needs_auto_applied"] = auto_applied
        logger.warning(
            f"Needs validator auto-applied {len(auto_applied)} update(s) - "
            "GM should call satisfy_need tool for these actions"
        )

    return result


def create_needs_validator_node(
    db: Session,
    game_session: GameSession,
):
    """Create a needs validator node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that validates needs updates.
    """

    async def node(state: GameState) -> dict[str, Any]:
        # Inject db and game_session into state for the main function
        state_with_deps = dict(state)
        state_with_deps["_db"] = db
        state_with_deps["_game_session"] = game_session
        return await needs_validator_node(GameState(**state_with_deps))

    return node
