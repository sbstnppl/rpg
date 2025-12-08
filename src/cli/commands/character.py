"""Character-related commands."""

import json
import random
import re
import unicodedata
from dataclasses import dataclass, field
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
from src.database.connection import get_db_session
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
from src.llm.audit_logger import set_audit_context

app = typer.Typer(help="Character commands")
console = Console()


@dataclass
class CharacterCreationState:
    """Tracks the state of character creation across conversation turns.

    All required fields must be filled before character creation can complete.
    Hidden fields are set by AI and never shown to the player.
    """

    # Group 1: Name
    name: str | None = None

    # Group 2: Attributes (must have all 6)
    attributes: dict[str, int] | None = None

    # Group 3: Appearance
    age: int | None = None
    gender: str | None = None
    build: str | None = None
    hair_color: str | None = None
    hair_style: str | None = None
    eye_color: str | None = None
    skin_tone: str | None = None
    species: str | None = None

    # Group 4: Background
    background: str | None = None

    # Group 5: Personality
    personality_notes: str | None = None

    # Hidden data (AI generates, player doesn't see)
    hidden_backstory: str | None = None

    # AI-inferred fields (generated after player confirms)
    inferred_skills: list[dict] = field(default_factory=list)
    inferred_preferences: dict = field(default_factory=dict)
    inferred_need_modifiers: list[dict] = field(default_factory=list)

    # Conversation history for context
    conversation_history: list[str] = field(default_factory=list)

    def get_missing_groups(self) -> list[str]:
        """Return list of incomplete group names.

        Returns:
            List of group names that still need to be filled.
        """
        missing = []
        if not self.name:
            missing.append("name")
        if not self.attributes:
            missing.append("attributes")
        if not all([self.age, self.gender, self.build, self.hair_color, self.eye_color]):
            missing.append("appearance")
        if not self.background:
            missing.append("background")
        if not self.personality_notes:
            missing.append("personality")
        return missing

    def is_complete(self) -> bool:
        """Check if all required groups are filled.

        Returns:
            True if character creation can proceed.
        """
        return len(self.get_missing_groups()) == 0

    def get_current_state_summary(self) -> str:
        """Generate a summary of current state for the AI prompt.

        Returns:
            Formatted string showing filled and missing fields.
        """
        lines = ["## Current Character State"]

        # Name
        if self.name:
            lines.append(f"- Name: {self.name} ✓")
        else:
            lines.append("- Name: [not set]")

        # Attributes
        if self.attributes:
            attrs = ", ".join(f"{k}={v}" for k, v in self.attributes.items())
            lines.append(f"- Attributes: {attrs} ✓")
        else:
            lines.append("- Attributes: [not set]")

        # Appearance
        appearance_fields = {
            "age": self.age,
            "gender": self.gender,
            "build": self.build,
            "hair_color": self.hair_color,
            "eye_color": self.eye_color,
            "skin_tone": self.skin_tone,
            "species": self.species,
        }
        filled = [f"{k}={v}" for k, v in appearance_fields.items() if v]
        missing = [k for k, v in appearance_fields.items() if not v]
        if filled:
            lines.append(f"- Appearance: {', '.join(filled)}")
        if missing:
            lines.append(f"  (missing: {', '.join(missing)})")

        # Background
        if self.background:
            preview = self.background[:50] + "..." if len(self.background) > 50 else self.background
            lines.append(f"- Background: {preview} ✓")
        else:
            lines.append("- Background: [not set]")

        # Personality
        if self.personality_notes:
            preview = self.personality_notes[:50] + "..." if len(self.personality_notes) > 50 else self.personality_notes
            lines.append(f"- Personality: {preview} ✓")
        else:
            lines.append("- Personality: [not set]")

        # Missing groups
        missing_groups = self.get_missing_groups()
        if missing_groups:
            lines.append(f"\n**Still needed:** {', '.join(missing_groups)}")
        else:
            lines.append("\n**All required fields complete!**")

        return "\n".join(lines)


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
    with get_db_session() as db:
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

        # Get needs (all 9)
        needs = None
        needs_manager = NeedsManager(db, game_session)
        needs_state = needs_manager.get_needs(player.id)
        if needs_state:
            needs = {
                "Hunger": int(needs_state.hunger),
                "Energy": int(needs_state.energy),
                "Hygiene": int(needs_state.hygiene),
                "Comfort": int(needs_state.comfort),
                "Wellness": int(needs_state.wellness),
                "Social": int(needs_state.social_connection),
                "Morale": int(needs_state.morale),
                "Purpose": int(needs_state.sense_of_purpose),
                "Intimacy": int(needs_state.intimacy),
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


@app.command()
def inventory(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show player inventory."""
    with get_db_session() as db:
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


@app.command()
def equipment(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show equipped items."""
    with get_db_session() as db:
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

    with get_db_session() as db:
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
    creation_state: CharacterCreationState | None = None,
) -> Entity:
    """Create all database records for a new character.

    Args:
        db: Database session.
        game_session: Game session.
        name: Character display name.
        attributes: Dict of attribute_key to value.
        background: Optional background text.
        creation_state: Optional full state from AI-assisted creation.

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

    # Create entity with all fields from state if available
    entity = Entity(
        session_id=game_session.id,
        entity_key=slugify(name),
        display_name=name,
        entity_type=EntityType.PLAYER,
        is_alive=True,
        is_active=True,
        background=background or None,
    )

    # Apply appearance and other fields from creation state
    if creation_state:
        if creation_state.age:
            entity.age = creation_state.age
        if creation_state.gender:
            entity.gender = creation_state.gender
        if creation_state.build:
            entity.build = creation_state.build
        if creation_state.hair_color:
            entity.hair_color = creation_state.hair_color
        if creation_state.hair_style:
            entity.hair_style = creation_state.hair_style
        if creation_state.eye_color:
            entity.eye_color = creation_state.eye_color
        if creation_state.skin_tone:
            entity.skin_tone = creation_state.skin_tone
        if creation_state.species:
            entity.species = creation_state.species
        if creation_state.personality_notes:
            entity.personality_notes = creation_state.personality_notes
        if creation_state.hidden_backstory:
            entity.hidden_backstory = creation_state.hidden_backstory

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
    # All needs: 0 = bad (action required), 100 = good (no action needed)
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=80,
        energy=80,
        hygiene=80,
        comfort=70,
        wellness=100,
        social_connection=50,
        morale=70,
        sense_of_purpose=60,
        intimacy=80,
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


def _load_inference_template() -> str:
    """Load the character inference prompt template.

    Returns:
        Template string.
    """
    template_path = Path(__file__).parent.parent.parent.parent / "data" / "templates" / "character_inference.md"
    if template_path.exists():
        return template_path.read_text()
    return ""


async def _infer_gameplay_fields(
    state: CharacterCreationState,
    session_id: int | None = None,
) -> dict | None:
    """Infer gameplay-relevant fields from character background and personality.

    Uses AI to analyze the character's background and personality to determine:
    - Starting skills (based on background experiences)
    - Character preferences (social tendency, food preferences, etc.)
    - Need modifiers (how traits affect game needs)

    Args:
        state: Character creation state with background and personality.
        session_id: Optional session ID for logging.

    Returns:
        Dict with inferred_skills, inferred_preferences, inferred_need_modifiers,
        or None if inference fails.
    """
    try:
        from src.llm.factory import get_extraction_provider
        from src.llm.message_types import Message, MessageRole
    except ImportError:
        return None

    # Set audit context for logging
    set_audit_context(session_id=session_id, call_type="character_inference")

    template = _load_inference_template()
    if not template:
        return None

    prompt = template.format(
        character_name=state.name or "Unknown",
        age=state.age or "Unknown",
        background=state.background or "No background provided",
        personality=state.personality_notes or "No personality notes provided",
    )

    try:
        provider = get_extraction_provider()
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await provider.complete(messages)

        # Parse JSON from response - look for the outermost JSON object
        json_match = re.search(r'\{[\s\S]*\}', response.content)
        if json_match:
            result = json.loads(json_match.group())
            return result
    except Exception as e:
        console.print(f"[dim]Inference warning: {e}[/dim]")

    return None


def _create_inferred_records(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    inference: dict,
) -> None:
    """Create database records from AI inference results.

    Creates:
    - EntitySkill records for inferred skills
    - CharacterPreferences record with inferred preferences
    - NeedModifier records for inferred modifiers

    Args:
        db: Database session.
        game_session: Game session.
        entity: Player entity.
        inference: Dict with inferred_skills, inferred_preferences, inferred_need_modifiers.
    """
    from src.database.models.character_preferences import (
        CharacterPreferences,
        NeedModifier,
    )
    from src.database.models.entities import EntitySkill
    from src.database.models.enums import (
        AlcoholTolerance,
        DriveLevel,
        IntimacyStyle,
        ModifierSource,
        SocialTendency,
    )

    # Create skills
    skills_created = 0
    for skill_data in inference.get("inferred_skills", []):
        skill_key = skill_data.get("skill_key")
        proficiency = skill_data.get("proficiency", 20)

        if not skill_key:
            continue

        # Check for duplicate
        existing = db.query(EntitySkill).filter(
            EntitySkill.entity_id == entity.id,
            EntitySkill.skill_key == skill_key,
        ).first()
        if existing:
            continue

        skill = EntitySkill(
            entity_id=entity.id,
            skill_key=skill_key,
            proficiency_level=min(100, max(1, proficiency)),
            experience_points=0,
        )
        db.add(skill)
        skills_created += 1

    # Create preferences
    prefs_data = inference.get("inferred_preferences", {})
    if prefs_data:
        # Check for existing preferences
        existing_prefs = db.query(CharacterPreferences).filter(
            CharacterPreferences.entity_id == entity.id,
        ).first()

        if not existing_prefs:
            # Map string enums to actual enum values
            social_tendency = SocialTendency.AMBIVERT
            if prefs_data.get("social_tendency"):
                try:
                    social_tendency = SocialTendency(prefs_data["social_tendency"].lower())
                except ValueError:
                    pass

            drive_level = DriveLevel.MODERATE
            if prefs_data.get("drive_level"):
                try:
                    drive_level = DriveLevel(prefs_data["drive_level"].lower())
                except ValueError:
                    pass

            intimacy_style = IntimacyStyle.EMOTIONAL
            if prefs_data.get("intimacy_style"):
                try:
                    intimacy_style = IntimacyStyle(prefs_data["intimacy_style"].lower())
                except ValueError:
                    pass

            alcohol_tolerance = AlcoholTolerance.MODERATE
            if prefs_data.get("alcohol_tolerance"):
                try:
                    alcohol_tolerance = AlcoholTolerance(prefs_data["alcohol_tolerance"].lower())
                except ValueError:
                    pass

            prefs = CharacterPreferences(
                entity_id=entity.id,
                session_id=game_session.id,
                # Food preferences
                favorite_foods=prefs_data.get("favorite_foods"),
                disliked_foods=prefs_data.get("disliked_foods"),
                is_vegetarian=prefs_data.get("is_vegetarian", False),
                is_vegan=prefs_data.get("is_vegan", False),
                food_allergies=prefs_data.get("food_allergies"),
                is_greedy_eater=prefs_data.get("is_greedy_eater", False),
                is_picky_eater=prefs_data.get("is_picky_eater", False),
                # Drink preferences
                favorite_drinks=prefs_data.get("favorite_drinks"),
                disliked_drinks=prefs_data.get("disliked_drinks"),
                alcohol_tolerance=alcohol_tolerance,
                is_alcoholic=prefs_data.get("is_alcoholic", False),
                is_teetotaler=prefs_data.get("is_teetotaler", False),
                # Intimacy (age-appropriate defaults)
                drive_level=drive_level,
                intimacy_style=intimacy_style,
                attraction_preferences=prefs_data.get("attraction_preferences"),
                # Social
                social_tendency=social_tendency,
                preferred_group_size=prefs_data.get("preferred_group_size", 3),
                is_social_butterfly=prefs_data.get("is_social_butterfly", False),
                is_loner=prefs_data.get("is_loner", False),
                # Stamina
                has_high_stamina=prefs_data.get("has_high_stamina", False),
                has_low_stamina=prefs_data.get("has_low_stamina", False),
                is_insomniac=prefs_data.get("is_insomniac", False),
                is_heavy_sleeper=prefs_data.get("is_heavy_sleeper", False),
                # Extra
                extra_preferences=prefs_data.get("extra_preferences"),
            )
            db.add(prefs)

    # Create need modifiers
    modifiers_created = 0
    for mod_data in inference.get("inferred_need_modifiers", []):
        need_name = mod_data.get("need_name")
        if not need_name:
            continue

        # Check for duplicate modifier from trait source
        source_detail = mod_data.get("reason", "character_creation")[:100]
        existing = db.query(NeedModifier).filter(
            NeedModifier.entity_id == entity.id,
            NeedModifier.need_name == need_name,
            NeedModifier.modifier_source == ModifierSource.TRAIT,
            NeedModifier.source_detail == source_detail,
        ).first()
        if existing:
            continue

        modifier = NeedModifier(
            entity_id=entity.id,
            session_id=game_session.id,
            need_name=need_name,
            modifier_source=ModifierSource.TRAIT,
            source_detail=source_detail,
            decay_rate_multiplier=mod_data.get("decay_rate_multiplier", 1.0),
            satisfaction_multiplier=mod_data.get("satisfaction_multiplier", 1.0),
            max_intensity_cap=mod_data.get("max_intensity_cap"),
            threshold_adjustment=mod_data.get("threshold_adjustment", 0),
            is_active=True,
        )
        db.add(modifier)
        modifiers_created += 1

    db.flush()

    # Log results
    if skills_created or modifiers_created:
        console.print(
            f"[dim]Inferred {skills_created} skills, "
            f"{modifiers_created} need modifiers[/dim]"
        )


async def _extract_world_data(
    character_output: str,
    character_name: str,
    character_background: str,
    setting_name: str,
    session_id: int | None = None,
) -> dict | None:
    """Extract world data from character creation output using LLM.

    Args:
        character_output: Full conversation from character creation.
        character_name: Character's name.
        character_background: Character's background story.
        setting_name: Game setting name.
        session_id: Optional session ID for logging.

    Returns:
        Extracted world data dict or None if extraction fails.
    """
    try:
        from src.llm.factory import get_extraction_provider
        from src.llm.message_types import Message, MessageRole
    except ImportError:
        return None

    # Set audit context for logging
    set_audit_context(session_id=session_id, call_type="world_extraction")

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


def _strip_json_comments(json_str: str) -> str:
    """Strip JavaScript-style comments from JSON string.

    LLMs sometimes add // comments which are invalid in JSON.

    Args:
        json_str: JSON string that may contain comments.

    Returns:
        JSON string with comments removed.
    """
    # Remove single-line // comments (but not inside strings)
    # This is a simple approach that works for typical LLM output
    lines = json_str.split('\n')
    cleaned_lines = []
    for line in lines:
        # Find // that's not inside a string
        # Simple approach: remove everything after // if it's not preceded by http
        if '//' in line and 'http' not in line:
            # Check if // is inside a string by counting quotes before it
            idx = line.find('//')
            before = line[:idx]
            # Count unescaped quotes
            quote_count = before.count('"') - before.count('\\"')
            if quote_count % 2 == 0:  # Not inside a string
                line = before.rstrip()
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def _sanitize_json_string(json_str: str) -> str:
    """Sanitize JSON string by escaping control characters in string values.

    LLMs sometimes put literal newlines inside JSON string values, which is invalid.
    This function escapes them properly.

    Args:
        json_str: JSON string that may have unescaped control characters.

    Returns:
        JSON string with control characters properly escaped.
    """
    # First, handle the simple case of newlines inside string values
    # We need to be careful not to escape newlines that are structural (between key-value pairs)

    # Strategy: Find string values and escape newlines within them
    result = []
    in_string = False
    escape_next = False
    i = 0

    while i < len(json_str):
        char = json_str[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == '\\':
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            # Inside a string - escape control characters
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            elif ord(char) < 32:  # Other control characters
                result.append(f'\\u{ord(char):04x}')
            else:
                result.append(char)
        else:
            result.append(char)

        i += 1

    return ''.join(result)


def _parse_field_updates(response: str) -> dict | None:
    """Parse field updates from AI response.

    Looks for JSON blocks with field_updates key containing character data.
    Handles malformed JSON with comments.

    Args:
        response: LLM response text.

    Returns:
        Dict with field updates if found, else None.

    Example response format:
        {"field_updates": {"name": "Finn", "age": 12, "gender": "male"}}
    """
    try:
        # Look for field_updates JSON in markdown code blocks
        code_block_match = re.search(
            r'```json\s*(\{[^`]*"field_updates"[^`]*\})\s*```',
            response,
            re.DOTALL
        )
        if code_block_match:
            json_str = _strip_json_comments(code_block_match.group(1))
            json_str = _sanitize_json_string(json_str)
            data = json.loads(json_str)
            if "field_updates" in data:
                return data["field_updates"]

        # Look for inline field_updates JSON (possibly multiline with braces)
        inline_match = re.search(
            r'\{"field_updates":\s*(\{[\s\S]*?\})\s*\}',
            response,
        )
        if inline_match:
            json_str = _strip_json_comments(inline_match.group(1))
            json_str = _sanitize_json_string(json_str)
            return json.loads(json_str)

    except json.JSONDecodeError as e:
        # Log for debugging but don't crash
        console.print(f"[dim]JSON parse warning: {e}[/dim]")
    return None


def _parse_hidden_content(response: str) -> dict | None:
    """Parse hidden content from AI response.

    Looks for JSON blocks with hidden_content key containing secret data.

    Args:
        response: LLM response text.

    Returns:
        Dict with hidden content if found, else None.

    Example response format:
        {"hidden_content": {"backstory": "Unknown to the character...", "traits": ["destiny-touched"]}}
    """
    try:
        # Look for hidden_content JSON in markdown code blocks
        code_block_match = re.search(
            r'```json\s*(\{[^`]*"hidden_content"[^`]*\})\s*```',
            response,
            re.DOTALL
        )
        if code_block_match:
            data = json.loads(code_block_match.group(1))
            if "hidden_content" in data:
                return data["hidden_content"]

        # Look for inline hidden_content JSON
        inline_match = re.search(
            r'\{"hidden_content":\s*\{([^}]+)\}\s*\}',
            response,
            re.DOTALL
        )
        if inline_match:
            return json.loads("{" + inline_match.group(1) + "}")

    except json.JSONDecodeError:
        pass
    return None


def _parse_ready_to_play(response: str) -> bool:
    """Parse ready_to_play signal from AI response.

    Looks for JSON blocks with ready_to_play key set to true.

    Args:
        response: LLM response text.

    Returns:
        True if AI signals ready to play, False otherwise.

    Example response format:
        {"ready_to_play": true}
    """
    try:
        # Look for ready_to_play JSON in markdown code blocks
        code_block_match = re.search(
            r'```json\s*(\{[^`]*"ready_to_play"[^`]*\})\s*```',
            response,
            re.DOTALL
        )
        if code_block_match:
            json_str = _strip_json_comments(code_block_match.group(1))
            json_str = _sanitize_json_string(json_str)
            data = json.loads(json_str)
            if data.get("ready_to_play") is True:
                return True

        # Look for inline ready_to_play JSON
        inline_match = re.search(
            r'\{"ready_to_play":\s*(true|false)\s*\}',
            response,
            re.IGNORECASE
        )
        if inline_match:
            return inline_match.group(1).lower() == "true"

    except json.JSONDecodeError:
        pass
    return False


def _parse_point_buy_switch(response: str) -> bool:
    """Parse switch_to_point_buy signal from AI response.

    Looks for JSON blocks with switch_to_point_buy key set to true.
    This signals that the player wants to manually distribute attribute points
    instead of having the AI suggest them.

    Args:
        response: LLM response text.

    Returns:
        True if AI signals switch to point-buy, False otherwise.

    Example response format:
        {"switch_to_point_buy": true}
    """
    try:
        # Look for switch_to_point_buy JSON in markdown code blocks
        code_block_match = re.search(
            r'```json\s*(\{[^`]*"switch_to_point_buy"[^`]*\})\s*```',
            response,
            re.DOTALL
        )
        if code_block_match:
            json_str = _strip_json_comments(code_block_match.group(1))
            json_str = _sanitize_json_string(json_str)
            data = json.loads(json_str)
            if data.get("switch_to_point_buy") is True:
                return True

        # Look for inline switch_to_point_buy JSON
        inline_match = re.search(
            r'\{"switch_to_point_buy":\s*(true|false)\s*\}',
            response,
            re.IGNORECASE
        )
        if inline_match:
            return inline_match.group(1).lower() == "true"

    except json.JSONDecodeError:
        pass
    return False


def _apply_field_updates(state: CharacterCreationState, updates: dict) -> None:
    """Apply field updates to character creation state.

    Args:
        state: Current character creation state.
        updates: Dict of field updates from AI.
    """
    # Map update keys to state attributes
    field_mapping = {
        "name": "name",
        "display_name": "name",
        "age": "age",
        "gender": "gender",
        "build": "build",
        "hair_color": "hair_color",
        "hair_style": "hair_style",
        "eye_color": "eye_color",
        "skin_tone": "skin_tone",
        "species": "species",
        "background": "background",
        "personality": "personality_notes",
        "personality_notes": "personality_notes",
        "attributes": "attributes",
    }

    for key, value in updates.items():
        if key in field_mapping:
            setattr(state, field_mapping[key], value)


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
    text = re.sub(r'\{[^{}]*"field_updates"[^{}]*\{[^{}]*\}[^{}]*\}', '', text)
    text = re.sub(r'\{[^{}]*"hidden_content"[^{}]*\{[^{}]*\}[^{}]*\}', '', text)
    text = re.sub(r'\{[^{}]*"ready_to_play"[^{}]*\}', '', text)
    text = re.sub(r'\{[^{}]*"switch_to_point_buy"[^{}]*\}', '', text)
    # Clean up extra whitespace left behind
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_name_from_history(conversation_history: list[str]) -> str | None:
    """Extract character name from conversation history.

    Looks for patterns where the AI refers to the character by name.

    Args:
        conversation_history: List of conversation messages.

    Returns:
        Extracted name or None.
    """
    # Join history and look for common name patterns from AI responses
    history_text = "\n".join(conversation_history)

    # Patterns like "Finn is a...", "name is Finn", "called Finn", "character Finn"
    patterns = [
        r"(?:name is|named|called|character)\s+([A-Z][a-z]+)",
        r"([A-Z][a-z]+)\s+is\s+(?:a\s+)?(?:\d+[- ]year[- ]old|young|an?\s+)",
        r"([A-Z][a-z]+)'s\s+(?:character|attributes|background|stats|name)",
        r"for\s+([A-Z][a-z]+)(?:\s+are)?:",
        r"we have\s+([A-Z][a-z]+)'s",
        r"Now that we have\s+([A-Z][a-z]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, history_text)
        if match:
            name = match.group(1)
            # Filter out common false positives
            if name.lower() not in (
                "the", "this", "that", "here", "there", "what", "would",
                "strength", "dexterity", "constitution", "intelligence",
                "wisdom", "charisma", "player", "character", "assistant",
                "now", "since", "great", "based", "your",
            ):
                return name

    return None


def _extract_name_from_input(player_input: str) -> str | None:
    """Extract a name if the player input looks like just a name.

    Args:
        player_input: The player's message.

    Returns:
        The name if input looks like a single name, else None.
    """
    # Clean the input
    cleaned = player_input.strip()

    # If it's a single capitalized word that looks like a name
    if re.match(r'^[A-Z][a-z]+$', cleaned):
        # Filter out common words (compare lowercase)
        lower = cleaned.lower()
        if lower not in (
            "yes", "no", "sure", "okay", "done", "ready", "start", "begin",
            "male", "female", "human", "elf", "dwarf", "tall", "short",
            "ok", "yep", "yeah", "yup", "nope", "go", "confirm",
        ):
            return cleaned

    # Handle "My name is X" or "Call me X" or "Name: X"
    patterns = [
        r"(?:my name is|call me|name:?)\s+([A-Z][a-z]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            name = match.group(1)
            # Capitalize first letter
            name = name[0].upper() + name[1:].lower()
            # Double-check it's not a common word
            if name.lower() not in (
                "yes", "no", "sure", "okay", "done", "ready", "start", "begin",
                "male", "female", "human", "elf", "dwarf", "tall", "short",
                "ok", "yep", "yeah", "yup", "nope", "go", "confirm",
            ):
                return name

    return None


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
    session_id: int | None = None,
) -> CharacterCreationState:
    """Run AI-assisted character creation.

    Args:
        schema: Setting schema.
        session_id: Optional session ID for logging.

    Returns:
        CharacterCreationState with all fields populated.

    Raises:
        typer.Exit: If creation is cancelled.
    """
    import asyncio
    return asyncio.run(_ai_character_creation_async(schema, session_id))


async def _ai_character_creation_async(
    schema: SettingSchema,
    session_id: int | None = None,
) -> CharacterCreationState:
    """Async implementation of AI-assisted character creation.

    Uses CharacterCreationState to track all required fields and ensures
    character is complete before allowing creation.

    Args:
        schema: Setting schema.
        session_id: Optional session ID for logging.

    Returns:
        CharacterCreationState with all fields populated.

    Raises:
        typer.Exit: If creation is cancelled.
    """
    try:
        from src.llm.factory import get_cheap_provider
    except ImportError:
        display_error("LLM providers not available. Use standard creation instead.")
        raise typer.Exit(1)

    # Set audit context for logging
    set_audit_context(session_id=session_id, call_type="character_creation")

    provider = get_cheap_provider()

    # Prepare context
    template = _load_character_creator_template()
    attributes_list = "\n".join(
        f"- {attr.display_name} ({attr.key}): {attr.description}"
        for attr in schema.attributes
    )

    # Initialize state
    state = CharacterCreationState()

    console.print("\n[bold magenta]═══ AI-Assisted Character Creation ═══[/bold magenta]\n")
    console.print("[dim]Chat with the AI to create your character. Type 'quit' to cancel.[/dim]\n")

    # Initial greeting
    initial_prompt = f"""You are starting a character creation session.

Setting: {schema.name}
Attributes available: {attributes_list}
Point-buy rules: {schema.point_buy_total} points, values {schema.point_buy_min}-{schema.point_buy_max}

Required field groups: name, attributes, appearance, background, personality.

Start by greeting the player and asking what kind of character they want to create.
When they provide information, output field_updates JSON to record it."""

    try:
        from src.llm.message_types import Message, MessageRole

        messages = [Message(role=MessageRole.USER, content=initial_prompt)]
        response = await provider.complete(messages)
        display_ai_message(_strip_json_blocks(response.content))
        state.conversation_history.append(f"Assistant: {response.content}")

    except Exception as e:
        display_error(f"Failed to connect to AI: {e}")
        display_info("Falling back to standard character creation...")
        raise typer.Exit(1)

    # Conversation loop
    max_turns = 30  # Increased for more field groups
    for turn in range(max_turns):
        player_input = prompt_ai_input()

        if player_input.lower() in ("quit", "exit", "cancel"):
            display_info("Character creation cancelled.")
            raise typer.Exit(0)

        # Show current state on request
        if player_input.lower() in ("status", "show", "state", "progress"):
            console.print("\n[bold cyan]Current Character State:[/bold cyan]")
            _display_state_summary(state)
            missing = state.get_missing_groups()
            if missing:
                console.print(f"\n[yellow]Still need: {', '.join(missing)}[/yellow]")
            continue

        state.conversation_history.append(f"Player: {player_input}")

        # Build prompt with current state
        prompt = template.format(
            setting_name=schema.name,
            setting_description=f"{schema.name.title()} setting",
            attributes_list=attributes_list,
            point_buy_total=schema.point_buy_total,
            point_buy_min=schema.point_buy_min,
            point_buy_max=schema.point_buy_max,
            character_state=state.get_current_state_summary(),
            conversation_history="\n".join(state.conversation_history[-10:]),
            player_input=player_input,
        )

        try:
            messages = [Message(role=MessageRole.USER, content=prompt)]
            response = await provider.complete(messages)
            ai_response = response.content

            state.conversation_history.append(f"Assistant: {ai_response}")

            # Parse and apply field updates
            field_updates = _parse_field_updates(ai_response)
            if field_updates:
                # Validate attributes if provided
                if "attributes" in field_updates:
                    is_valid, error = _validate_ai_attributes(field_updates["attributes"], schema)
                    if not is_valid:
                        console.print(f"[yellow]Note: Attributes invalid: {error}[/yellow]")
                        del field_updates["attributes"]

                _apply_field_updates(state, field_updates)

                # Show what was captured
                captured = ", ".join(f"{k}" for k in field_updates.keys())
                console.print(f"[dim green]Saved: {captured}[/dim green]")

            # Fallback: Try to extract name from player input if not in state
            # This handles cases where AI doesn't output JSON but player gave a name
            if not state.name:
                extracted_name = _extract_name_from_input(player_input)
                if extracted_name:
                    state.name = extracted_name
                    console.print(f"[dim green]Saved: name ({extracted_name})[/dim green]")

            # Also check for old-style suggested_attributes (backward compatibility)
            suggested = _parse_attribute_suggestion(ai_response)
            if suggested and not state.attributes:
                is_valid, error = _validate_ai_attributes(suggested, schema)
                if is_valid:
                    state.attributes = suggested
                    display_suggested_attributes(suggested)

            # Parse hidden content
            hidden = _parse_hidden_content(ai_response)
            if hidden:
                if "backstory" in hidden:
                    state.hidden_backstory = hidden["backstory"]

            # Check if AI signals switch to point-buy mode
            if _parse_point_buy_switch(ai_response) and not state.attributes:
                # Display the AI message first (explains why switching)
                display_ai_message(_strip_json_blocks(ai_response))
                console.print("\n[bold cyan]Entering Point-Buy Mode...[/bold cyan]")
                state.attributes = _point_buy_interactive(schema)
                console.print("[dim green]Saved: attributes[/dim green]")
                console.print("[dim]Returning to character creation...[/dim]\n")
                # Continue the conversation - AI will move to next group
                continue

            # Check if AI signals ready to play
            if _parse_ready_to_play(ai_response):
                if state.is_complete():
                    # AI confirmed player is ready and all fields filled
                    display_ai_message(_strip_json_blocks(ai_response))
                    console.print("\n[bold green]Character complete![/bold green]")
                    return state
                else:
                    # AI thinks we're ready but fields are missing - show what's needed
                    missing = state.get_missing_groups()
                    console.print(
                        f"[yellow]Almost there! Still need: {', '.join(missing)}[/yellow]"
                    )

            # Display AI response (stripped of JSON)
            display_ai_message(_strip_json_blocks(ai_response))

        except Exception as e:
            display_error(f"AI error: {e}")
            continue

    # If we reach max turns, offer manual completion for missing fields
    display_info("Let's wrap up character creation.")

    if not state.name:
        state.name = prompt_character_name()

    if not state.attributes:
        console.print("\n[dim]Falling back to point-buy for attributes...[/dim]")
        state.attributes = _point_buy_interactive(schema)

    if not state.background:
        state.background = prompt_background()

    # Fill in minimal defaults for appearance if missing
    if not state.age:
        state.age = 25  # Default age
    if not state.gender:
        state.gender = "unknown"
    if not state.build:
        state.build = "average"
    if not state.hair_color:
        state.hair_color = "brown"
    if not state.eye_color:
        state.eye_color = "brown"

    if not state.personality_notes:
        state.personality_notes = "A curious adventurer"

    return state


def _display_state_summary(state: CharacterCreationState) -> None:
    """Display a summary of the character state.

    Args:
        state: Current character creation state.
    """
    from rich.panel import Panel
    from rich.table import Table

    # Build summary text
    lines = []
    lines.append(f"[bold]Name:[/bold] {state.name}")
    lines.append(f"[bold]Age:[/bold] {state.age}  [bold]Gender:[/bold] {state.gender}  [bold]Species:[/bold] {state.species or 'Human'}")
    lines.append("")
    lines.append("[bold]Appearance:[/bold]")
    lines.append(f"  Build: {state.build}")
    lines.append(f"  Hair: {state.hair_color}" + (f" ({state.hair_style})" if state.hair_style else ""))
    lines.append(f"  Eyes: {state.eye_color}")
    if state.skin_tone:
        lines.append(f"  Skin: {state.skin_tone}")
    lines.append("")

    if state.attributes:
        lines.append("[bold]Attributes:[/bold]")
        attr_line = "  " + "  ".join(
            f"{k.upper()[:3]}: {v}" for k, v in state.attributes.items()
        )
        lines.append(attr_line)
        lines.append("")

    if state.background:
        bg_preview = state.background[:100] + "..." if len(state.background) > 100 else state.background
        lines.append(f"[bold]Background:[/bold] {bg_preview}")
        lines.append("")

    if state.personality_notes:
        lines.append(f"[bold]Personality:[/bold] {state.personality_notes}")

    panel = Panel(
        "\n".join(lines),
        title="Character Summary",
        border_style="green",
    )
    console.print(panel)


@app.command()
def create(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    random_stats: bool = typer.Option(False, "--random", "-r", help="Use random 4d6 drop lowest"),
    ai_assisted: bool = typer.Option(False, "--ai", "-a", help="Use AI-assisted character creation"),
) -> None:
    """Create a new player character (interactive).

    Use --ai for conversational AI-assisted creation, or --random for dice rolls.
    """
    console.print("[yellow]⚠ Deprecated: Use 'rpg game start' instead[/yellow]")
    console.print()
    with get_db_session() as db:
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

        # Track state for AI mode, simple values for other modes
        creation_state: CharacterCreationState | None = None

        if ai_assisted:
            # AI-assisted character creation - returns full state
            creation_state = _ai_character_creation(schema, session_id=game_session.id)
            name = creation_state.name
            attributes = creation_state.attributes
            background = creation_state.background
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
                creation_state=creation_state,  # Pass full state for AI mode
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

            # If AI-assisted, extract world data and infer gameplay fields
            if ai_assisted and creation_state:
                import asyncio

                # Extract world data (NPCs, locations from backstory)
                conversation_history = "\n".join(creation_state.conversation_history)
                console.print("[dim]Extracting world from backstory...[/dim]")
                world_data = asyncio.run(_extract_world_data(
                    character_output=conversation_history,
                    character_name=name,
                    character_background=background or "",
                    setting_name=game_session.setting,
                    session_id=game_session.id,
                ))
                if world_data:
                    _create_world_from_extraction(db, game_session, entity, world_data)

                # Infer gameplay-relevant fields (skills, preferences, modifiers)
                console.print("[dim]Inferring skills and preferences...[/dim]")
                inference = asyncio.run(_infer_gameplay_fields(creation_state, session_id=game_session.id))
                if inference:
                    _create_inferred_records(db, game_session, entity, inference)

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
