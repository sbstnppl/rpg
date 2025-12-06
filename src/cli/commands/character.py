"""Character-related commands."""

import random
import re
import unicodedata
from typing import Optional

import typer
from rich.console import Console
from sqlalchemy.orm import Session

from src.cli.display import (
    display_attribute_table,
    display_character_status,
    display_dice_roll,
    display_error,
    display_info,
    display_inventory,
    display_point_buy_status,
    display_success,
    prompt_background,
    prompt_character_name,
)
from src.cli.commands.session import get_db_session
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntityAttribute
from src.database.models.enums import EntityType, VitalStatus
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.database.models.vital_state import EntityVitalState
from src.managers.needs import NeedsManager
from src.schemas.settings import (
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

        # Get stats from attributes JSON
        stats = {}
        if player.attributes:
            for key, value in player.attributes.items():
                if isinstance(value, (int, float)):
                    stats[key.replace("_", " ").title()] = value

        # Get needs
        needs = None
        needs_manager = NeedsManager(db, game_session)
        needs_state = needs_manager.get_needs_state(player.id)
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
                "equipped": item.is_equipped,
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

        # Get equipped items
        items = (
            db.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.holder_id == player.id,
                Item.is_equipped == True,
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
            }
            for item in items
        ]

        display_inventory(item_dicts)

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


@app.command()
def create(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    random_stats: bool = typer.Option(False, "--random", "-r", help="Use random 4d6 drop lowest"),
) -> None:
    """Create a new player character (interactive)."""
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

        console.print("\n[bold cyan]═══ Character Creation ═══[/bold cyan]\n")

        # Get name
        name = prompt_character_name()

        # Get attributes
        schema = get_setting_schema(game_session.setting)

        if random_stats:
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
        else:
            attributes = _point_buy_interactive(schema)

        # Get background
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
            db.commit()

            console.print()
            display_success(f"Character '{name}' created successfully!")
            console.print("\n[dim]Use 'rpg play' to start your adventure.[/dim]")

        except ValueError as e:
            display_error(str(e))
            raise typer.Exit(1)

    finally:
        db.close()
