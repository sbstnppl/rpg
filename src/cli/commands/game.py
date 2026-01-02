"""Game commands including the main game loop."""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.cli.display import (
    display_error,
    display_game_wizard_welcome,
    display_info,
    display_narrative,
    display_ooc_response,
    display_starting_equipment,
    display_success,
    display_welcome,
    progress_spinner,
    prompt_input,
    prompt_session_name,
    prompt_setting_choice,
)
from src.database.connection import get_db_session
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession, Turn
from src.database.models.world import TimeState

app = typer.Typer(help="Game commands")
console = Console()

# Action command patterns - explicit slash commands that trigger validation
ACTION_COMMANDS: dict[str, str] = {
    "go": r"^/go\s+(.+)$",
    "take": r"^/take\s+(.+)$",
    "drop": r"^/drop\s+(.+)$",
    "give": r"^/give\s+(.+)\s+to\s+(.+)$",
    "attack": r"^/attack\s+(.+)$",
}

# Natural language intent patterns - same actions without slash prefix
INTENT_PATTERNS: list[tuple[str, str]] = [
    (r"\b(pick up|take|grab|get)\s+(?:the\s+)?(.+)", "take"),
    (r"\b(go|walk|head|move|travel)\s+(?:to|towards?|into)\s+(?:the\s+)?(.+)", "go"),
    (r"\b(drop|put down|set down|leave)\s+(?:the\s+)?(.+)", "drop"),
    (r"\b(give|hand)\s+(?:the\s+)?(.+?)\s+to\s+(.+)", "give"),
    (r"\b(attack|hit|strike|fight)\s+(?:the\s+)?(.+)", "attack"),
]

# Quantum pipeline progress phases
NODE_PROGRESS_MESSAGES: dict[str, str] = {
    "quantum_match": "Checking prepared outcomes...",
    "quantum_generate": "Generating narrative...",
    "quantum_collapse": "Rolling dice...",
    "quantum_anticipate": "Preparing for next actions...",
}


def _detect_action(player_input: str) -> tuple[str | None, str | None, str | None]:
    """Detect action from command or natural language.

    Args:
        player_input: The raw player input string.

    Returns:
        Tuple of (action_type, target, secondary_target).
        - action_type: "go", "take", "drop", "give", "attack", or None
        - target: The primary target of the action
        - secondary_target: For 'give', the recipient (NPC name)
    """
    # Check explicit slash commands first
    for action, pattern in ACTION_COMMANDS.items():
        if match := re.match(pattern, player_input, re.IGNORECASE):
            if action == "give":
                return action, match.group(1), match.group(2)
            return action, match.group(1), None

    # Try natural language patterns
    for pattern, action in INTENT_PATTERNS:
        if match := re.search(pattern, player_input, re.IGNORECASE):
            if action == "give":
                # Pattern: give <item> to <recipient>
                return action, match.group(2), match.group(3)
            elif action in ("take", "drop", "attack"):
                # Pattern: verb <target>
                return action, match.group(2), None
            else:
                # Pattern: verb (to|towards) <target>
                return action, match.group(2), None

    return None, None, None


async def _validate_and_enhance_input(
    db, game_session, player, player_input: str, player_location: str
) -> tuple[str, str | None]:
    """Pre-validate player action and enhance input for GM.

    For mechanical actions (take, drop, go, attack), this validates constraints
    before passing to the GM. If invalid, returns an error for immediate feedback.
    If valid, enhances the input with validation context for the GM.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        player_input: Raw player input.
        player_location: Current player location key.

    Returns:
        Tuple of (enhanced_input, error_message).
        - If valid: enhanced_input has validation context, error is None
        - If invalid: enhanced_input is original, error has feedback for player
    """
    from src.managers.item_manager import ItemManager

    action_type, target, secondary = _detect_action(player_input)

    if action_type is None:
        # Not a mechanical action, pass through to GM unchanged
        return player_input, None

    if action_type == "take":
        item_mgr = ItemManager(db, game_session)

        # Check if player can carry more weight (estimate 1 lb for unknown items)
        # The GM/acquire_item tool will do the real validation
        if not item_mgr.can_carry_weight(player.id, additional_weight=1.0):
            return player_input, "You're carrying too much weight already. Drop something first."

        # Check if there's an available slot
        available_slot = item_mgr.find_available_slot(player.id, "misc", "medium")
        if available_slot is None:
            return player_input, "Your hands and pockets are full. Drop or stow something first."

        # Valid - add context for GM
        return f"[VALIDATED: pickup '{target}'] {player_input}", None

    elif action_type == "drop":
        item_mgr = ItemManager(db, game_session)

        # Check if player has the item
        inventory = item_mgr.get_inventory(player.id)
        target_lower = target.lower().strip()

        matching_items = [
            item for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key
        ]

        if not matching_items:
            return player_input, f"You don't have '{target}' to drop."

        # Valid - add context with item key for GM
        item = matching_items[0]
        return f"[VALIDATED: drop '{item.item_key}'] {player_input}", None

    elif action_type == "go":
        # For movement, we pass through with context
        # The GM will use entity_move tool which handles location creation
        return f"[VALIDATED: move to '{target}'] {player_input}", None

    elif action_type == "give":
        if not secondary:
            return player_input, "Give what to whom? Try: /give <item> to <recipient>"

        item_mgr = ItemManager(db, game_session)

        # Check if player has the item
        inventory = item_mgr.get_inventory(player.id)
        target_lower = target.lower().strip()

        matching_items = [
            item for item in inventory
            if target_lower in item.display_name.lower()
            or target_lower == item.item_key
        ]

        if not matching_items:
            return player_input, f"You don't have '{target}' to give."

        # Valid - add context
        item = matching_items[0]
        return f"[VALIDATED: give '{item.item_key}' to '{secondary}'] {player_input}", None

    elif action_type == "attack":
        # For attack, pass through with context
        # Combat initiation happens through start_combat tool
        return f"[VALIDATED: attack '{target}'] {player_input}", None

    # Unknown action type - pass through
    return player_input, None


def _get_active_session(db) -> GameSession | None:
    """Get the most recent active session."""
    return (
        db.query(GameSession)
        .filter(GameSession.status == "active")
        .order_by(GameSession.id.desc())
        .first()
    )


def _get_player(db, game_session: GameSession) -> Entity | None:
    """Get the player entity for the session, or None if not created."""
    return (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )


def _get_last_turn(db, session_id: int) -> Turn | None:
    """Get the most recent turn for a session.

    Args:
        db: Database session.
        session_id: The game session ID.

    Returns:
        The most recent Turn record, or None if no turns exist.
    """
    return (
        db.query(Turn)
        .filter(Turn.session_id == session_id)
        .order_by(Turn.turn_number.desc())
        .first()
    )


