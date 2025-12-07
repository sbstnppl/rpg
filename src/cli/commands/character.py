"""Character-related commands."""

import json
import random
import re
import unicodedata
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from sqlalchemy.orm import Session

from src.cli.display import (
    display_ai_message,
    display_attribute_table,
    display_character_status,
    display_character_summary,
    display_dice_roll,
    display_error,
    display_info,
    display_inventory,
    display_point_buy_status,
    display_starting_equipment,
    display_success,
    display_suggested_attributes,
    prompt_ai_input,
    prompt_background,
    prompt_character_name,
)
from src.cli.commands.session import get_db_session
from src.database.models.character_state import (
    CharacterNeeds,
    IntimacyProfile,
    DriveLevel,
    IntimacyStyle,
)
from src.database.models.entities import Entity, EntityAttribute
from src.database.models.enums import EntityType, VitalStatus
from src.database.models.items import Item
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession
from src.database.models.vital_state import EntityVitalState
from src.managers.entity_manager import EntityManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from src.schemas.settings import (
    SettingSchema,
    get_setting_schema,
    roll_all_attributes,
    validate_point_buy,
    calculate_point_cost,
)

app = typer.Typer(help="Character commands")
console = Console()


def _get_active_session(db) -> GameSession | None:
    """Get the most recent active session."""
    return (
        db.query(GameSession)
        .filter(GameSession.status == "active")
        .order_by(GameSession.id.desc())
        .first()
    )


def _get_player(db, game_session: GameSession) -> Entity | None:
    """Get the player entity for a session."""
    return (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )


