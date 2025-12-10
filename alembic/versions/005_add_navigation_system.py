"""Add navigation system models.

Revision ID: 005_navigation
Revises: 004_normalize_need_semantics
Create Date: 2024-12-08

This migration adds the zone-based navigation system:
- TerrainZone: Explorable terrain segments
- ZoneConnection: Paths between zones
- LocationZonePlacement: Links locations to zones
- TransportMode: Transport methods with terrain costs
- ZoneDiscovery: Fog of war for zones
- LocationDiscovery: Fog of war for locations
- MapItem: Map item extension
- DigitalMapAccess: Digital map services
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_navigation"
down_revision = "004_normalize_needs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TerrainZone table
    op.create_table(
        "terrain_zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("zone_key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column(
            "terrain_type",
            sa.Enum(
                "plains", "forest", "road", "trail", "mountain", "swamp",
                "desert", "lake", "river", "ocean", "cliff", "cave",
                "urban", "ruins",
                name="terraintype",
            ),
            nullable=False,
        ),
        sa.Column("parent_zone_id", sa.Integer(), nullable=True),
        sa.Column(
            "base_travel_cost",
            sa.Integer(),
            nullable=False,
            server_default="10",
            comment="Base walking time in minutes per unit distance",
        ),
        sa.Column(
            "mounted_travel_cost",
            sa.Integer(),
            nullable=True,
            comment="Travel time on mount (null = impassable by mount)",
        ),
        sa.Column(
            "requires_skill",
            sa.String(50),
            nullable=True,
            comment="Skill required to enter (e.g., 'swimming', 'climbing')",
        ),
        sa.Column(
            "skill_difficulty",
            sa.Integer(),
            nullable=True,
            comment="DC for skill check if required",
        ),
        sa.Column(
            "failure_consequence",
            sa.String(100),
            nullable=True,
            comment="What happens on failed check (e.g., 'drowning', 'fall_damage')",
        ),
        sa.Column(
            "visibility_range",
            sa.Enum("far", "medium", "short", "none", name="visibilityrange"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "encounter_frequency",
            sa.Enum("none", "low", "medium", "high", "very_high", name="encounterfrequency"),
            nullable=False,
            server_default="low",
        ),
        sa.Column("encounter_table_key", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("atmosphere", sa.Text(), nullable=True),
        sa.Column("is_accessible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_zone_id"],
            ["terrain_zones.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "zone_key", name="uq_terrain_zone_session_key"),
    )
    op.create_index("ix_terrain_zones_id", "terrain_zones", ["id"])
    op.create_index("ix_terrain_zones_session_id", "terrain_zones", ["session_id"])
    op.create_index("ix_terrain_zones_zone_key", "terrain_zones", ["zone_key"])
    op.create_index("ix_terrain_zones_terrain_type", "terrain_zones", ["terrain_type"])

    # ZoneConnection table
    op.create_table(
        "zone_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("from_zone_id", sa.Integer(), nullable=False),
        sa.Column("to_zone_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(30), nullable=True),
        sa.Column(
            "connection_type",
            sa.Enum(
                "open", "path", "bridge", "climb", "swim", "door", "gate", "hidden",
                name="connectiontype",
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column("crossing_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("requires_skill", sa.String(50), nullable=True),
        sa.Column("skill_difficulty", sa.Integer(), nullable=True),
        sa.Column("is_bidirectional", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_passable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_zone_id"],
            ["terrain_zones.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_zone_id"],
            ["terrain_zones.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zone_connections_id", "zone_connections", ["id"])
    op.create_index("ix_zone_connections_session_id", "zone_connections", ["session_id"])
    op.create_index("ix_zone_connections_from_zone_id", "zone_connections", ["from_zone_id"])
    op.create_index("ix_zone_connections_to_zone_id", "zone_connections", ["to_zone_id"])
    op.create_index(
        "ix_zone_connection_from_passable",
        "zone_connections",
        ["from_zone_id", "is_passable"],
    )

    # LocationZonePlacement table
    op.create_table(
        "location_zone_placements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column(
            "placement_type",
            sa.Enum("within", "edge", "landmark", name="placementtype"),
            nullable=False,
            server_default="within",
        ),
        sa.Column("visibility", sa.String(50), nullable=False, server_default="visible_from_zone"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["terrain_zones.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "location_id", name="uq_location_zone_placement_location"
        ),
    )
    op.create_index("ix_location_zone_placements_id", "location_zone_placements", ["id"])
    op.create_index(
        "ix_location_zone_placements_session_id", "location_zone_placements", ["session_id"]
    )
    op.create_index(
        "ix_location_zone_placements_location_id", "location_zone_placements", ["location_id"]
    )
    op.create_index(
        "ix_location_zone_placements_zone_id", "location_zone_placements", ["zone_id"]
    )

    # TransportMode table (global, not session-scoped)
    op.create_table(
        "transport_modes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode_key", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column(
            "transport_type",
            sa.Enum(
                "walking", "running", "mounted", "swimming", "climbing",
                "flying", "boat", "ship", "vehicle",
                name="transporttype",
            ),
            nullable=False,
        ),
        sa.Column("terrain_costs", sa.JSON(), nullable=False),
        sa.Column("requires_skill", sa.String(50), nullable=True),
        sa.Column("requires_item", sa.String(100), nullable=True),
        sa.Column("fatigue_rate", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("encounter_modifier", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transport_modes_id", "transport_modes", ["id"])
    op.create_index("ix_transport_modes_mode_key", "transport_modes", ["mode_key"], unique=True)

    # ZoneDiscovery table
    op.create_table(
        "zone_discoveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("discovered_turn", sa.Integer(), nullable=False),
        sa.Column(
            "discovery_method",
            sa.Enum(
                "visited", "told_by_npc", "map_viewed", "digital_lookup",
                "visible_from", "starting_knowledge",
                name="discoverymethod",
            ),
            nullable=False,
        ),
        sa.Column("source_map_id", sa.Integer(), nullable=True),
        sa.Column("source_entity_id", sa.Integer(), nullable=True),
        sa.Column("source_zone_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["terrain_zones.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_map_id"],
            ["items.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["entities.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_zone_id"],
            ["terrain_zones.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "zone_id", name="uq_zone_discovery_session_zone"),
    )
    op.create_index("ix_zone_discoveries_id", "zone_discoveries", ["id"])
    op.create_index("ix_zone_discoveries_session_id", "zone_discoveries", ["session_id"])
    op.create_index("ix_zone_discoveries_zone_id", "zone_discoveries", ["zone_id"])

    # LocationDiscovery table
    op.create_table(
        "location_discoveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("discovered_turn", sa.Integer(), nullable=False),
        sa.Column(
            "discovery_method",
            sa.Enum(
                "visited", "told_by_npc", "map_viewed", "digital_lookup",
                "visible_from", "starting_knowledge",
                name="discoverymethod",
                create_type=False,  # Already created above
            ),
            nullable=False,
        ),
        sa.Column("source_map_id", sa.Integer(), nullable=True),
        sa.Column("source_entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_map_id"],
            ["items.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["entities.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "location_id", name="uq_location_discovery_session_location"
        ),
    )
    op.create_index("ix_location_discoveries_id", "location_discoveries", ["id"])
    op.create_index(
        "ix_location_discoveries_session_id", "location_discoveries", ["session_id"]
    )
    op.create_index(
        "ix_location_discoveries_location_id", "location_discoveries", ["location_id"]
    )

    # MapItem table
    op.create_table(
        "map_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column(
            "map_type",
            sa.Enum("world", "regional", "city", "dungeon", "building", name="maptype"),
            nullable=False,
        ),
        sa.Column("coverage_zone_id", sa.Integer(), nullable=True),
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("revealed_zone_ids", sa.JSON(), nullable=True),
        sa.Column("revealed_location_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["coverage_zone_id"],
            ["terrain_zones.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_map_items_id", "map_items", ["id"])
    op.create_index("ix_map_items_session_id", "map_items", ["session_id"])
    op.create_index("ix_map_items_item_id", "map_items", ["item_id"], unique=True)

    # DigitalMapAccess table
    op.create_table(
        "digital_map_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("service_key", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("requires_device", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("requires_connection", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "coverage_map_type",
            sa.Enum("world", "regional", "city", "dungeon", "building", name="maptype", create_type=False),
            nullable=False,
            server_default="regional",
        ),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("unavailable_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "service_key", name="uq_digital_map_access_session_service"
        ),
    )
    op.create_index("ix_digital_map_access_id", "digital_map_access", ["id"])
    op.create_index("ix_digital_map_access_session_id", "digital_map_access", ["session_id"])
    op.create_index("ix_digital_map_access_service_key", "digital_map_access", ["service_key"])

    # Seed default transport modes
    op.execute("""
        INSERT INTO transport_modes (mode_key, display_name, transport_type, terrain_costs, fatigue_rate, encounter_modifier, created_at, updated_at)
        VALUES
        ('walking', 'Walking', 'walking', '{"plains": 1.0, "forest": 2.0, "road": 0.8, "trail": 1.2, "mountain": 3.0, "swamp": 2.5, "desert": 1.5, "urban": 0.9, "ruins": 1.5, "cave": 1.5}', 1.0, 1.0, NOW(), NOW()),
        ('running', 'Running', 'running', '{"plains": 0.6, "forest": 1.5, "road": 0.5, "trail": 0.8, "mountain": 2.0, "swamp": 2.0, "desert": 1.2, "urban": 0.6, "ruins": 1.2, "cave": 1.2}', 2.5, 0.8, NOW(), NOW()),
        ('mounted', 'Mounted (Horse)', 'mounted', '{"plains": 0.5, "road": 0.3, "trail": 0.7, "desert": 0.8, "urban": 0.6}', 0.5, 0.7, NOW(), NOW()),
        ('swimming', 'Swimming', 'swimming', '{"lake": 1.5, "river": 2.0, "ocean": 3.0, "swamp": 2.0}', 3.0, 1.2, NOW(), NOW()),
        ('climbing', 'Climbing', 'climbing', '{"cliff": 5.0, "mountain": 3.0}', 4.0, 0.5, NOW(), NOW())
    """)


def downgrade() -> None:
    # Drop tables in reverse order (dependencies first)
    op.drop_table("digital_map_access")
    op.drop_table("map_items")
    op.drop_table("location_discoveries")
    op.drop_table("zone_discoveries")
    op.drop_table("transport_modes")
    op.drop_table("location_zone_placements")
    op.drop_table("zone_connections")
    op.drop_table("terrain_zones")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS terraintype")
    op.execute("DROP TYPE IF EXISTS visibilityrange")
    op.execute("DROP TYPE IF EXISTS encounterfrequency")
    op.execute("DROP TYPE IF EXISTS connectiontype")
    op.execute("DROP TYPE IF EXISTS placementtype")
    op.execute("DROP TYPE IF EXISTS transporttype")
    op.execute("DROP TYPE IF EXISTS discoverymethod")
    op.execute("DROP TYPE IF EXISTS maptype")