def _get_player_current_location(
    player: Entity,
    fallback: str | None = None,
) -> str:
    """Get player's current location from database.

    Reads from npc_extension.current_location (set by UPDATE_LOCATION delta),
    falling back to provided fallback or "starting_location".

    Args:
        player: Player entity with npc_extension loaded.
        fallback: Optional fallback location key.

    Returns:
        Current location key.
    """
    # First try npc_extension.current_location (updated by deltas)
    if player.npc_extension and player.npc_extension.current_location:
        return player.npc_extension.current_location

    # Fallback to provided value or default
    return fallback or "starting_location"


def _get_available_settings() -> list[dict]:
    """Get list of available settings with descriptions.

    Scans the data/settings directory for JSON files.

    Returns:
        List of dicts with 'key', 'name', 'description'.
    """
    settings_dir = Path(__file__).parent.parent.parent.parent / "data" / "settings"
    settings = []

    if settings_dir.exists():
        for json_file in sorted(settings_dir.glob("*.json")):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    settings.append({
                        "key": data.get("name", json_file.stem),
                        "name": data.get("name", json_file.stem).title(),
                        "description": data.get("description", "No description available."),
                    })
            except (json.JSONDecodeError, KeyError):
                continue

    # Fallback if no JSON files found
    if not settings:
        settings = [
            {
                "key": "fantasy",
                "name": "Fantasy",
                "description": "Swords, magic, and medieval adventure.",
            }
        ]

    return settings


@app.command()
def start(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Session name"),
    setting: Optional[str] = typer.Option(None, "--setting", help="Setting (fantasy, contemporary, scifi)"),
    wizard: bool = typer.Option(True, "--wizard/--conversational", help="Use wizard mode (default) or conversational AI"),
    auto: bool = typer.Option(False, "--auto", help="Auto-setup with test defaults (for testing)"),
) -> None:
    """Start a new game with guided setup wizard.

    Creates a new session and guides you through character creation
    in one seamless flow, then starts the game.

    Use --conversational for the old freeform AI character creation style.
    Use --auto to skip all prompts and create a test session (for testing).
    """
    try:
        asyncio.run(_start_wizard_async(name, setting, use_wizard=wizard, auto=auto))
    except KeyboardInterrupt:
        display_info("\nWizard cancelled. No changes were saved.")


def _create_auto_character_state() -> "CharacterCreationState":
    """Create a pre-populated character state for auto mode testing.

    Returns:
        A complete CharacterCreationState with test defaults.
    """
    from src.cli.commands.character import CharacterCreationState

    return CharacterCreationState(
        name="Test Hero",
        species="Human",
        gender="Male",
        age=25,
        build="Average",
        height="5'10\"",
        hair_color="Brown",
        hair_style="Short",
        eye_color="Brown",
        skin_tone="Fair",
        attributes={
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        },
        background="A wandering adventurer seeking fortune and glory in the realm.",
        personality_notes="Curious and brave, always ready for adventure.",
        confirmed=True,
        conversation_history=["[Auto-generated test character]"],
    )


def _create_auto_world(
    db: "Session",
    game_session: "GameSession",
    player: "Entity",
) -> str:
    """Create minimal starter world for --auto sessions.

    Creates a small village with tavern, square, and market - enough to test
    the GM pipeline and anticipation system.

    Args:
        db: Database session.
        game_session: The game session to populate.
        player: The player entity.

    Returns:
        The starting location key.
    """
    from src.managers.location_manager import LocationManager
    from src.managers.entity_manager import EntityManager
    from src.database.models.enums import EntityType
    from src.database.models.entities import NPCExtension

    loc_mgr = LocationManager(db, game_session)
    ent_mgr = EntityManager(db, game_session)

    # Create locations with exits via spatial_layout
    loc_mgr.create_location(
        location_key="village_tavern",
        display_name="The Rusty Tankard",
        description="A cozy village tavern with worn wooden tables and a crackling fireplace. The bar runs along the back wall, lined with stools.",
        category="tavern",
        atmosphere="Warm firelight flickers across the room. The smell of ale and roasted meat fills the air.",
        spatial_layout={"exits": ["village_square"]},
    )

    loc_mgr.create_location(
        location_key="village_square",
        display_name="Village Square",
        description="The central square of a small village, with a stone well at its center. Cobblestones worn smooth by generations of footsteps.",
        category="outdoor",
        atmosphere="Villagers go about their daily business under the open sky.",
        spatial_layout={"exits": ["village_tavern", "village_market"]},
    )

    loc_mgr.create_location(
        location_key="village_market",
        display_name="Market Stalls",
        description="A row of merchant stalls selling various wares and supplies. Colorful awnings shade the goods from the sun.",
        category="market",
        atmosphere="Vendors call out their wares while customers haggle over prices.",
        spatial_layout={"exits": ["village_square"]},
    )

    # Create NPCs with EntityManager + NPCExtension
    innkeeper = ent_mgr.create_entity(
        entity_key="innkeeper_tom",
        display_name="Old Tom",
        entity_type=EntityType.NPC,
        occupation="Innkeeper",
    )
    tom_ext = NPCExtension(
        entity_id=innkeeper.id,
        current_location="village_tavern",
        home_location="village_tavern",
        current_activity="wiping down the bar",
        current_mood="friendly",
    )
    db.add(tom_ext)

    merchant = ent_mgr.create_entity(
        entity_key="merchant_anna",
        display_name="Anna",
        entity_type=EntityType.NPC,
        occupation="Merchant",
    )
    anna_ext = NPCExtension(
        entity_id=merchant.id,
        current_location="village_market",
        home_location="village_market",
        current_activity="arranging goods on display",
        current_mood="busy",
    )
    db.add(anna_ext)

    # Set player's starting location
    ent_mgr.update_location(player.entity_key, "village_tavern")

    db.flush()
    return "village_tavern"


