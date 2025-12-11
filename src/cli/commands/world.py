"""World-related commands."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.cli.display import display_error, display_info, display_location_info, display_success
from src.database.connection import get_db_session
from src.database.models.entities import Entity
from src.database.models.enums import EntityType, TerrainType
from src.database.models.navigation import TerrainZone, ZoneConnection, ZoneDiscovery
from src.database.models.session import GameSession
from src.database.models.world import Location, TimeState, WorldEvent
from src.managers.discovery_manager import DiscoveryManager
from src.managers.zone_manager import ZoneManager

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
    with get_db_session() as db:
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


@app.command()
def locations(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """List known locations."""
    with get_db_session() as db:
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


@app.command()
def npcs(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Filter by location"),
) -> None:
    """List known NPCs."""
    with get_db_session() as db:
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


@app.command()
def events(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of events to show"),
) -> None:
    """Show recent world events."""
    with get_db_session() as db:
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


# ============================================================================
# Navigation / Zone Commands
# ============================================================================


@app.command()
def zones(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all zones (not just discovered)"),
) -> None:
    """List terrain zones."""
    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        zone_mgr = ZoneManager(db, game_session)
        all_zones = zone_mgr.get_all_zones()

        if not all_zones:
            display_info("No terrain zones defined")
            return

        # Filter to discovered zones unless --all
        if show_all:
            zones_to_show = all_zones
        else:
            discovered_ids = set(
                z.zone_id for z in db.query(ZoneDiscovery)
                .filter(ZoneDiscovery.session_id == game_session.id)
                .all()
            )
            zones_to_show = [z for z in all_zones if z.id in discovered_ids]

        if not zones_to_show:
            display_info("No discovered zones yet (use --all to see all)")
            return

        table = Table(title="Terrain Zones" + (" (all)" if show_all else " (discovered)"))
        table.add_column("Zone Key", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Terrain", style="yellow")
        table.add_column("Travel Cost", style="white")

        for zone in zones_to_show:
            terrain = zone.terrain_type.value if zone.terrain_type else "unknown"
            cost = str(zone.base_travel_cost) + " min" if zone.base_travel_cost else "-"
            table.add_row(zone.zone_key, zone.display_name, terrain, cost)

        console.print(table)


@app.command("create-zone")
def create_zone(
    zone_key: str = typer.Argument(..., help="Unique zone key"),
    name: str = typer.Argument(..., help="Display name"),
    terrain: str = typer.Argument(..., help="Terrain type (forest, plains, road, lake, etc.)"),
    travel_cost: int = typer.Option(15, "--cost", "-c", help="Base travel cost in minutes"),
    description: str = typer.Option(None, "--desc", "-d", help="Zone description"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Create a new terrain zone."""
    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        # Parse terrain type
        try:
            terrain_type = TerrainType(terrain.lower())
        except ValueError:
            valid = ", ".join(t.value for t in TerrainType)
            display_error(f"Invalid terrain type '{terrain}'. Valid: {valid}")
            raise typer.Exit(1)

        zone_mgr = ZoneManager(db, game_session)

        # Check if exists
        existing = zone_mgr.get_zone(zone_key)
        if existing:
            display_error(f"Zone '{zone_key}' already exists")
            raise typer.Exit(1)

        zone = zone_mgr.create_zone(
            zone_key=zone_key,
            display_name=name,
            terrain_type=terrain_type,
            base_travel_cost=travel_cost,
            description=description,
        )
        db.commit()

        display_success(f"Created zone '{zone.display_name}' ({zone_key})")


