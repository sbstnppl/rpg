"""Tests for navigation models (TerrainZone, ZoneConnection, etc.)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
from src.database.models.navigation import (
    DigitalMapAccess,
    LocationDiscovery,
    LocationZonePlacement,
    MapItem,
    TerrainZone,
    TransportMode,
    ZoneConnection,
    ZoneDiscovery,
)
from src.database.models.session import GameSession
from tests.factories import (
    create_digital_map_access,
    create_game_session,
    create_item,
    create_location,
    create_location_discovery,
    create_location_zone_placement,
    create_map_item,
    create_terrain_zone,
    create_transport_mode,
    create_zone_connection,
    create_zone_discovery,
)


class TestTerrainZone:
    """Tests for TerrainZone model."""

    def test_create_terrain_zone_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify TerrainZone creation with required fields."""
        zone = TerrainZone(
            session_id=game_session.id,
            zone_key="darkwood_forest",
            display_name="Darkwood Forest",
            terrain_type=TerrainType.FOREST,
            description="A dense, dark forest.",
        )
        db_session.add(zone)
        db_session.flush()

        assert zone.id is not None
        assert zone.session_id == game_session.id
        assert zone.zone_key == "darkwood_forest"
        assert zone.terrain_type == TerrainType.FOREST

    def test_terrain_zone_unique_constraint(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + zone_key."""
        create_terrain_zone(db_session, game_session, zone_key="forest")

        with pytest.raises(IntegrityError):
            create_terrain_zone(db_session, game_session, zone_key="forest")

    def test_terrain_zone_same_key_different_sessions(self, db_session: Session):
        """Verify same zone_key allowed in different sessions."""
        session1 = create_game_session(db_session)
        session2 = create_game_session(db_session)

        zone1 = create_terrain_zone(db_session, session1, zone_key="forest")
        zone2 = create_terrain_zone(db_session, session2, zone_key="forest")

        assert zone1.id != zone2.id

    def test_terrain_zone_hierarchy(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify parent_zone_id self-reference."""
        region = create_terrain_zone(
            db_session,
            game_session,
            zone_key="westlands",
            display_name="The Westlands",
        )
        forest = create_terrain_zone(
            db_session,
            game_session,
            zone_key="darkwood",
            display_name="Darkwood Forest",
            parent_zone_id=region.id,
        )

        db_session.refresh(forest)

        assert forest.parent_zone_id == region.id
        assert forest.parent_zone is not None
        assert forest.parent_zone.zone_key == "westlands"

    def test_terrain_zone_all_terrain_types(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all terrain types can be stored."""
        for terrain_type in TerrainType:
            zone = create_terrain_zone(
                db_session,
                game_session,
                terrain_type=terrain_type,
            )
            db_session.refresh(zone)
            assert zone.terrain_type == terrain_type

    def test_terrain_zone_movement_costs(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify movement cost fields."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            base_travel_cost=20,
            mounted_travel_cost=None,  # Impassable by mount
        )

        db_session.refresh(zone)

        assert zone.base_travel_cost == 20
        assert zone.mounted_travel_cost is None

    def test_terrain_zone_skill_requirements(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify skill requirement fields."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            terrain_type=TerrainType.LAKE,
            requires_skill="swimming",
            skill_difficulty=12,
            failure_consequence="drowning",
        )

        db_session.refresh(zone)

        assert zone.requires_skill == "swimming"
        assert zone.skill_difficulty == 12
        assert zone.failure_consequence == "drowning"

    def test_terrain_zone_environment(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify environment fields."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            visibility_range=VisibilityRange.SHORT,
            encounter_frequency=EncounterFrequency.HIGH,
            encounter_table_key="forest_encounters",
        )

        db_session.refresh(zone)

        assert zone.visibility_range == VisibilityRange.SHORT
        assert zone.encounter_frequency == EncounterFrequency.HIGH
        assert zone.encounter_table_key == "forest_encounters"

    def test_terrain_zone_accessibility(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_accessible and blocked_reason fields."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            is_accessible=False,
            blocked_reason="The forest is engulfed in magical flames.",
        )

        db_session.refresh(zone)

        assert zone.is_accessible is False
        assert zone.blocked_reason == "The forest is engulfed in magical flames."

    def test_terrain_zone_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        zone = create_terrain_zone(
            db_session,
            game_session,
            zone_key="darkwood",
            terrain_type=TerrainType.FOREST,
        )

        repr_str = repr(zone)
        assert "TerrainZone" in repr_str
        assert "darkwood" in repr_str
        assert "forest" in repr_str


class TestZoneConnection:
    """Tests for ZoneConnection model."""

    def test_create_zone_connection_required_fields(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ZoneConnection creation with required fields."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="plains")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="forest")

        connection = ZoneConnection(
            session_id=game_session.id,
            from_zone_id=zone1.id,
            to_zone_id=zone2.id,
        )
        db_session.add(connection)
        db_session.flush()

        assert connection.id is not None
        assert connection.from_zone_id == zone1.id
        assert connection.to_zone_id == zone2.id

    def test_zone_connection_direction(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify direction field."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="plains")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="forest")

        connection = create_zone_connection(
            db_session,
            game_session,
            from_zone=zone1,
            to_zone=zone2,
            direction="north",
        )

        db_session.refresh(connection)
        assert connection.direction == "north"

    def test_zone_connection_types(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all connection types can be stored."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="zone1")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="zone2")

        for conn_type in ConnectionType:
            connection = create_zone_connection(
                db_session,
                game_session,
                from_zone=zone1,
                to_zone=zone2,
                connection_type=conn_type,
            )
            db_session.refresh(connection)
            assert connection.connection_type == conn_type

    def test_zone_connection_crossing_requirements(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify crossing requirement fields."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="cliff_top")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="cliff_bottom")

        connection = create_zone_connection(
            db_session,
            game_session,
            from_zone=zone1,
            to_zone=zone2,
            connection_type=ConnectionType.CLIMB,
            crossing_minutes=15,
            requires_skill="climbing",
            skill_difficulty=15,
        )

        db_session.refresh(connection)

        assert connection.crossing_minutes == 15
        assert connection.requires_skill == "climbing"
        assert connection.skill_difficulty == 15

    def test_zone_connection_one_way(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify one-way connection (cliff jump)."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="cliff_top")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="cliff_bottom")

        connection = create_zone_connection(
            db_session,
            game_session,
            from_zone=zone1,
            to_zone=zone2,
            is_bidirectional=False,
        )

        db_session.refresh(connection)
        assert connection.is_bidirectional is False

    def test_zone_connection_blocked(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_passable and blocked_reason fields."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="east_bank")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="west_bank")

        connection = create_zone_connection(
            db_session,
            game_session,
            from_zone=zone1,
            to_zone=zone2,
            connection_type=ConnectionType.BRIDGE,
            is_passable=False,
            blocked_reason="The bridge was destroyed by the dragon.",
        )

        db_session.refresh(connection)

        assert connection.is_passable is False
        assert connection.blocked_reason == "The bridge was destroyed by the dragon."

    def test_zone_connection_hidden(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_visible field for secret passages."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="library")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="secret_room")

        connection = create_zone_connection(
            db_session,
            game_session,
            from_zone=zone1,
            to_zone=zone2,
            connection_type=ConnectionType.HIDDEN,
            is_visible=False,
        )

        db_session.refresh(connection)
        assert connection.is_visible is False

    def test_zone_connection_relationships(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify relationships to zones."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="plains")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="forest")

        connection = create_zone_connection(
            db_session, game_session, from_zone=zone1, to_zone=zone2
        )

        db_session.refresh(connection)
        db_session.refresh(zone1)
        db_session.refresh(zone2)

        assert connection.from_zone.zone_key == "plains"
        assert connection.to_zone.zone_key == "forest"
        assert len(zone1.outgoing_connections) == 1
        assert len(zone2.incoming_connections) == 1

    def test_zone_connection_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="plains")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="forest")

        connection = create_zone_connection(
            db_session,
            game_session,
            from_zone=zone1,
            to_zone=zone2,
            direction="north",
        )

        repr_str = repr(connection)
        assert "ZoneConnection" in repr_str
        assert "(north)" in repr_str


class TestLocationZonePlacement:
    """Tests for LocationZonePlacement model."""

    def test_create_location_zone_placement(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify LocationZonePlacement creation."""
        zone = create_terrain_zone(db_session, game_session, zone_key="plains")
        location = create_location(db_session, game_session, location_key="village")

        placement = LocationZonePlacement(
            session_id=game_session.id,
            location_id=location.id,
            zone_id=zone.id,
        )
        db_session.add(placement)
        db_session.flush()

        assert placement.id is not None
        assert placement.location_id == location.id
        assert placement.zone_id == zone.id

    def test_location_zone_placement_types(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all placement types."""
        zone = create_terrain_zone(db_session, game_session, zone_key="plains")

        for placement_type in PlacementType:
            location = create_location(db_session, game_session)
            placement = create_location_zone_placement(
                db_session,
                game_session,
                location=location,
                zone=zone,
                placement_type=placement_type,
            )
            db_session.refresh(placement)
            assert placement.placement_type == placement_type

    def test_location_zone_placement_visibility(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify visibility field."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        location = create_location(db_session, game_session, location_key="cabin")

        placement = create_location_zone_placement(
            db_session,
            game_session,
            location=location,
            zone=zone,
            visibility="requires_search",
        )

        db_session.refresh(placement)
        assert placement.visibility == "requires_search"

    def test_location_zone_placement_unique_location(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify a location can only be in one zone per session."""
        zone1 = create_terrain_zone(db_session, game_session, zone_key="plains")
        zone2 = create_terrain_zone(db_session, game_session, zone_key="forest")
        location = create_location(db_session, game_session, location_key="cabin")

        create_location_zone_placement(
            db_session, game_session, location=location, zone=zone1
        )

        with pytest.raises(IntegrityError):
            create_location_zone_placement(
                db_session, game_session, location=location, zone=zone2
            )

    def test_location_zone_placement_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        zone = create_terrain_zone(db_session, game_session, zone_key="plains")
        location = create_location(db_session, game_session, location_key="village")

        placement = create_location_zone_placement(
            db_session, game_session, location=location, zone=zone
        )

        repr_str = repr(placement)
        assert "LocationZonePlacement" in repr_str


class TestTransportMode:
    """Tests for TransportMode model."""

    def test_create_transport_mode(self, db_session: Session):
        """Verify TransportMode creation."""
        mode = TransportMode(
            mode_key="walking",
            display_name="Walking",
            transport_type=TransportType.WALKING,
            terrain_costs={"plains": 1.0, "forest": 2.0, "mountain": 3.0},
        )
        db_session.add(mode)
        db_session.flush()

        assert mode.id is not None
        assert mode.mode_key == "walking"
        assert mode.terrain_costs["forest"] == 2.0

    def test_transport_mode_unique_key(self, db_session: Session):
        """Verify unique constraint on mode_key."""
        create_transport_mode(db_session, mode_key="walking")

        with pytest.raises(IntegrityError):
            create_transport_mode(db_session, mode_key="walking")

    def test_transport_mode_terrain_costs_json(self, db_session: Session):
        """Verify terrain_costs JSON field with null for impassable."""
        mode = create_transport_mode(
            db_session,
            mode_key="mounted",
            terrain_costs={
                "plains": 0.5,
                "road": 0.4,
                "forest": None,  # Impassable
                "lake": None,  # Impassable
            },
        )

        db_session.refresh(mode)

        assert mode.terrain_costs["plains"] == 0.5
        assert mode.terrain_costs["forest"] is None

    def test_transport_mode_requirements(self, db_session: Session):
        """Verify skill and item requirements."""
        mode = create_transport_mode(
            db_session,
            mode_key="mounted",
            requires_skill="riding",
            requires_item="horse",
        )

        db_session.refresh(mode)

        assert mode.requires_skill == "riding"
        assert mode.requires_item == "horse"

    def test_transport_mode_effects(self, db_session: Session):
        """Verify fatigue_rate and encounter_modifier."""
        mode = create_transport_mode(
            db_session,
            mode_key="running",
            fatigue_rate=2.0,  # Uses more energy
            encounter_modifier=0.5,  # Less likely to encounter
        )

        db_session.refresh(mode)

        assert mode.fatigue_rate == 2.0
        assert mode.encounter_modifier == 0.5

    def test_transport_mode_repr(self, db_session: Session):
        """Verify string representation."""
        mode = create_transport_mode(db_session, mode_key="swimming")

        repr_str = repr(mode)
        assert "TransportMode" in repr_str
        assert "swimming" in repr_str


class TestZoneDiscovery:
    """Tests for ZoneDiscovery model."""

    def test_create_zone_discovery(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify ZoneDiscovery creation."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")

        discovery = ZoneDiscovery(
            session_id=game_session.id,
            zone_id=zone.id,
            discovered_turn=5,
            discovery_method=DiscoveryMethod.VISITED,
        )
        db_session.add(discovery)
        db_session.flush()

        assert discovery.id is not None
        assert discovery.zone_id == zone.id
        assert discovery.discovered_turn == 5

    def test_zone_discovery_methods(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all discovery methods."""
        for method in DiscoveryMethod:
            zone = create_terrain_zone(db_session, game_session)
            discovery = create_zone_discovery(
                db_session,
                game_session,
                zone=zone,
                discovery_method=method,
            )
            db_session.refresh(discovery)
            assert discovery.discovery_method == method

    def test_zone_discovery_unique_per_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify a zone can only be discovered once per session."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")

        create_zone_discovery(db_session, game_session, zone=zone)

        with pytest.raises(IntegrityError):
            create_zone_discovery(db_session, game_session, zone=zone)

    def test_zone_discovery_source_tracking(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify source tracking fields."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        from_zone = create_terrain_zone(db_session, game_session, zone_key="plains")

        discovery = create_zone_discovery(
            db_session,
            game_session,
            zone=zone,
            discovery_method=DiscoveryMethod.VISIBLE_FROM,
            source_zone_id=from_zone.id,
        )

        db_session.refresh(discovery)
        assert discovery.source_zone_id == from_zone.id

    def test_zone_discovery_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        zone = create_terrain_zone(db_session, game_session, zone_key="forest")
        discovery = create_zone_discovery(
            db_session, game_session, zone=zone, discovered_turn=10
        )

        repr_str = repr(discovery)
        assert "ZoneDiscovery" in repr_str
        assert "10" in repr_str


class TestLocationDiscovery:
    """Tests for LocationDiscovery model."""

    def test_create_location_discovery(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify LocationDiscovery creation."""
        location = create_location(db_session, game_session, location_key="tavern")

        discovery = LocationDiscovery(
            session_id=game_session.id,
            location_id=location.id,
            discovered_turn=5,
            discovery_method=DiscoveryMethod.VISITED,
        )
        db_session.add(discovery)
        db_session.flush()

        assert discovery.id is not None
        assert discovery.location_id == location.id
        assert discovery.discovered_turn == 5

    def test_location_discovery_unique_per_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify a location can only be discovered once per session."""
        location = create_location(db_session, game_session, location_key="tavern")

        create_location_discovery(db_session, game_session, location=location)

        with pytest.raises(IntegrityError):
            create_location_discovery(db_session, game_session, location=location)

    def test_location_discovery_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        location = create_location(db_session, game_session, location_key="tavern")
        discovery = create_location_discovery(
            db_session, game_session, location=location, discovered_turn=10
        )

        repr_str = repr(discovery)
        assert "LocationDiscovery" in repr_str


class TestMapItem:
    """Tests for MapItem model."""

    def test_create_map_item(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify MapItem creation."""
        item = create_item(db_session, game_session, display_name="Regional Map")
        zone = create_terrain_zone(db_session, game_session, zone_key="westlands")

        map_item = MapItem(
            session_id=game_session.id,
            item_id=item.id,
            map_type=MapType.REGIONAL,
            coverage_zone_id=zone.id,
        )
        db_session.add(map_item)
        db_session.flush()

        assert map_item.id is not None
        assert map_item.item_id == item.id
        assert map_item.map_type == MapType.REGIONAL

    def test_map_item_all_types(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify all map types."""
        for map_type in MapType:
            item = create_item(db_session, game_session)
            map_item = create_map_item(
                db_session,
                game_session,
                item=item,
                map_type=map_type,
            )
            db_session.refresh(map_item)
            assert map_item.map_type == map_type

    def test_map_item_revealed_ids_json(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify revealed_zone_ids and revealed_location_ids JSON fields."""
        item = create_item(db_session, game_session)
        map_item = create_map_item(
            db_session,
            game_session,
            item=item,
            revealed_zone_ids=[1, 2, 3],
            revealed_location_ids=[10, 20],
        )

        db_session.refresh(map_item)

        assert map_item.revealed_zone_ids == [1, 2, 3]
        assert map_item.revealed_location_ids == [10, 20]

    def test_map_item_incomplete(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_complete field for partial/damaged maps."""
        item = create_item(db_session, game_session)
        map_item = create_map_item(
            db_session,
            game_session,
            item=item,
            is_complete=False,
        )

        db_session.refresh(map_item)
        assert map_item.is_complete is False

    def test_map_item_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        item = create_item(db_session, game_session)
        map_item = create_map_item(
            db_session,
            game_session,
            item=item,
            map_type=MapType.CITY,
        )

        repr_str = repr(map_item)
        assert "MapItem" in repr_str
        assert "city" in repr_str


class TestDigitalMapAccess:
    """Tests for DigitalMapAccess model."""

    def test_create_digital_map_access(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify DigitalMapAccess creation."""
        access = DigitalMapAccess(
            session_id=game_session.id,
            service_key="google_maps",
            display_name="Google Maps",
        )
        db_session.add(access)
        db_session.flush()

        assert access.id is not None
        assert access.service_key == "google_maps"

    def test_digital_map_access_unique_per_session(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify unique constraint on session_id + service_key."""
        create_digital_map_access(
            db_session, game_session, service_key="google_maps"
        )

        with pytest.raises(IntegrityError):
            create_digital_map_access(
                db_session, game_session, service_key="google_maps"
            )

    def test_digital_map_access_requirements(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify requires_device and requires_connection fields."""
        access = create_digital_map_access(
            db_session,
            game_session,
            requires_device=True,
            requires_connection=True,
        )

        db_session.refresh(access)

        assert access.requires_device is True
        assert access.requires_connection is True

    def test_digital_map_access_unavailable(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify is_available and unavailable_reason fields."""
        access = create_digital_map_access(
            db_session,
            game_session,
            is_available=False,
            unavailable_reason="No cell coverage in this area.",
        )

        db_session.refresh(access)

        assert access.is_available is False
        assert access.unavailable_reason == "No cell coverage in this area."

    def test_digital_map_access_coverage_type(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify coverage_map_type field."""
        access = create_digital_map_access(
            db_session,
            game_session,
            coverage_map_type=MapType.CITY,
        )

        db_session.refresh(access)
        assert access.coverage_map_type == MapType.CITY

    def test_digital_map_access_repr(
        self, db_session: Session, game_session: GameSession
    ):
        """Verify string representation."""
        access = create_digital_map_access(
            db_session,
            game_session,
            service_key="google_maps",
            is_available=True,
        )

        repr_str = repr(access)
        assert "DigitalMapAccess" in repr_str
        assert "google_maps" in repr_str
        assert "available" in repr_str