async def _start_wizard_async(
    preset_name: str | None = None,
    preset_setting: str | None = None,
    use_wizard: bool = True,
    auto: bool = False,
) -> None:
    """Run the full game start wizard.

    Guides through session setup, character creation, and starts the game.

    Args:
        preset_name: Optional preset session name (skips prompt).
        preset_setting: Optional preset setting (skips prompt).
        use_wizard: If True, use step-by-step wizard; if False, use conversational AI.
        auto: If True, skip all prompts and use test defaults.
    """
    from src.cli.commands.character import (
        CharacterCreationState,
        CharacterWizardState,
        _ai_character_creation_async,
        _wizard_character_creation_async,
        _create_character_records,
        _create_starting_equipment,
        _create_character_preferences,
        _extract_world_data,
        _create_world_from_extraction,
        _infer_gameplay_fields,
        _create_inferred_records,
    )
    from src.schemas.settings import get_setting_schema
    from src.llm.audit_logger import set_audit_context

    # Auto mode: skip all prompts and use test defaults
    if auto:
        selected_setting = preset_setting or "fantasy"
        session_name = preset_name or "Test Adventure"
        creation_state = _create_auto_character_state()
        potential_stats = None
        occupation = None
        occupation_years = None
        console.print(f"[dim]Auto-creating '{session_name}' with test character...[/dim]")
    else:
        # Phase 1: Welcome and Session Setup
        display_game_wizard_welcome()

        # Get available settings
        available_settings = _get_available_settings()

        # Select setting
        if preset_setting and any(s["key"] == preset_setting for s in available_settings):
            selected_setting = preset_setting
        else:
            selected_setting = prompt_setting_choice(available_settings, default="fantasy")

        # Get session name
        if preset_name:
            session_name = preset_name
        else:
            session_name = prompt_session_name(default="New Adventure")

        console.print(f"\n[dim]Creating adventure '{session_name}' in {selected_setting} setting...[/dim]")

        # Phase 2: Character Creation (before DB commit)
        schema = get_setting_schema(selected_setting)

        console.print()  # Spacing before character creation

        # Use wizard or conversational mode
        if use_wizard:
            wizard_state = await _wizard_character_creation_async(schema, session_id=None)
            if wizard_state is None:
                display_info("Character creation cancelled.")
                return
            # Convert wizard state to creation state for compatibility
            creation_state = wizard_state.character
            # Store potential stats and occupation for later
            potential_stats = wizard_state.potential_stats
            occupation = wizard_state.occupation
            occupation_years = wizard_state.occupation_years
        else:
            creation_state = await _ai_character_creation_async(schema, session_id=None)
            potential_stats = None
            occupation = None
            occupation_years = None

        if not creation_state or not creation_state.is_complete():
            display_error("Character creation was not completed.")
            return

    # Get schema for equipment creation
    schema = get_setting_schema(selected_setting)

    # Phase 3: Create all DB records (only after character confirmed)
    with get_db_session() as db:
        # Create game session
        game_session = GameSession(
            session_name=session_name,
            setting=selected_setting,
            status="active",
            total_turns=0,
            llm_provider="anthropic",
            gm_model="claude-sonnet-4-20250514",
        )
        db.add(game_session)
        db.flush()

        # Create time state
        time_state = TimeState(
            session_id=game_session.id,
            current_day=1,
            current_time="09:00",
            day_of_week="Monday",
            season="Spring",
            weather="Clear",
        )
        db.add(time_state)

        # Set audit context now that we have session ID
        set_audit_context(session_id=game_session.id, call_type="game_start")

        # Create character records
        entity = _create_character_records(
            db=db,
            game_session=game_session,
            name=creation_state.name,
            attributes=creation_state.attributes,
            background=creation_state.background or "",
            creation_state=creation_state,
            potential_stats=potential_stats,
            occupation=occupation,
            occupation_years=occupation_years,
        )

        # Create starting equipment
        starting_items = _create_starting_equipment(
            db=db,
            game_session=game_session,
            entity=entity,
            schema=schema,
        )

        # Create character preferences (includes intimacy settings)
        _create_character_preferences(db, game_session, entity)

        starting_location_key = None

        # Skip LLM inference in auto mode for speed
        if not auto:
            # Extract world data (NPCs, locations from backstory)
            console.print("[dim]Extracting world from backstory...[/dim]")
            conversation_history = "\n".join(creation_state.conversation_history)
            world_data = await _extract_world_data(
                character_output=conversation_history,
                character_name=creation_state.name,
                character_background=creation_state.background or "",
                setting_name=selected_setting,
                session_id=game_session.id,
            )
            if world_data:
                starting_location_key = _create_world_from_extraction(db, game_session, entity, world_data)

            # Infer gameplay fields (skills, preferences, modifiers)
            console.print("[dim]Inferring skills and preferences...[/dim]")
            inference = await _infer_gameplay_fields(creation_state, session_id=game_session.id)
            if inference:
                _create_inferred_records(db, game_session, entity, inference)

        db.commit()

        console.print()
        display_success(f"Character '{creation_state.name}' created successfully!")

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

        # Auto mode: create minimal world and exit without game loop
        if auto:
            starting_location = _create_auto_world(db, game_session, entity)
            db.commit()
            display_success(f"Session {game_session.id} ready for testing.")
            display_success(f"Starting location: {starting_location}")
            return

        # Phase 4: Start the game loop directly
        console.print()
        await _game_loop(
            db, game_session, entity,
            initial_location=starting_location_key,
        )


