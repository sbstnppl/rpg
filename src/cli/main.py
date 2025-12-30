"""Main CLI application for the RPG game."""

import typer

from src.cli.commands import session, character, world, game, scene

# Create main app
app = typer.Typer(
    name="rpg",
    help="An AI-powered console RPG with multi-agent orchestration",
    add_completion=True,
)

# Add sub-commands
app.add_typer(session.app, name="session")
app.add_typer(character.app, name="character")
app.add_typer(world.app, name="world")
app.add_typer(game.app, name="game")
app.add_typer(scene.app, name="scene")


@app.command()
def play(
    session_id: int = typer.Option(None, "--session", "-s", help="Session ID to play"),
) -> None:
    """Quick start - begin or continue playing.

    This is a shortcut for 'rpg game play'.
    """
    # Pass explicit defaults since Typer Option objects aren't resolved
    # when calling function directly (not via CLI)
    game.play(session_id=session_id, roll_mode="auto", anticipation=None)


@app.callback()
def main() -> None:
    """RPG Game - An AI-powered console RPG.

    Use 'rpg session start' to create a new game, then 'rpg play' to begin.
    """
    pass


if __name__ == "__main__":
    app()
