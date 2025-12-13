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

    # Needs with progress bars and status descriptions
    if needs:
        needs_table = Table(title="Needs", box=box.ROUNDED)
        needs_table.add_column("Need", style="white", width=10)
        needs_table.add_column("Level", width=22)
        needs_table.add_column("", justify="right", width=4)
        needs_table.add_column("Status", width=18)

        for need_name, value in needs.items():
            bar = _create_progress_bar(value, 100)
            description, color = _get_need_description(need_name, value)
            styled_desc = f"[{color}]{description}[/{color}]"
            needs_table.add_row(need_name, bar, str(value), styled_desc)

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


def _get_need_description(need_name: str, value: int) -> tuple[str, str]:
    """Return human-readable description and color for a need value.

    All needs follow the same semantics: 0 = bad (red), 100 = good (green).

    Args:
        need_name: Name of the need (lowercase).
        value: Current value (0-100).

    Returns:
        Tuple of (description, color) for the need state.
    """
    # Each need has thresholds: (max_value, description, color)
    # Listed from lowest to highest threshold
    # All needs: low value = red/yellow, high value = green
    descriptions = {
        "hunger": [
            (15, "starving", "red"),
            (30, "very hungry", "red"),
            (50, "hungry", "yellow"),
            (70, "satisfied", "green"),
            (85, "full", "green"),
            (100, "stuffed", "yellow"),
        ],
        "energy": [
            (20, "exhausted", "red"),
            (40, "very tired", "red"),
            (60, "tired", "yellow"),
            (80, "rested", "green"),
            (100, "energized", "green"),
        ],
        "hygiene": [
            (20, "filthy", "red"),
            (40, "dirty", "yellow"),
            (60, "passable", "yellow"),
            (80, "clean", "green"),
            (100, "spotless", "green"),
        ],
        "comfort": [
            (20, "miserable", "red"),
            (40, "uncomfortable", "yellow"),
            (60, "okay", "yellow"),
            (80, "comfortable", "green"),
            (100, "luxurious", "green"),
        ],
        "wellness": [
            (20, "agony", "red"),
            (40, "severe pain", "red"),
            (60, "moderate pain", "yellow"),
            (80, "slight discomfort", "yellow"),
            (100, "pain-free", "green"),
        ],
        "social": [
            (20, "lonely", "red"),
            (40, "isolated", "yellow"),
            (60, "connected", "yellow"),
            (80, "social", "green"),
            (100, "fulfilled", "green"),
        ],
        "morale": [
            (20, "depressed", "red"),
            (40, "low spirits", "yellow"),
            (60, "neutral", "yellow"),
            (80, "good spirits", "green"),
            (100, "elated", "green"),
        ],
        "purpose": [
            (20, "aimless", "red"),
            (40, "uncertain", "yellow"),
            (60, "focused", "yellow"),
            (80, "driven", "green"),
            (100, "inspired", "green"),
        ],
        "intimacy": [
            (20, "desperate", "red"),
            (40, "yearning", "yellow"),
            (60, "longing", "yellow"),
            (80, "satisfied", "green"),
            (100, "content", "green"),
        ],
    }

    # Get thresholds for this need
    thresholds = descriptions.get(need_name.lower(), [])
    if not thresholds:
        # Default fallback
        if value < 30:
            return ("low", "red")
        elif value < 70:
            return ("moderate", "yellow")
        else:
            return ("high", "green")

    # Find the matching threshold
    for threshold, desc, color in thresholds:
        if value <= threshold:
            return (desc, color)

    # Shouldn't happen, but fallback to last entry
    _, desc, color = thresholds[-1]
    return (desc, color)


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


def display_game_wizard_welcome() -> None:
    """Display welcome banner for the game start wizard."""
    console.print()
    console.print(Panel(
        "[bold cyan]Welcome to RPG Game[/bold cyan]\n\n"
        "[dim]Let's set up your adventure![/dim]",
        style="cyan",
        padding=(1, 2),
    ))
    console.print()


def display_setting_menu(settings: list[dict]) -> None:
    """Display setting selection menu.

    Args:
        settings: List of dicts with 'key', 'name', 'description'.
    """
    console.print("[bold]Choose a setting:[/bold]\n")
    for i, setting in enumerate(settings, 1):
        console.print(f"  [cyan][{i}][/cyan] {setting['name']}")
        console.print(f"      [dim]{setting['description']}[/dim]")
    console.print()


