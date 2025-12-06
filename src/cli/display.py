"""Rich display helpers for CLI output."""

from contextlib import contextmanager

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
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
    """Display character status with Rich tables.

    Args:
        name: Character name.
        stats: Dict of stat name to value.
        needs: Optional dict of need name to value (0-100).
        conditions: Optional list of condition strings.
    """
    console.print()
    console.print(f"[bold cyan]{name}[/bold cyan]")
    console.print()

    # Attributes table
    if stats:
        attr_table = Table(title="Attributes", box=box.ROUNDED)
        attr_table.add_column("Attribute", style="white")
        attr_table.add_column("Value", justify="center", style="cyan")
        attr_table.add_column("Modifier", justify="center", style="yellow")

        for stat_name, value in stats.items():
            modifier = (value - 10) // 2
            mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)
            attr_table.add_row(stat_name, str(value), mod_str)

        console.print(attr_table)
        console.print()

    # Needs with progress bars
    if needs:
        needs_table = Table(title="Needs", box=box.ROUNDED)
        needs_table.add_column("Need", style="white", width=12)
        needs_table.add_column("Level", width=25)
        needs_table.add_column("Value", justify="right", width=8)

        for need_name, value in needs.items():
            bar = _create_progress_bar(value, 100)
            needs_table.add_row(need_name, bar, f"{value}/100")

        console.print(needs_table)
        console.print()

    # Conditions
    if conditions:
        cond_table = Table(title="Conditions", box=box.ROUNDED)
        cond_table.add_column("Status", style="yellow")
        for condition in conditions:
            cond_table.add_row(condition)
        console.print(cond_table)


def display_inventory(items: list[dict]) -> None:
    """Display inventory table with enhanced formatting.

    Args:
        items: List of item dicts with name, type, equipped, slot, condition.
    """
    if not items:
        console.print("[dim]Inventory is empty.[/dim]")
        return

    table = Table(title="Inventory", box=box.ROUNDED)
    table.add_column("Item", style="white", no_wrap=True)
    table.add_column("Type", style="cyan")
    table.add_column("Slot", style="blue")
    table.add_column("Condition", style="yellow")
    table.add_column("Status", style="green")

    for item in items:
        status = "[green]Equipped[/green]" if item.get("equipped") else ""
        slot = item.get("slot", "")
        condition = item.get("condition", "good").title()

        # Color condition based on state
        if condition.lower() == "pristine":
            condition = f"[bright_green]{condition}[/bright_green]"
        elif condition.lower() == "good":
            condition = f"[green]{condition}[/green]"
        elif condition.lower() == "worn":
            condition = f"[yellow]{condition}[/yellow]"
        elif condition.lower() == "damaged":
            condition = f"[red]{condition}[/red]"
        elif condition.lower() == "broken":
            condition = f"[bright_red]{condition}[/bright_red]"

        table.add_row(
            item.get("name", "Unknown"),
            item.get("type", "misc").title(),
            slot.replace("_", " ").title() if slot else "-",
            condition,
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


def _create_progress_bar(value: int, max_value: int, width: int = 20) -> Text:
    """Create a Rich Text progress bar with color coding.

    Args:
        value: Current value.
        max_value: Maximum value.
        width: Bar width in characters.

    Returns:
        Rich Text object with styled progress bar.
    """
    filled = int((value / max_value) * width) if max_value > 0 else 0
    empty = width - filled

    # Color based on value percentage
    if value > 60:
        color = "green"
    elif value > 30:
        color = "yellow"
    else:
        color = "red"

    bar_text = Text()
    bar_text.append("[", style="dim")
    bar_text.append("=" * filled, style=color)
    bar_text.append(" " * empty, style="dim")
    bar_text.append("]", style="dim")

    return bar_text


def _progress_bar(value: int, max_value: int, width: int = 20) -> str:
    """Create a simple progress bar string (legacy).

    Args:
        value: Current value.
        max_value: Maximum value.
        width: Bar width in characters.

    Returns:
        Progress bar string.
    """
    filled = int((value / max_value) * width) if max_value > 0 else 0
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


def display_ai_message(text: str) -> None:
    """Display AI assistant message in conversation style.

    Args:
        text: AI response text.
    """
    panel = Panel(
        text,
        title="Character Creation Assistant",
        title_align="left",
        border_style="magenta",
        padding=(1, 2),
    )
    console.print(panel)


def display_suggested_attributes(attributes: dict[str, int]) -> None:
    """Display AI-suggested attributes.

    Args:
        attributes: Dict of attribute_key to suggested value.
    """
    console.print("\n[bold magenta]Suggested Attributes:[/bold magenta]")
    display_attribute_table(attributes, show_modifiers=True)


def prompt_ai_input() -> str:
    """Get player input during AI conversation.

    Returns:
        Player input.
    """
    return console.input("\n[bold cyan]You: [/bold cyan]").strip()


def display_character_summary(
    name: str,
    attributes: dict[str, int],
    background: str,
) -> None:
    """Display final character summary for confirmation.

    Args:
        name: Character name.
        attributes: Final attributes.
        background: Character background.
    """
    lines = [
        f"[bold]Name:[/bold] {name}",
        "",
        "[underline]Attributes[/underline]",
    ]

    for key, value in attributes.items():
        modifier = (value - 10) // 2
        mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)
        lines.append(f"  {key.title()}: {value} ({mod_str})")

    if background:
        lines.extend(["", "[underline]Background[/underline]", f"  {background}"])

    panel = Panel(
        "\n".join(lines),
        title="Character Summary",
        border_style="green",
    )
    console.print(panel)


