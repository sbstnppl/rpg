"""Extended world loader for NPCs, schedules, items, and facts.

This service handles loading extended world data from JSON files,
including NPCs with extensions, schedules, items, and world facts.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import (
    DayOfWeek,
    EntityType,
    FactCategory,
    ItemType,
)
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.database.models.world import Fact
from src.managers.entity_manager import EntityManager
from src.managers.fact_manager import FactManager
from src.managers.item_manager import ItemManager
from src.managers.schedule_manager import ScheduleManager
from src.schemas.world_template import (
    FactListTemplate,
    ItemListTemplate,
    NPCListTemplate,
    NPCTemplate,
    ScheduleListTemplate,
)
from src.services.world_loader import load_world_from_file


def load_complete_world(
    db: Session,
    game_session: GameSession,
    world_dir: Path,
    world_name: str,
) -> dict[str, Any]:
    """Load complete world data from directory.

    Loads zones, locations, NPCs, schedules, items, and facts.

    Expected files in world_dir:
    - {world_name}.yaml - Zones, locations, connections
    - {world_name}_npcs.json - NPC definitions
    - {world_name}_schedules.json - NPC schedules
    - {world_name}_items.json - Item definitions
    - {world_name}_facts.json - World facts

    Args:
        db: Database session.
        game_session: Current game session.
        world_dir: Directory containing world files.
        world_name: Base name for world files.

    Returns:
        Dict with counts and errors for each file type.
    """
    results = {
        "world": {},
        "npcs": {"count": 0, "errors": []},
        "schedules": {"count": 0, "errors": []},
        "items": {"count": 0, "errors": []},
        "facts": {"count": 0, "errors": []},
    }

    # 1. Load base world (zones, locations, connections)
    world_file = world_dir / f"{world_name}.yaml"
    if world_file.exists():
        try:
            results["world"] = load_world_from_file(db, game_session, world_file)
        except Exception as e:
            results["world"] = {"errors": [str(e)]}
    else:
        # Try JSON fallback
        world_file = world_dir / f"{world_name}.json"
        if world_file.exists():
            try:
                results["world"] = load_world_from_file(db, game_session, world_file)
            except Exception as e:
                results["world"] = {"errors": [str(e)]}

    db.flush()

    # 2. Load NPCs
    npcs_file = world_dir / f"{world_name}_npcs.json"
    if npcs_file.exists():
        npc_results = load_npcs_from_file(db, game_session, npcs_file)
        results["npcs"] = npc_results

    db.flush()

    # 3. Load schedules
    schedules_file = world_dir / f"{world_name}_schedules.json"
    if schedules_file.exists():
        schedule_results = load_schedules_from_file(db, game_session, schedules_file)
        results["schedules"] = schedule_results

    db.flush()

    # 4. Load items
    items_file = world_dir / f"{world_name}_items.json"
    if items_file.exists():
        item_results = load_items_from_file(db, game_session, items_file)
        results["items"] = item_results

    db.flush()

    # 5. Load facts
    facts_file = world_dir / f"{world_name}_facts.json"
    if facts_file.exists():
        fact_results = load_facts_from_file(db, game_session, facts_file)
        results["facts"] = fact_results

    db.commit()

    return results


def load_npcs_from_file(
    db: Session,
    game_session: GameSession,
    file_path: Path,
) -> dict[str, Any]:
    """Load NPCs from JSON file.

    Args:
        db: Database session.
        game_session: Current game session.
        file_path: Path to NPC JSON file.

    Returns:
        Dict with count and errors.
    """
    results = {"count": 0, "errors": [], "entity_keys": []}

    if not file_path.exists():
        results["errors"].append(f"File not found: {file_path}")
        return results

    try:
        with open(file_path) as f:
            data = json.load(f)
        template = NPCListTemplate.model_validate(data)
    except Exception as e:
        results["errors"].append(f"Failed to parse {file_path}: {e}")
        return results

    entity_manager = EntityManager(db, game_session)

    for npc_template in template.npcs:
        try:
            entity = _create_npc(db, entity_manager, npc_template)
            results["count"] += 1
            results["entity_keys"].append(entity.entity_key)
        except Exception as e:
            results["errors"].append(f"Failed to create NPC {npc_template.entity_key}: {e}")

    return results


def _create_npc(
    db: Session,
    entity_manager: EntityManager,
    template: NPCTemplate,
) -> Entity:
    """Create an NPC entity from template."""
    # Parse entity type
    entity_type = _parse_entity_type(template.entity_type)

    # Build entity kwargs
    entity_kwargs = {}

    # Appearance fields
    appearance_fields = [
        "age", "age_apparent", "gender", "height", "build",
        "hair_color", "hair_style", "eye_color", "skin_tone",
        "species", "distinguishing_features", "voice_description",
    ]
    for field in appearance_fields:
        value = getattr(template, field, None)
        if value is not None:
            entity_kwargs[field] = value

    # Background fields
    if template.occupation:
        entity_kwargs["occupation"] = template.occupation
    if template.occupation_years:
        entity_kwargs["occupation_years"] = template.occupation_years
    if template.background:
        entity_kwargs["background"] = template.background
    if template.personality_notes:
        entity_kwargs["personality_notes"] = template.personality_notes
    if template.hidden_backstory:
        entity_kwargs["hidden_backstory"] = template.hidden_backstory

    # Create entity
    entity = entity_manager.create_entity(
        entity_key=template.entity_key,
        display_name=template.display_name,
        entity_type=entity_type,
        **entity_kwargs,
    )

    # Create NPC extension if provided
    if template.npc_extension:
        ext = template.npc_extension
        npc_ext = NPCExtension(
            entity_id=entity.id,
            job=ext.job,
            workplace=ext.workplace,
            home_location=ext.home_location,
            hobbies=ext.hobbies,
            speech_pattern=ext.speech_pattern,
            personality_traits=ext.personality_traits,
            dark_secret=ext.dark_secret,
            hidden_goal=ext.hidden_goal,
            betrayal_conditions=ext.betrayal_conditions,
        )
        db.add(npc_ext)

    # Store knowledge areas in appearance JSON as extension data
    if template.knowledge_areas:
        if entity.appearance is None:
            entity.appearance = {}
        entity.appearance["knowledge_areas"] = {
            key: {
                "description": area.description,
                "disclosure_threshold": area.disclosure_threshold,
                "sample_content": area.sample_content,
            }
            for key, area in template.knowledge_areas.items()
        }

    db.flush()
    return entity


def load_schedules_from_file(
    db: Session,
    game_session: GameSession,
    file_path: Path,
) -> dict[str, Any]:
    """Load NPC schedules from JSON file.

    Args:
        db: Database session.
        game_session: Current game session.
        file_path: Path to schedule JSON file.

    Returns:
        Dict with count and errors.
    """
    results = {"count": 0, "errors": []}

    if not file_path.exists():
        results["errors"].append(f"File not found: {file_path}")
        return results

    try:
        with open(file_path) as f:
            data = json.load(f)
        template = ScheduleListTemplate.model_validate(data)
    except Exception as e:
        results["errors"].append(f"Failed to parse {file_path}: {e}")
        return results

    schedule_manager = ScheduleManager(db, game_session)

    for npc_schedule in template.schedules:
        # Find entity by key
        entity = (
            db.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_key == npc_schedule.entity_key,
            )
            .first()
        )

        if not entity:
            results["errors"].append(
                f"Entity not found for schedule: {npc_schedule.entity_key}"
            )
            continue

        for entry in npc_schedule.entries:
            try:
                day_pattern = _parse_day_pattern(entry.day_pattern)
                schedule_manager.set_schedule_entry(
                    entity_id=entity.id,
                    day_pattern=day_pattern,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    activity=entry.activity,
                    location_key=entry.location_key,
                    priority=entry.priority,
                )
                results["count"] += 1
            except Exception as e:
                results["errors"].append(
                    f"Failed to create schedule for {npc_schedule.entity_key}: {e}"
                )

    return results


def load_items_from_file(
    db: Session,
    game_session: GameSession,
    file_path: Path,
) -> dict[str, Any]:
    """Load items from JSON file.

    Args:
        db: Database session.
        game_session: Current game session.
        file_path: Path to item JSON file.

    Returns:
        Dict with count and errors.
    """
    results = {"count": 0, "errors": [], "item_keys": []}

    if not file_path.exists():
        results["errors"].append(f"File not found: {file_path}")
        return results

    try:
        with open(file_path) as f:
            data = json.load(f)
        template = ItemListTemplate.model_validate(data)
    except Exception as e:
        results["errors"].append(f"Failed to parse {file_path}: {e}")
        return results

    item_manager = ItemManager(db, game_session)

    for item_template in template.items:
        try:
            item = _create_item(db, game_session, item_manager, item_template)
            results["count"] += 1
            results["item_keys"].append(item.item_key)
        except Exception as e:
            results["errors"].append(f"Failed to create item {item_template.item_key}: {e}")

    return results


def _create_item(
    db: Session,
    game_session: GameSession,
    item_manager: ItemManager,
    template,
) -> Item:
    """Create an item from template."""
    # Parse item type
    item_type = _parse_item_type(template.item_type)

    # Build kwargs
    item_kwargs = {}

    if template.description:
        item_kwargs["description"] = template.description
    if template.body_slot:
        item_kwargs["body_slot"] = template.body_slot
    if template.body_layer is not None:
        item_kwargs["body_layer"] = template.body_layer
    if template.properties:
        item_kwargs["properties"] = template.properties

    # Resolve owner entity
    owner_id = None
    if template.owner_entity_key:
        owner = (
            db.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_key == template.owner_entity_key,
            )
            .first()
        )
        if owner:
            owner_id = owner.id

    # Resolve holder entity
    holder_id = None
    if template.holder_entity_key:
        holder = (
            db.query(Entity)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_key == template.holder_entity_key,
            )
            .first()
        )
        if holder:
            holder_id = holder.id
            item_kwargs["holder_id"] = holder_id

    # Create item
    item = item_manager.create_item(
        item_key=template.item_key,
        display_name=template.display_name,
        item_type=item_type,
        owner_id=owner_id,
        **item_kwargs,
    )

    # Store location info in notes if provided
    if template.location_key or template.location_description:
        notes_parts = []
        if template.location_key:
            notes_parts.append(f"Found at: {template.location_key}")
        if template.location_description:
            notes_parts.append(f"Specifically: {template.location_description}")
        item.notes = " | ".join(notes_parts)

    return item


def load_facts_from_file(
    db: Session,
    game_session: GameSession,
    file_path: Path,
) -> dict[str, Any]:
    """Load world facts from JSON file.

    Args:
        db: Database session.
        game_session: Current game session.
        file_path: Path to fact JSON file.

    Returns:
        Dict with count and errors.
    """
    results = {"count": 0, "errors": []}

    if not file_path.exists():
        results["errors"].append(f"File not found: {file_path}")
        return results

    try:
        with open(file_path) as f:
            data = json.load(f)
        template = FactListTemplate.model_validate(data)
    except Exception as e:
        results["errors"].append(f"Failed to parse {file_path}: {e}")
        return results

    fact_manager = FactManager(db, game_session)

    for fact_template in template.facts:
        try:
            _create_fact(fact_manager, fact_template)
            results["count"] += 1
        except Exception as e:
            results["errors"].append(
                f"Failed to create fact {fact_template.subject_key}.{fact_template.predicate}: {e}"
            )

    return results


def _create_fact(
    fact_manager: FactManager,
    template,
) -> Fact:
    """Create a fact from template."""
    # Parse category
    category = _parse_fact_category(template.category)

    # Use record_fact for basic facts
    fact = fact_manager.record_fact(
        subject_type=template.subject_type,
        subject_key=template.subject_key,
        predicate=template.predicate,
        value=template.value,
        category=category,
        is_secret=template.is_secret,
        confidence=template.confidence,
    )

    # Add additional fields
    if template.player_believes:
        fact.player_believes = template.player_believes
    if template.is_foreshadowing:
        fact.is_foreshadowing = True
        fact.foreshadow_target = template.foreshadow_target
        fact.times_mentioned = template.times_mentioned

    return fact


# =============================================================================
# Enum parsing helpers
# =============================================================================


def _parse_entity_type(value: str) -> EntityType:
    """Parse entity type string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        "player": EntityType.PLAYER,
        "npc": EntityType.NPC,
        "monster": EntityType.MONSTER,
        "animal": EntityType.ANIMAL,
    }
    return mapping.get(value_lower, EntityType.NPC)


