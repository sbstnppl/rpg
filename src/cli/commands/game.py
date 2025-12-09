"""Game commands including the main game loop."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.cli.display import (
    display_error,
    display_game_wizard_welcome,
    display_info,
    display_narrative,
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
from src.database.models.session import GameSession
from src.database.models.world import TimeState

app = typer.Typer(help="Game commands")
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
    """Get the player entity for the session, or None if not created."""
    return (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )


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
) -> None:
    """Start a new game with guided setup wizard.

    Creates a new session and guides you through character creation
    in one seamless flow, then starts the game.

    Use --conversational for the old freeform AI character creation style.
    """
    try:
        asyncio.run(_start_wizard_async(name, setting, use_wizard=wizard))
    except KeyboardInterrupt:
        display_info("\nWizard cancelled. No changes were saved.")


async def _start_wizard_async(
    preset_name: str | None = None,
    preset_setting: str | None = None,
    use_wizard: bool = True,
) -> None:
    """Run the full game start wizard.

    Guides through session setup, character creation, and starts the game.

    Args:
        preset_name: Optional preset session name (skips prompt).
        preset_setting: Optional preset setting (skips prompt).
        use_wizard: If True, use step-by-step wizard; if False, use conversational AI.
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
            _create_world_from_extraction(db, game_session, entity, world_data)

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

        # Phase 4: Start the game loop directly
        console.print()
        await _game_loop(db, game_session, entity)


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
) -> None:
    """Start the interactive game loop."""
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
            asyncio.run(_game_loop(db, game_session, player))

    except KeyboardInterrupt:
        display_info("\nGame paused. Use 'rpg game play' to continue.")


async def _game_loop(db, game_session: GameSession, player: Entity) -> None:
    """Main game loop.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
    """
    from src.agents.graph import build_game_graph
    from src.agents.state import create_initial_state

    display_welcome(game_session.session_name)

    # Build and compile the graph
    graph = build_game_graph()
    compiled = graph.compile()

    # Get player location (default to "starting_location")
    player_location = "starting_location"

    display_info("Type your actions. Use /quit to exit, /help for commands.")
    console.print()

    # Initial scene description - introduce the character and scene
    initial_state = create_initial_state(
        session_id=game_session.id,
        player_id=player.id,
        player_location=player_location,
        player_input="[FIRST TURN: Introduce the player character - describe who they are, what they look like, what they're wearing, and how they feel. Then describe the scene they find themselves in.]",
        turn_number=game_session.total_turns + 1,
    )
    initial_state["_db"] = db
    initial_state["_game_session"] = game_session

    with progress_spinner("Setting the scene..."):
        try:
            result = await compiled.ainvoke(initial_state)
            if result.get("gm_response"):
                display_narrative(result["gm_response"])
                player_location = result.get("player_location", player_location)
        except Exception as e:
            display_error(f"Error generating scene: {e}")

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
            else:
                display_error(f"Unknown command: /{cmd}")
                continue

        # Process player input through the agent graph
        game_session.total_turns += 1

        state = create_initial_state(
            session_id=game_session.id,
            player_id=player.id,
            player_location=player_location,
            player_input=player_input,
            turn_number=game_session.total_turns,
        )
        state["_db"] = db
        state["_game_session"] = game_session

        with progress_spinner("Thinking..."):
            try:
                result = await compiled.ainvoke(state)
            except Exception as e:
                display_error(f"Error: {e}")
                game_session.total_turns -= 1
                continue

        # Display skill checks interactively (before the narrative)
        skill_checks = result.get("skill_checks", [])
        if skill_checks:
            _display_skill_checks_interactive(skill_checks)

        # Display the response
        if result.get("gm_response"):
            display_narrative(result["gm_response"])

        # Update player location if changed
        if result.get("location_changed"):
            player_location = result.get("player_location", player_location)
            display_info(f"[You are now at: {player_location}]")

        # Handle errors
        if result.get("errors"):
            for error in result["errors"]:
                display_error(error)

        # Commit after each turn
        db.commit()


def _display_skill_checks_interactive(skill_checks: list[dict]) -> None:
    """Display skill checks interactively, letting player roll.

    Args:
        skill_checks: List of skill check result dicts from executor.
    """
    from src.cli.display import (
        display_skill_check_prompt,
        display_skill_check_result,
        wait_for_roll,
        display_rolling_animation,
    )

    for check in skill_checks:
        # Show the pre-roll prompt
        display_skill_check_prompt(
            description=check.get("description", "Skill check"),
            skill_name=check.get("skill_name", "unknown"),
            skill_tier=check.get("skill_tier", "Novice"),
            skill_modifier=check.get("skill_modifier", 0),
            attribute_key=check.get("attribute_key", "unknown"),
            attribute_modifier=check.get("attribute_modifier", 0),
            total_modifier=check.get("total_modifier", 0),
            difficulty_assessment=check.get("difficulty_assessment", ""),
        )

        # Wait for player to press ENTER
        wait_for_roll()

        # Show rolling animation
        display_rolling_animation()

        # Show the result
        display_skill_check_result(
            success=check.get("success", False),
            natural_roll=check.get("natural_roll", 10),
            total_modifier=check.get("total_modifier", 0),
            total_roll=check.get("roll", 10),
            dc=check.get("dc", 10),
            margin=check.get("margin", 0),
            is_critical_success=check.get("is_critical_success", False),
            is_critical_failure=check.get("is_critical_failure", False),
        )


def _show_help() -> None:
    """Show in-game help."""
    console.print()
    console.print("[bold]Available Commands[/bold]")
    console.print("  /help      - Show this help")
    console.print("  /status    - Show character status")
    console.print("  /inventory - Show inventory")
    console.print("  /time      - Show current game time")
    console.print("  /save      - Save the game")
    console.print("  /quit      - Save and exit")
    console.print()
    console.print("[bold]Gameplay[/bold]")
    console.print("  Type your actions naturally, e.g.:")
    console.print("  - Look around")
    console.print("  - Talk to the bartender")
    console.print("  - Go to the market")
    console.print("  - Attack the goblin")
    console.print()


@app.command()
def turn(
    player_input: str = typer.Argument(..., help="Player input to process"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Execute a single turn (for testing)."""
    try:
        with get_db_session() as db:
            if session_id:
                game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
            else:
                game_session = _get_active_session(db)

            if not game_session:
                display_error("No active session found")
                raise typer.Exit(1)

            player = _get_or_create_player(db, game_session)

            # Run single turn
            asyncio.run(_single_turn(db, game_session, player, player_input))

    except Exception as e:
        display_error(f"Error: {e}")
        raise typer.Exit(1)


async def _single_turn(
    db,
    game_session: GameSession,
    player: Entity,
    player_input: str,
) -> None:
    """Execute a single turn.

    Args:
        db: Database session.
        game_session: Current game session.
        player: Player entity.
        player_input: Player's input.
    """
    from src.agents.graph import build_game_graph
    from src.agents.state import create_initial_state

    graph = build_game_graph()
    compiled = graph.compile()

    game_session.total_turns += 1

    state = create_initial_state(
        session_id=game_session.id,
        player_id=player.id,
        player_location="starting_location",
        player_input=player_input,
        turn_number=game_session.total_turns,
    )
    state["_db"] = db
    state["_game_session"] = game_session

    with progress_spinner("Processing..."):
        result = await compiled.ainvoke(state)

    if result.get("gm_response"):
        display_narrative(result["gm_response"])

    if result.get("errors"):
        for error in result["errors"]:
            display_error(error)

    db.commit()