@app.command()
def status(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show player character status."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            display_info("Use 'rpg session start' to create one")
            raise typer.Exit(1)

        player = _get_player(db, game_session)

        if not player:
            display_error("No player character found")
            display_info("Character creation not yet implemented")
            raise typer.Exit(1)

        # Get stats from entity attributes relationship
        stats = {}
        if player.attributes:
            for attr in player.attributes:
                stats[attr.attribute_key.replace("_", " ").title()] = attr.value

        # Get needs
        needs = None
        needs_manager = NeedsManager(db, game_session)
        needs_state = needs_manager.get_needs(player.id)
        if needs_state:
            needs = {
                "Hunger": int(needs_state.hunger),
                "Fatigue": int(needs_state.fatigue),
                "Hygiene": int(needs_state.hygiene),
                "Morale": int(needs_state.morale),
            }

        # Get conditions (placeholder)
        conditions = []
        if not player.is_alive:
            conditions.append("Dead")

        display_character_status(
            name=player.display_name,
            stats=stats,
            needs=needs,
            conditions=conditions if conditions else None,
        )

    finally:
        db.close()


@app.command()
def inventory(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show player inventory."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        player = _get_player(db, game_session)

        if not player:
            display_error("No player character found")
            raise typer.Exit(1)

        # Get items owned by player
        items = (
            db.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.owner_id == player.id,
            )
            .all()
        )

        item_dicts = [
            {
                "name": item.display_name,
                "type": item.item_type.value if item.item_type else "misc",
                "equipped": item.body_slot is not None,
                "slot": item.body_slot,
                "condition": item.condition.value if item.condition else "good",
            }
            for item in items
        ]

        display_inventory(item_dicts)

    finally:
        db.close()


@app.command()
def equipment(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show equipped items."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        player = _get_player(db, game_session)

        if not player:
            display_error("No player character found")
            raise typer.Exit(1)

        # Get equipped items (items with a body_slot are equipped)
        items = (
            db.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.holder_id == player.id,
                Item.body_slot.isnot(None),
            )
            .all()
        )

        if not items:
            display_info("No items equipped")
            return

        item_dicts = [
            {
                "name": item.display_name,
                "type": item.item_type.value if item.item_type else "misc",
                "equipped": True,
                "slot": item.body_slot,
                "layer": item.body_layer,
                "visible": item.is_visible,
                "condition": item.condition.value if item.condition else "good",
            }
            for item in items
        ]

        display_inventory(item_dicts)

    finally:
        db.close()


@app.command()
def outfit(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show current outfit with layers and visibility.

    Displays all equipped items organized by body slot, showing:
    - Layer ordering (innermost to outermost)
    - Visibility status (hidden items are dimmed)
    - Bonus slots provided by worn items (e.g., belt provides pouch slots)
    """
    from rich.panel import Panel
    from rich.text import Text

    from src.managers.item_manager import ItemManager, BODY_SLOTS

    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        player = _get_player(db, game_session)

        if not player:
            display_error("No player character found")
            raise typer.Exit(1)

        item_manager = ItemManager(db, game_session)
        outfit_by_slot = item_manager.get_outfit_by_slot(player.id)
        available_slots = item_manager.get_available_slots(player.id)

        if not outfit_by_slot:
            display_info("No items equipped")
            return

        # Build outfit display
        output = Text()

        # Define slot display order
        slot_order = [
            "head", "face", "ear_left", "ear_right",
            "neck", "torso", "full_body", "legs",
            "back", "waist",
            "forearm_left", "forearm_right",
            "hand_left", "hand_right", "main_hand", "off_hand",
            "thumb_left", "index_left", "middle_left", "ring_left", "pinky_left",
            "thumb_right", "index_right", "middle_right", "ring_right", "pinky_right",
            "feet_socks", "feet_shoes",
        ]

        # Add bonus slots at the end
        bonus_slots = [s for s in available_slots if s not in BODY_SLOTS]
        slot_order.extend(sorted(bonus_slots))

        visible_items = []

        for slot in slot_order:
            if slot not in outfit_by_slot:
                continue

            items = outfit_by_slot[slot]
            slot_info = available_slots.get(slot, {})
            display_name = slot_info.get("desc", slot.replace("_", " ").title())

            output.append(f"\n{slot.replace('_', ' ').title()}:\n", style="bold cyan")

            for item in items:
                layer_str = f"  L{item.body_layer}: "
                if item.is_visible:
                    output.append(layer_str)
                    output.append(f"{item.display_name}\n", style="white")
                    visible_items.append(item.display_name)
                else:
                    output.append(layer_str, style="dim")
                    output.append(f"{item.display_name} (hidden)\n", style="dim")

            # Show if this item provides slots
            for item in items:
                if item.provides_slots:
                    slots_str = ", ".join(item.provides_slots)
                    output.append(f"  → Provides: {slots_str}\n", style="yellow")

        console.print(Panel(output, title="[bold cyan]Outfit[/bold cyan]", border_style="cyan"))

        # Show visible summary
        if visible_items:
            console.print(f"\n[bold]Visible:[/bold] {', '.join(visible_items)}")

    finally:
        db.close()


def slugify(name: str) -> str:
    """Convert a name to a valid entity_key.

    Args:
        name: Character name.

    Returns:
        Lowercase key with underscores.
    """
    # Normalize unicode (é -> e)
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase and replace non-alphanumeric with spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", ascii_name.lower())

    # Collapse multiple spaces and convert to underscores
    return re.sub(r"\s+", "_", cleaned.strip())


def _create_character_records(
    db: Session,
    game_session: GameSession,
    name: str,
    attributes: dict[str, int],
    background: str = "",
) -> Entity:
    """Create all database records for a new character.

    Args:
        db: Database session.
        game_session: Game session.
        name: Character display name.
        attributes: Dict of attribute_key to value.
        background: Optional background text.

    Returns:
        Created Entity.

    Raises:
        ValueError: If session already has a player.
    """
    # Check for existing player
    existing = (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )
    if existing:
        raise ValueError(f"Session already has a player: {existing.display_name}")

    # Create entity
    entity = Entity(
        session_id=game_session.id,
        entity_key=slugify(name),
        display_name=name,
        entity_type=EntityType.PLAYER,
        is_alive=True,
        is_active=True,
        background=background or None,
    )
    db.add(entity)
    db.flush()

    # Create attributes
    for attr_key, value in attributes.items():
        attr = EntityAttribute(
            entity_id=entity.id,
            attribute_key=attr_key,
            value=value,
            temporary_modifier=0,
        )
        db.add(attr)

    # Create character needs with defaults
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=80,
        fatigue=20,
        hygiene=80,
        comfort=70,
        pain=0,
        social_connection=50,
        morale=70,
        sense_of_purpose=60,
        intimacy=20,
    )
    db.add(needs)

    # Create vital state
    vital = EntityVitalState(
        session_id=game_session.id,
        entity_id=entity.id,
        vital_status=VitalStatus.HEALTHY,
        death_saves_remaining=3,
        death_saves_failed=0,
        is_dead=False,
        has_been_revived=False,
        revival_count=0,
    )
    db.add(vital)

    db.flush()
    return entity


def _create_starting_equipment(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    schema: SettingSchema,
) -> list:
    """Create starting equipment for a new character.

    Args:
        db: Database session.
        game_session: Game session.
        entity: The player entity.
        schema: Setting schema with starting equipment definitions.

    Returns:
        List of created Item objects.
    """
    from src.database.models.enums import ItemType, ItemCondition
    from src.managers.item_manager import ItemManager

    if not schema.starting_equipment:
        return []

    item_manager = ItemManager(db, game_session)
    created_items = []

    for equip in schema.starting_equipment:
        # Map string to ItemType enum
        try:
            item_type = ItemType(equip.item_type)
        except ValueError:
            item_type = ItemType.MISC

        # Create unique key for this player
        unique_key = f"{entity.entity_key}_{equip.item_key}"

        item = item_manager.create_item(
            item_key=unique_key,
            display_name=equip.display_name,
            item_type=item_type,
            owner_id=entity.id,
            holder_id=entity.id,
            description=equip.description or None,
            properties=equip.properties,
            condition=ItemCondition.GOOD,
        )

        # Equip if body_slot specified
        if equip.body_slot:
            item_manager.equip_item(
                unique_key,
                entity.id,
                body_slot=equip.body_slot,
                body_layer=equip.body_layer,
            )

        created_items.append(item)

    # Update visibility for equipped items
    item_manager.update_visibility(entity.id)

    return created_items


def _point_buy_interactive(schema) -> dict[str, int]:
    """Interactive point-buy attribute allocation.

    Args:
        schema: SettingSchema with attributes.

    Returns:
        Dict of attribute_key to value.
    """
    attributes = {attr.key: 8 for attr in schema.attributes}
    total_points = schema.point_buy_total

    console.print("\n[bold]Point-Buy Attribute Allocation[/bold]")
    console.print(f"You have {total_points} points to distribute.")
    console.print("Each attribute starts at 8. Values must be 8-15.")
    console.print("Costs: 8=0, 9=1, 10=2, 11=3, 12=4, 13=5, 14=7, 15=9\n")

    while True:
        # Show current state
        display_attribute_table(attributes, show_modifiers=True)
        used = sum(calculate_point_cost(v) for v in attributes.values())
        display_point_buy_status(used, total_points)

        # Check if valid
        is_valid, _ = validate_point_buy(attributes, total_points)

        console.print("\nCommands: [attr] [value] (e.g., 'str 14'), 'done', 'reset'")
        cmd = console.input("[bold cyan]> [/bold cyan]").strip().lower()

        if cmd == "done":
            if is_valid:
                return attributes
            console.print("[red]Invalid allocation. Adjust your attributes.[/red]")
            continue

        if cmd == "reset":
            attributes = {attr.key: 8 for attr in schema.attributes}
            continue

        # Parse attribute change
        parts = cmd.split()
        if len(parts) != 2:
            console.print("[red]Use: [attr] [value], e.g., 'str 14'[/red]")
            continue

        attr_input, value_str = parts

        # Find matching attribute
        attr_key = None
        for attr in schema.attributes:
            if attr.key.startswith(attr_input) or attr.display_name.lower().startswith(attr_input):
                attr_key = attr.key
                break

        if not attr_key:
            console.print(f"[red]Unknown attribute: {attr_input}[/red]")
            continue

        try:
            value = int(value_str)
            if value < 8 or value > 15:
                console.print("[red]Value must be 8-15[/red]")
                continue
            attributes[attr_key] = value
        except ValueError:
            console.print("[red]Invalid value[/red]")


def _roll_attributes_interactive() -> dict[str, int]:
    """Roll attributes using 4d6-drop-lowest.

    Returns:
        Dict of attribute_key to value.
    """
    console.print("\n[bold]Rolling Attributes (4d6 drop lowest)[/bold]\n")

    attributes = {}
    for attr_key in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
        # Roll 4d6
        rolls = [random.randint(1, 6) for _ in range(4)]
        rolls_sorted = sorted(rolls)
        dropped = rolls_sorted[0]
        total = sum(rolls_sorted[1:])

        display_dice_roll(attr_key, rolls, dropped, total)
        attributes[attr_key] = total

    console.print()
    return attributes


def _load_character_creator_template() -> str:
    """Load the character creator prompt template.

    Returns:
        Template string.
    """
    template_path = Path(__file__).parent.parent.parent.parent / "data" / "templates" / "character_creator.md"
    if template_path.exists():
        return template_path.read_text()
    return ""


def _load_world_extraction_template() -> str:
    """Load the world extraction prompt template.

    Returns:
        Template string.
    """
    template_path = Path(__file__).parent.parent.parent.parent / "data" / "templates" / "world_extraction.md"
    if template_path.exists():
        return template_path.read_text()
    return ""


async def _extract_world_data(
    character_output: str,
    character_name: str,
    character_background: str,
    setting_name: str,
) -> dict | None:
    """Extract world data from character creation output using LLM.

    Args:
        character_output: Full conversation from character creation.
        character_name: Character's name.
        character_background: Character's background story.
        setting_name: Game setting name.

    Returns:
        Extracted world data dict or None if extraction fails.
    """
    try:
        from src.llm.factory import get_extraction_provider
        from src.llm.message_types import Message, MessageRole
    except ImportError:
        return None

    template = _load_world_extraction_template()
    if not template:
        return None

    prompt = template.format(
        character_output=character_output,
        character_name=character_name,
        character_background=character_background,
        setting_name=setting_name,
    )

    try:
        provider = get_extraction_provider()
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await provider.complete(messages)

        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response.content)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        console.print(f"[dim]World extraction warning: {e}[/dim]")

    return None


def _create_world_from_extraction(
    db: Session,
    game_session: GameSession,
    player: Entity,
    world_data: dict,
) -> None:
    """Create shadow entities and relationships from extracted world data.

    Args:
        db: Database session.
        game_session: Game session.
        player: Player entity.
        world_data: Extracted world data dict.
    """
    entity_manager = EntityManager(db, game_session)
    relationship_manager = RelationshipManager(db, game_session)

    # Update player appearance from extraction
    player_appearance = world_data.get("player_appearance", {})
    if player_appearance:
        for field, value in player_appearance.items():
            if value is not None and field in Entity.APPEARANCE_FIELDS:
                player.set_appearance_field(field, value)

    # Create shadow entities from backstory
    shadow_entities = world_data.get("shadow_entities", [])
    created_entities = {}

    for shadow in shadow_entities:
        entity_key = shadow.get("entity_key")
        if not entity_key:
            continue

        # Map entity type string to enum
        entity_type_str = shadow.get("entity_type", "npc").upper()
        try:
            entity_type = EntityType[entity_type_str]
        except KeyError:
            entity_type = EntityType.NPC

        # Create the shadow entity
        entity = entity_manager.create_shadow_entity(
            entity_key=entity_key,
            display_name=shadow.get("display_name", entity_key.replace("_", " ").title()),
            entity_type=entity_type,
            background=shadow.get("brief_description"),
        )

        # Mark as alive or dead
        if not shadow.get("is_alive", True):
            entity.is_alive = False

        created_entities[entity_key] = entity

        # Create bidirectional relationship with player
        rel_type = shadow.get("relationship_to_player", "acquaintance")
        trust = shadow.get("trust", 50)
        liking = shadow.get("liking", 50)
        respect = shadow.get("respect", 50)

        # Player's relationship TO the shadow entity
        player_rel = Relationship(
            session_id=game_session.id,
            from_entity_id=player.id,
            to_entity_id=entity.id,
            knows=True,  # Player knows them from backstory
            trust=trust,
            liking=liking,
            respect=respect,
            familiarity=80 if rel_type == "family" else 60 if rel_type == "friend" else 30,
            relationship_type=rel_type,
        )
        db.add(player_rel)

        # Shadow entity's relationship TO player
        shadow_rel = Relationship(
            session_id=game_session.id,
            from_entity_id=entity.id,
            to_entity_id=player.id,
            knows=True,
            trust=trust,
            liking=liking,
            respect=respect,
            familiarity=80 if rel_type == "family" else 60 if rel_type == "friend" else 30,
            relationship_type=rel_type,
        )
        db.add(shadow_rel)

    db.flush()

    # Log results
    if created_entities:
        console.print(f"[dim]Created {len(created_entities)} backstory connections[/dim]")


def _create_intimacy_profile(
    db: Session,
    game_session: GameSession,
    entity: Entity,
) -> IntimacyProfile:
    """Create intimacy profile with default values.

    Args:
        db: Database session.
        game_session: Game session.
        entity: The entity to create profile for.

    Returns:
        Created IntimacyProfile.
    """
    profile = IntimacyProfile(
        session_id=game_session.id,
        entity_id=entity.id,
        drive_level=DriveLevel.MODERATE,
        drive_threshold=50,
        intimacy_style=IntimacyStyle.EMOTIONAL,
        has_regular_partner=False,
        is_actively_seeking=False,
    )
    db.add(profile)
    db.flush()
    return profile


def _parse_attribute_suggestion(response: str) -> dict[str, int] | None:
    """Extract suggested attributes from LLM response.

    Args:
        response: LLM response text.

    Returns:
        Dict of attribute_key to value, or None if not found.
    """
    # Look for JSON block with suggested_attributes
    try:
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*"suggested_attributes"[^{}]*\{[^{}]*\}[^{}]*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return data.get("suggested_attributes")

        # Try simpler JSON with just attributes
        json_match = re.search(r'\{[^{}]*"[a-z]+"\s*:\s*\d+[^{}]*\}', response, re.DOTALL)
        if json_match:
            # Could be direct attributes
            data = json.loads(json_match.group())
            # Check if it looks like attributes (has expected keys)
            if any(k in data for k in ["strength", "dexterity", "intelligence", "physical", "reflexes"]):
                return data

    except json.JSONDecodeError:
        pass

    return None


def _parse_character_complete(response: str) -> dict | None:
    """Check if character creation is complete.

    Args:
        response: LLM response text.

    Returns:
        Dict with name, attributes, background if complete, else None.
    """
    try:
        json_match = re.search(r'\{[^{}]*"character_complete"[^{}]*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            if data.get("character_complete"):
                return data
    except json.JSONDecodeError:
        pass
    return None


def _strip_json_blocks(text: str) -> str:
    """Remove JSON blocks from AI response before displaying to user.

    Strips both markdown code blocks containing JSON and inline JSON blocks
    that are meant for machine parsing, not human reading.

    Args:
        text: AI response text that may contain JSON blocks.

    Returns:
        Text with JSON blocks removed.
    """
    # Strip markdown code blocks containing JSON (```json ... ```)
    text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text)
    # Strip inline JSON blocks with our special keys
    text = re.sub(r'\{[^{}]*"suggested_attributes"[^{}]*\{[^{}]*\}[^{}]*\}', '', text)
    text = re.sub(r'\{[^{}]*"character_complete"[^{}]*\}', '', text)
    # Clean up extra whitespace left behind
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _validate_ai_attributes(
    attributes: dict[str, int],
    schema: SettingSchema,
) -> tuple[bool, str | None]:
    """Validate AI-suggested attributes against point-buy rules.

    Args:
        attributes: Suggested attributes.
        schema: Setting schema with rules.

    Returns:
        Tuple of (is_valid, error_message or None).
    """
    # Check all required attributes are present
    required_keys = {attr.key for attr in schema.attributes}
    provided_keys = set(attributes.keys())

    if required_keys != provided_keys:
        missing = required_keys - provided_keys
        extra = provided_keys - required_keys
        errors = []
        if missing:
            errors.append(f"Missing: {missing}")
        if extra:
            errors.append(f"Extra: {extra}")
        return False, ", ".join(errors)

    # Validate point-buy
    return validate_point_buy(attributes, schema.point_buy_total)


def _ai_character_creation(
    schema: SettingSchema,
) -> tuple[str, dict[str, int], str, str]:
    """Run AI-assisted character creation.

    Args:
        schema: Setting schema.

    Returns:
        Tuple of (name, attributes, background, conversation_history).

    Raises:
        typer.Exit: If creation is cancelled.
    """
    import asyncio
    return asyncio.run(_ai_character_creation_async(schema))


async def _ai_character_creation_async(
    schema: SettingSchema,
) -> tuple[str, dict[str, int], str, str]:
    """Async implementation of AI-assisted character creation.

    Args:
        schema: Setting schema.

    Returns:
        Tuple of (name, attributes, background, conversation_history).

    Raises:
        typer.Exit: If creation is cancelled.
    """
    try:
        from src.llm.factory import get_cheap_provider
    except ImportError:
        display_error("LLM providers not available. Use standard creation instead.")
        raise typer.Exit(1)

    provider = get_cheap_provider()

    # Prepare context
    template = _load_character_creator_template()
    attributes_list = "\n".join(
        f"- {attr.display_name} ({attr.key}): {attr.description}"
        for attr in schema.attributes
    )

    conversation_history = []
    stage = "concept"
    stage_descriptions = {
        "concept": "Ask about their character concept and playstyle",
        "name": "Help choose a fitting character name",
        "attributes": "Suggest attribute allocation based on concept",
        "background": "Develop the character's backstory",
        "review": "Confirm the final character",
    }

    # Collected data
    character_name = ""
    character_attributes: dict[str, int] = {}
    character_background = ""

    console.print("\n[bold magenta]═══ AI-Assisted Character Creation ═══[/bold magenta]\n")
    console.print("[dim]Chat with the AI to create your character. Type 'quit' to cancel.[/dim]\n")

    # Initial greeting
    initial_prompt = f"""You are starting a character creation session.

Setting: {schema.name}
Attributes available: {attributes_list}
Point-buy rules: {schema.point_buy_total} points, values {schema.point_buy_min}-{schema.point_buy_max}

Start by greeting the player and asking what kind of character they want to create."""

    try:
        from src.llm.message_types import Message, MessageRole

        messages = [Message(role=MessageRole.USER, content=initial_prompt)]
        response = await provider.complete(messages)
        display_ai_message(response.content)
        conversation_history.append(f"Assistant: {response.content}")

    except Exception as e:
        display_error(f"Failed to connect to AI: {e}")
        display_info("Falling back to standard character creation...")
        raise typer.Exit(1)

    # Conversation loop
    max_turns = 20
    for turn in range(max_turns):
        player_input = prompt_ai_input()

        if player_input.lower() in ("quit", "exit", "cancel"):
            display_info("Character creation cancelled.")
            raise typer.Exit(0)

        conversation_history.append(f"Player: {player_input}")

        # Build prompt
        prompt = template.format(
            setting_name=schema.name,
            setting_description=f"{schema.name.title()} setting",
            attributes_list=attributes_list,
            point_buy_total=schema.point_buy_total,
            point_buy_min=schema.point_buy_min,
            point_buy_max=schema.point_buy_max,
            conversation_history="\n".join(conversation_history[-10:]),  # Last 10 messages
            stage=stage,
            stage_description=stage_descriptions.get(stage, ""),
            player_input=player_input,
        )

        try:
            messages = [Message(role=MessageRole.USER, content=prompt)]
            response = await provider.complete(messages)
            ai_response = response.content

            conversation_history.append(f"Assistant: {ai_response}")

            # Check for suggested attributes
            suggested = _parse_attribute_suggestion(ai_response)
            if suggested:
                is_valid, error = _validate_ai_attributes(suggested, schema)
                if is_valid:
                    character_attributes = suggested
                    display_ai_message(_strip_json_blocks(ai_response))
                    display_suggested_attributes(suggested)
                    stage = "background" if character_name else "name"
                else:
                    display_ai_message(_strip_json_blocks(ai_response))
                    console.print(f"[yellow]Note: Suggested attributes invalid: {error}[/yellow]")
            else:
                display_ai_message(_strip_json_blocks(ai_response))

            # Check for completion
            complete = _parse_character_complete(ai_response)
            if complete:
                character_name = complete.get("name", character_name)
                if "attributes" in complete:
                    character_attributes = complete["attributes"]
                character_background = complete.get("background", character_background)

                # Validate and confirm
                if character_name and character_attributes:
                    console.print("\n[bold green]Character creation complete![/bold green]\n")
                    display_character_summary(character_name, character_attributes, character_background)

                    confirm = console.input("\n[bold cyan]Create this character? (y/n): [/bold cyan]").strip().lower()
                    if confirm in ("y", "yes"):
                        history_text = "\n".join(conversation_history)
                        return character_name, character_attributes, character_background, history_text
                    else:
                        console.print("[dim]Let's continue refining...[/dim]")
                        stage = "concept"

            # Detect name if mentioned
            if not character_name and "name" in player_input.lower():
                # Try to extract a name from the conversation
                name_match = re.search(r'(?:name is|called|named)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', player_input)
                if name_match:
                    character_name = name_match.group(1)
                    stage = "attributes" if not character_attributes else "background"

        except Exception as e:
            display_error(f"AI error: {e}")
            continue

    # If we reach max turns, offer manual completion
    display_info("Let's wrap up character creation.")

    if not character_name:
        character_name = prompt_character_name()

    if not character_attributes:
        console.print("\n[dim]Falling back to point-buy for attributes...[/dim]")
        character_attributes = _point_buy_interactive(schema)

    if not character_background:
        character_background = prompt_background()

    history_text = "\n".join(conversation_history)
    return character_name, character_attributes, character_background, history_text


@app.command()
def create(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    random_stats: bool = typer.Option(False, "--random", "-r", help="Use random 4d6 drop lowest"),
    ai_assisted: bool = typer.Option(False, "--ai", "-a", help="Use AI-assisted character creation"),
) -> None:
    """Create a new player character (interactive).

    Use --ai for conversational AI-assisted creation, or --random for dice rolls.
    """
    db = get_db_session()

    try:
        # Get session
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            display_info("Use 'rpg session start' to create one first")
            raise typer.Exit(1)

        # Check for existing player
        existing = _get_player(db, game_session)
        if existing:
            display_error(f"Session already has a character: {existing.display_name}")
            display_info("Use 'rpg character status' to view your character")
            raise typer.Exit(1)

        # Get attributes from schema
        schema = get_setting_schema(game_session.setting)

        # Track conversation history for world extraction (AI mode only)
        conversation_history = ""

        if ai_assisted:
            # AI-assisted character creation
            name, attributes, background, conversation_history = _ai_character_creation(schema)
        elif random_stats:
            console.print("\n[bold cyan]═══ Character Creation ═══[/bold cyan]\n")
            name = prompt_character_name()

            attributes = _roll_attributes_interactive()
            display_attribute_table(attributes)

            # Confirm or reroll
            while True:
                choice = console.input("\n[bold cyan]Keep these stats? (y/n): [/bold cyan]").strip().lower()
                if choice in ("y", "yes"):
                    break
                elif choice in ("n", "no"):
                    attributes = _roll_attributes_interactive()
                    display_attribute_table(attributes)

            background = prompt_background()
        else:
            # Standard point-buy
            console.print("\n[bold cyan]═══ Character Creation ═══[/bold cyan]\n")
            name = prompt_character_name()
            attributes = _point_buy_interactive(schema)
            background = prompt_background()

        # Create character
        try:
            entity = _create_character_records(
                db=db,
                game_session=game_session,
                name=name,
                attributes=attributes,
                background=background,
            )

            # Create starting equipment
            starting_items = _create_starting_equipment(
                db=db,
                game_session=game_session,
                entity=entity,
                schema=schema,
            )

            # Create intimacy profile with defaults
            _create_intimacy_profile(db, game_session, entity)

            # If AI-assisted, extract world data and create shadow entities
            if ai_assisted and conversation_history:
                import asyncio
                console.print("[dim]Extracting world from backstory...[/dim]")
                world_data = asyncio.run(_extract_world_data(
                    character_output=conversation_history,
                    character_name=name,
                    character_background=background,
                    setting_name=game_session.setting,
                ))
                if world_data:
                    _create_world_from_extraction(db, game_session, entity, world_data)

            db.commit()

            console.print()
            display_success(f"Character '{name}' created successfully!")

            # Display starting equipment
            if starting_items:
                item_dicts = [
                    {
                        "name": item.display_name,
                        "type": item.item_type.value if item.item_type else "misc",
                        "slot": item.body_slot,
                    }
                    for item in starting_items
                ]
                display_starting_equipment(item_dicts)

            console.print("\n[dim]Use 'rpg play' to start your adventure.[/dim]")

        except ValueError as e:
            display_error(str(e))
            raise typer.Exit(1)

    finally:
        db.close()
