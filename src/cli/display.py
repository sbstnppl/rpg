"""Rich display helpers for CLI output."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# Shared console instance
console = Console()


def display_narrative(text: str) -> None:
    """Display GM narrative with formatting.

    Args:
        text: Narrative text to display.
    """
    # Wrap in a panel with soft styling
    panel = Panel(
        text,
        border_style="dim",
        padding=(1, 2),
    )
    console.print(panel)


def display_welcome(session_name: str | None = None) -> None:
    """Display welcome message.

    Args:
        session_name: Optional session name.
    """
    title = "[bold cyan]RPG Game[/bold cyan]"
    if session_name:
        title += f" - {session_name}"

    console.print()
    console.print(Panel(title, style="cyan"))
    console.print()


def display_error(message: str) -> None:
    """Display error message.

    Args:
        message: Error message.
    """
    console.print(f"[bold red]Error:[/bold red] {message}")


def display_success(message: str) -> None:
    """Display success message.

    Args:
        message: Success message.
    """
    console.print(f"[bold green]{message}[/bold green]")


def display_info(message: str) -> None:
    """Display info message.

    Args:
        message: Info message.
    """
    console.print(f"[dim]{message}[/dim]")


def display_session_list(sessions: list[dict]) -> None:
    """Display list of game sessions.

    Args:
        sessions: List of session dicts with id, name, status, turns.
    """
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title="Game Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Setting", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Turns", justify="right")

    for s in sessions:
        status_style = "green" if s.get("status") == "active" else "dim"
        table.add_row(
            str(s.get("id", "")),
            s.get("name", "Unnamed"),
            s.get("setting", "fantasy"),
            f"[{status_style}]{s.get('status', 'unknown')}[/{status_style}]",
            str(s.get("turns", 0)),
        )

    console.print(table)


def display_character_status(
    name: str,
    stats: dict,
    needs: dict | None = None,
    conditions: list[str] | None = None,
) -> None:
    """Display character status panel.

    Args:
        name: Character name.
        stats: Dict of stat name to value.
        needs: Optional dict of need name to value (0-100).
        conditions: Optional list of condition strings.
    """
    lines = [f"[bold]{name}[/bold]", ""]

    # Stats
    if stats:
        lines.append("[underline]Attributes[/underline]")
        for stat_name, value in stats.items():
            lines.append(f"  {stat_name}: {value}")
        lines.append("")

    # Needs as progress bars
    if needs:
        lines.append("[underline]Needs[/underline]")
        for need_name, value in needs.items():
            bar = _progress_bar(value, 100)
            color = "green" if value > 60 else "yellow" if value > 30 else "red"
            lines.append(f"  {need_name}: [{color}]{bar}[/{color}] {value}/100")
        lines.append("")

    # Conditions
    if conditions:
        lines.append("[underline]Conditions[/underline]")
        for condition in conditions:
            lines.append(f"  - {condition}")

    panel = Panel("\n".join(lines), title="Character Status", border_style="blue")
    console.print(panel)


def display_inventory(items: list[dict]) -> None:
    """Display inventory table.

    Args:
        items: List of item dicts with name, type, equipped.
    """
    if not items:
        console.print("[dim]Inventory is empty.[/dim]")
        return

    table = Table(title="Inventory")
    table.add_column("Item", style="white")
    table.add_column("Type", style="cyan")
    table.add_column("Status", style="yellow")

    for item in items:
        status = "[green]Equipped[/green]" if item.get("equipped") else ""
        table.add_row(
            item.get("name", "Unknown"),
            item.get("type", "misc"),
            status,
        )

    console.print(table)


def display_location_info(
    name: str,
    description: str | None = None,
    npcs: list[str] | None = None,
) -> None:
    """Display location information.

    Args:
        name: Location name.
        description: Optional description.
        npcs: Optional list of NPC names present.
    """
    lines = [f"[bold]{name}[/bold]"]

    if description:
        lines.append("")
        lines.append(description)

    if npcs:
        lines.append("")
        lines.append("[underline]NPCs Present[/underline]")
        for npc in npcs:
            lines.append(f"  - {npc}")

    panel = Panel("\n".join(lines), title="Location", border_style="green")
    console.print(panel)


def _progress_bar(value: int, max_value: int, width: int = 20) -> str:
    """Create a simple progress bar string.

    Args:
        value: Current value.
        max_value: Maximum value.
        width: Bar width in characters.

    Returns:
        Progress bar string.
    """
    filled = int((value / max_value) * width)
    empty = width - filled
    return "[" + "=" * filled + " " * empty + "]"


def prompt_input(prompt: str = "> ") -> str:
    """Get input from user with styled prompt.

    Args:
        prompt: Prompt string.

    Returns:
        User input.
    """
    return console.input(f"[bold cyan]{prompt}[/bold cyan]")


def display_attribute_table(
    attributes: dict[str, int],
    show_modifiers: bool = True,
) -> None:
    """Display attribute values in a table.

    Args:
        attributes: Dict of attribute_key to value.
        show_modifiers: Whether to show D&D-style modifiers.
    """
    table = Table(title="Attributes")
    table.add_column("Attribute", style="white")
    table.add_column("Value", justify="right", style="cyan")
    if show_modifiers:
        table.add_column("Modifier", justify="right", style="yellow")

    for key, value in attributes.items():
        row = [key.title(), str(value)]
        if show_modifiers:
            modifier = (value - 10) // 2
            mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)
            row.append(mod_str)
        table.add_row(*row)

    console.print(table)


def display_dice_roll(
    attribute: str,
    rolls: list[int],
    dropped: int,
    total: int,
) -> None:
    """Display a 4d6-drop-lowest roll result.

    Args:
        attribute: Attribute name being rolled.
        rolls: The 4 dice values rolled.
        dropped: The dropped lowest value.
        total: Final total.
    """
    roll_str = ", ".join(
        f"[red]{r}[/red]" if r == dropped else f"[green]{r}[/green]"
        for r in rolls
    )
    console.print(
        f"  {attribute.title()}: [{roll_str}] → [bold cyan]{total}[/bold cyan]"
    )


def display_point_buy_status(used: int, total: int) -> None:
    """Display point-buy budget status.

    Args:
        used: Points used so far.
        total: Total budget.
    """
    remaining = total - used
    color = "green" if remaining > 5 else "yellow" if remaining > 0 else "red"
    console.print(
        f"Points: [{color}]{used}/{total}[/{color}] "
        f"([{color}]{remaining} remaining[/{color}])"
    )


def prompt_character_name() -> str:
    """Prompt for character name with validation.

    Returns:
        Valid character name.
    """
    while True:
        name = console.input("[bold cyan]Character name: [/bold cyan]").strip()
        if len(name) >= 2:
            return name
        console.print("[red]Name must be at least 2 characters.[/red]")


def prompt_background() -> str:
    """Prompt for optional character background.

    Returns:
        Background text or empty string.
    """
    console.print("\n[dim]Enter a brief background for your character (or press Enter to skip):[/dim]")
    return console.input("[bold cyan]Background: [/bold cyan]").strip()
