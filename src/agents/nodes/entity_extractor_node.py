"""EntityExtractor node for parsing GM responses.

This node extracts entities, facts, and state changes from GM responses
using structured LLM output.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.agents.schemas.extraction import ExtractionResult
from src.database.models.session import GameSession
from src.llm.factory import get_extraction_provider
from src.llm.message_types import Message
from src.llm.audit_logger import set_audit_context
from src.managers.context_validator import ContextValidator


logger = logging.getLogger(__name__)


# Template path
TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "templates" / "entity_extractor.md"


async def entity_extractor_node(state: GameState) -> dict[str, Any]:
    """Extract entities and facts from GM response.

    This is the default node function that expects _db and _game_session
    to be present in state.

    Args:
        state: Current game state with _db and _game_session.

    Returns:
        Partial state update with extraction results.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "errors": ["Missing database session or game session in state"],
            "next_agent": "persistence",
        }

    return await _extract_entities(state)


def create_entity_extractor_node(
    db: Session,
    game_session: GameSession,
) -> Callable[[GameState], Coroutine[Any, Any, dict[str, Any]]]:
    """Create an entity extractor node with bound dependencies.

    Args:
        db: Database session.
        game_session: Current game session.

    Returns:
        Async node function that extracts entities.
    """

    async def node(state: GameState) -> dict[str, Any]:
        """Extract entities from GM response.

        Args:
            state: Current game state.

        Returns:
            Partial state update with extractions.
        """
        return await _extract_entities(state)

    return node


async def _extract_entities(state: GameState) -> dict[str, Any]:
    """Internal helper to extract entities from GM response.

    Args:
        state: Current game state.

    Returns:
        Partial state update with extraction results.
    """
    # Set audit context for logging
    session_id = state.get("session_id")
    turn_number = state.get("turn_number")
    set_audit_context(
        session_id=session_id,
        turn_number=turn_number,
        call_type="entity_extractor",
    )

    gm_response = state.get("gm_response")

    # Skip extraction if no GM response
    if not gm_response:
        return {
            "extracted_entities": [],
            "extracted_facts": [],
            "relationship_changes": [],
            "next_agent": "persistence",
        }

    # Load and format template
    template = _load_template()
    prompt = template.format(
        gm_response=gm_response,
        player_input=state.get("player_input", ""),
        player_location=state.get("player_location", "unknown"),
    )

    # Get LLM provider and extract
    provider = get_extraction_provider()

    response = await provider.complete_structured(
        messages=[Message.user(prompt)],
        response_schema=ExtractionResult,
        max_tokens=2048,
        temperature=0.0,  # Low temperature for extraction
    )

    # Convert extraction result to state update
    # parsed_content is a dict from tool arguments, parse into Pydantic model
    raw_extraction = response.parsed_content

    try:
        if isinstance(raw_extraction, dict):
            # Ensure list fields have proper defaults (LLM may return null or non-list)
            for list_field in ["characters", "items", "locations", "facts", "relationship_changes", "appointments"]:
                val = raw_extraction.get(list_field)
                if val is None or not isinstance(val, list):
                    raw_extraction[list_field] = []
            extraction = ExtractionResult.model_validate(raw_extraction)
        elif raw_extraction is None:
            extraction = ExtractionResult()
        else:
            extraction = raw_extraction
    except Exception as e:
        # If parsing fails, return empty extraction with error
        return {
            "extracted_entities": [],
            "extracted_items": [],
            "extracted_locations": [],
            "extracted_facts": [],
            "relationship_changes": [],
            "appointments": [],
            "errors": [f"Extraction parsing failed: {e}"],
            "next_agent": "persistence",
        }

    # Validate entity references
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")
    validation_warnings: list[str] = []

    if db is not None and game_session is not None:
        validator = ContextValidator(db, game_session)

        # Collect all entity keys referenced in extraction
        referenced_keys: set[str] = set()

        # From relationship changes
        for r in extraction.relationship_changes:
            referenced_keys.add(r.from_entity)
            referenced_keys.add(r.to_entity)

        # From item owners
        for i in extraction.items:
            if i.owner_key:
                referenced_keys.add(i.owner_key)

        # From appointment participants
        for a in extraction.appointments:
            referenced_keys.update(a.participants)

        # Validate references (excluding newly created characters)
        new_character_keys = {c.entity_key for c in extraction.characters}
        keys_to_validate = referenced_keys - new_character_keys

        if keys_to_validate:
            result = validator.validate_entity_references(list(keys_to_validate))
            for issue in result.issues:
                validation_warnings.append(
                    f"Entity reference warning: {issue.description}"
                )
                logger.warning(
                    "Extraction references non-existent entity: %s",
                    issue.entity_key,
                )

        # Validate location references
        if extraction.location_change:
            loc_result = validator.validate_location_reference(
                extraction.location_change,
                allow_new=True,  # New locations may be discovered
            )
            for issue in loc_result.issues:
                validation_warnings.append(
                    f"Location reference warning: {issue.description}"
                )
                logger.warning(
                    "Extraction references non-existent location: %s",
                    extraction.location_change,
                )

    return {
        "extracted_entities": [
            {
                "entity_key": c.entity_key,
                "display_name": c.display_name,
                "entity_type": c.entity_type,
                "description": c.description,
                "personality_traits": c.personality_traits,
                "current_activity": c.current_activity,
                "current_location": c.current_location,
            }
            for c in extraction.characters
        ],
        "extracted_items": [
            {
                "item_key": i.item_key,
                "display_name": i.display_name,
                "item_type": i.item_type,
                "description": i.description,
                "owner_key": i.owner_key,
                "action": i.action,
            }
            for i in extraction.items
        ],
        "extracted_locations": [
            {
                "location_key": loc.location_key,
                "display_name": loc.display_name,
                "category": loc.category,
                "description": loc.description,
                "parent_location_key": loc.parent_location_key,
            }
            for loc in extraction.locations
        ],
        "extracted_facts": [
            {
                "subject": f.subject,
                "predicate": f.predicate,
                "value": f.value,
                "is_secret": f.is_secret,
            }
            for f in extraction.facts
        ],
        "relationship_changes": [
            {
                "from_entity": r.from_entity,
                "to_entity": r.to_entity,
                "dimension": r.dimension,
                "delta": r.delta,
                "reason": r.reason,
            }
            for r in extraction.relationship_changes
        ],
        "appointments": [
            {
                "description": a.description,
                "day": a.day,
                "time": a.time,
                "location_key": a.location_key,
                "participants": a.participants,
            }
            for a in extraction.appointments
        ],
        "validation_warnings": validation_warnings,
        # Propagate location from state or extraction result
        "player_location": extraction.location_change or state.get("player_location"),
        "location_changed": state.get("location_changed", False) or bool(extraction.location_change),
        "next_agent": "persistence",
    }


def _load_template() -> str:
    """Load the extraction prompt template.

    Returns:
        Template string.
    """
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text()

    # Fallback inline template
    return """Extract entities from:

## GM Response
{gm_response}

## Player Input
{player_input}

## Location
{player_location}

Return JSON matching ExtractionResult schema."""