@app.command("connect-zones")
def connect_zones(
    from_zone: str = typer.Argument(..., help="Source zone key"),
    to_zone: str = typer.Argument(..., help="Destination zone key"),
    direction: str = typer.Option(None, "--direction", "-d", help="Direction (north, south, east, west, up, down)"),
    crossing_time: int = typer.Option(5, "--time", "-t", help="Crossing time in minutes"),
    bidirectional: bool = typer.Option(True, "--bidirectional/--one-way", "-b/-o", help="Create connection in both directions"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Connect two terrain zones."""
    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        zone_mgr = ZoneManager(db, game_session)

        # Verify zones exist
        from_z = zone_mgr.get_zone(from_zone)
        to_z = zone_mgr.get_zone(to_zone)

        if not from_z:
            display_error(f"Zone '{from_zone}' not found")
            raise typer.Exit(1)
        if not to_z:
            display_error(f"Zone '{to_zone}' not found")
            raise typer.Exit(1)

        result = zone_mgr.connect_zones(
            from_zone_key=from_zone,
            to_zone_key=to_zone,
            direction=direction,
            crossing_minutes=crossing_time,
            bidirectional=bidirectional,
        )

        if result["success"]:
            dir_str = f" ({direction})" if direction else ""
            bi_str = " (bidirectional)" if bidirectional else " (one-way)"
            display_success(f"Connected {from_zone} -> {to_zone}{dir_str}{bi_str}")
        else:
            display_error(f"Failed to connect zones: {result.get('reason', 'unknown error')}")
            raise typer.Exit(1)


@app.command("place-location")
def place_location(
    location_key: str = typer.Argument(..., help="Location key"),
    zone_key: str = typer.Argument(..., help="Zone key to place in"),
    visibility: str = typer.Option("visible_from_zone", "--visibility", "-v", help="Visibility level"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Place a location in a terrain zone."""
    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        zone_mgr = ZoneManager(db, game_session)

        # Verify zone exists
        zone = zone_mgr.get_zone(zone_key)
        if not zone:
            display_error(f"Zone '{zone_key}' not found")
            raise typer.Exit(1)

        # Verify location exists
        location = (
            db.query(Location)
            .filter(
                Location.session_id == game_session.id,
                Location.location_key == location_key,
            )
            .first()
        )
        if not location:
            display_error(f"Location '{location_key}' not found")
            raise typer.Exit(1)

        result = zone_mgr.place_location_in_zone(
            location_key=location_key,
            zone_key=zone_key,
            visibility=visibility,
        )
        db.commit()

        if result["success"]:
            display_success(f"Placed '{location.display_name}' in zone '{zone.display_name}'")
        else:
            display_error(f"Failed to place location: {result.get('reason', 'unknown error')}")
            raise typer.Exit(1)


@app.command("zone-info")
def zone_info(
    zone_key: str = typer.Argument(..., help="Zone key"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show detailed information about a zone."""
    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        zone_mgr = ZoneManager(db, game_session)
        zone = zone_mgr.get_zone(zone_key)

        if not zone:
            display_error(f"Zone '{zone_key}' not found")
            raise typer.Exit(1)

        console.print()
        console.print(f"[bold]{zone.display_name}[/bold] ({zone.zone_key})")
        console.print()

        if zone.terrain_type:
            console.print(f"[bold]Terrain:[/bold] {zone.terrain_type.value}")
        if zone.base_travel_cost:
            console.print(f"[bold]Travel Cost:[/bold] {zone.base_travel_cost} minutes")
        if zone.description:
            console.print(f"[bold]Description:[/bold] {zone.description}")
        if zone.requires_skill:
            console.print(f"[bold]Requires:[/bold] {zone.requires_skill} (DC {zone.skill_difficulty})")

        # Show adjacent zones
        adjacent = zone_mgr.get_adjacent_zones_with_directions(zone_key)
        if adjacent:
            console.print()
            console.print("[bold]Adjacent Zones:[/bold]")
            for item in adjacent:
                adj_zone = item["zone"]
                direction = item["direction"]
                dir_str = f"({direction}) " if direction else ""
                console.print(f"  {dir_str}{adj_zone.display_name}")

        # Show locations in this zone
        locations_list = zone_mgr.get_zone_locations(zone_key)
        if locations_list:
            console.print()
            console.print("[bold]Locations:[/bold]")
            for loc in locations_list:
                console.print(f"  - {loc.display_name}")

        console.print()


@app.command("discovered")
def discovered(
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Show all discovered zones and locations."""
    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found")
            raise typer.Exit(1)

        discovery_mgr = DiscoveryManager(db, game_session)

        # Get discovered zones
        zones_list = discovery_mgr.get_known_zones()
        locations_list = discovery_mgr.get_known_locations()

        console.print()
        console.print("[bold]Discovered Areas[/bold]")
        console.print()

        if zones_list:
            console.print("[bold]Zones:[/bold]")
            for zone in zones_list:
                terrain = zone.terrain_type.value if zone.terrain_type else "unknown"
                console.print(f"  - {zone.display_name} ({terrain})")
        else:
            console.print("[dim]No zones discovered[/dim]")

        console.print()

        if locations_list:
            console.print("[bold]Locations:[/bold]")
            for loc in locations_list:
                console.print(f"  - {loc.display_name}")
        else:
            console.print("[dim]No locations discovered[/dim]")

        console.print()


@app.command("import")
def import_world(
    file_path: str = typer.Argument(..., help="Path to YAML/JSON world file"),
    session_id: Optional[int] = typer.Option(None, "--session", "-s", help="Session ID"),
) -> None:
    """Import world data from a YAML or JSON file.

    The file should contain zones, connections, and locations in the
    WorldTemplate format. Use YAML for easy editing or JSON for programmatic
    generation.

    Example YAML structure:

        name: "My World"
        zones:
          - zone_key: village
            display_name: Village Center
            terrain_type: grassland
        connections:
          - from_zone: village
            to_zone: forest
            direction: north
        locations:
          - location_key: tavern
            display_name: The Rusty Tankard
            zone_key: village
            category: tavern
    """
    from pathlib import Path

    from src.services.world_loader import WorldLoadError, load_world_from_file

    path = Path(file_path)

    with get_db_session() as db:
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = _get_active_session(db)

        if not game_session:
            display_error("No active session found. Create a session first.")
            raise typer.Exit(1)

        try:
            results = load_world_from_file(db, game_session, path)
        except FileNotFoundError:
            display_error(f"File not found: {path}")
            raise typer.Exit(1)
        except WorldLoadError as e:
            display_error(f"Failed to load world: {e}")
            raise typer.Exit(1)

        # Report results
        console.print()
        display_success(
            f"Imported world from {path.name}:\n"
            f"  - {results['zones']} zones\n"
            f"  - {results['connections']} connections\n"
            f"  - {results['locations']} locations"
        )

        if results.get("errors"):
            console.print()
            console.print("[yellow]Warnings:[/yellow]")
            for error in results["errors"]:
                console.print(f"  - {error}")

        console.print()
