"""World-related commands."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.cli.display import display_error, display_info, display_location_info
from src.cli.commands.session import get_db_session
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.database.models.world import Location, TimeState, WorldEvent

app = typer.Typer(help="World information commands")
console = Console()


def _get_active_session(db) -> GameSession | None:
    """Get the most recent active session."""
    return (
        db.query(GameSession)
        .filter(GameSession.status == "active")
        .order_by(GameSession.id.desc())
        .first()
    )


@app.command()
def time(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show current game time."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        time_state = (
            db.query(TimeState)
            .filter(TimeState.session_id == game_session.id)
            .first()
        )

        if not time_state:
            display_info("Time not initialized")
            return

        console.print()
        console.print(f"[bold]Day {time_state.current_day}[/bold] ({time_state.day_of_week})")
        console.print(f"[bold]Time:[/bold] {time_state.current_time}")

        if time_state.season:
            console.print(f"[bold]Season:[/bold] {time_state.season}")
        if time_state.weather:
            console.print(f"[bold]Weather:[/bold] {time_state.weather}")
        if time_state.temperature:
            console.print(f"[bold]Temperature:[/bold] {time_state.temperature}")

        console.print()

    finally:
        db.close()


@app.command()
def locations(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """List known locations."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        locations_list = (
            db.query(Location)
            .filter(Location.session_id == game_session.id)
            .order_by(Location.display_name)
            .all()
        )

        if not locations_list:
            display_info("No locations discovered yet")
            return

        table = Table(title="Known Locations")
        table.add_column("Location", style="green")
        table.add_column("Type", style="cyan")
        table.add_column("Description", style="white", max_width=50)

        for loc in locations_list:
            table.add_row(
                loc.display_name,
                loc.location_type or "unknown",
                (loc.description[:47] + "...") if loc.description and len(loc.description) > 50 else (loc.description or ""),
            )

        console.print(table)

    finally:
        db.close()


@app.command()
def npcs(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Filter by location"),
) -> None:
    """List known NPCs."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        query = db.query(Entity).filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.NPC,
            Entity.is_alive == True,
        )

        # Note: Location filtering would require tracking current_location
        # For now, show all NPCs

        npcs_list = query.order_by(Entity.display_name).all()

        if not npcs_list:
            display_info("No NPCs encountered yet")
            return

        table = Table(title="Known NPCs")
        table.add_column("Name", style="yellow")
        table.add_column("Status", style="green")

        for npc in npcs_list:
            status = "Active" if npc.is_active else "Inactive"
            table.add_row(npc.display_name, status)

        console.print(table)

    finally:
        db.close()


@app.command()
def events(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of events to show"),
) -> None:
    """Show recent world events."""
    db = get_db_session()

    try:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        events_list = (
            db.query(WorldEvent)
            .filter(WorldEvent.session_id == game_session.id)
            .order_by(WorldEvent.id.desc())
            .limit(limit)
            .all()
        )

        if not events_list:
            display_info("No events recorded yet")
            return

        console.print()
        console.print("[bold]Recent Events[/bold]")
        console.print()

        for event in reversed(events_list):  # Show oldest first
            console.print(f"[dim]Day {event.game_day}, {event.game_time}[/dim]")
            console.print(f"  {event.description}")
            console.print()

    finally:
        db.close()