def prompt_setting_choice(settings: list[dict], default: str = "fantasy") -> str:
    """Prompt user to select a setting.

    Args:
        settings: List of setting dicts with 'key', 'name', 'description'.
        default: Default setting key if user presses Enter.

    Returns:
        Selected setting key.
    """
    display_setting_menu(settings)

    # Find default index for display
    default_idx = next(
        (i for i, s in enumerate(settings, 1) if s['key'] == default),
        1
    )

    while True:
        choice = console.input(
            f"[bold cyan]Your choice (1-{len(settings)}, Enter for {default.title()}): [/bold cyan]"
        ).strip()

        if not choice:
            return default

        # Try as number
        try:
            idx = int(choice)
            if 1 <= idx <= len(settings):
                return settings[idx - 1]['key']
            console.print(f"[red]Please enter a number between 1 and {len(settings)}[/red]")
            continue
        except ValueError:
            pass

        # Try as name
        choice_lower = choice.lower()
        for setting in settings:
            if setting['key'].lower() == choice_lower or setting['name'].lower().startswith(choice_lower):
                return setting['key']

        console.print("[red]Invalid choice. Enter a number or setting name.[/red]")


def prompt_session_name(default: str = "New Adventure") -> str:
    """Prompt for session/adventure name.

    Args:
        default: Default name if user presses Enter.

    Returns:
        Session name.
    """
    name = console.input(
        f"[bold cyan]What would you like to call this adventure? ({default}): [/bold cyan]"
    ).strip()
    return name if name else default


# ==================== Character Creation Wizard Display ====================


def display_character_wizard_menu(
    section_statuses: dict[str, str],
    section_titles: dict[str, str],
    section_order: list[str],
    section_accessible: dict[str, bool] | None = None,
) -> None:
    """Display the character creation wizard menu.

    Args:
        section_statuses: Dict of section_name -> status ("not_started", "in_progress", "complete")
        section_titles: Dict of section_name -> display title
        section_order: List of section names in display order
        section_accessible: Optional dict of section_name -> is_accessible. If None, all sections
            are considered accessible. Locked sections show [-] indicator.
    """
    console.print()

    # Build the menu content
    lines = []
    for i, section_name in enumerate(section_order, 1):
        title = section_titles.get(section_name, section_name.title())
        status = section_statuses.get(section_name, "not_started")
        is_accessible = (
            section_accessible.get(section_name, True)
            if section_accessible
            else True
        )

        # Status indicator - locked takes priority over not_started
        if not is_accessible:
            status_text = "[dim][-][/dim]"
        elif status == "complete":
            status_text = "[green][✓][/green]"
        elif status == "in_progress":
            status_text = "[yellow][~][/yellow]"
        else:
            status_text = "[dim][ ][/dim]"

        lines.append(f"  [cyan][{i}][/cyan] {title:<20} {status_text}")

    content = "\n".join(lines)

    panel = Panel(
        content,
        title="[bold cyan]Character Creation[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def prompt_wizard_section_choice(
    section_order: list[str],
    can_review: bool = False,
) -> int | str:
    """Prompt user to select a wizard section.

    Args:
        section_order: List of section names in order.
        can_review: Whether the review option is available.

    Returns:
        Section index (1-based) or 'q' for quit.
    """
    num_sections = len(section_order)

    while True:
        prompt = f"[bold cyan]Select section (1-{num_sections})"
        if can_review:
            prompt += ", or \\[r]eview"
        prompt += ", or \\[q]uit: [/bold cyan]"

        choice = console.input(prompt).strip().lower()

        if choice == 'q':
            return 'q'

        if choice == 'r' and can_review:
            # Return the index of review section
            return num_sections  # Review is always last

        try:
            idx = int(choice)
            if 1 <= idx <= num_sections:
                return idx
            console.print(f"[red]Please enter a number between 1 and {num_sections}[/red]")
        except ValueError:
            console.print("[red]Invalid choice. Enter a number, 'r' for review, or 'q' to quit.[/red]")


def display_section_header(section_title: str) -> None:
    """Display header when entering a wizard section.

    Args:
        section_title: Display title of the section.
    """
    console.print()
    console.print(Panel(
        f"[bold]{section_title}[/bold]",
        style="cyan",
        padding=(0, 2),
    ))
    console.print()


def display_section_complete(section_title: str) -> None:
    """Display message when section is completed.

    Args:
        section_title: Display title of the section.
    """
    console.print()
    console.print(f"[green]✓ {section_title} complete![/green]")
    console.print()


