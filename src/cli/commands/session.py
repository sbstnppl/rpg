"""Session management commands."""

from typing import Optional

import typer
from rich.console import Console

from src.cli.display import (
    display_error,
    display_info,
    display_session_list,
    display_success,
)
from src.database.connection import get_db_session
from src.database.models.session import GameSession
from src.database.models.world import TimeState

app = typer.Typer(help="Manage game sessions")
console = Console()


def _deprecation_warning(new_command: str) -> None:
    """Display deprecation warning for session commands."""
    console.print(f"[yellow]⚠ Deprecated: Use '{new_command}' instead[/yellow]")
    console.print()


@app.command()
def start(
    name: str = typer.Option("New Adventure", "--name", "-n", help="Session name"),
    setting: str = typer.Option("fantasy", "--setting", "-s", help="Game setting"),
) -> None:
    """Start a new game session."""
    _deprecation_warning("rpg game start")
    try:
        with get_db_session() as db:
            # Create game session
            session = GameSession(
                session_name=name,
                setting=setting,
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="claude-sonnet-4-20250514",
            )
            db.add(session)
            db.flush()

            # Create initial time state
            time_state = TimeState(
                session_id=session.id,
                current_day=1,
                current_time="09:00",
                day_of_week="Monday",
                season="Spring",
                weather="Clear",
                temperature="Mild",
            )
            db.add(time_state)

            display_success(f"Created session '{name}' (ID: {session.id})")
            display_info(f"Setting: {setting}")
            display_info("Use 'rpg game play' to start playing!")

    except Exception as e:
        display_error(f"Failed to create session: {e}")
        raise typer.Exit(1)


@app.command("list")
def list_sessions(
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
) -> None:
    """List all game sessions."""
    _deprecation_warning("rpg game list")
    with get_db_session() as db:
        query = db.query(GameSession)
        if status:
            query = query.filter(GameSession.status == status)

        sessions = query.order_by(GameSession.id.desc()).all()

        session_dicts = [
            {
                "id": s.id,
                "name": s.session_name,
                "setting": s.setting,
                "status": s.status,
                "turns": s.total_turns,
            }
            for s in sessions
        ]

        display_session_list(session_dicts)


@app.command()
def load(
    session_id: int = typer.Argument(..., help="Session ID to load"),
) -> None:
    """Load and display session info."""
    _deprecation_warning("rpg game list")
    with get_db_session() as db:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()

        if not session:
            display_error(f"Session {session_id} not found")
            raise typer.Exit(1)

        console.print()
        console.print(f"[bold]Session:[/bold] {session.session_name}")
        console.print(f"[bold]ID:[/bold] {session.id}")
        console.print(f"[bold]Setting:[/bold] {session.setting}")
        console.print(f"[bold]Status:[/bold] {session.status}")
        console.print(f"[bold]Turns:[/bold] {session.total_turns}")
        console.print()


@app.command()
def delete(
    session_id: int = typer.Argument(..., help="Session ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a game session."""
    _deprecation_warning("rpg game delete")
    try:
        with get_db_session() as db:
            session = db.query(GameSession).filter(GameSession.id == session_id).first()

            if not session:
                display_error(f"Session {session_id} not found")
                raise typer.Exit(1)

            if not force:
                confirm = typer.confirm(
                    f"Delete session '{session.session_name}' (ID: {session_id})?"
                )
                if not confirm:
                    display_info("Cancelled")
                    return

            db.delete(session)

            display_success(f"Deleted session {session_id}")

    except typer.Exit:
        raise
    except Exception as e:
        display_error(f"Failed to delete session: {e}")
        raise typer.Exit(1)


@app.command("continue")
def continue_session(
    session_id: Optional[int] = typer.Argument(None, help="Session ID to continue"),
) -> None:
    """Continue the most recent or specified session."""
    _deprecation_warning("rpg game play")
    with get_db_session() as db:
        if session_id:
            session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            # Get most recent active session
            session = (
                db.query(GameSession)
                .filter(GameSession.status == "active")
                .order_by(GameSession.id.desc())
                .first()
            )

        if not session:
            display_error("No session found to continue")
            display_info("Use 'rpg session start' to create a new session")
            raise typer.Exit(1)

        display_success(f"Continuing session: {session.session_name} (ID: {session.id})")
        display_info(f"Turn: {session.total_turns}")
        display_info("Use 'rpg game play' to start playing!")