def display_equipment(slots: dict[str, list[dict]]) -> None:
    """Display equipment by body slot with layer visualization.

    Args:
        slots: Dict of slot_name to list of items at that slot.
               Each item dict should have: name, layer, visible, condition.
    """
    if not slots or all(not items for items in slots.values()):
        console.print("[dim]No equipment worn.[/dim]")
        return

    table = Table(title="Equipment", box=box.ROUNDED)
    table.add_column("Slot", style="cyan", width=15)
    table.add_column("Layer", justify="center", width=6)
    table.add_column("Item", style="white")
    table.add_column("Visible", justify="center", width=8)
    table.add_column("Condition", style="yellow")

    for slot_name, items in sorted(slots.items()):
        if not items:
            table.add_row(
                slot_name.replace("_", " ").title(),
                "-",
                "[dim]Empty[/dim]",
                "-",
                "-"
            )
        else:
            # Sort by layer (innermost first)
            sorted_items = sorted(items, key=lambda x: x.get("layer", 0))
            for i, item in enumerate(sorted_items):
                visible = "[green]Yes[/green]" if item.get("visible", True) else "[dim]No[/dim]"
                slot_display = slot_name.replace("_", " ").title() if i == 0 else ""
                condition = item.get("condition", "good").title()

                # Color condition
                if condition.lower() == "pristine":
                    condition = f"[bright_green]{condition}[/bright_green]"
                elif condition.lower() == "good":
                    condition = f"[green]{condition}[/green]"
                elif condition.lower() == "worn":
                    condition = f"[yellow]{condition}[/yellow]"
                elif condition.lower() == "damaged":
                    condition = f"[red]{condition}[/red]"
                elif condition.lower() == "broken":
                    condition = f"[bright_red]{condition}[/bright_red]"

                table.add_row(
                    slot_display,
                    str(item.get("layer", 0)),
                    item.get("name", "Unknown"),
                    visible,
                    condition
                )

    console.print(table)


def display_starting_equipment(items: list[dict]) -> None:
    """Display starting equipment after character creation.

    Args:
        items: List of item dicts with name, type, slot.
    """
    if not items:
        return

    console.print("\n[bold cyan]Starting Equipment:[/bold cyan]")
    table = Table(box=box.SIMPLE)
    table.add_column("Item", style="white")
    table.add_column("Type", style="cyan")
    table.add_column("Slot", style="blue")

    for item in items:
        slot = item.get("slot", "")
        table.add_row(
            item.get("name", "Unknown"),
            item.get("type", "misc").title(),
            slot.replace("_", " ").title() if slot else "Inventory",
        )

    console.print(table)


@contextmanager
def progress_spinner(description: str = "Processing..."):
    """Context manager for spinner during operations.

    Args:
        description: Text to show next to spinner.

    Yields:
        Tuple of (progress, task_id) for optional updates.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description, total=None)
        yield progress, task


@contextmanager
def progress_bar(description: str, total: int = 100):
    """Context manager for progress bar during multi-step operations.

    Args:
        description: Text to show next to bar.
        total: Total steps (default 100 for percentage).

    Yields:
        Tuple of (progress, task_id) for updating.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description, total=total)
        yield progress, task
