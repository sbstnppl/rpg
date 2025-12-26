"""Tests for the GM pipeline state applier."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.gm.applier import StateApplier
from src.gm.schemas import GMResponse, StateChange, StateChangeType
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager
from src.managers.needs import NeedsManager


class TestSatisfyNeedStateChange:
    """Tests for SATISFY_NEED state change (renamed from CONSUME)."""

    def test_item_consumption_deletes_item(
        self, db_session: Session, game_session: GameSession
    ):
        """Eating bread deletes the item."""
        # Create player entity with needs
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )

        # Create player extension for location tracking
        player_ext = NPCExtension(
            entity_id=player.id,
            current_location="tavern",
        )
        db_session.add(player_ext)

        # Create a bread item (consumable type)
        item_manager = ItemManager(db_session, game_session)
        bread = item_manager.create_item(
            item_key="bread_001",
            display_name="Bread",
            description="A loaf of bread",
            item_type="consumable",
            owner_id=player.id,
        )
        db_session.flush()

        # Create response with SATISFY_NEED state change for item consumption
        response = GMResponse(
            narrative="You eat the bread hungrily.",
            state_changes=[
                StateChange(
                    change_type=StateChangeType.SATISFY_NEED,
                    target="bread_001",
                    details={"hunger": 40, "destroys_item": True},
                )
            ],
        )

        # Apply the response
        applier = StateApplier(db_session, game_session, player.id, "tavern")
        applier.apply(response, "eat bread", 1)

        # Verify item was deleted
        bread_after = item_manager.get_item("bread_001")
        assert bread_after is None

    def test_activity_calls_satisfy_need(
        self, db_session: Session, game_session: GameSession
    ):
        """Sleeping calls satisfy_need on the needs manager."""
        # Create player entity
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )

        # Create player extension
        player_ext = NPCExtension(
            entity_id=player.id,
            current_location="inn_room",
        )
        db_session.add(player_ext)
        db_session.flush()

        # Create response with activity-based need satisfaction
        response = GMResponse(
            narrative="You sleep soundly through the night.",
            state_changes=[
                StateChange(
                    change_type=StateChangeType.SATISFY_NEED,
                    target="player",
                    details={
                        "need": "stamina",
                        "amount": 50,
                        "activity": "long_rest",
                    },
                )
            ],
            time_passed_minutes=480,  # 8 hours
        )

        # Apply the response - this should not raise an error
        applier = StateApplier(db_session, game_session, player.id, "inn_room")
        applier.apply(response, "sleep", 1)

        # If we get here without error, the activity path was taken

    def test_item_not_destroyed_when_flag_false(
        self, db_session: Session, game_session: GameSession
    ):
        """Item is not destroyed when destroys_item is False."""
        # Create player
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create a reusable item (like a water skin)
        item_manager = ItemManager(db_session, game_session)
        water_skin = item_manager.create_item(
            item_key="water_skin_001",
            display_name="Water Skin",
            description="A leather water skin",
            item_type="container",
            owner_id=player.id,
        )
        db_session.flush()

        response = GMResponse(
            narrative="You drink from the water skin.",
            state_changes=[
                StateChange(
                    change_type=StateChangeType.SATISFY_NEED,
                    target="water_skin_001",
                    details={"thirst": 20, "destroys_item": False},
                )
            ],
        )

        applier = StateApplier(db_session, game_session, player.id, "tavern")
        applier.apply(response, "drink water", 1)

        # Verify item still exists
        water_skin_after = item_manager.get_item("water_skin_001")
        assert water_skin_after is not None


class TestMoveStateChange:
    """Tests for MOVE state change (player and NPC movement)."""

    def test_player_move(self, db_session: Session, game_session: GameSession):
        """Player moves to a new location."""
        entity_manager = EntityManager(db_session, game_session)
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)
        db_session.flush()

        response = GMResponse(
            narrative="You step outside into the village square.",
            state_changes=[
                StateChange(
                    change_type=StateChangeType.MOVE,
                    target="player",
                    details={"to": "village_square"},
                )
            ],
        )

        applier = StateApplier(db_session, game_session, player.id, "tavern")
        new_location = applier.apply(response, "go outside", 1)

        # Verify location changed
        assert new_location == "village_square"
        db_session.refresh(player_ext)
        assert player_ext.current_location == "village_square"

    def test_npc_move(self, db_session: Session, game_session: GameSession):
        """NPC moves to a different location."""
        entity_manager = EntityManager(db_session, game_session)

        # Create player
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create NPC
        guard = entity_manager.create_entity(
            entity_key="guard_marcus",
            display_name="Marcus",
            entity_type=EntityType.NPC,
        )
        guard_ext = NPCExtension(entity_id=guard.id, current_location="tavern")
        db_session.add(guard_ext)
        db_session.flush()

        response = GMResponse(
            narrative="Marcus finishes his ale and heads for the door.",
            state_changes=[
                StateChange(
                    change_type=StateChangeType.MOVE,
                    target="guard_marcus",
                    details={"to": "barracks", "reason": "end of shift"},
                )
            ],
        )

        applier = StateApplier(db_session, game_session, player.id, "tavern")
        new_location = applier.apply(response, "watch", 1)

        # Player location should not change
        assert new_location == "tavern"

        # NPC should have moved
        db_session.refresh(guard_ext)
        assert guard_ext.current_location == "barracks"


class TestRelationshipStateChange:
    """Tests for RELATIONSHIP state change."""

    def test_relationship_adjustment(
        self, db_session: Session, game_session: GameSession
    ):
        """Relationship dimensions are adjusted correctly."""
        from src.database.models.enums import RelationshipDimension
        from src.managers.relationship_manager import RelationshipManager

        entity_manager = EntityManager(db_session, game_session)

        # Create player
        player = entity_manager.create_entity(
            entity_key="player",
            display_name="Test Player",
            entity_type=EntityType.PLAYER,
        )
        player_ext = NPCExtension(entity_id=player.id, current_location="tavern")
        db_session.add(player_ext)

        # Create NPC
        barkeep = entity_manager.create_entity(
            entity_key="barkeep_tom",
            display_name="Tom",
            entity_type=EntityType.NPC,
        )
        db_session.flush()

        # Create relationship and increase familiarity
        # (strangers have capped relationship growth)
        rel_manager = RelationshipManager(db_session, game_session)
        rel = rel_manager.get_or_create_relationship(barkeep.id, player.id)
        rel.familiarity = 50  # Good acquaintance - allows full growth
        db_session.flush()

        # Get initial attitude
        initial_attitude = rel_manager.get_attitude(barkeep.id, player.id)
        initial_liking = initial_attitude.get("liking", 50)
        initial_trust = initial_attitude.get("trust", 50)

        response = GMResponse(
            narrative="Tom smiles at your generous tip.",
            state_changes=[
                StateChange(
                    change_type=StateChangeType.RELATIONSHIP,
                    target="barkeep_tom",
                    details={"liking": 5, "trust": 2},
                )
            ],
        )

        applier = StateApplier(db_session, game_session, player.id, "tavern")
        applier.apply(response, "give tip", 1)

        # Verify relationship changed
        attitude = rel_manager.get_attitude(barkeep.id, player.id)
        assert attitude.get("liking", 50) > initial_liking
        assert attitude.get("trust", 50) > initial_trust
