"""Character-related commands."""

import json
import random
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import typer
from rich.console import Console
from sqlalchemy.orm import Session

from src.cli.display import (
    display_ai_message,
    display_attribute_table,
    display_character_status,
    display_character_summary,
    display_dice_roll,
    display_equipment,
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
from src.database.models.character_preferences import CharacterPreferences
from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntityAttribute, NPCExtension
from src.database.models.enums import DriveLevel, EntityType, IntimacyStyle, VitalStatus
from src.database.models.items import Item
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession, Turn
from src.managers.item_manager import ItemManager
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
    height: str | None = None  # e.g., "175 cm" or "5'9\""
    build: str | None = None
    hair_color: str | None = None
    hair_style: str | None = None
    eye_color: str | None = None
    skin_tone: str | None = None
    voice_description: str | None = None  # e.g., "deep and resonant"
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

    # Whether the user has confirmed the character in the Review section
    confirmed: bool = False

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
            "height": self.height,
            "build": self.build,
            "hair_color": self.hair_color,
            "eye_color": self.eye_color,
            "skin_tone": self.skin_tone,
            "voice": self.voice_description,
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


# ==================== Wizard Mode Dataclasses ====================


class WizardSectionName(str, Enum):
    """Names of wizard sections in order."""

    SPECIES = "species"  # Species & Gender (was NAME)
    NAME = "name"  # Name & Appearance (was APPEARANCE)
    BACKGROUND = "background"
    PERSONALITY = "personality"
    ATTRIBUTES = "attributes"
    REVIEW = "review"


# Section display order
WIZARD_SECTION_ORDER = [
    WizardSectionName.SPECIES,
    WizardSectionName.NAME,
    WizardSectionName.BACKGROUND,
    WizardSectionName.PERSONALITY,
    WizardSectionName.ATTRIBUTES,
    WizardSectionName.REVIEW,
]

# Section display names
WIZARD_SECTION_TITLES = {
    WizardSectionName.SPECIES: "Species & Gender",
    WizardSectionName.NAME: "Name & Appearance",
    WizardSectionName.BACKGROUND: "Background",
    WizardSectionName.PERSONALITY: "Personality",
    WizardSectionName.ATTRIBUTES: "Attributes",
    WizardSectionName.REVIEW: "Review & Confirm",
}

# Required fields per section
# Note: "build" is intentionally NOT required in NAME section - it's auto-derived from
# attributes in the ATTRIBUTES section using infer_build_from_stats()
WIZARD_SECTION_REQUIREMENTS: dict[WizardSectionName, list[str]] = {
    WizardSectionName.SPECIES: ["species", "gender"],
    WizardSectionName.NAME: ["name", "age", "hair_color", "eye_color"],  # build is optional
    WizardSectionName.BACKGROUND: ["background"],
    WizardSectionName.PERSONALITY: ["personality_notes"],
    WizardSectionName.ATTRIBUTES: ["attributes"],  # Also sets build based on stats
    WizardSectionName.REVIEW: [],  # No fields, just confirmation
}

# Prerequisites: which sections must be complete before accessing a section
# Allows sequential unlocking while permitting revisiting completed sections
WIZARD_SECTION_PREREQUISITES: dict[WizardSectionName, list[WizardSectionName]] = {
    WizardSectionName.SPECIES: [],  # No prerequisites
    WizardSectionName.NAME: [WizardSectionName.SPECIES],
    WizardSectionName.BACKGROUND: [WizardSectionName.SPECIES, WizardSectionName.NAME],
    WizardSectionName.PERSONALITY: [
        WizardSectionName.SPECIES,
        WizardSectionName.NAME,
        WizardSectionName.BACKGROUND,
    ],
    WizardSectionName.ATTRIBUTES: [
        WizardSectionName.SPECIES,
        WizardSectionName.NAME,
        WizardSectionName.BACKGROUND,
        WizardSectionName.PERSONALITY,
    ],
    WizardSectionName.REVIEW: [
        WizardSectionName.SPECIES,
        WizardSectionName.NAME,
        WizardSectionName.BACKGROUND,
        WizardSectionName.PERSONALITY,
        WizardSectionName.ATTRIBUTES,
    ],
}


@dataclass
class WizardSection:
    """Tracks state of a single wizard section.

    Each section has its own conversation history to prevent
    context pollution between sections.
    """

    name: WizardSectionName
    status: Literal["not_started", "in_progress", "complete"] = "not_started"
    conversation_history: list[str] = field(default_factory=list)

    # Section-specific extracted data
    data: dict = field(default_factory=dict)

    def is_complete(self, character_state: "CharacterCreationState") -> bool:
        """Check if this section's requirements are met.

        Args:
            character_state: The overall character state to check against.

        Returns:
            True if all required fields for this section are filled.
        """
        # REVIEW section requires explicit confirmation, not just empty requirements
        if self.name == WizardSectionName.REVIEW:
            return character_state.confirmed

        requirements = WIZARD_SECTION_REQUIREMENTS.get(self.name, [])

        for field_name in requirements:
            if field_name == "attributes":
                # Special case: attributes is a dict
                if not character_state.attributes:
                    return False
            else:
                value = getattr(character_state, field_name, None)
                if value is None or value == "":
                    return False

        return True

    def get_missing_fields(self, character_state: "CharacterCreationState") -> list[str]:
        """Get list of fields still needed for this section.

        Args:
            character_state: The overall character state to check against.

        Returns:
            List of field names that are not yet filled.
        """
        missing = []
        requirements = WIZARD_SECTION_REQUIREMENTS.get(self.name, [])

        for field_name in requirements:
            if field_name == "attributes":
                if not character_state.attributes:
                    missing.append(field_name)
            else:
                value = getattr(character_state, field_name, None)
                if value is None or value == "":
                    missing.append(field_name)

        return missing


@dataclass
class CharacterWizardState:
    """Tracks the overall state of the wizard-based character creation.

    Manages section navigation and aggregates character data.
    """

    # Section states
    sections: dict[WizardSectionName, WizardSection] = field(default_factory=dict)

    # Current section being edited
    current_section: WizardSectionName | None = None

    # The actual character data being built
    character: CharacterCreationState = field(default_factory=CharacterCreationState)

    # Hidden potential stats (rolled, never shown to player)
    potential_stats: dict[str, int] | None = None

    # Extracted occupation for attribute calculation
    occupation: str | None = None
    occupation_years: int | None = None

    # Lifestyle tags extracted from background
    lifestyles: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize all sections if not already done."""
        if not self.sections:
            for section_name in WIZARD_SECTION_ORDER:
                self.sections[section_name] = WizardSection(name=section_name)

    def get_section_status(
        self, section_name: WizardSectionName
    ) -> Literal["not_started", "in_progress", "complete"]:
        """Get the status of a section.

        Args:
            section_name: The section to check.

        Returns:
            Status string.
        """
        section = self.sections.get(section_name)
        if section is None:
            return "not_started"

        # Check actual completion based on character state
        if section.is_complete(self.character):
            return "complete"
        elif section.status == "in_progress" or section.conversation_history:
            return "in_progress"
        return "not_started"

    def get_next_incomplete_section(self) -> WizardSectionName | None:
        """Get the next section that needs to be completed.

        Returns:
            Next incomplete section name, or None if all complete.
        """
        for section_name in WIZARD_SECTION_ORDER:
            # Skip review - it's always last and doesn't have requirements
            if section_name == WizardSectionName.REVIEW:
                continue
            if self.get_section_status(section_name) != "complete":
                return section_name
        return WizardSectionName.REVIEW

    def is_ready_for_review(self) -> bool:
        """Check if all sections except review are complete.

        Returns:
            True if character can proceed to review.
        """
        for section_name in WIZARD_SECTION_ORDER:
            if section_name == WizardSectionName.REVIEW:
                continue
            if self.get_section_status(section_name) != "complete":
                return False
        return True

    def is_section_accessible(self, section_name: WizardSectionName) -> bool:
        """Check if a section can be accessed based on prerequisites.

        Sections unlock sequentially - a section is accessible if all its
        prerequisites are complete. Once completed, sections remain accessible
        for editing.

        Args:
            section_name: The section to check accessibility for.

        Returns:
            True if the section can be accessed.
        """
        prerequisites = WIZARD_SECTION_PREREQUISITES.get(section_name, [])
        for prereq in prerequisites:
            if self.get_section_status(prereq) != "complete":
                return False
        return True

    def get_completed_data_summary(self) -> str:
        """Generate a summary of all completed character data.

        Used to provide context to section prompts.

        Returns:
            Formatted summary string.
        """
        lines = []

        if self.character.name:
            lines.append(f"Name: {self.character.name}")
        if self.character.species:
            lines.append(f"Species: {self.character.species}")
        if self.character.age:
            lines.append(f"Age: {self.character.age}")
        if self.character.gender:
            lines.append(f"Gender: {self.character.gender}")
        if self.character.build:
            lines.append(f"Build: {self.character.build}")
        if self.character.hair_color:
            hair = self.character.hair_color
            if self.character.hair_style:
                hair = f"{self.character.hair_style} {hair}"
            lines.append(f"Hair: {hair}")
        if self.character.eye_color:
            lines.append(f"Eyes: {self.character.eye_color}")
        if self.character.background:
            # Truncate for context
            bg = self.character.background
            if len(bg) > 200:
                bg = bg[:200] + "..."
            lines.append(f"Background: {bg}")
        if self.occupation:
            occ = self.occupation
            if self.occupation_years:
                occ += f" ({self.occupation_years} years)"
            lines.append(f"Occupation: {occ}")
        if self.character.personality_notes:
            lines.append(f"Personality: {self.character.personality_notes}")
        if self.character.attributes:
            attrs = ", ".join(f"{k.upper()[:3]}:{v}" for k, v in self.character.attributes.items())
            lines.append(f"Attributes: {attrs}")

        return "\n".join(lines) if lines else "No data yet."


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
    """Show player inventory (items currently carried)."""
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

        # Get structured inventory using ItemManager
        item_manager = ItemManager(db, game_session)
        inventory_data = item_manager.get_carried_inventory(player.id)

        # Convert to display format
        equipped_dicts = [
            {
                "name": item.display_name,
                "type": item.item_type.value if item.item_type else "misc",
                "slot": item.body_slot,
                "condition": item.condition.value if item.condition else "good",
            }
            for item in inventory_data["equipped"]
        ]

        held_dicts = [
            {
                "name": item.display_name,
                "type": item.item_type.value if item.item_type else "misc",
                "condition": item.condition.value if item.condition else "good",
            }
            for item in inventory_data["held"]
        ]

        container_dicts = []
        for container_info in inventory_data["containers"]:
            container = container_info["container"]
            storage = container_info["storage"]
            contents = container_info["contents"]

            container_dicts.append({
                "name": container.display_name,
                "capacity": storage.capacity if storage else None,
                "used": len(contents),
                "contents": [
                    {
                        "name": item.display_name,
                        "type": item.item_type.value if item.item_type else "misc",
                    }
                    for item in contents
                ],
            })

        display_inventory({
            "equipped": equipped_dicts,
            "held": held_dicts,
            "containers": container_dicts,
        })


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

        # Organize items by slot for display_equipment()
        slots: dict[str, list[dict]] = {}
        for item in items:
            slot_name = item.body_slot or "unknown"
            if slot_name not in slots:
                slots[slot_name] = []
            slots[slot_name].append({
                "name": item.display_name,
                "layer": item.body_layer or 0,
                "visible": item.is_visible if item.is_visible is not None else True,
                "condition": item.condition.value if item.condition else "good",
            })

        display_equipment(slots)


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
                # Extract visual summary (color + material) if available
                visual_summary = ""
                if item.properties and "visual" in item.properties:
                    visual = item.properties["visual"]
                    parts = []
                    if color := visual.get("primary_color"):
                        parts.append(color)
                    if material := visual.get("material"):
                        parts.append(material)
                    if parts:
                        visual_summary = " ".join(parts)

                if item.is_visible:
                    output.append(layer_str)
                    if visual_summary:
                        output.append(f"{item.display_name} ", style="white")
                        output.append(f"({visual_summary})\n", style="dim cyan")
                    else:
                        output.append(f"{item.display_name}\n", style="white")
                    visible_items.append(item.display_name)
                else:
                    output.append(layer_str, style="dim")
                    if visual_summary:
                        output.append(f"{item.display_name} ({visual_summary}) (hidden)\n", style="dim")
                    else:
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


@app.command()
def nearby(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show items at current location (ground and surfaces)."""
    from src.cli.display import display_nearby_items
    from src.database.models.items import StorageLocation
    from src.database.models.world import Location
    from src.managers.location_manager import LocationManager

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

        # Get player's current location from last turn
        last_turn = (
            db.query(Turn)
            .filter(Turn.session_id == game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )
        location_key = last_turn.location_at_turn if last_turn else None

        if not location_key:
            display_error("Player location unknown")
            raise typer.Exit(1)

        location_manager = LocationManager(db, game_session)
        location = location_manager.get_location(location_key)
        location_name = location.display_name if location else location_key

        # Get NPCs at this location
        npcs_at_location = (
            db.query(Entity)
            .join(NPCExtension)
            .filter(
                Entity.session_id == game_session.id,
                NPCExtension.current_location == location_key,
            )
            .all()
        )
        npc_names = [npc.display_name for npc in npcs_at_location]

        # Get storage locations at this world location
        storage_locations = (
            db.query(StorageLocation)
            .join(Location, StorageLocation.world_location_id == Location.id)
            .filter(
                StorageLocation.session_id == game_session.id,
                Location.location_key == location_key,
            )
            .all()
        )

        # Organize items by surface
        ground_items = []
        surfaces = {}

        for storage in storage_locations:
            # Get items in this storage
            items_in_storage = (
                db.query(Item)
                .filter(
                    Item.session_id == game_session.id,
                    Item.storage_location_id == storage.id,
                )
                .all()
            )

            if not items_in_storage:
                continue

            item_list = [
                {
                    "name": item.display_name,
                    "type": item.item_type.value if item.item_type else "misc",
                }
                for item in items_in_storage
            ]

            # Determine if ground or a surface
            if storage.container_type in ("ground", "floor", None):
                ground_items.extend(item_list)
            else:
                surface_name = storage.container_type or "Surface"
                if surface_name not in surfaces:
                    surfaces[surface_name] = []
                surfaces[surface_name].extend(item_list)

        display_nearby_items({
            "location": location_name,
            "npcs": npc_names,
            "ground": ground_items,
            "surfaces": surfaces,
        })


@app.command()
def locate(
    item_name: str = typer.Argument(..., help="Item name to search for"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Find where an item is located."""
    from src.database.models.items import StorageLocation
    from src.database.models.world import Location

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

        # Search for items by name (case insensitive, partial match)
        items = (
            db.query(Item)
            .filter(
                Item.session_id == game_session.id,
                Item.display_name.ilike(f"%{item_name}%"),
            )
            .all()
        )

        if not items:
            console.print(f"[dim]You don't remember where you left '{item_name}'[/dim]")
            return

        console.print()
        for item in items:
            location_desc = _describe_item_location(db, game_session, player, item)
            console.print(f"[bold]{item.display_name}[/bold]: {location_desc}")
        console.print()


def _describe_item_location(db: Session, game_session: GameSession, player: Entity, item: Item) -> str:
    """Describe where an item is located.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        item: Item to describe.

    Returns:
        Human-readable location description.
    """
    from src.database.models.items import StorageLocation
    from src.database.models.world import Location

    # Check if equipped on body slot
    if item.body_slot:
        slot_name = item.body_slot.replace("_", " ").title()
        if item.holder_id == player.id:
            return f"Worn on your {slot_name}"
        else:
            # Find who has it
            holder = db.query(Entity).filter(Entity.id == item.holder_id).first()
            holder_name = holder.display_name if holder else "someone"
            return f"Worn by {holder_name} ({slot_name})"

    # Check if held by someone
    if item.holder_id:
        if item.holder_id == player.id:
            return "In your hands"
        else:
            holder = db.query(Entity).filter(Entity.id == item.holder_id).first()
            holder_name = holder.display_name if holder else "someone"
            return f"Held by {holder_name}"

    # Check if in a storage location
    if item.storage_location_id:
        storage = db.query(StorageLocation).filter(StorageLocation.id == item.storage_location_id).first()
        if storage:
            # Check if it's a container (linked to an item)
            if storage.container_item_id:
                container_item = db.query(Item).filter(Item.id == storage.container_item_id).first()
                if container_item:
                    return f"In {container_item.display_name}"

            # Check if at a world location
            if storage.world_location_id:
                location = db.query(Location).filter(Location.id == storage.world_location_id).first()
                location_name = location.display_name if location else "somewhere"
                surface = storage.display_name or storage.container_type or "ground"
                return f"At {location_name} (on {surface})"

            return f"In storage ({storage.display_name or 'unknown'})"

    return "Location unknown"


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


def _infer_initial_needs(
    backstory: str = "",
    age: int | None = None,
    occupation: str | None = None,
    starting_scene: str = "",
) -> dict[str, int]:
    """Infer starting need values from character context.

    Uses keyword-based heuristics to set context-appropriate initial values
    instead of arbitrary defaults.

    Args:
        backstory: Character's backstory text.
        age: Character's age.
        occupation: Character's occupation.
        starting_scene: Description of starting scene/situation.

    Returns:
        Dictionary of need_name -> initial_value (0-100).
    """
    # Start with reasonable defaults
    needs = {
        "hunger": 80,
        "thirst": 80,
        "energy": 80,
        "hygiene": 80,
        "comfort": 70,
        "wellness": 100,
        "social_connection": 50,
        "morale": 70,
        "sense_of_purpose": 60,
        "intimacy": 80,
    }

    backstory_lower = backstory.lower() if backstory else ""
    combined_text = f"{backstory_lower} {starting_scene.lower()}" if starting_scene else backstory_lower

    # Adjust based on backstory context
    # Hardship indicators -> lower comfort/morale
    hardship_words = ["escaped", "fled", "lost", "disaster", "homeless", "poor", "starving"]
    if any(word in backstory_lower for word in hardship_words):
        needs["comfort"] = max(30, needs["comfort"] - 30)
        needs["morale"] = max(40, needs["morale"] - 20)
        needs["hunger"] = max(40, needs["hunger"] - 30)
        needs["thirst"] = max(50, needs["thirst"] - 20)
        needs["hygiene"] = max(40, needs["hygiene"] - 30)

    # Isolation indicators -> lower social
    isolation_words = ["alone", "solitary", "hermit", "isolated", "exile", "wanderer", "loner"]
    if any(word in backstory_lower for word in isolation_words):
        needs["social_connection"] = max(20, needs["social_connection"] - 30)

    # Social/community indicators -> higher social
    social_words = ["family", "friends", "community", "beloved", "popular", "well-liked"]
    if any(word in backstory_lower for word in social_words):
        needs["social_connection"] = min(80, needs["social_connection"] + 20)

    # Purpose indicators -> higher sense of purpose
    purpose_words = ["mission", "destiny", "quest", "calling", "duty", "sworn", "devoted"]
    if any(word in backstory_lower for word in purpose_words):
        needs["sense_of_purpose"] = min(90, needs["sense_of_purpose"] + 25)

    # Trauma indicators -> lower morale, potentially lower wellness
    trauma_words = ["traumatic", "nightmare", "haunted", "wounded", "scarred", "injured"]
    if any(word in backstory_lower for word in trauma_words):
        needs["morale"] = max(40, needs["morale"] - 20)
        needs["wellness"] = max(70, needs["wellness"] - 20)

    # Comfortable life indicators -> higher comfort
    comfort_words = ["wealthy", "noble", "privileged", "comfortable", "luxurious", "pampered"]
    if any(word in backstory_lower for word in comfort_words):
        needs["comfort"] = min(95, needs["comfort"] + 20)
        needs["hygiene"] = min(95, needs["hygiene"] + 10)

    # Age-based adjustments
    if age:
        if age < 18:
            # Young -> more energy, higher social needs
            needs["energy"] = min(95, needs["energy"] + 10)
            needs["social_connection"] = min(70, needs["social_connection"] + 10)
        elif age > 60:
            # Elderly -> less energy, potentially lower intimacy drive
            needs["energy"] = max(60, needs["energy"] - 15)
            needs["intimacy"] = min(90, needs["intimacy"] + 10)  # More content

    # Occupation-based adjustments
    if occupation:
        occupation_lower = occupation.lower()
        # Physical jobs start well-fed and hydrated (workers eat/drink)
        if occupation_lower in ["farmer", "smith", "soldier", "miner", "laborer"]:
            needs["hunger"] = min(90, needs["hunger"] + 5)
            needs["thirst"] = min(90, needs["thirst"] + 5)
        # Scholarly/indoor jobs -> potentially lower energy
        if occupation_lower in ["scholar", "scribe", "wizard", "librarian"]:
            needs["energy"] = max(70, needs["energy"] - 5)
        # Social jobs -> higher social satisfaction
        if occupation_lower in ["merchant", "innkeeper", "bard", "diplomat"]:
            needs["social_connection"] = min(75, needs["social_connection"] + 15)

    # Situational adjustments from starting scene
    # Wet indicators -> lower hygiene, lower comfort
    wet_words = ["swimming", "swim", "lake", "river", "rain", "storm", "soaked", "drenched"]
    if any(word in combined_text for word in wet_words):
        needs["hygiene"] = max(40, needs["hygiene"] - 30)
        needs["comfort"] = max(30, needs["comfort"] - 25)

    # Cold indicators -> lower comfort, lower energy
    cold_words = ["cold", "freezing", "frozen", "snow", "ice", "winter", "blizzard"]
    if any(word in combined_text for word in cold_words):
        needs["comfort"] = max(20, needs["comfort"] - 35)
        needs["energy"] = max(50, needs["energy"] - 15)

    # Dirty indicators -> lower hygiene
    dirty_words = ["dirty", "filthy", "mud", "sewer", "dungeon", "prison", "mine"]
    if any(word in combined_text for word in dirty_words):
        needs["hygiene"] = max(20, needs["hygiene"] - 40)

    return needs


def _infer_initial_vital_status(
    backstory: str = "",
    starting_scene: str = "",
) -> VitalStatus:
    """Infer starting vital status from character context.

    Uses keyword-based heuristics to set appropriate health status
    instead of always starting HEALTHY.

    Args:
        backstory: Character's backstory text.
        starting_scene: Description of starting scene/situation.

    Returns:
        Appropriate VitalStatus enum value.
    """
    combined_text = f"{backstory} {starting_scene}".lower()

    # Critical injury indicators -> WOUNDED
    critical_words = [
        "gravely wounded", "nearly died", "barely survived", "mortally",
        "bleeding out", "dying", "on death's door", "fatal",
    ]
    if any(phrase in combined_text for phrase in critical_words):
        return VitalStatus.WOUNDED

    # Injury indicators -> WOUNDED
    injury_words = [
        "wounded", "injured", "hurt", "bleeding", "broken bone",
        "stabbed", "shot", "beaten", "tortured", "burned",
        "scarred", "limping", "crippled",
    ]
    if any(word in combined_text for word in injury_words):
        return VitalStatus.WOUNDED

    # Illness indicators -> WOUNDED (using WOUNDED as general "not healthy")
    illness_words = [
        "sick", "ill", "diseased", "poisoned", "infected",
        "fever", "plague", "weakened", "frail",
    ]
    if any(word in combined_text for word in illness_words):
        return VitalStatus.WOUNDED

    # Recent hardship that might affect health
    hardship_words = [
        "starving", "malnourished", "dehydrated", "exhausted",
        "collapsed", "fainted",
    ]
    if any(word in combined_text for word in hardship_words):
        return VitalStatus.WOUNDED

    return VitalStatus.HEALTHY


def _infer_equipment_condition(
    backstory: str = "",
    occupation: str | None = None,
) -> "ItemCondition":
    """Infer starting equipment condition from character context.

    Args:
        backstory: Character's backstory text.
        occupation: Character's occupation.

    Returns:
        Appropriate ItemCondition enum value for starting gear.
    """
    from src.database.models.enums import ItemCondition

    backstory_lower = backstory.lower() if backstory else ""

    # Wealthy/noble -> excellent equipment
    wealthy_words = ["wealthy", "noble", "rich", "privileged", "aristocrat", "royal"]
    if any(word in backstory_lower for word in wealthy_words):
        return ItemCondition.PRISTINE

    # Well-maintained professional -> good equipment
    professional_words = ["soldier", "knight", "guard", "merchant", "craftsman"]
    if occupation and occupation.lower() in professional_words:
        return ItemCondition.GOOD

    # Hardship -> worn or damaged equipment
    hardship_words = [
        "escaped", "fled", "refugee", "homeless", "poor", "beggar",
        "wanderer", "exile", "outcast", "destitute",
    ]
    if any(word in backstory_lower for word in hardship_words):
        return ItemCondition.WORN

    # Disaster/combat -> damaged equipment
    disaster_words = [
        "disaster", "battle", "war", "burned", "fire", "flood",
        "attacked", "ambushed", "shipwreck", "crash",
    ]
    if any(word in backstory_lower for word in disaster_words):
        return ItemCondition.DAMAGED

    # Poverty indicators -> worn
    poverty_words = ["peasant", "servant", "slave", "urchin", "orphan"]
    if any(word in backstory_lower for word in poverty_words):
        return ItemCondition.WORN

    # Default to good condition
    return ItemCondition.GOOD


def _infer_starting_situation(
    backstory: str = "",
    starting_scene: str = "",
) -> dict:
    """Infer starting situation details from context.

    Returns a dict with situational modifiers that affect character state:
    - is_wet: Character is wet (swimming, rain, etc.)
    - is_cold: Character is cold (exposure, winter, etc.)
    - is_dirty: Character is dirty (labor, prison, etc.)
    - minimal_equipment: Character has minimal gear (swimming, prisoner, etc.)
    - no_weapons: Character has no weapons (prisoner, peaceful, etc.)

    Args:
        backstory: Character's backstory text.
        starting_scene: Description of starting scene.

    Returns:
        Dict of situational flags.
    """
    combined = f"{backstory} {starting_scene}".lower()

    situation = {
        "is_wet": False,
        "is_cold": False,
        "is_dirty": False,
        "minimal_equipment": False,
        "no_weapons": False,
        "no_armor": False,
    }

    # Wet indicators
    wet_words = [
        "swimming", "swim", "lake", "river", "ocean", "sea", "rain",
        "storm", "flood", "drowned", "soaked", "drenched", "shipwreck",
        "waterfall", "underwater", "bath", "wading",
    ]
    if any(word in combined for word in wet_words):
        situation["is_wet"] = True

    # Cold indicators
    cold_words = [
        "cold", "freezing", "frozen", "snow", "ice", "winter", "blizzard",
        "frost", "chilled", "hypothermia", "mountain", "tundra",
    ]
    if any(word in combined for word in cold_words):
        situation["is_cold"] = True

    # Dirty indicators
    dirty_words = [
        "dirty", "filthy", "mud", "grime", "soot", "coal", "mine",
        "sewer", "dungeon", "prison", "slave", "labor", "dig",
    ]
    if any(word in combined for word in dirty_words):
        situation["is_dirty"] = True

    # Minimal equipment situations
    minimal_words = [
        "swimming", "bath", "prisoner", "captive", "slave", "stripped",
        "naked", "undressed", "shipwreck", "washed ashore",
    ]
    if any(word in combined for word in minimal_words):
        situation["minimal_equipment"] = True
        situation["no_armor"] = True

    # No weapons situations
    no_weapon_words = [
        "prisoner", "captive", "unarmed", "peaceful", "monk",
        "pacifist", "disarmed", "confiscated",
    ]
    if any(word in combined for word in no_weapon_words):
        situation["no_weapons"] = True

    return situation


def _create_character_records(
    db: Session,
    game_session: GameSession,
    name: str,
    attributes: dict[str, int],
    background: str = "",
    creation_state: CharacterCreationState | None = None,
    potential_stats: dict[str, int] | None = None,
    occupation: str | None = None,
    occupation_years: int | None = None,
) -> Entity:
    """Create all database records for a new character.

    Args:
        db: Database session.
        game_session: Game session.
        name: Character display name.
        attributes: Dict of attribute_key to value.
        background: Optional background text.
        creation_state: Optional full state from AI-assisted creation.
        potential_stats: Hidden potential stats from wizard mode (e.g.,
            {"strength": 14, "dexterity": 12, ...}). Stored but never shown.
        occupation: Character's occupation (e.g., "blacksmith", "farmer").
        occupation_years: Years spent in the occupation.

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
        if creation_state.height:
            entity.height = creation_state.height
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
        if creation_state.voice_description:
            entity.voice_description = creation_state.voice_description
        if creation_state.species:
            entity.species = creation_state.species
        if creation_state.personality_notes:
            entity.personality_notes = creation_state.personality_notes
        if creation_state.hidden_backstory:
            entity.hidden_backstory = creation_state.hidden_backstory

    # Apply occupation (from wizard mode)
    if occupation:
        entity.occupation = occupation
    if occupation_years is not None:
        entity.occupation_years = occupation_years

    # Apply hidden potential stats (from wizard mode)
    if potential_stats:
        entity.potential_strength = potential_stats.get("strength")
        entity.potential_dexterity = potential_stats.get("dexterity")
        entity.potential_constitution = potential_stats.get("constitution")
        entity.potential_intelligence = potential_stats.get("intelligence")
        entity.potential_wisdom = potential_stats.get("wisdom")
        entity.potential_charisma = potential_stats.get("charisma")

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

    # Create character needs with context-aware values
    # All needs: 0 = bad (action required), 100 = good (no action needed)
    initial_needs = _infer_initial_needs(
        backstory=background,
        age=entity.age,
        occupation=entity.occupation,
    )
    needs = CharacterNeeds(
        session_id=game_session.id,
        entity_id=entity.id,
        hunger=initial_needs.get("hunger", 80),
        thirst=initial_needs.get("thirst", 80),
        energy=initial_needs.get("energy", 80),
        hygiene=initial_needs.get("hygiene", 80),
        comfort=initial_needs.get("comfort", 70),
        wellness=initial_needs.get("wellness", 100),
        social_connection=initial_needs.get("social_connection", 50),
        morale=initial_needs.get("morale", 70),
        sense_of_purpose=initial_needs.get("sense_of_purpose", 60),
        intimacy=initial_needs.get("intimacy", 80),
    )
    db.add(needs)

    # Create vital state with context-aware status
    initial_vital_status = _infer_initial_vital_status(
        backstory=background,
        starting_scene="",  # Could be passed in from game start
    )
    vital = EntityVitalState(
        session_id=game_session.id,
        entity_id=entity.id,
        vital_status=initial_vital_status,
        death_saves_remaining=3,
        death_saves_failed=0,
        is_dead=False,
        has_been_revived=False,
        revival_count=0,
    )
    db.add(vital)

    db.flush()

    # Extract memories from backstory (synchronous, rule-based)
    if background or (creation_state and creation_state.hidden_backstory):
        _extract_backstory_memories(
            db=db,
            game_session=game_session,
            entity_id=entity.id,
            backstory=background or "",
            hidden_backstory=(
                creation_state.hidden_backstory if creation_state else ""
            ) or "",
        )

    return entity


def _extract_backstory_memories(
    db: Session,
    game_session: GameSession,
    entity_id: int,
    backstory: str,
    hidden_backstory: str = "",
) -> None:
    """Extract significant memories from backstory and create CharacterMemory records.

    Uses rule-based extraction (no LLM required) to identify potential memories
    from the character's backstory.

    Args:
        db: Database session.
        game_session: Game session.
        entity_id: The character entity ID.
        backstory: Visible backstory text.
        hidden_backstory: Hidden backstory (GM secrets).
    """
    from src.services.memory_extractor import MemoryExtractor

    extractor = MemoryExtractor(db, game_session)

    # Use synchronous rule-based extraction
    extracted = extractor.extract_from_backstory_sync(
        entity_id=entity_id,
        backstory=backstory,
        hidden_backstory=hidden_backstory,
    )

    # Create database records
    if extracted:
        extractor.create_memories_from_extracted(
            entity_id=entity_id,
            extracted=extracted,
            source="backstory",
        )


def _create_starting_equipment(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    schema: SettingSchema,
    backstory: str = "",
    starting_scene: str = "",
) -> list:
    """Create starting equipment for a new character.

    Equipment condition and selection is context-aware based on backstory
    and starting situation.

    Args:
        db: Database session.
        game_session: Game session.
        entity: The player entity.
        schema: Setting schema with starting equipment definitions.
        backstory: Character's backstory for condition inference.
        starting_scene: Starting scene description for situation inference.

    Returns:
        List of created Item objects.
    """
    from src.database.models.enums import ItemType, ItemCondition
    from src.managers.item_manager import ItemManager
    from src.services.clothing_visual_generator import ClothingVisualGenerator

    if not schema.starting_equipment:
        return []

    item_manager = ItemManager(db, game_session)
    visual_generator = ClothingVisualGenerator(setting_name=game_session.setting)
    created_items = []

    # Infer equipment condition from backstory
    equipment_condition = _infer_equipment_condition(
        backstory=backstory,
        occupation=entity.occupation,
    )

    # Infer situational constraints
    situation = _infer_starting_situation(
        backstory=backstory,
        starting_scene=starting_scene,
    )

    for equip in schema.starting_equipment:
        # Map string to ItemType enum
        try:
            item_type = ItemType(equip.item_type)
        except ValueError:
            item_type = ItemType.MISC

        # Skip weapons if situation says no weapons
        if situation["no_weapons"] and item_type == ItemType.WEAPON:
            continue

        # Skip armor if situation says no armor
        if situation["no_armor"] and item_type == ItemType.ARMOR:
            continue

        # For minimal equipment situations, only keep basic clothing
        if situation["minimal_equipment"]:
            # Only allow clothing items in minimal situations
            allowed_in_minimal = {
                ItemType.CLOTHING,
                ItemType.CONTAINER,  # Basic pouch/bag
            }
            if item_type not in allowed_in_minimal:
                continue

        # Create unique key for this player
        unique_key = f"{entity.entity_key}_{equip.item_key}"

        # Build properties with visual attributes for clothing/armor
        properties = equip.properties.copy() if equip.properties else {}
        if item_type in (ItemType.CLOTHING, ItemType.ARMOR):
            if equip.visual:
                # Use predefined visual from setting
                properties["visual"] = equip.visual
            elif "visual" not in properties:
                # Generate random visual
                properties["visual"] = visual_generator.generate_visual_properties(
                    equip.item_key,
                    quality="common",
                    display_name=equip.display_name,
                )

        item = item_manager.create_item(
            item_key=unique_key,
            display_name=equip.display_name,
            item_type=item_type,
            owner_id=entity.id,
            holder_id=entity.id,
            description=equip.description or None,
            properties=properties if properties else None,
            condition=equipment_condition,
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
    """Create fully-generated NPCs and relationships from extracted world data.

    Args:
        db: Database session.
        game_session: Game session.
        player: Player entity.
        world_data: Extracted world data dict.
    """
    from src.services.emergent_npc_generator import EmergentNPCGenerator

    entity_manager = EntityManager(db, game_session)
    npc_generator = EmergentNPCGenerator(db, game_session)

    # Update player appearance from extraction
    player_appearance = world_data.get("player_appearance", {})
    if player_appearance:
        for field, value in player_appearance.items():
            if value is not None and field in Entity.APPEARANCE_FIELDS:
                player.set_appearance_field(field, value)

    # Create entities from backstory
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

        # For NPCs, use full NPC generation with all traits
        if entity_type == EntityType.NPC:
            # Generate full NPC with personality, preferences, needs, etc.
            npc_state = npc_generator.create_backstory_npc(
                shadow_data=shadow,
                player_name=player.display_name,
            )
            # Get the created entity from database
            entity = entity_manager.get_entity(entity_key)
            if not entity:
                # Fallback to shadow entity if generation failed
                entity = entity_manager.create_shadow_entity(
                    entity_key=entity_key,
                    display_name=shadow.get("display_name", entity_key.replace("_", " ").title()),
                    entity_type=entity_type,
                    background=shadow.get("brief_description"),
                )
        else:
            # For non-NPC entities (monsters, animals, orgs), use shadow entities
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

        # Player's relationship TO the entity
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

        # Entity's relationship TO player
        entity_rel = Relationship(
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
        db.add(entity_rel)

    db.flush()

    # Log results
    if created_entities:
        console.print(f"[dim]Created {len(created_entities)} backstory connections[/dim]")


def _create_character_preferences(
    db: Session,
    game_session: GameSession,
    entity: Entity,
) -> CharacterPreferences:
    """Create character preferences with default values.

    This creates the consolidated preferences record that includes
    intimacy, food, drink, social, and stamina preferences.

    Args:
        db: Database session.
        game_session: Game session.
        entity: The entity to create preferences for.

    Returns:
        Created CharacterPreferences.
    """
    prefs = CharacterPreferences(
        session_id=game_session.id,
        entity_id=entity.id,
        # Intimacy defaults (previously in IntimacyProfile)
        drive_level=DriveLevel.MODERATE,
        drive_threshold=50,
        intimacy_style=IntimacyStyle.EMOTIONAL,
        has_regular_partner=False,
        is_actively_seeking=False,
        # Other defaults are set by model
    )
    db.add(prefs)
    db.flush()
    return prefs


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
    """Remove JSON blocks and template artifacts from AI response.

    Strips markdown code blocks containing JSON, inline JSON blocks meant for
    machine parsing, and prompt template sections that the LLM may echo back.

    Args:
        text: AI response text that may contain JSON blocks or template artifacts.

    Returns:
        Text with JSON blocks and template artifacts removed.
    """
    # Strip markdown code blocks containing JSON (```json ... ```)
    text = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', text)

    # Strip combined/complex JSON blocks containing our special keys
    # This handles cases where field_updates and section_complete are in one JSON
    # Use a function to find and remove balanced JSON containing special keys
    def remove_special_json(text: str) -> str:
        """Remove JSON blocks containing wizard-specific keys."""
        special_keys = [
            '"field_updates"', '"section_complete"', '"hidden_content"',
            '"ready_to_play"', '"switch_to_point_buy"', '"suggested_attributes"',
            '"character_complete"', '"data"'
        ]
        result = []
        i = 0
        while i < len(text):
            if text[i] == '{':
                # Find matching closing brace
                depth = 1
                j = i + 1
                while j < len(text) and depth > 0:
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                    j += 1
                # Extract the JSON block
                json_block = text[i:j]
                # Check if it contains any special keys
                if any(key in json_block for key in special_keys):
                    # Skip this JSON block (don't add to result)
                    i = j
                    continue
            result.append(text[i])
            i += 1
        return ''.join(result)

    text = remove_special_json(text)

    # Strip prompt template sections that LLM may echo back
    # These are internal prompt headers that should never appear in output
    text = re.sub(r'##\s*Player Input\s*\n.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'##\s*Conversation History.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'##\s*Required Fields.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'##\s*Currently Saved Fields.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'##\s*Optional Fields.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'##\s*SCOPE BOUNDARIES.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'##\s*CRITICAL:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    # Strip simulated player dialogue and subsequent assistant responses
    # The LLM sometimes generates fake "Player: ..." lines followed by "Assistant: ..."
    # We need to remove all of these simulated conversations
    text = re.sub(r'\n\s*Player:.*?(?=\n\s*Player:|\n\s*$|$)', '', text, flags=re.DOTALL)
    # Also strip "Assistant:" prefixes that appear after simulated player turns
    text = re.sub(r'\n\s*Assistant:\s*', '\n\n', text)

    # SAFETY NET: Strip any hidden backstory that leaked into narrative
    # The hidden_backstory should ONLY be in the JSON, never shown to player
    text = re.sub(r'(?i)Hidden Backstory[^:]*:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'(?i)Secret[^:]*:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'(?i)GM Note[^:]*:.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    # Strip "Unknown to X, ..." pattern that reveals secrets
    text = re.sub(r'(?i)\n\s*Unknown to \w+,.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)

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

            # Also try extracting name from conversation history (when AI uses name but forgets JSON)
            if not state.name:
                extracted_name = _extract_name_from_history(state.conversation_history)
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

            # Create starting equipment with context-aware condition
            starting_items = _create_starting_equipment(
                db=db,
                game_session=game_session,
                entity=entity,
                schema=schema,
                backstory=background or "",
                starting_scene="",  # Could be passed from game start
            )

            # Create character preferences with defaults
            _create_character_preferences(db, game_session, entity)

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


# ==================== Wizard Mode Implementation ====================


def _load_wizard_template(section_name: str) -> str:
    """Load a wizard section prompt template.

    Args:
        section_name: Name of the section (e.g., "name", "appearance").

    Returns:
        Template string, or empty string if not found.
    """
    template_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "templates"
        / "wizard"
        / f"wizard_{section_name}.md"
    )
    if template_path.exists():
        return template_path.read_text()
    return ""


def _parse_wizard_response(response: str) -> tuple[dict | None, dict | None, bool]:
    """Parse AI response for field updates and section completion.

    Args:
        response: AI response text.

    Returns:
        Tuple of (field_updates dict, section_data dict, section_complete bool).
    """
    field_updates = None
    section_data = None
    section_complete = False

    # Look for field_updates JSON (code-fenced first, then raw)
    field_match = re.search(
        r'```json\s*\n?\s*\{["\']?field_updates["\']?\s*:\s*(\{[^}]+\})\s*\}\s*```',
        response,
        re.DOTALL,
    )
    if not field_match:
        # Fallback: raw JSON
        field_match = re.search(
            r'\{["\']?field_updates["\']?\s*:\s*(\{[^}]+\})\s*\}',
            response,
            re.DOTALL,
        )
    if field_match:
        try:
            field_updates = json.loads(field_match.group(1))
        except json.JSONDecodeError:
            pass

    # Look for section_complete (with or without code fences)
    if re.search(r'["\']?section_complete["\']?\s*:\s*true', response, re.IGNORECASE):
        section_complete = True

        # Try to extract data - code-fenced JSON first
        data_match = re.search(
            r'```json\s*\n?\s*(\{[^`]+\})\s*```',
            response,
            re.DOTALL,
        )
        if data_match:
            try:
                parsed = json.loads(_strip_json_comments(data_match.group(1)))
                section_data = parsed.get("data", {})
            except json.JSONDecodeError:
                pass
        else:
            # Fallback: raw JSON - find objects with one level of nesting
            for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response):
                try:
                    obj = json.loads(match.group())
                    if obj.get('section_complete') is True:
                        section_data = obj.get('data', {})
                        break
                except json.JSONDecodeError:
                    continue

    return field_updates, section_data, section_complete


def _extract_missing_appearance_fields(response: str, updates: dict) -> dict:
    """Fallback: extract appearance fields from narrative if missing from JSON.

    The LLM sometimes mentions appearance details in narrative but forgets to
    include them in the field_updates JSON. This function extracts common
    fields like eye_color and hair_color from the narrative text.

    Args:
        response: AI response text (narrative).
        updates: The field_updates dict from JSON parsing.

    Returns:
        Updated dict with any extracted fields added.
    """
    if updates is None:
        updates = {}

    # Words that shouldn't be captured as colors
    skip_words = {'the', 'his', 'her', 'their', 'your', 'my', 'with', 'and', 'a', 'an'}

    # Extract eye_color if missing
    if "eye_color" not in updates:
        # Patterns for eye color in narrative
        eye_patterns = [
            r'\b([\w-]+)\s+eyes\b',  # "hazel eyes", "green eyes"
            r'\beyes\s+(?:are|were|of)\s+([\w-]+)',  # "eyes are green"
            r'\b([\w-]+)-eyed\b',  # "green-eyed"
        ]
        for pattern in eye_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                color = match.group(1).strip()
                if color.lower() not in skip_words:
                    updates["eye_color"] = color
                    break

    # Extract hair_color if missing
    if "hair_color" not in updates:
        hair_patterns = [
            r'\b([\w-]+)\s+hair\b',  # "brown hair", "black hair"
            r'\bhair\s+(?:is|was|of)\s+([\w-]+)',  # "hair is brown"
        ]
        for pattern in hair_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                color = match.group(1).strip()
                if color.lower() not in skip_words:
                    updates["hair_color"] = color
                    break

    return updates


async def _run_section_conversation(
    wizard_state: CharacterWizardState,
    section_name: WizardSectionName,
    schema: SettingSchema,
    session_id: int | None = None,
) -> bool:
    """Run a conversation loop for a single wizard section.

    Args:
        wizard_state: The overall wizard state.
        section_name: Which section to run.
        schema: Setting schema.
        session_id: Optional session ID for logging.

    Returns:
        True if section completed successfully, False if cancelled.
    """
    from rich.panel import Panel

    from src.llm.factory import get_cheap_provider
    from src.llm.message_types import Message, MessageRole
    from src.cli.display import (
        display_section_header,
        display_section_complete,
        display_ai_message,
        prompt_ai_input,
    )

    provider = get_cheap_provider()
    section = wizard_state.sections[section_name]
    section.status = "in_progress"

    # Load template
    template = _load_wizard_template(section_name.value)
    if not template:
        display_error(f"Template not found for section: {section_name.value}")
        return False

    # Display section header
    title = WIZARD_SECTION_TITLES.get(section_name, section_name.value.title())
    display_section_header(title)

    # Display current value for content-heavy sections when revisiting
    char = wizard_state.character
    if section_name == WizardSectionName.BACKGROUND and char.background:
        console.print("[dim]Current background:[/dim]")
        console.print(Panel(char.background, style="dim", padding=(0, 1)))
        console.print()
    elif section_name == WizardSectionName.PERSONALITY and char.personality_notes:
        console.print("[dim]Current personality:[/dim]")
        console.print(Panel(char.personality_notes, style="dim", padding=(0, 1)))
        console.print()

    # Build species list with their available genders
    available_species_with_genders = "Human (Male, Female)"  # Default
    if hasattr(schema, 'species') and schema.species:
        species_lines = []
        for sp in schema.species:
            # SpeciesDefinition has .name and .genders attributes
            genders_str = ", ".join(sp.genders)
            species_lines.append(f"- {sp.name}: {genders_str}")
        available_species_with_genders = "\n".join(species_lines)

    # Section-specific context preparation
    extra_context = {}

    if section_name == WizardSectionName.NAME:
        # Show what name/appearance fields have been saved so far
        char = wizard_state.character
        appearance_fields = []
        for field, label in [
            ("name", "Name"),
            ("age", "Age"),
            ("build", "Build"),
            ("hair_color", "Hair color"),
            ("eye_color", "Eye color"),
            ("height", "Height"),
            ("hair_style", "Hair style"),
            ("skin_tone", "Skin tone"),
        ]:
            value = getattr(char, field, None)
            if value:
                appearance_fields.append(f"- {label}: {value} [SAVED]")
            else:
                is_required = field in ["name", "age", "build", "hair_color", "eye_color"]
                marker = "[REQUIRED - NOT YET SAVED]" if is_required else "[optional]"
                appearance_fields.append(f"- {label}: {marker}")

        extra_context["current_appearance_fields"] = "\n".join(appearance_fields)

    elif section_name == WizardSectionName.ATTRIBUTES:
        # For attributes, we need to roll potential and calculate current
        from src.services.attribute_calculator import (
            roll_potential_stats,
            calculate_current_stats,
            AttributeCalculator,
            infer_build_from_stats,
        )

        # Roll potential if not already done
        if wizard_state.potential_stats is None:
            potential = roll_potential_stats()
            wizard_state.potential_stats = potential.to_dict()

        # Calculate current stats
        current = calculate_current_stats(
            potential=wizard_state.potential_stats,
            age=wizard_state.character.age or 25,
            occupation=wizard_state.occupation or "commoner",
            occupation_years=wizard_state.occupation_years,
            lifestyles=wizard_state.lifestyles,
        )

        # Store calculated attributes
        wizard_state.character.attributes = current.to_dict()

        # Auto-derive build from physical stats if not already set
        if not wizard_state.character.build:
            wizard_state.character.build = infer_build_from_stats(current)

        # Get twist narratives
        twists = AttributeCalculator.get_twist_narrative(
            current, wizard_state.occupation or "commoner"
        )

        # Format for template
        attrs_display = "\n".join(
            f"- {name.title()}: {value}"
            for name, value in current.to_dict().items()
        )
        attrs_narrative = f"Based on {wizard_state.character.name}'s background as a {wizard_state.occupation or 'commoner'}, these attributes reflect their life experience."
        twist_text = "\n".join(f"- {stat}: {text}" for stat, text in twists.items()) if twists else "No significant twists."

        extra_context = {
            "attributes_display": attrs_display,
            "attributes_narrative": attrs_narrative,
            "twist_narratives": twist_text,
            "attributes_json": json.dumps(current.to_dict()),
        }

    # Initial greeting for new sections
    if not section.conversation_history:
        initial_prompt = template.format(
            setting_name=schema.name,
            setting_description=f"{schema.name.title()} setting",
            completed_data_summary=wizard_state.get_completed_data_summary(),
            available_species_with_genders=available_species_with_genders,
            section_conversation_history="[First turn - greet the player]",
            player_input="[Starting section]",
            **extra_context,
        )

        try:
            messages = [Message(role=MessageRole.USER, content=initial_prompt)]
            response = await provider.complete(messages)
            display_ai_message(_strip_json_blocks(response.content))
            section.conversation_history.append(f"Assistant: {response.content}")
        except Exception as e:
            display_error(f"AI error: {e}")
            return False

    # Conversation loop
    max_turns = 10
    pending_confirmation = False  # Track if we're waiting for user to accept auto-filled values
    for turn in range(max_turns):
        player_input = prompt_ai_input()

        if player_input.lower() in ("quit", "exit", "cancel", "back", "menu"):
            display_info("Returning to menu...")
            return False

        # Check if user is accepting auto-filled values
        if pending_confirmation:
            acceptance_patterns = (
                "ok", "okay", "yes", "y", "sure", "accept", "good", "fine",
                "looks good", "that's good", "that works", "perfect", "great",
                "sounds good", "yep", "yeah", "correct", "right", "confirm",
            )
            if player_input.lower().strip() in acceptance_patterns:
                # User accepted - complete the section without going to LLM
                section.status = "complete"
                display_section_complete(title)
                return True
            # User provided different input - reset flag and continue to LLM
            pending_confirmation = False

        section.conversation_history.append(f"Player: {player_input}")

        # Update name/appearance fields context (so AI sees latest saved state)
        if section_name == WizardSectionName.NAME:
            char = wizard_state.character
            appearance_fields = []
            for field, label in [
                ("name", "Name"),
                ("age", "Age"),
                ("build", "Build"),
                ("hair_color", "Hair color"),
                ("eye_color", "Eye color"),
                ("height", "Height"),
                ("hair_style", "Hair style"),
                ("skin_tone", "Skin tone"),
            ]:
                value = getattr(char, field, None)
                if value:
                    appearance_fields.append(f"- {label}: {value} [SAVED]")
                else:
                    is_required = field in ["name", "age", "build", "hair_color", "eye_color"]
                    marker = "[REQUIRED - NOT YET SAVED]" if is_required else "[optional]"
                    appearance_fields.append(f"- {label}: {marker}")
            extra_context["current_appearance_fields"] = "\n".join(appearance_fields)

        # Build prompt
        prompt = template.format(
            setting_name=schema.name,
            setting_description=f"{schema.name.title()} setting",
            completed_data_summary=wizard_state.get_completed_data_summary(),
            available_species_with_genders=available_species_with_genders,
            section_conversation_history="\n".join(section.conversation_history[-8:]),
            player_input=player_input,
            **extra_context,
        )

        try:
            messages = [Message(role=MessageRole.USER, content=prompt)]
            response = await provider.complete(messages)
            ai_response = response.content

            section.conversation_history.append(f"Assistant: {ai_response}")

            # Parse response
            field_updates, section_data, section_complete = _parse_wizard_response(ai_response)

            # Display response (without JSON)
            display_ai_message(_strip_json_blocks(ai_response))

            # Check for reroll_attributes request (ATTRIBUTES section only)
            if section_name == WizardSectionName.ATTRIBUTES:
                if re.search(r'["\']?reroll_attributes["\']?\s*:\s*true', ai_response, re.IGNORECASE):
                    # Clear potential stats to trigger fresh roll on next iteration
                    wizard_state.potential_stats = None
                    wizard_state.character.attributes = None
                    wizard_state.character.build = None
                    console.print("[dim cyan]Rolling new attributes...[/dim cyan]")
                    continue  # Re-enter section to trigger fresh calculation

            # Capture what fields are already saved BEFORE applying any updates
            # This is needed to detect if this response introduces new values
            already_saved = set()
            requirements = WIZARD_SECTION_REQUIREMENTS.get(section_name, [])
            for field_name in requirements:
                value = getattr(wizard_state.character, field_name, None)
                if value is not None and value != "":
                    already_saved.add(field_name)

            # Apply field updates
            if field_updates:
                # For NAME section, extract appearance fields from narrative as fallback
                # (LLM sometimes mentions eye/hair color but forgets to include in JSON)
                if section_name == WizardSectionName.NAME:
                    field_updates = _extract_missing_appearance_fields(ai_response, field_updates)
                _apply_wizard_field_updates(wizard_state, section_name, field_updates)
                captured = ", ".join(field_updates.keys())
                console.print(f"[dim green]Saved: {captured}[/dim green]")

            # Handle section completion
            if section_complete:

                if section_data:
                    _apply_wizard_section_data(wizard_state, section_name, section_data)

                # Validate that all required fields are actually filled
                if section.is_complete(wizard_state.character):
                    # Check if section_data introduced new values without user confirmation
                    newly_added = []
                    for field_name in requirements:
                        if field_name not in already_saved:
                            value = getattr(wizard_state.character, field_name, None)
                            if value is not None and value != "":
                                newly_added.append(f"{field_name}={value}")

                    # For content-heavy sections (BACKGROUND, PERSONALITY), always require
                    # confirmation even if the field was saved in a previous turn
                    content_sections = {
                        WizardSectionName.BACKGROUND,
                        WizardSectionName.PERSONALITY,
                    }
                    if section_name in content_sections and not newly_added:
                        # Field was previously saved, still require confirmation
                        console.print(
                            "[dim]Say 'ok' to confirm, or provide changes[/dim]"
                        )
                        pending_confirmation = True
                        continue

                    if newly_added:
                        # LLM snuck in values without asking - show them and ask for confirmation
                        console.print(
                            f"[yellow]Auto-filled: {', '.join(newly_added)}[/yellow]"
                        )
                        console.print(
                            "[dim]Say 'ok' to accept, or provide different values[/dim]"
                        )
                        pending_confirmation = True  # Track that we're waiting for user acceptance
                        continue  # Don't mark complete, let user confirm

                    section.status = "complete"
                    display_section_complete(title)
                    return True
                else:
                    # AI said complete but required fields are missing
                    missing = section.get_missing_fields(wizard_state.character)
                    if missing:
                        console.print(
                            f"[yellow]Still need: {', '.join(missing)}[/yellow]"
                        )

        except Exception as e:
            display_error(f"AI error: {e}")
            continue

    # Max turns reached
    display_info("Section taking too long. Returning to menu...")
    return False


def _apply_wizard_field_updates(
    wizard_state: CharacterWizardState,
    section_name: WizardSectionName,
    updates: dict,
) -> None:
    """Apply field updates from AI response to wizard state.

    Args:
        wizard_state: Wizard state to update.
        section_name: Current section.
        updates: Dict of field_name -> value.
    """
    char = wizard_state.character

    # Map field names to character state
    field_mapping = {
        "name": "name",
        "species": "species",
        "age": "age",
        "gender": "gender",
        "build": "build",
        "hair_color": "hair_color",
        "hair_style": "hair_style",
        "eye_color": "eye_color",
        "skin_tone": "skin_tone",
        "background": "background",
        "personality_notes": "personality_notes",
    }

    for key, value in updates.items():
        if key in field_mapping:
            setattr(char, field_mapping[key], value)
        elif key == "attributes" and isinstance(value, dict):
            char.attributes = value
        elif key == "occupation":
            wizard_state.occupation = value
        elif key == "occupation_years":
            wizard_state.occupation_years = value
        elif key == "lifestyles" and isinstance(value, list):
            wizard_state.lifestyles = value


def _apply_wizard_section_data(
    wizard_state: CharacterWizardState,
    section_name: WizardSectionName,
    data: dict,
) -> None:
    """Apply section completion data to wizard state.

    Args:
        wizard_state: Wizard state to update.
        section_name: Completed section.
        data: Section data dict from AI.
    """
    char = wizard_state.character

    # Apply all fields from data
    for key, value in data.items():
        if key == "hidden_backstory":
            char.hidden_backstory = value
        elif key == "occupation":
            wizard_state.occupation = value
        elif key == "occupation_years":
            wizard_state.occupation_years = value
        elif key == "lifestyles" and isinstance(value, list):
            wizard_state.lifestyles = value
        elif key == "attributes" and isinstance(value, dict):
            char.attributes = value
        elif hasattr(char, key):
            setattr(char, key, value)


async def _wizard_character_creation_async(
    schema: SettingSchema,
    session_id: int | None = None,
) -> CharacterWizardState | None:
    """Run the wizard-based character creation flow.

    Args:
        schema: Setting schema.
        session_id: Optional session ID for logging.

    Returns:
        CharacterWizardState with completed character, or None if cancelled.
    """
    from src.cli.display import (
        display_character_wizard_menu,
        prompt_wizard_section_choice,
        display_character_review,
        prompt_review_confirmation,
    )

    # Set audit context
    set_audit_context(session_id=session_id, call_type="character_wizard")

    # Initialize wizard state
    wizard_state = CharacterWizardState()

    console.print("\n[bold magenta]Character Creation Wizard[/bold magenta]")
    console.print("[dim]Complete each section to create your character.[/dim]")
    console.print("[dim]Type 'back' or 'menu' during any section to return here.[/dim]\n")

    while True:
        # Build section statuses
        statuses = {
            section.value: wizard_state.get_section_status(section)
            for section in WIZARD_SECTION_ORDER
        }
        titles = {
            section.value: title
            for section, title in WIZARD_SECTION_TITLES.items()
        }
        order = [section.value for section in WIZARD_SECTION_ORDER]

        # Build section accessibility
        accessible = {
            section.value: wizard_state.is_section_accessible(section)
            for section in WIZARD_SECTION_ORDER
        }

        # Display menu with accessibility info
        display_character_wizard_menu(statuses, titles, order, accessible)

        # Check if ready for review
        can_review = wizard_state.is_ready_for_review()

        # Get user choice
        choice = prompt_wizard_section_choice(order, can_review)

        if choice == 'q':
            display_info("Character creation cancelled.")
            return None

        # Convert choice to section name
        section_idx = choice - 1 if isinstance(choice, int) else len(order) - 1
        section_name = WIZARD_SECTION_ORDER[section_idx]

        # Check if section is accessible (prerequisites complete)
        if not wizard_state.is_section_accessible(section_name):
            display_error("Complete previous sections first.")
            continue

        # Handle review section
        if section_name == WizardSectionName.REVIEW:
            if not can_review:
                display_error("Complete all sections before review.")
                continue

            # Show character review
            char = wizard_state.character
            hair_desc = char.hair_color
            if char.hair_style:
                hair_desc = f"{char.hair_style} {char.hair_color}"

            display_character_review(
                name=char.name or "Unknown",
                species=char.species,
                age=char.age,
                gender=char.gender,
                build=char.build,
                hair_description=hair_desc,
                eye_color=char.eye_color,
                background=char.background,
                occupation=wizard_state.occupation,
                personality=char.personality_notes,
                attributes=char.attributes,
            )

            # Confirm or edit
            result = prompt_review_confirmation()
            if result == 'confirm':
                wizard_state.character.confirmed = True
                console.print("\n[bold green]Character creation complete![/bold green]")
                return wizard_state
            elif result == 'quit':
                display_info("Character creation cancelled.")
                return None
            # 'edit' continues the loop

        else:
            # Run section conversation
            completed = await _run_section_conversation(
                wizard_state=wizard_state,
                section_name=section_name,
                schema=schema,
                session_id=session_id,
            )

            if completed:
                # Auto-advance to next section if appropriate
                next_section = wizard_state.get_next_incomplete_section()
                if next_section and next_section != WizardSectionName.REVIEW:
                    console.print(f"[dim]Moving to next section: {WIZARD_SECTION_TITLES[next_section]}[/dim]")


def wizard_character_creation(
    schema: SettingSchema,
    session_id: int | None = None,
) -> CharacterWizardState | None:
    """Synchronous wrapper for wizard character creation.

    Args:
        schema: Setting schema.
        session_id: Optional session ID for logging.

    Returns:
        CharacterWizardState with completed character, or None if cancelled.
    """
    import asyncio
    return asyncio.run(_wizard_character_creation_async(schema, session_id))