def display_character_review(
    name: str,
    species: str | None,
    age: int | None,
    gender: str | None,
    build: str | None,
    hair_description: str | None,
    eye_color: str | None,
    background: str | None,
    occupation: str | None,
    personality: str | None,
    attributes: dict[str, int] | None,
) -> None:
    """Display the full character review before confirmation.

    Args:
        name: Character name.
        species: Species (e.g., "human", "elf").
        age: Age in years.
        gender: Gender.
        build: Body build.
        hair_description: Hair color/style.
        eye_color: Eye color.
        background: Backstory summary.
        occupation: Primary occupation.
        personality: Personality traits.
        attributes: Dict of attribute name -> value.
    """
    console.print()

    # Identity section
    identity_lines = [f"[bold]{name}[/bold]"]
    if species and species.lower() != "human":
        identity_lines[0] += f" ({species})"
    if age:
        identity_lines.append(f"Age: {age}")
    if gender:
        identity_lines.append(f"Gender: {gender}")

    # Appearance section
    appearance_parts = []
    if build:
        appearance_parts.append(f"{build} build")
    if hair_description:
        appearance_parts.append(f"{hair_description} hair")
    if eye_color:
        appearance_parts.append(f"{eye_color} eyes")

    # Attributes table
    if attributes:
        attr_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        attr_table.add_column("Stat", style="cyan")
        attr_table.add_column("Value", justify="right")

        for attr_name in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            value = attributes.get(attr_name, "?")
            # Color code by value
            if isinstance(value, int):
                if value >= 14:
                    val_style = "green"
                elif value <= 8:
                    val_style = "red"
                else:
                    val_style = "white"
            else:
                val_style = "dim"
            attr_table.add_row(attr_name.upper()[:3], f"[{val_style}]{value}[/{val_style}]")

    # Build the review panel
    content = "\n".join(identity_lines)
    if appearance_parts:
        content += f"\n\n[dim]Appearance:[/dim] {', '.join(appearance_parts)}"
    if occupation:
        content += f"\n[dim]Occupation:[/dim] {occupation}"
    if background:
        bg_preview = background[:300] + "..." if len(background) > 300 else background
        content += f"\n\n[dim]Background:[/dim]\n{bg_preview}"
    if personality:
        content += f"\n\n[dim]Personality:[/dim] {personality}"

    panel = Panel(
        content,
        title="[bold cyan]Character Review[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)

    # Attributes as separate table
    if attributes:
        console.print()
        console.print("[dim]Attributes:[/dim]")
        console.print(attr_table)

    console.print()


def prompt_review_confirmation() -> str:
    """Prompt user to confirm or edit character.

    Returns:
        'confirm' to proceed, 'edit' to go back, 'quit' to cancel.
    """
    console.print("[dim]Ready to begin your adventure?[/dim]")
    console.print()
    console.print("  [cyan][1][/cyan] Start adventure")
    console.print("  [cyan][2][/cyan] Edit character")
    console.print("  [cyan][q][/cyan] Cancel")
    console.print()

    while True:
        choice = console.input("[bold cyan]Your choice: [/bold cyan]").strip().lower()

        if choice in ('1', 'y', 'yes', 'start', 's'):
            return 'confirm'
        elif choice in ('2', 'e', 'edit'):
            return 'edit'
        elif choice in ('q', 'quit', 'cancel'):
            return 'quit'
        else:
            console.print("[red]Please enter 1, 2, or q[/red]")


def display_wizard_ai_thinking() -> None:
    """Display thinking indicator for AI processing."""
    console.print("[dim]Thinking...[/dim]", end="\r")


def clear_wizard_ai_thinking() -> None:
    """Clear the thinking indicator."""
    console.print(" " * 20, end="\r")  # Clear the line


# ==================== Skill Check Display ====================


def display_skill_check_prompt(
    description: str,
    skill_name: str,
    skill_tier: str,
    skill_modifier: int,
    attribute_key: str,
    attribute_modifier: int,
    total_modifier: int,
    difficulty_assessment: str,
) -> None:
    """Display skill check prompt before rolling.

    Shows the player what they're attempting and their modifiers,
    without revealing the DC. Uses 2d10 bell curve system.

    Args:
        description: What the character is attempting.
        skill_name: Name of the skill.
        skill_tier: Tier name (Novice, Apprentice, etc.).
        skill_modifier: Modifier from skill proficiency.
        attribute_key: Governing attribute name.
        attribute_modifier: Modifier from attribute.
        total_modifier: Combined modifier.
        difficulty_assessment: How difficult this appears to the character.
    """
    # Format modifiers as +/- strings
    skill_mod_str = f"+{skill_modifier}" if skill_modifier >= 0 else str(skill_modifier)
    attr_mod_str = f"+{attribute_modifier}" if attribute_modifier >= 0 else str(attribute_modifier)
    total_mod_str = f"+{total_modifier}" if total_modifier >= 0 else str(total_modifier)

    lines = [
        f"[bold]{description}[/bold]",
        "",
        "[dim]Your modifiers (2d10 + modifier):[/dim]",
        f"  {skill_name.title()}: {skill_mod_str} ({skill_tier})",
        f"  {attribute_key.title()}: {attr_mod_str}",
        f"  [bold]Total: {total_mod_str}[/bold]",
        "",
        f"[italic]{difficulty_assessment}[/italic]",
        "",
        "[dim]Press ENTER to roll...[/dim]",
    ]

    panel = Panel(
        "\n".join(lines),
        title="[bold cyan]Skill Check[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)


def display_skill_check_result(
    success: bool,
    dice_rolls: list[int] | None,
    total_modifier: int,
    total_roll: int | None,
    dc: int,
    margin: int,
    outcome_tier: str,
    is_critical_success: bool = False,
    is_critical_failure: bool = False,
    is_auto_success: bool = False,
) -> None:
    """Display skill check result after rolling.

    Shows the roll (2d10), total, DC, and outcome tier.
    Uses 2d10 bell curve system with auto-success support.

    Args:
        success: Whether the check succeeded.
        dice_rolls: Individual 2d10 rolls (None if auto-success).
        total_modifier: Combined modifier applied.
        total_roll: Final total (dice + modifier), None if auto-success.
        dc: Difficulty Class that was beaten/missed.
        margin: How much over/under the DC.
        outcome_tier: Degree of success/failure (exceptional, clear_success, etc.).
        is_critical_success: Both dice = 10 (double-10).
        is_critical_failure: Both dice = 1 (double-1).
        is_auto_success: True if auto-success (no roll needed).
    """
    mod_str = f"+{total_modifier}" if total_modifier >= 0 else str(total_modifier)

    # Handle auto-success case
    if is_auto_success:
        lines = [
            "[bold green]AUTO-SUCCESS[/bold green]",
            "",
            f"[dim]DC {dc} ≤ {10 + total_modifier} (10 + your modifier)[/dim]",
            "",
            "[italic]This is routine for someone with your skill.[/italic]",
        ]

        panel = Panel(
            "\n".join(lines),
            title="[bold]Result[/bold]",
            border_style="green",
            padding=(0, 2),
        )
        console.print(panel)
        console.print()
        return

    # Format the dice roll (2d10)
    if dice_rolls and len(dice_rolls) == 2:
        dice_sum = sum(dice_rolls)
        if is_critical_success:
            # Both dice = 10
            dice_display = f"[bold yellow]({dice_rolls[0]}+{dice_rolls[1]})[/bold yellow]"
            crit_label = " CRITICAL!"
        elif is_critical_failure:
            # Both dice = 1
            dice_display = f"[bold red]({dice_rolls[0]}+{dice_rolls[1]})[/bold red]"
            crit_label = " CRITICAL!"
        else:
            dice_display = f"({dice_rolls[0]}+{dice_rolls[1]})"
            crit_label = ""
    else:
        dice_display = "?"
        dice_sum = 0
        crit_label = ""

    # Format the outcome based on tier
    tier_display = {
        "exceptional": ("[bold green]EXCEPTIONAL SUCCESS![/bold green]", "green"),
        "clear_success": ("[bold green]CLEAR SUCCESS[/bold green]", "green"),
        "narrow_success": ("[green]NARROW SUCCESS[/green]", "green"),
        "bare_success": ("[yellow]BARE SUCCESS[/yellow]", "yellow"),
        "partial_failure": ("[yellow]PARTIAL FAILURE[/yellow]", "yellow"),
        "clear_failure": ("[red]CLEAR FAILURE[/red]", "red"),
        "catastrophic": ("[bold red]CATASTROPHIC FAILURE![/bold red]", "red"),
    }

    if is_critical_success:
        outcome = "[bold yellow]CRITICAL SUCCESS![/bold yellow]"
        border_style = "yellow"
    elif is_critical_failure:
        outcome = "[bold red]CRITICAL FAILURE![/bold red]"
        border_style = "red"
    else:
        outcome, border_style = tier_display.get(
            outcome_tier,
            ("[green]SUCCESS[/green]" if success else "[red]FAILURE[/red]", "green" if success else "red")
        )

    # Build result display
    margin_str = f"+{margin}" if margin >= 0 else str(margin)
    lines = [
        f"Roll: {dice_display} {mod_str} = [bold]{total_roll}[/bold]{crit_label}",
        f"vs DC {dc}",
        "",
        outcome,
        f"[dim](margin: {margin_str})[/dim]",
    ]

    panel = Panel(
        "\n".join(lines),
        title="[bold]Result[/bold]",
        border_style=border_style,
        padding=(0, 2),
    )
    console.print(panel)
    console.print()


def wait_for_roll() -> None:
    """Wait for player to press ENTER to roll dice."""
    console.input("")


def display_rolling_animation() -> None:
    """Display a brief rolling animation.

    Uses a simple text-based animation for the dice roll.
    """
    import time
    import random

    # Quick animation showing dice tumbling
    dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    for _ in range(6):
        face = random.choice(dice_faces)
        console.print(f"  Rolling... {face}", end="\r")
        time.sleep(0.08)
    console.print(" " * 30, end="\r")  # Clear the line
