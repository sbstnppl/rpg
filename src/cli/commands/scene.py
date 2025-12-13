"""Scene commands for dumping current scene context."""

from typing import Optional

import typer
from rich.console import Console

from src.database.connection import get_db_session
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.managers.context_compiler import ContextCompiler
from src.managers.item_manager import ItemManager

app = typer.Typer(help="Scene commands")
console = Console()


def _get_active_session(db) -> GameSession | None:
    """Get the most recent active session."""
    return (
        db.query(GameSession)
        .filter(GameSession.status == "active")
        .order_by(GameSession.id.desc())
        .first()
    )


def _get_session(db, session_id: Optional[int]) -> GameSession:
    """Get session by ID or most recent active session."""
    if session_id:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            console.print(f"[red]Session {session_id} not found.[/red]")
            raise typer.Exit(1)
        return session

    session = _get_active_session(db)
    if not session:
        console.print("[red]No active session found. Start a game first.[/red]")
        raise typer.Exit(1)
    return session


def _get_player(db, game_session: GameSession) -> Entity:
    """Get the player entity for the session."""
    player = (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )
    if not player:
        console.print("[red]No player character found in this session.[/red]")
        raise typer.Exit(1)
    return player


@app.command("dump")
def dump_scene(
    session_id: Optional[int] = typer.Option(
        None, "--session", "-s", help="Session ID (defaults to active session)"
    ),
) -> None:
    """Dump current scene context for image generation.

    Outputs location, player, NPCs, and time context from the database.
    Used by the /scene-image slash command to generate FLUX prompts.
    """
    with get_db_session() as db:
        game_session = _get_session(db, session_id)
        player = _get_player(db, game_session)

        # Get player's current location
        if not player.npc_extension or not player.npc_extension.current_location:
            console.print("[red]Player has no current location set.[/red]")
            raise typer.Exit(1)

        location_key = player.npc_extension.current_location

        # Compile scene context
        compiler = ContextCompiler(db, game_session)
        scene = compiler.compile_scene(
            player_id=player.id,
            location_key=location_key,
            turn_number=game_session.total_turns or 1,
            include_secrets=False,  # No GM secrets for image generation
        )

        # Output sections with clear headers for Claude to parse
        console.print("[bold cyan]== LOCATION ==[/bold cyan]")
        console.print(scene.location_context)
        console.print()

        console.print("[bold cyan]== TIME ==[/bold cyan]")
        console.print(scene.time_context)
        console.print()

        console.print("[bold cyan]== PLAYER ==[/bold cyan]")
        console.print(scene.player_context)
        console.print()

        if scene.npcs_context and scene.npcs_context.strip():
            console.print("[bold cyan]== NPCS PRESENT ==[/bold cyan]")
            console.print(scene.npcs_context)


@app.command("portrait")
def dump_portrait(
    session_id: Optional[int] = typer.Option(
        None, "--session", "-s", help="Session ID (defaults to active session)"
    ),
    no_equipment: bool = typer.Option(
        False, "--no-equipment", help="Exclude visible clothing/gear"
    ),
    no_condition: bool = typer.Option(
        False, "--no-condition", help="Exclude hygiene/energy/hunger effects"
    ),
    no_injuries: bool = typer.Option(
        False, "--no-injuries", help="Exclude visible injuries"
    ),
) -> None:
    """Dump player character portrait data for image generation.

    Outputs appearance, equipment, conditions, and injuries.
    Used by the /portrait slash command to generate FLUX prompts.

    By default shows all visible state. Use --no-X flags to exclude:
      --no-equipment  Skip clothing and gear
      --no-condition  Skip tired/dirty/hungry effects
      --no-injuries   Skip visible injuries
    """
    with get_db_session() as db:
        game_session = _get_session(db, session_id)
        player = _get_player(db, game_session)

        # Base appearance
        console.print("[bold cyan]== BASE APPEARANCE ==[/bold cyan]")
        if player.species:
            console.print(f"Species: {player.species}")
        if player.age:
            age_str = str(player.age)
            if player.age_apparent:
                age_str += f" (appears {player.age_apparent})"
            console.print(f"Age: {age_str}")
        if player.gender:
            console.print(f"Gender: {player.gender}")
        height_build = []
        if player.height:
            height_build.append(player.height)
        if player.build:
            height_build.append(f"{player.build} build")
        if height_build:
            console.print(f"Build: {', '.join(height_build)}")
        hair_parts = []
        if player.hair_color:
            hair_parts.append(player.hair_color)
        if player.hair_style:
            hair_parts.append(player.hair_style)
        if hair_parts:
            console.print(f"Hair: {' '.join(hair_parts)}")
        if player.eye_color:
            console.print(f"Eyes: {player.eye_color}")
        if player.skin_tone:
            console.print(f"Skin: {player.skin_tone}")
        if player.distinguishing_features:
            console.print(f"Distinguishing: {player.distinguishing_features}")
        console.print()

        # Equipment (visible clothing/gear)
        if not no_equipment:
            item_manager = ItemManager(db, game_session)
            outfit = item_manager.format_outfit_description(player.id)
            if outfit:
                console.print("[bold cyan]== EQUIPMENT ==[/bold cyan]")
                console.print(outfit)
                console.print()

        # Condition and injuries need ContextCompiler
        compiler = ContextCompiler(db, game_session)

        # Condition (needs affecting appearance)
        if not no_condition:
            condition = compiler._get_needs_description(player.id, visible_only=True)
            if condition:
                console.print("[bold cyan]== CONDITION ==[/bold cyan]")
                console.print(condition.capitalize())
                console.print()

        # Injuries (visible)
        if not no_injuries:
            injuries = compiler._get_injury_description(player.id, visible_only=True)
            if injuries:
                console.print("[bold cyan]== INJURIES ==[/bold cyan]")
                console.print(injuries.capitalize())
