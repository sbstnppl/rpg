"""Info formatter node for direct factual responses.

This node bypasses the full narrator for simple queries, producing
concise (5-20 word) responses directly from the narrator_facts.

Used when response_mode="info" for queries like:
- "What color is my shirt?" -> "Light purple with brown stitching."
- "Am I hungry?" -> "Slightly hungry. You haven't eaten since yesterday."
- "Where am I?" -> "The farmhouse kitchen."

Note: INFO responses still extract items AND locations for world-building.
When the response mentions "bucket at the well", the well is created as a
location and the bucket is deferred for on-demand spawning AT that location.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.narrator.item_extractor import ItemExtractor, ItemImportance
from src.narrator.location_extractor import LocationExtractor

logger = logging.getLogger(__name__)


import re


def _convert_to_second_person(fact: str) -> str:
    """Clean up narrator fact for display.

    With the planner now generating second-person facts directly ("You recall..."),
    this function primarily handles edge cases and cleanup:
    - Removes "Player " prefix if the planner occasionally regresses
    - Converts verb-leading third-person patterns as fallback
    - Converts "their" -> "your" (safe for player-centric facts)
    - Converts "Player's" -> "your"

    IMPORTANT: We do NOT convert "his/her" because these often refer to
    third parties (NPCs, family members) and converting them breaks grammar.
    For example: "You haven't heard about her" (mother) should NOT become
    "You haven't heard about your" (broken).

    Args:
        fact: Raw narrator fact string.

    Returns:
        Cleaned fact ready for display.
    """
    cleaned = fact.strip()

    # Remove "Player " prefix first (e.g., "Player recalls that...")
    if cleaned.lower().startswith("player "):
        cleaned = cleaned[7:]

    # Handle verb-leading patterns and convert to "You [verb]..."
    # This is a fallback for occasional third-person output from the planner
    lower = cleaned.lower()

    verb_patterns = [
        (r"^knows\s+(?:that\s+)?", "You know "),
        (r"^recalls?\s+(?:that\s+)?", "You recall "),
        (r"^remembers?\s+(?:that\s+)?", "You remember "),
        (r"^sees?\s+(?:that\s+)?", "You see "),
        (r"^believes?\s+(?:that\s+)?", "You believe "),
        (r"^thinks?\s+(?:that\s+)?", "You think "),
        (r"^understands?\s+(?:that\s+)?", "You understand "),
        (r"^checks?\s+and\s+finds?\s+", "You find "),
        (r"^is\s+", "You are "),
        (r"^has\s+", "You have "),
        (r"^was\s+", "You were "),
        (r"^were\s+", "You were "),
        (r"^can\s+", "You can "),
        (r"^cannot\s+", "You cannot "),
        (r"^can't\s+", "You can't "),
        (r"^should\s+", "You should "),
        (r"^would\s+", "You would "),
        (r"^could\s+", "You could "),
        (r"^might\s+", "You might "),
        (r"^must\s+", "You must "),
    ]

    for pattern, replacement in verb_patterns:
        match = re.match(pattern, lower)
        if match:
            # Replace pattern preserving the rest of the string
            cleaned = replacement + cleaned[match.end():]
            break

    # Replace safe possessive pronouns only
    # "their father" -> "your father" (safe - "their" is player-neutral)
    cleaned = re.sub(r"\btheir\b", "your", cleaned, flags=re.IGNORECASE)

    # Replace "Player's" with "your"
    cleaned = re.sub(r"\bPlayer'?s?\b", "your", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthe player'?s?\b", "your", cleaned, flags=re.IGNORECASE)

    # NOTE: We intentionally do NOT replace "his", "her", "him" because
    # these often refer to third parties (NPCs, family). For example:
    # - "about her" (mother) should stay, not become "about your"
    # - "his sword" (NPC's sword) should stay, not become "your sword"
    # The planner is now instructed to use proper names for third parties.

    # Replace reflexive pronouns when they refer to the player
    # These are still safe because they're explicitly self-referential
    cleaned = re.sub(r"\bthemselves\b", "yourself", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthemself\b", "yourself", cleaned, flags=re.IGNORECASE)

    # Capitalize first letter
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    # Ensure proper punctuation
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."

    return cleaned


async def info_formatter_node(state: GameState) -> dict[str, Any]:
    """Format INFO mode responses directly from state.

    Takes narrator_facts from dynamic_plans and formats them as concise answers.
    Also extracts locations and items from the response for world-building.

    Args:
        state: Current game state with dynamic_plans containing narrator_facts.

    Returns:
        Partial state update with gm_response, deferred_items, extracted_locations.
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
    # Remove redundant phrases and convert to second person
    formatted_facts = []
    for fact in all_facts:
        cleaned = _convert_to_second_person(fact)
        formatted_facts.append(cleaned)

    # Join facts into a concise response
    response = " ".join(formatted_facts)

    # Ensure proper punctuation
    if response and not response[-1] in ".!?":
        response += "."

    logger.debug(f"INFO mode response: {response[:100]}...")

    # Extract locations and items from INFO response
    # This enables world-building: "bucket at the well" creates well location
    # and defers bucket for spawning at that location
    extraction_result = await _extract_locations_and_items(state, response)

    result: dict[str, Any] = {"gm_response": response}

    if extraction_result.get("extracted_locations"):
        result["extracted_locations"] = extraction_result["extracted_locations"]
        logger.debug(
            f"INFO mode extracted {len(extraction_result['extracted_locations'])} locations"
        )

    if extraction_result.get("deferred_items"):
        result["deferred_items"] = extraction_result["deferred_items"]
        logger.debug(
            f"INFO mode deferred {len(extraction_result['deferred_items'])} items"
        )

    return result