@app.command("list")
def list_games(
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status (active, paused)"),
) -> None:
    """List all games."""
    from rich.table import Table

    with get_db_session() as db:
        query = db.query(GameSession)
        if status:
            query = query.filter(GameSession.status == status)

        sessions = query.order_by(GameSession.id.desc()).all()

        if not sessions:
            console.print("[dim]No games found.[/dim]")
            return

        table = Table(title="Games")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Setting", style="green")
        table.add_column("Player", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Turns", justify="right")

        for s in sessions:
            # Get player name if exists
            player = _get_player(db, s)
            player_name = player.display_name if player else "[dim]-[/dim]"

            status_style = "green" if s.status == "active" else "dim"
            table.add_row(
                str(s.id),
                s.session_name,
                s.setting,
                player_name,
                f"[{status_style}]{s.status}[/{status_style}]",
                str(s.total_turns),
            )

        console.print(table)


@app.command("history")
def history(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID (default: most recent)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of turns to show"),
    order: str = typer.Option("asc", "--order", "-o", help="Sort order: asc or desc"),
    full: bool = typer.Option(False, "--full", "-f", help="Show full text in panel view"),
) -> None:
    """Show turn history for a game session."""
    from rich.panel import Panel
    from rich.table import Table

    with get_db_session() as db:
        # Get session
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = db.query(GameSession).order_by(GameSession.id.desc()).first()

        if not game_session:
            display_error("No game session found")
            raise typer.Exit(1)

        # Query turns
        query = db.query(Turn).filter(Turn.session_id == game_session.id)
        if order.lower() == "desc":
            query = query.order_by(Turn.turn_number.desc())
        else:
            query = query.order_by(Turn.turn_number.asc())
        turns = query.limit(limit).all()

        if not turns:
            display_info(f"No turns found for session '{game_session.session_name}'")
            return

        console.print()

        if full:
            # Panel view - show full text for each turn
            console.print(f"[bold]Turn History - {game_session.session_name}[/bold]")
            console.print()

            for turn in turns:
                # Build header with context
                header_parts = [f"Turn {turn.turn_number}"]
                if turn.game_day_at_turn:
                    header_parts.append(f"Day {turn.game_day_at_turn}")
                if turn.game_time_at_turn:
                    header_parts.append(turn.game_time_at_turn)
                if turn.location_at_turn and turn.location_at_turn not in ("starting_location", "unknown"):
                    location_name = turn.location_at_turn.replace("_", " ").title()
                    header_parts.append(location_name)

                header = " │ ".join(header_parts)

                # Build panel content
                content_lines = [f"[cyan]> {turn.player_input}[/cyan]", ""]
                if turn.gm_response:
                    content_lines.append(turn.gm_response)

                console.print(Panel(
                    "\n".join(content_lines),
                    title=header,
                    border_style="dim",
                ))
                console.print()
        else:
            # Table view - compact with truncation
            table = Table(title=f"Turn History - {game_session.session_name}")
            table.add_column("#", style="cyan", justify="right", width=4)
            table.add_column("Day", style="dim", justify="right", width=4)
            table.add_column("Time", style="dim", width=5)
            table.add_column("Location", style="green", max_width=15)
            table.add_column("Input", style="white", max_width=30)
            table.add_column("Response", style="dim", max_width=50)

            for turn in turns:
                # Truncate text
                input_text = turn.player_input or ""
                if len(input_text) > 28:
                    input_text = input_text[:28] + "..."

                response_text = turn.gm_response or ""
                if len(response_text) > 48:
                    response_text = response_text[:48] + "..."

                # Format location
                location = turn.location_at_turn or ""
                if location in ("starting_location", "unknown"):
                    location = "-"
                elif len(location) > 13:
                    location = location[:13] + "..."
                else:
                    location = location.replace("_", " ").title()

                table.add_row(
                    str(turn.turn_number),
                    str(turn.game_day_at_turn or "-"),
                    turn.game_time_at_turn or "-",
                    location,
                    input_text,
                    response_text,
                )

            console.print(table)

        console.print(f"[dim]Showing {len(turns)} of {game_session.total_turns} turns[/dim]")


@app.command("reset")
def reset_to_turn(
    turn_number: int = typer.Argument(..., help="Turn number to reset to"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID (default: most recent)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Reset game to a specific turn, restoring exact state from snapshot."""
    from rich.panel import Panel

    from src.managers.snapshot_manager import SnapshotManager

    with get_db_session() as db:
        # Get session
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = db.query(GameSession).order_by(GameSession.id.desc()).first()

        if not game_session:
            display_error("No game session found")
            raise typer.Exit(1)

        # Check if snapshot exists
        snapshot_mgr = SnapshotManager(db, game_session)
        snapshot = snapshot_mgr.get_snapshot(turn_number)

        if not snapshot:
            available = snapshot_mgr.get_available_snapshots()
            if available:
                display_error(f"No snapshot for turn {turn_number}")
                display_info(f"Available snapshots: {', '.join(str(t) for t in available)}")
            else:
                display_error("No snapshots available for this session")
                display_info("Snapshots are created during gameplay. Play a few turns first.")
            raise typer.Exit(1)

        if turn_number >= game_session.total_turns:
            display_error(f"Turn {turn_number} is not in the past (current: {game_session.total_turns})")
            raise typer.Exit(1)

        # Get the turn for preview
        turn = db.query(Turn).filter(
            Turn.session_id == game_session.id,
            Turn.turn_number == turn_number
        ).first()

        turns_to_delete = game_session.total_turns - turn_number

        if not force:
            # Show preview
            console.print()
            console.print(f"[bold]Reset to turn {turn_number}?[/bold]")
            console.print()

            if turn:
                # Build header
                header_parts = [f"Turn {turn.turn_number}"]
                if turn.game_day_at_turn:
                    header_parts.append(f"Day {turn.game_day_at_turn}")
                if turn.game_time_at_turn:
                    header_parts.append(turn.game_time_at_turn)
                if turn.location_at_turn and turn.location_at_turn not in ("starting_location", "unknown"):
                    location_name = turn.location_at_turn.replace("_", " ").title()
                    header_parts.append(location_name)

                header = " │ ".join(header_parts)

                # Show turn preview
                input_preview = turn.player_input[:60] + "..." if len(turn.player_input) > 60 else turn.player_input
                response_preview = (turn.gm_response or "")[:80]
                if len(turn.gm_response or "") > 80:
                    response_preview += "..."

                console.print(Panel(
                    f"[cyan]> {input_preview}[/cyan]\n\n[dim]{response_preview}[/dim]",
                    title=header,
                    border_style="dim",
                ))

            console.print()
            console.print(f"[yellow]{turns_to_delete} turns will be deleted.[/yellow]")
            console.print()

            if not typer.confirm("Continue?"):
                display_info("Cancelled")
                return

        # Perform reset
        try:
            snapshot_mgr.restore_snapshot(turn_number)
            db.commit()
            display_success(f"Reset complete. Session now at turn {turn_number}.")
        except Exception as e:
            db.rollback()
            display_error(f"Reset failed: {e}")
            raise typer.Exit(1)


@app.command()
def delete(
    game_id: int = typer.Argument(..., help="Game ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a game and all its data."""
    try:
        with get_db_session() as db:
            game_session = db.query(GameSession).filter(GameSession.id == game_id).first()

            if not game_session:
                display_error(f"Game {game_id} not found")
                raise typer.Exit(1)

            if not force:
                confirm = typer.confirm(
                    f"Delete game '{game_session.session_name}' (ID: {game_id})?"
                )
                if not confirm:
                    display_info("Cancelled")
                    return

            db.delete(game_session)
            display_success(f"Deleted game '{game_session.session_name}'")

    except typer.Exit:
        raise
    except Exception as e:
        display_error(f"Failed to delete game: {e}")
        raise typer.Exit(1)


@app.command()
def play(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    roll_mode: str = typer.Option(
        "auto",
        "--roll-mode",
        "-r",
        help="Roll mode: 'auto' (background) or 'manual' (player rolls)",
    ),
    anticipation: Optional[bool] = typer.Option(
        None,
        "--anticipation/--no-anticipation",
        help="Enable/disable anticipatory pre-generation (default: from config)",
    ),
    ref_based: bool = typer.Option(
        False,
        "--ref-based",
        help="Use ref-based architecture (A/B/C refs for entity disambiguation)",
    ),
) -> None:
    """Start the interactive game loop using the quantum branching pipeline."""
    # Determine anticipation setting
    from src.config import get_settings
    settings = get_settings()
    use_anticipation = anticipation if anticipation is not None else settings.anticipation_enabled

    # Validate roll mode
    if roll_mode not in ("auto", "manual"):
        display_error(f"Invalid roll mode: {roll_mode}. Use 'auto' or 'manual'.")
        raise typer.Exit(1)

    # First check for session and player
    game_session_id = None
    needs_character = False

    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            display_info("Use 'rpg session start' to create one")
            raise typer.Exit(1)

        game_session_id = game_session.id
        player = _get_player(db, game_session)

        if not player:
            needs_character = True

    # Handle character creation outside the db context
    if needs_character:
        display_info("No character found for this session.")
        choice = console.input("[bold cyan]Create a character now? (y/n): [/bold cyan]").strip().lower()

        if choice in ("y", "yes"):
            from src.cli.commands.character import create as create_character
            create_character(session_id=game_session_id, random_stats=False, ai_assisted=True)
        else:
            display_info("Use 'rpg character create' to create a character first")
            raise typer.Exit(0)

    # Now run the game loop with a fresh db session
    try:
        with get_db_session() as db:
            game_session = db.query(GameSession).filter(GameSession.id == game_session_id).first()
            player = _get_player(db, game_session)

            if not player:
                display_error("Character creation was cancelled or failed")
                raise typer.Exit(1)

            # Run the async game loop
            asyncio.run(_game_loop(
                db, game_session, player,
                roll_mode=roll_mode,
                anticipation_enabled=use_anticipation,
                ref_based_enabled=ref_based,
            ))

    except KeyboardInterrupt:
        display_info("\nGame paused. Use 'rpg game play' to continue.")


def _display_resume_context(
    db, player: Entity, last_turn: Turn, game_session: GameSession
) -> None:
    """Display rich context summary when resuming a session.

    Queries current game state to show accurate context.

    Args:
        db: Database session.
        player: The player entity.
        last_turn: The most recent turn record.
        game_session: The game session being resumed.
    """
    from rich.panel import Panel

    from src.database.models.world import Location

    # Get current time state
    time_state = (
        db.query(TimeState)
        .filter(TimeState.session_id == game_session.id)
        .first()
    )
    day = time_state.current_day if time_state else 1
    time_str = time_state.current_time if time_state else ""

    # Get location - only use if it's a real location (not "starting_location")
    location_key = last_turn.location_at_turn
    location_name = None

    if location_key and location_key not in ("starting_location", "unknown"):
        location = db.query(Location).filter(
            Location.session_id == game_session.id,
            Location.location_key == location_key
        ).first()
        location_name = location.display_name if location else None

    # NO FALLBACK - don't show wrong location data

    # Get NPCs at current location only (not all NPCs ever met)
    from src.database.models.entities import NPCExtension

    npc_names = []
    if location_key and location_key not in ("starting_location", "unknown"):
        npcs_at_location = (
            db.query(Entity)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == game_session.id,
                Entity.entity_type == EntityType.NPC,
                NPCExtension.current_location == location_key,
            )
            .all()
        )
        npc_names = [npc.display_name for npc in npcs_at_location]

    # Build context lines
    lines = [f"[bold]Welcome back, {player.display_name}![/bold]"]

    # Time line
    if time_str:
        lines.append(f"Day {day}, {time_str}")
    else:
        lines.append(f"Day {day}")

    # Location line
    if location_name:
        lines.append(f"Location: {location_name}")

    # NPCs line (nearby, not all ever met)
    if npc_names:
        lines.append(f"Present: {', '.join(npc_names)}")

    # Add a brief context excerpt from the last response (first ~150 chars)
    # But skip if it's a minimal/bad response
    if last_turn.gm_response:
        response = last_turn.gm_response.strip()
        is_bad_excerpt = (
            len(response) < 50
            or response.startswith("Attempted:")
            or response == "Nothing happens."
        )
        if not is_bad_excerpt:
            # Get first sentence or first 150 chars
            first_sentence_end = min(
                response.find(". ") + 1 if ". " in response else len(response),
                response.find(".\n") + 1 if ".\n" in response else len(response),
                150
            )
            if first_sentence_end < 20:  # Too short, take more
                first_sentence_end = min(150, len(response))
            excerpt = response[:first_sentence_end].strip()
            if len(response) > first_sentence_end:
                excerpt += "..."
            lines.append("")
            lines.append(f"[dim italic]{excerpt}[/dim italic]")

    # Display as a panel
    console.print(Panel("\n".join(lines), title="Session Resumed", border_style="cyan"))
    console.print()

    # Show the last GM response so player knows where they left off
    # But skip if it's a minimal/bad response (like "Attempted: custom.")
    gm_response = last_turn.gm_response or ""
    is_bad_response = (
        len(gm_response) < 50
        or gm_response.strip().startswith("Attempted:")
        or gm_response.strip() == "Nothing happens."
    )
    if gm_response and not is_bad_response:
        display_info("When we last left off...")
        display_narrative(gm_response)
    else:
        display_info("Type 'look around' or '/look' to see your surroundings.")


async def _game_loop(
    db,
    game_session: GameSession,
    player: Entity,
    initial_location: str | None = None,
    roll_mode: str = "auto",
    anticipation_enabled: bool = False,
    ref_based_enabled: bool = False,
) -> None:
    """Main game loop using the quantum pipeline.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        initial_location: Optional starting location key from character creation.
        roll_mode: "auto" or "manual" for dice rolls.
        anticipation_enabled: Whether to enable anticipatory scene generation.
        ref_based_enabled: Whether to use ref-based architecture (A/B/C refs).
    """
    display_welcome(game_session.session_name)

    # Initialize Quantum Pipeline
    from src.world_server.quantum import QuantumPipeline, AnticipationConfig
    from src.config import get_settings
    settings = get_settings()

    use_anticipation = anticipation_enabled if anticipation_enabled is not None else settings.quantum_anticipation_enabled
    anticipation_config = AnticipationConfig(
        enabled=use_anticipation,
        max_actions_per_cycle=settings.quantum_max_actions_per_cycle,
        max_gm_decisions_per_action=settings.quantum_max_gm_decisions,
        cycle_delay_seconds=settings.quantum_cycle_delay,
    )
    quantum_pipeline = QuantumPipeline(
        db=db,
        game_session=game_session,
        anticipation_config=anticipation_config,
    )

    # Enable ref-based architecture if requested
    if ref_based_enabled:
        quantum_pipeline.enable_ref_based(True)
        display_info("Using ref-based architecture (A/B/C refs)")
    else:
        display_info("Using Quantum pipeline")

    if anticipation_config.enabled:
        display_info("Quantum anticipation enabled")

    # Get player location - use initial_location if provided, otherwise find suitable location
    from src.database.models.world import Location

    player_location = initial_location
    if not player_location:
        # Try to find player's home_location from NPC extension
        if player.npc_extension and player.npc_extension.home_location:
            # Verify the home location exists
            home_loc = db.query(Location).filter(
                Location.session_id == game_session.id,
                Location.location_key == player.npc_extension.home_location,
            ).first()
            if home_loc:
                player_location = home_loc.location_key

    if not player_location:
        # Try to find a location with category "home" or "residence"
        home_location = db.query(Location).filter(
            Location.session_id == game_session.id,
            Location.category.in_(["home", "residence"])
        ).first()
        if home_location:
            player_location = home_location.location_key

    if not player_location:
        # Fall back to the first location in the session
        first_location = db.query(Location).filter(
            Location.session_id == game_session.id,
        ).first()
        if first_location:
            player_location = first_location.location_key
        else:
            display_error("No locations found in game session. Cannot start game.")
            return

    display_info("Type your actions. Use /quit to exit, /help for commands.")
    console.print()

    # Check if this is a resume (existing turns) or new game
    last_turn = _get_last_turn(db, game_session.id)
    is_resume = last_turn is not None

    if is_resume:
        # RESUME: Show context and last response, skip scene generation
        _display_resume_context(db, player, last_turn, game_session)
        # Get current location from DB (may have changed via MOVE delta)
        player_location = _get_player_current_location(
            player, fallback=last_turn.location_at_turn
        )

        # Sync total_turns with actual turn count (guards against crashes/inconsistencies)
        if last_turn.turn_number != game_session.total_turns:
            game_session.total_turns = last_turn.turn_number
            db.commit()
    else:
        # NEW GAME: Generate initial scene
        game_session.total_turns += 1  # Increment for first turn

        first_turn_input = "[FIRST TURN: Introduce the player character - describe who they are, what they look like, what they're wearing, and how they feel. Then describe the scene they find themselves in.]"

        # Generate initial scene with quantum pipeline
        with progress_spinner("Setting the scene...") as (progress, task):
            try:
                progress.update(task, description="Generating narrative...")
                turn_result = await quantum_pipeline.process_turn(
                    player_input=first_turn_input,
                    location_key=player_location,
                    turn_number=game_session.total_turns,
                )
                if turn_result.narrative:
                    display_narrative(turn_result.narrative)
            except Exception as e:
                display_error(f"Error generating scene: {e}")
        # Start anticipation after first turn
        if quantum_pipeline.anticipation_config.enabled:
            await quantum_pipeline.start_anticipation()

    # Main loop
    while True:
        console.print()
        player_input = prompt_input()

        if not player_input.strip():
            continue

        # Handle commands
        if player_input.startswith("/"):
            cmd = player_input[1:].lower().split()[0]
            if cmd in ("quit", "exit", "q"):
                display_info("Saving and exiting...")
                game_session.status = "paused"
                db.commit()
                # Shutdown quantum pipeline
                await quantum_pipeline.stop_anticipation()
                break
            elif cmd == "help":
                _show_help()
                continue
            elif cmd == "status":
                from src.cli.commands.character import status
                status(session_id=game_session.id)
                continue
            elif cmd == "inventory":
                from src.cli.commands.character import inventory
                inventory(session_id=game_session.id)
                continue
            elif cmd == "time":
                from src.cli.commands.world import time
                time(session_id=game_session.id)
                continue
            elif cmd == "save":
                db.commit()
                display_success("Game saved!")
                continue
            elif cmd == "scene":
                args = player_input[1:].lower().split()[1:]
                perspective = args[0] if len(args) > 0 and args[0] in ("pov", "third") else "pov"
                style = args[1] if len(args) > 1 and args[1] in ("photo", "art") else "photo"
                await _handle_scene_command(db, game_session, player, perspective, style)
                continue
            elif cmd == "portrait":
                args = player_input[1:].lower().split()[1:]
                mode = args[0] if len(args) > 0 and args[0] in ("base", "current") else "current"
                style = args[1] if len(args) > 1 and args[1] in ("photo", "art") else "photo"
                await _handle_portrait_command(db, game_session, player, mode, style)
                continue
            elif cmd == "nearby":
                from src.cli.commands.character import nearby
                nearby(session_id=game_session.id)
                continue
            elif cmd in ("location", "loc", "where"):
                _show_location(db, game_session, player_location)
                continue
            elif cmd in ("equipment", "equip"):
                from src.cli.commands.character import equipment
                equipment(session_id=game_session.id)
                continue
            elif cmd in ("look", "l"):
                # LOOK command - trigger scene generation
                player_input = "look around"
                # Fall through to process as normal input
            elif cmd == "outfit":
                from src.cli.commands.character import outfit
                outfit(session_id=game_session.id)
                continue
            elif cmd in ("quests", "quest", "tasks"):
                _show_quests(db, game_session)
                continue
            elif cmd in ACTION_COMMANDS:
                # Action commands go through validation, not handled here
                pass  # Fall through to validation below
            else:
                display_error(f"Unknown command: /{cmd}")
                continue

        # Pre-validate action commands and enhance input for GM
        enhanced_input, validation_error = await _validate_and_enhance_input(
            db, game_session, player, player_input, player_location
        )

        if validation_error:
            display_error(validation_error)
            continue  # Don't invoke graph, immediate feedback

        # Capture snapshot before processing turn (for reset functionality)
        from src.managers.snapshot_manager import SnapshotManager
        snapshot_mgr = SnapshotManager(db, game_session)
        snapshot_mgr.capture_snapshot(game_session.total_turns + 1)
        snapshot_mgr.prune_snapshots()

        # Process player input
        game_session.total_turns += 1

        # Quantum pipeline: use process_turn
        with progress_spinner("Processing...") as (progress, task):
            try:
                # Show cache check phase
                progress.update(task, description="Checking prepared outcomes...")

                turn_result = await quantum_pipeline.process_turn(
                    player_input=enhanced_input,
                    location_key=player_location,
                    turn_number=game_session.total_turns,
                )

                # Update progress based on cache hit
                if turn_result.was_cache_hit:
                    progress.update(task, description="Cache hit! Rolling dice...")
                else:
                    progress.update(task, description="Generating narrative...")

            except Exception as e:
                display_error(f"Error: {e}")
                game_session.total_turns -= 1
                continue

        # Display skill check if present
        if turn_result.skill_check_result:
            _display_quantum_skill_check(turn_result.skill_check_result)

        # Display the response
        if turn_result.narrative:
            display_narrative(turn_result.narrative)

            # Immediately persist the turn
            _save_turn_immediately(
                db=db,
                game_session=game_session,
                turn_number=game_session.total_turns,
                player_input=player_input,
                gm_response=turn_result.narrative,
                player_location=player_location,
                is_ooc=False,
            )

            # Show cache/latency info
            if turn_result.was_cache_hit:
                display_info(f"[dim](cache hit, {turn_result.latency_ms:.0f}ms)[/dim]")
        else:
            display_error("No response from quantum pipeline. Try rephrasing your action.")

        # Handle errors from quantum pipeline
        if turn_result.errors:
            for error in turn_result.errors:
                display_error(error)

        # Commit after each turn
        db.commit()

        # Refresh player location after turn (may have moved via delta)
        db.refresh(player)
        player_location = _get_player_current_location(player, fallback=player_location)


def _display_quantum_skill_check(skill_check_result) -> None:
    """Display skill check result from quantum pipeline.

    Args:
        skill_check_result: SkillCheckResult from dice/types.py
    """
    from src.cli.display import (
        display_skill_check_prompt,
        display_skill_check_result,
        wait_for_roll,
        display_rolling_animation,
    )

    # Extract values from SkillCheckResult (now includes skill metadata)
    skill_name = skill_check_result.skill_name or "Skill"
    skill_modifier = skill_check_result.skill_modifier
    attribute_key = skill_check_result.attribute_key
    attribute_modifier = skill_check_result.attribute_modifier
    total_modifier = skill_check_result.total_modifier

    # Show pre-roll prompt
    display_skill_check_prompt(
        description=f"{skill_name} check",
        skill_name=skill_name,
        skill_tier="Practiced",  # Default tier for quantum
        skill_modifier=skill_modifier,
        attribute_key=attribute_key,
        attribute_modifier=attribute_modifier,
        total_modifier=total_modifier,
        difficulty_assessment="",
    )

    # Wait for player to press ENTER (dice already rolled, but for suspense)
    wait_for_roll()

    # Show rolling animation
    display_rolling_animation()

    # Extract dice results from RollResult
    if skill_check_result.roll_result:
        dice_rolls = list(skill_check_result.roll_result.individual_rolls)
        total_roll = skill_check_result.roll_result.total
    else:
        # Auto-success case - no dice rolled
        dice_rolls = []
        total_roll = total_modifier + 11  # Average 2d10 roll

    # Show the result
    display_skill_check_result(
        success=skill_check_result.success,
        dice_rolls=dice_rolls,
        total_modifier=total_modifier,
        total_roll=total_roll,
        dc=skill_check_result.dc,
        margin=skill_check_result.margin,
        outcome_tier=skill_check_result.outcome_tier.value if hasattr(skill_check_result.outcome_tier, 'value') else str(skill_check_result.outcome_tier),
        is_critical_success=skill_check_result.is_critical_success,
        is_critical_failure=skill_check_result.is_critical_failure,
    )


def _save_turn_immediately(
    db,
    game_session: GameSession,
    turn_number: int,
    player_input: str,
    gm_response: str,
    player_location: str,
    is_ooc: bool = False,
) -> None:
    """Save turn record immediately to prevent data loss on quit.

    This creates the Turn record and commits it right away, so if the user
    quits before the full turn processing completes, the GM response is preserved.

    If the turn was already created by persistence_node (during graph execution),
    this updates it instead of creating a duplicate.

    Args:
        db: Database session.
        game_session: Current game session.
        turn_number: Turn number for this interaction.
        player_input: What the player typed.
        gm_response: The GM's narrative response.
        player_location: Current location key.
        is_ooc: Whether this is an OOC response.
    """
    from src.database.models.session import Turn
    from src.database.models.world import TimeState

    # Get current game time for turn snapshot
    time_state = (
        db.query(TimeState)
        .filter(TimeState.session_id == game_session.id)
        .first()
    )

    # Check if turn already exists (created by persistence_node during graph)
    existing = (
        db.query(Turn)
        .filter(
            Turn.session_id == game_session.id,
            Turn.turn_number == turn_number,
        )
        .first()
    )

    if existing:
        # Update existing turn with response data
        existing.player_input = player_input
        existing.gm_response = gm_response
        existing.location_at_turn = player_location
        existing.is_ooc = is_ooc
        # Set date/time if not already set
        if time_state and existing.game_day_at_turn is None:
            existing.game_day_at_turn = time_state.current_day
            existing.game_time_at_turn = time_state.current_time
    else:
        # Create new turn
        turn = Turn(
            session_id=game_session.id,
            turn_number=turn_number,
            player_input=player_input,
            gm_response=gm_response,
            is_ooc=is_ooc,
            location_at_turn=player_location,
            game_day_at_turn=time_state.current_day if time_state else None,
            game_time_at_turn=time_state.current_time if time_state else None,
        )
        db.add(turn)

    db.commit()


def _show_help() -> None:
    """Show in-game help."""
    console.print()
    console.print("[bold cyan]━━━ Character ━━━[/bold cyan]")
    console.print("  /status      Health, attributes, needs")
    console.print("  /inventory   Items you're carrying")
    console.print("  /equipment   Weapons, armor, accessories")
    console.print("  /outfit      Current clothing (layers)")
    console.print()
    console.print("[bold cyan]━━━ World ━━━[/bold cyan]")
    console.print("  /location    Current location details")
    console.print("  /nearby      NPCs and items here")
    console.print("  /time        Current day and time")
    console.print("  /quests      Active quests and tasks")
    console.print()
    console.print("[bold cyan]━━━ Actions (validated shortcuts) ━━━[/bold cyan]")
    console.print("  /go <place>           Move to a location")
    console.print("  /take <item>          Pick up an item")
    console.print("  /drop <item>          Drop an item")
    console.print("  /give <item> to <npc> Give item to someone")
    console.print("  /attack <target>      Start combat")
    console.print("    [dim]These validate constraints before the GM responds.[/dim]")
    console.print()
    console.print("[bold cyan]━━━ System ━━━[/bold cyan]")
    console.print("  /help        Show this help")
    console.print("  /save        Save the game")
    console.print("  /quit        Save and exit (or Ctrl+C)")
    console.print()
    console.print("[bold cyan]━━━ Image Generation (FLUX prompts) ━━━[/bold cyan]")
    console.print("  /scene [pov|third] [photo|art]")
    console.print("    [dim]pov = first-person view, third = player visible in scene[/dim]")
    console.print("  /portrait [base|current] [photo|art]")
    console.print("    [dim]base = appearance only, current = with equipment & condition[/dim]")
    console.print("    [dim]photo = photorealistic, art = digital illustration[/dim]")
    console.print()
    console.print("[bold cyan]━━━ Gameplay Tips ━━━[/bold cyan]")
    console.print("  Type your actions naturally:")
    console.print("    [dim]> Look around the tavern[/dim]")
    console.print("    [dim]> Ask Marta about the blacksmith[/dim]")
    console.print("    [dim]> Pick up the sword[/dim]")
    console.print("    [dim]> Go to the market square[/dim]")
    console.print()
    console.print("  Speak out of character to the GM:")
    console.print("    [dim]> ooc: What skills would help me here?[/dim]")
    console.print("    [dim]> ooc: Can I roll to persuade him?[/dim]")
    console.print("    [dim]> ooc: Skip ahead to evening[/dim]")
    console.print()


def _show_location(db, game_session: GameSession, player_location: str) -> None:
    """Show current location details."""
    from rich.panel import Panel

    from src.database.models.world import Location

    location = db.query(Location).filter(
        Location.session_id == game_session.id,
        Location.location_key == player_location
    ).first()

    if location:
        lines = [f"[bold]{location.display_name}[/bold]"]
        if location.description:
            lines.append(f"[dim]{location.description}[/dim]")
        if location.category:
            lines.append(f"Type: {location.category}")
        console.print(Panel("\n".join(lines), title="Current Location", border_style="green"))
    elif player_location in ("starting_location", "unknown"):
        console.print("[dim]Location not yet established. Type '/look' to explore your surroundings.[/dim]")
    else:
        # Location key exists but no record - display humanized version
        display_name = player_location.replace("_", " ").title()
        console.print(f"[dim]Location: {display_name}[/dim]")


def _show_quests(db, game_session: GameSession) -> None:
    """Show active quests and tasks."""
    from rich.table import Table

    from src.database.models.tasks import Quest, Task

    console.print()

    # Get active quests
    quests = db.query(Quest).filter(
        Quest.session_id == game_session.id,
        Quest.status == "active"
    ).all()

    # Get active tasks (not completed)
    tasks = db.query(Task).filter(
        Task.session_id == game_session.id,
        Task.completed == False
    ).all()

    if not quests and not tasks:
        console.print("[dim]No active quests or tasks.[/dim]")
        return

    if quests:
        table = Table(title="Active Quests", show_header=True)
        table.add_column("Quest", style="cyan")
        table.add_column("Stage", style="yellow")
        table.add_column("Status", style="green")
        for q in quests:
            table.add_row(q.name, f"Stage {q.current_stage}", q.status.value if hasattr(q.status, 'value') else str(q.status))
        console.print(table)

    if tasks:
        table = Table(title="Tasks", show_header=True)
        table.add_column("Task", style="cyan")
        table.add_column("Category", style="yellow")
        table.add_column("Priority", style="magenta")
        for t in tasks:
            cat = t.category.value if hasattr(t.category, 'value') else str(t.category)
            table.add_row(t.description[:50], cat, str(t.priority))
        console.print(table)
    console.print()


async def _handle_scene_command(
    db,
    game_session: GameSession,
    player: Entity,
    perspective: str,
    style: str,
) -> None:
    """Handle the /scene command to generate an image prompt.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        perspective: 'pov' or 'third'.
        style: 'photo' or 'art'.
    """
    from src.services.image_prompt_generator import ImagePromptGenerator, estimate_tokens

    console.print()
    with progress_spinner("Generating scene prompt..."):
        generator = ImagePromptGenerator(db, game_session, player)
        prompt = await generator.generate_scene_prompt(perspective, style)

    tokens = estimate_tokens(prompt)
    console.print(f"[bold cyan]== FLUX PROMPT (scene, {perspective}, {style}) ==[/bold cyan]")
    console.print(f"[white]{prompt}[/white]")
    console.print(f"[dim](~{tokens} tokens)[/dim]")
    console.print()


async def _handle_portrait_command(
    db,
    game_session: GameSession,
    player: Entity,
    mode: str,
    style: str,
) -> None:
    """Handle the /portrait command to generate an image prompt.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        mode: 'base' or 'current'.
        style: 'photo' or 'art'.
    """
    from src.services.image_prompt_generator import ImagePromptGenerator, estimate_tokens

    console.print()
    with progress_spinner("Generating portrait prompt..."):
        generator = ImagePromptGenerator(db, game_session, player)
        prompt = await generator.generate_portrait_prompt(mode, style)

    tokens = estimate_tokens(prompt)
    console.print(f"[bold cyan]== FLUX PROMPT (portrait, {mode}, {style}) ==[/bold cyan]")
    console.print(f"[white]{prompt}[/white]")
    console.print(f"[dim](~{tokens} tokens)[/dim]")
    console.print()


@app.command()
def turn(
    player_input: str = typer.Argument(..., help="Player input to process"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    split: bool = typer.Option(False, "--split", help="Use split architecture (Phases 2-5)"),
    ref_based: bool = typer.Option(False, "--ref-based", help="Use ref-based architecture (A/B/C refs)"),
) -> None:
    """Execute a single turn using the quantum pipeline (for testing)."""
    try:
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
                display_error("No player found in session. Create a character first.")
                raise typer.Exit(1)

            # Run single turn
            asyncio.run(_single_turn(db, game_session, player, player_input, use_split=split, use_ref_based=ref_based))

    except Exception as e:
        display_error(f"Error: {e}")
        raise typer.Exit(1)


async def _single_turn(
    db,
    game_session: GameSession,
    player: Entity,
    player_input: str,
    use_split: bool = False,
    use_ref_based: bool = False,
) -> None:
    """Execute a single turn using the quantum pipeline.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        player_input: Player's input.
        use_split: Whether to use split architecture (Phases 2-5).
        use_ref_based: Whether to use ref-based architecture (A/B/C refs).
    """
    from src.world_server.quantum import QuantumPipeline, AnticipationConfig
    from src.database.models.world import Location

    # Initialize quantum pipeline without anticipation (single turn)
    quantum_pipeline = QuantumPipeline(
        db=db,
        game_session=game_session,
        anticipation_config=AnticipationConfig(enabled=False),
    )

    # Enable ref-based architecture if requested (takes priority over split)
    if use_ref_based:
        display_info("Using ref-based architecture (A/B/C refs)")
        quantum_pipeline.enable_ref_based(True)
    elif use_split:
        display_info("Using split architecture (Phases 2-5)")
        quantum_pipeline.enable_split_architecture(True)

    # Find player location - prefer DB (current), fallback to last turn
    last_turn = _get_last_turn(db, game_session.id)
    fallback_location = last_turn.location_at_turn if last_turn else None

    # If no last turn, try to find any location in the session
    if not fallback_location:
        any_location = db.query(Location).filter(
            Location.session_id == game_session.id
        ).first()
        if any_location:
            fallback_location = any_location.location_key

    # Get current location from player's npc_extension (updated by MOVE deltas)
    player_location = _get_player_current_location(player, fallback=fallback_location)

    game_session.total_turns += 1

    with progress_spinner("Processing...") as (progress, task):
        progress.update(task, description="Generating narrative...")
        turn_result = await quantum_pipeline.process_turn(
            player_input=player_input,
            location_key=player_location,
            turn_number=game_session.total_turns,
        )

    # Display skill check if present
    if turn_result.skill_check_result:
        check = turn_result.skill_check_result
        result_str = "✓ Success" if check.success else "✗ Failure"
        if check.is_auto_success:
            display_info(f"[{check.skill_name} Check] DC {check.dc}: Auto-success → {result_str}")
        elif check.roll_result:
            display_info(f"[{check.skill_name} Check] DC {check.dc}: {check.roll_result.total} → {result_str}")
        else:
            display_info(f"[{check.skill_name} Check] DC {check.dc}: → {result_str}")

    if turn_result.narrative:
        display_narrative(turn_result.narrative)

    if turn_result.errors:
        for error in turn_result.errors:
            display_error(error)

    # Persist turn to database (same as play command)
    if turn_result.narrative:
        _save_turn_immediately(
            db=db,
            game_session=game_session,
            turn_number=game_session.total_turns,
            player_input=player_input,
            gm_response=turn_result.narrative,
            player_location=player_location,
            is_ooc=False,
        )

    db.commit()
