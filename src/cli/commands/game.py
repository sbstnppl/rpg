"""Game commands including the main game loop."""

import asyncio
from typing import Optional

import typer
from rich.console import Console

from src.cli.display import (
    display_error,
    display_info,
    display_narrative,
    display_success,
    display_welcome,
    progress_spinner,
    prompt_input,
)
from src.cli.commands.session import get_db_session
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession

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


def _get_or_create_player(db, game_session: GameSession) -> Entity:
    """Get or create a player entity for the session."""
    player = (
        db.query(Entity)
        .filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER,
        )
        .first()
    )

    if not player:
        player = Entity(
            session_id=game_session.id,
            entity_key="player",
            display_name="Adventurer",
            entity_type=EntityType.PLAYER,
            is_alive=True,
            is_active=True,
        )
        db.add(player)
        db.flush()

    return player


@app.command()
def play(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Start the interactive game loop."""
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

        player = _get_or_create_player(db, game_session)
        db.commit()

        # Run the async game loop
        asyncio.run(_game_loop(db, game_session, player))

    except KeyboardInterrupt:
        display_info("\nGame paused. Use 'rpg game play' to continue.")
    finally:
        db.close()


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

    # Initial scene description
    initial_state = create_initial_state(
        session_id=game_session.id,
        player_id=player.id,
        player_location=player_location,
        player_input="[Looking around at the starting scene]",
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
                status()
                continue
            elif cmd == "inventory":
                from src.cli.commands.character import inventory
                inventory()
                continue
            elif cmd == "time":
                from src.cli.commands.world import time
                time()
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
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        player = _get_or_create_player(db, game_session)
        db.commit()

        # Run single turn
        asyncio.run(_single_turn(db, game_session, player, player_input))

    except Exception as e:
        display_error(f"Error: {e}")
        raise typer.Exit(1)
    finally:
        db.close()


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
