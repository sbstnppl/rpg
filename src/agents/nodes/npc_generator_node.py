"""NPC Generator node for creating full character data for new NPCs.

This node runs after entity extraction and before persistence.
For each newly extracted NPC, it generates comprehensive character data
including appearance, background, skills, inventory, preferences, and needs.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.llm.audit_logger import set_audit_context
from src.services.npc_generator import NPCGeneratorService


logger = logging.getLogger(__name__)


# Entity types that should receive full generation
GENERATABLE_TYPES = {"npc", "animal"}


async def npc_generator_node(state: GameState) -> dict[str, Any]:
    """Generate full character data for newly extracted NPCs.

    This node processes entities extracted by the entity_extractor_node
    and generates comprehensive character data for each new NPC.

    Args:
        state: Current game state with extracted_entities.

    Returns:
        Partial state update with generated_npcs and next_agent.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        logger.error("Missing database session or game session in state")
        return {
            "generated_npcs": [],
            "errors": ["Missing database session or game session in state"],
            "next_agent": "persistence",
        }

    # Set audit context
    session_id = state.get("session_id")
    turn_number = state.get("turn_number")
    set_audit_context(
        session_id=session_id,
        turn_number=turn_number,
        call_type="npc_generator",
    )

    # Get extracted entities that need generation
    extracted_entities = state.get("extracted_entities", [])

    entities_to_generate = [
        e for e in extracted_entities
        if e.get("entity_type") in GENERATABLE_TYPES
    ]

    if not entities_to_generate:
        logger.debug("No entities to generate")
        return {
            "generated_npcs": [],
            "next_agent": "persistence",
        }

    # Initialize generator service
    generator = NPCGeneratorService(db, game_session)
    generated_npcs: list[dict[str, Any]] = []
    errors: list[str] = []

    for entity_data in entities_to_generate:
        entity_key = entity_data.get("entity_key")
        if not entity_key:
            continue

        try:
            # Map string entity_type to enum
            entity_type_str = entity_data.get("entity_type", "npc")
            entity_type = _map_entity_type(entity_type_str)

            # Generate full NPC data
            entity = await generator.generate_npc(
                entity_key=entity_key,
                display_name=entity_data.get("display_name", entity_key),
                entity_type=entity_type,
                description=entity_data.get("description"),
                personality_traits=entity_data.get("personality_traits", []),
                current_activity=entity_data.get("current_activity"),
                current_location=entity_data.get("current_location"),
            )

            generated_npcs.append({
                "entity_key": entity.entity_key,
                "entity_id": entity.id,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type.value,
                "was_generated": True,
            })

            logger.info(f"Generated NPC: {entity_key} ({entity.display_name})")

        except Exception as e:
            error_msg = f"Failed to generate NPC {entity_key}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    result: dict[str, Any] = {
        "generated_npcs": generated_npcs,
        "next_agent": "persistence",
    }

    if errors:
        result["errors"] = errors

    return result


def _map_entity_type(type_str: str) -> EntityType:
    """Map string entity type to EntityType enum.

    Args:
        type_str: String entity type from extraction.

    Returns:
        EntityType enum value.
    """
    type_map = {
        "npc": EntityType.NPC,
        "monster": EntityType.MONSTER,
        "animal": EntityType.ANIMAL,
        "player": EntityType.PLAYER,
    }
    return type_map.get(type_str.lower(), EntityType.NPC)