async def _extract_locations_and_items(
    state: GameState,
    response: str,
) -> dict[str, Any]:
    """Extract locations and items from INFO response.

    This is the key function that enables proper world-building from narrative.
    When the response mentions "bucket at the well", this:
    1. Extracts "the well" as a new location
    2. Creates the location in the database (or matches existing)
    3. Extracts "bucket" as an item at "the well" location
    4. Defers the bucket with the correct location key

    Args:
        state: Current game state.
        response: The INFO response text.

    Returns:
        Dict with extracted_locations and deferred_items lists.
    """
    if not response or len(response) < 10:
        return {"extracted_locations": [], "deferred_items": []}

    try:
        from src.llm.factory import get_extraction_provider
        from src.managers.location_manager import LocationManager

        llm_provider = get_extraction_provider()
        player_location = state.get("player_location", "unknown")

        # Get database session for location creation
        db: Session | None = state.get("_db")
        game_session: GameSession | None = state.get("_game_session")

        # Get known locations to avoid re-extracting them
        known_locations: list[str] = []
        if db and game_session:
            location_manager = LocationManager(db, game_session)
            known_locations = location_manager.get_all_location_keys()

        # 1. Extract locations from response
        location_extractor = LocationExtractor(llm_provider=llm_provider)
        location_result = await location_extractor.extract(response, known_locations)

        # 2. Create extracted locations and build location key mapping
        # Maps location names ("the well") to location keys ("farmhouse_well")
        location_key_map: dict[str, str] = {}
        extracted_locations: list[dict[str, Any]] = []

        if location_result.locations and db and game_session:
            location_manager = LocationManager(db, game_session)

            for loc in location_result.locations:
                # Create or find existing location
                location = location_manager.resolve_or_create_location(
                    location_text=loc.name,
                    parent_hint=loc.parent_hint,
                    category=loc.category.value,
                    description=loc.description,
                )

                # Map the original name to the resolved key
                location_key_map[loc.name.lower()] = location.location_key

                # Also map without "the " prefix
                name_no_the = loc.name.lower()
                if name_no_the.startswith("the "):
                    name_no_the = name_no_the[4:]
                location_key_map[name_no_the] = location.location_key

                # Track for persistence node (may need to persist additional data)
                extracted_locations.append({
                    "location_key": location.location_key,
                    "display_name": location.display_name,
                    "category": loc.category.value,
                    "description": loc.description,
                    "parent_hint": loc.parent_hint,
                })

            logger.debug(
                f"Created/resolved {len(location_result.locations)} locations: "
                f"{[loc.name for loc in location_result.locations]}"
            )

        # 3. Extract items with their locations
        item_extractor = ItemExtractor(llm_provider=llm_provider)
        item_result = await item_extractor.extract(response, current_location=player_location)

        # 4. Build deferred items with correct location keys
        deferred_items: list[dict[str, Any]] = []

        if item_result.items:
            for item in item_result.items:
                # Skip items marked as REFERENCE (just talked about, not present)
                if item.importance == ItemImportance.REFERENCE:
                    continue

                # Determine item location
                item_location_key = player_location  # Default to player location

                if item.location:
                    # Try to match item's location to a known/extracted location
                    item_loc_lower = item.location.lower()

                    # Check our extracted locations map
                    if item_loc_lower in location_key_map:
                        item_location_key = location_key_map[item_loc_lower]
                    else:
                        # Try without "the " prefix
                        if item_loc_lower.startswith("the "):
                            item_loc_lower = item_loc_lower[4:]
                        if item_loc_lower in location_key_map:
                            item_location_key = location_key_map[item_loc_lower]
                        elif db and game_session:
                            # Try fuzzy match against existing locations
                            location_manager = LocationManager(db, game_session)
                            matched = location_manager.fuzzy_match_location(
                                item.location
                            )
                            if matched:
                                item_location_key = matched.location_key
                            else:
                                # Create new location for this item
                                new_loc = location_manager.resolve_or_create_location(
                                    location_text=item.location,
                                    category="exterior",
                                    description=f"Location mentioned in narrative",
                                )
                                item_location_key = new_loc.location_key
                                location_key_map[item_loc_lower] = new_loc.location_key

                                extracted_locations.append({
                                    "location_key": new_loc.location_key,
                                    "display_name": new_loc.display_name,
                                    "category": "exterior",
                                })

                deferred_items.append({
                    "name": item.name,
                    "context": item.context or response[:100],
                    "location": item_location_key,
                    "location_description": item.location_description,
                })

            logger.debug(
                f"Deferred {len(deferred_items)} items: "
                f"{[(i['name'], i['location']) for i in deferred_items]}"
            )

        return {
            "extracted_locations": extracted_locations,
            "deferred_items": deferred_items,
        }

    except Exception as e:
        logger.warning(f"Failed to extract locations/items from INFO response: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {"extracted_locations": [], "deferred_items": []}
