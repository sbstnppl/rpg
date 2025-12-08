"""Navigation models for world map, zones, paths, and discovery."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import (
    ConnectionType,
    DiscoveryMethod,
    EncounterFrequency,
    MapType,
    PlacementType,
    TerrainType,
    TransportType,
    VisibilityRange,
)

if TYPE_CHECKING:
    from src.database.models.items import Item
    from src.database.models.session import GameSession
    from src.database.models.world import Location


class TerrainZone(Base, TimestampMixin):
    """An explorable terrain zone in the world.

    Represents a segment of terrain (forest, plains, road, etc.) that players
    can traverse. Zones connect to each other via ZoneConnection and contain
    Locations within them.
    """

    __tablename__ = "terrain_zones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    zone_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'darkwood_forest_north')",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    terrain_type: Mapped[TerrainType] = mapped_column(
        Enum(TerrainType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )

    # Hierarchy (optional parent region/zone)
    parent_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Movement costs (minutes per unit of travel)
    base_travel_cost: Mapped[int] = mapped_column(
        default=10,
        nullable=False,
        comment="Base walking time in minutes per unit distance",
    )
    mounted_travel_cost: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Travel time on mount (null = impassable by mount)",
    )

    # Accessibility requirements
    requires_skill: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Skill required to enter (e.g., 'swimming', 'climbing')",
    )
    skill_difficulty: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="DC for skill check if required",
    )
    failure_consequence: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="What happens on failed check (e.g., 'drowning', 'fall_damage')",
    )

    # Environment
    visibility_range: Mapped[VisibilityRange] = mapped_column(
        Enum(VisibilityRange, values_callable=lambda obj: [e.value for e in obj]),
        default=VisibilityRange.MEDIUM,
        nullable=False,
        comment="How far player can see in this zone",
    )
    encounter_frequency: Mapped[EncounterFrequency] = mapped_column(
        Enum(EncounterFrequency, values_callable=lambda obj: [e.value for e in obj]),
        default=EncounterFrequency.LOW,
        nullable=False,
    )
    encounter_table_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Key to encounter table for this zone",
    )

    # Description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full description of the zone",
    )
    atmosphere: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Mood, sounds, smells",
    )

    # Dynamic state
    is_accessible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    blocked_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why zone is blocked (fire, flood, etc.)",
    )

    # Relationships
    parent_zone: Mapped["TerrainZone | None"] = relationship(
        remote_side="TerrainZone.id",
        foreign_keys=[parent_zone_id],
    )
    outgoing_connections: Mapped[list["ZoneConnection"]] = relationship(
        back_populates="from_zone",
        foreign_keys="ZoneConnection.from_zone_id",
    )
    incoming_connections: Mapped[list["ZoneConnection"]] = relationship(
        back_populates="to_zone",
        foreign_keys="ZoneConnection.to_zone_id",
    )
    location_placements: Mapped[list["LocationZonePlacement"]] = relationship(
        back_populates="zone",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "zone_key", name="uq_terrain_zone_session_key"),
    )

    def __repr__(self) -> str:
        return f"<TerrainZone {self.zone_key} ({self.terrain_type.value})>"


class ZoneConnection(Base, TimestampMixin):
    """Connection between two terrain zones.

    Represents a path, bridge, or passage between adjacent zones.
    Supports both bidirectional and one-way connections.
    """

    __tablename__ = "zone_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Connected zones
    from_zone_id: Mapped[int] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_zone_id: Mapped[int] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Connection properties
    direction: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Direction: north, south, east, west, up, down, inside, etc.",
    )
    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType, values_callable=lambda obj: [e.value for e in obj]),
        default=ConnectionType.OPEN,
        nullable=False,
    )

    # Crossing requirements
    crossing_minutes: Mapped[int] = mapped_column(
        default=5,
        nullable=False,
        comment="Time to cross this connection in minutes",
    )
    requires_skill: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Skill required to cross (additional to destination zone)",
    )
    skill_difficulty: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="DC for crossing skill check",
    )

    # Directionality
    is_bidirectional: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Can travel both ways?",
    )

    # State
    is_passable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    blocked_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why connection is blocked (bridge destroyed, locked, etc.)",
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False for secret passages",
    )

    # Description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the path/passage",
    )

    # Relationships
    from_zone: Mapped["TerrainZone"] = relationship(
        back_populates="outgoing_connections",
        foreign_keys=[from_zone_id],
    )
    to_zone: Mapped["TerrainZone"] = relationship(
        back_populates="incoming_connections",
        foreign_keys=[to_zone_id],
    )

    # Index for pathfinding queries
    __table_args__ = (
        Index("ix_zone_connection_from_passable", "from_zone_id", "is_passable"),
    )

    def __repr__(self) -> str:
        direction_str = f" ({self.direction})" if self.direction else ""
        return f"<ZoneConnection {self.from_zone_id} -> {self.to_zone_id}{direction_str}>"


class LocationZonePlacement(Base, TimestampMixin):
    """Links a Location to a TerrainZone.

    Specifies where a location (village, building, etc.) sits relative to
    a terrain zone.
    """

    __tablename__ = "location_zone_placements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Links
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Placement details
    placement_type: Mapped[PlacementType] = mapped_column(
        Enum(PlacementType, values_callable=lambda obj: [e.value for e in obj]),
        default=PlacementType.WITHIN,
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        String(50),
        default="visible_from_zone",
        nullable=False,
        comment="visible_from_zone, hidden, requires_search",
    )

    # Relationships
    location: Mapped["Location"] = relationship()
    zone: Mapped["TerrainZone"] = relationship(
        back_populates="location_placements",
    )

    # Unique constraint (a location can only be in one zone)
    __table_args__ = (
        UniqueConstraint(
            "session_id", "location_id", name="uq_location_zone_placement_location"
        ),
    )

    def __repr__(self) -> str:
        return f"<LocationZonePlacement loc={self.location_id} zone={self.zone_id}>"


class TransportMode(Base, TimestampMixin):
    """Defines a mode of transport and its terrain capabilities.

    Global definition (not per-session) of how different transport modes
    interact with terrain types.
    """

    __tablename__ = "transport_modes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identity
    mode_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique key (e.g., 'walking', 'mounted', 'swimming')",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    transport_type: Mapped[TransportType] = mapped_column(
        Enum(TransportType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Terrain costs (JSON: terrain_type -> cost_multiplier, null = impassable)
    terrain_costs: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment='Map of terrain_type to cost multiplier (null = impassable)',
    )

    # Requirements
    requires_skill: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Skill required to use this mode",
    )
    requires_item: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Item required (e.g., 'horse', 'boat')",
    )

    # Effects
    fatigue_rate: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Energy cost multiplier per unit time",
    )
    encounter_modifier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Encounter chance multiplier (0.5 = fewer, 2.0 = more)",
    )

    def __repr__(self) -> str:
        return f"<TransportMode {self.mode_key}>"


class ZoneDiscovery(Base, TimestampMixin):
    """Tracks which terrain zones a player has discovered (fog of war).

    Session-scoped discovery of terrain zones.
    """

    __tablename__ = "zone_discoveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What was discovered
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Discovery details
    discovered_turn: Mapped[int] = mapped_column(
        nullable=False,
        comment="Turn when zone was discovered",
    )
    discovery_method: Mapped[DiscoveryMethod] = mapped_column(
        Enum(DiscoveryMethod, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Source of discovery (optional)
    source_map_id: Mapped[int | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
        comment="If discovered via map item",
    )
    source_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="If told by NPC",
    )
    source_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="SET NULL"),
        nullable=True,
        comment="If visible from another zone",
    )

    # Unique constraint (a zone can only be discovered once per session)
    __table_args__ = (
        UniqueConstraint(
            "session_id", "zone_id", name="uq_zone_discovery_session_zone"
        ),
    )

    def __repr__(self) -> str:
        return f"<ZoneDiscovery zone={self.zone_id} turn={self.discovered_turn}>"


class LocationDiscovery(Base, TimestampMixin):
    """Tracks which locations a player has discovered (fog of war).

    Session-scoped discovery of specific locations within zones.
    """

    __tablename__ = "location_discoveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What was discovered
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Discovery details
    discovered_turn: Mapped[int] = mapped_column(
        nullable=False,
        comment="Turn when location was discovered",
    )
    discovery_method: Mapped[DiscoveryMethod] = mapped_column(
        Enum(DiscoveryMethod, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Source of discovery (optional)
    source_map_id: Mapped[int | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
        comment="If discovered via map item",
    )
    source_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="If told by NPC",
    )

    # Unique constraint (a location can only be discovered once per session)
    __table_args__ = (
        UniqueConstraint(
            "session_id", "location_id", name="uq_location_discovery_session_location"
        ),
    )

    def __repr__(self) -> str:
        return f"<LocationDiscovery loc={self.location_id} turn={self.discovered_turn}>"


class MapItem(Base, TimestampMixin):
    """Extension for Item that makes it a map revealing locations.

    Links to an Item and adds map-specific properties.
    """

    __tablename__ = "map_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Link to base Item
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Map properties
    map_type: Mapped[MapType] = mapped_column(
        Enum(MapType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    coverage_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("terrain_zones.id", ondelete="SET NULL"),
        nullable=True,
        comment="Root zone this map covers (and all children)",
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Full map or partial/damaged?",
    )

    # Specific zones/locations revealed (if not using coverage_zone_id)
    revealed_zone_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Specific zone IDs this map reveals",
    )
    revealed_location_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Specific location IDs this map reveals",
    )

    # Relationships
    item: Mapped["Item"] = relationship()
    coverage_zone: Mapped["TerrainZone | None"] = relationship()

    def __repr__(self) -> str:
        return f"<MapItem {self.map_type.value} item={self.item_id}>"


class DigitalMapAccess(Base, TimestampMixin):
    """Defines digital map services available in a session.

    For modern/sci-fi settings where players can access maps digitally.
    """

    __tablename__ = "digital_map_access"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Service identity
    service_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'google_maps', 'starship_nav')",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Requirements
    requires_device: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Needs phone/laptop/terminal?",
    )
    requires_connection: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Needs wifi/mobile data/network?",
    )

    # Coverage
    coverage_map_type: Mapped[MapType] = mapped_column(
        Enum(MapType, values_callable=lambda obj: [e.value for e in obj]),
        default=MapType.REGIONAL,
        nullable=False,
        comment="What level of detail this service provides",
    )

    # State
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Currently accessible in the game world?",
    )
    unavailable_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why service is unavailable (no signal, server down, etc.)",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint(
            "session_id", "service_key", name="uq_digital_map_access_session_service"
        ),
    )

    def __repr__(self) -> str:
        status = "available" if self.is_available else "unavailable"
        return f"<DigitalMapAccess {self.service_key} ({status})>"