def _parse_day_pattern(value: str) -> DayOfWeek:
    """Parse day pattern string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        "monday": DayOfWeek.MONDAY,
        "tuesday": DayOfWeek.TUESDAY,
        "wednesday": DayOfWeek.WEDNESDAY,
        "thursday": DayOfWeek.THURSDAY,
        "friday": DayOfWeek.FRIDAY,
        "saturday": DayOfWeek.SATURDAY,
        "sunday": DayOfWeek.SUNDAY,
        "weekday": DayOfWeek.WEEKDAY,
        "weekend": DayOfWeek.WEEKEND,
        "daily": DayOfWeek.DAILY,
    }
    return mapping.get(value_lower, DayOfWeek.DAILY)


def _parse_item_type(value: str) -> ItemType:
    """Parse item type string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        "weapon": ItemType.WEAPON,
        "armor": ItemType.ARMOR,
        "accessory": ItemType.ACCESSORY,
        "consumable": ItemType.CONSUMABLE,
        "tool": ItemType.TOOL,
        "container": ItemType.CONTAINER,
        "clothing": ItemType.CLOTHING,
        "equipment": ItemType.EQUIPMENT,
        "misc": ItemType.MISC,
        # Common aliases
        "key": ItemType.MISC,  # Keys are misc items with properties
        "book": ItemType.MISC,  # Books are misc items
        "currency": ItemType.MISC,  # Currency is misc items
    }
    return mapping.get(value_lower, ItemType.MISC)


def _parse_fact_category(value: str) -> FactCategory:
    """Parse fact category string to enum."""
    value_lower = value.lower().strip()
    mapping = {
        "personal": FactCategory.PERSONAL,
        "secret": FactCategory.SECRET,
        "preference": FactCategory.PREFERENCE,
        "skill": FactCategory.SKILL,
        "history": FactCategory.HISTORY,
        "relationship": FactCategory.RELATIONSHIP,
        "location": FactCategory.LOCATION,
        "world": FactCategory.WORLD,
    }
    return mapping.get(value_lower, FactCategory.WORLD)
