"""Snapshot manager for capturing and restoring complete session state."""

from datetime import datetime
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from src.database.models import (
    # Core
    GameSession,
    Turn,
    # Entities
    Entity,
    EntityAttribute,
    EntitySkill,
    NPCExtension,
    # Items
    Item,
    StorageLocation,
    # World
    Location,
    LocationVisit,
    Fact,
    WorldEvent,
    TimeState,
    Schedule,
    # Relationships
    Relationship,
    RelationshipChange,
    RelationshipMilestone,
    # Character state
    CharacterNeeds,
    NeedsCommunicationLog,
    CharacterMemory,
    CharacterPreferences,
    NeedModifier,
    NeedAdaptation,
    # Injuries & vital
    BodyInjury,
    ActivityRestriction,
    EntityVitalState,
    # Mental
    MentalCondition,
    GriefCondition,
    # Tasks
    Task,
    Appointment,
    Quest,
    QuestStage,
    # Goals
    NPCGoal,
    # Narrative
    StoryArc,
    Mystery,
    Conflict,
    ComplicationHistory,
    # Progression
    Achievement,
    EntityAchievement,
    # Faction
    Faction,
    FactionRelationship,
    EntityReputation,
    ReputationChange,
    # Combat
    EntityCondition,
    # Rumors
    Rumor,
    RumorKnowledge,
    # Relationship arcs
    RelationshipArc,
    # Economy
    MarketPrice,
    TradeRoute,
    EconomicEvent,
    # Magic
    SpellDefinition,
    EntityMagicProfile,
    SpellCastRecord,
    # Destiny
    Prophesy,
    DestinyElement,
    # Navigation
    TerrainZone,
    ZoneConnection,
    LocationZonePlacement,
    TransportMode,
    ZoneDiscovery,
    LocationDiscovery,
    MapItem,
    DigitalMapAccess,
    # Context
    Milestone,
    ContextSummary,
    NarrativeMentionLog,
    # Snapshots
    SessionSnapshot,
)
from src.managers.base import BaseManager


# Models that have session_id and need to be captured in snapshots
# Ordered for safe deletion (children before parents to respect FKs)
SESSION_SCOPED_MODELS = [
    # Leaf tables first (no FKs to other session tables)
    EntityAttribute,
    EntitySkill,
    NPCExtension,
    ActivityRestriction,
    NeedModifier,
    NeedAdaptation,
    RelationshipChange,
    RelationshipMilestone,
    NeedsCommunicationLog,
    NarrativeMentionLog,
    SpellCastRecord,
    EntityCondition,
    RumorKnowledge,
    ReputationChange,
    EntityAchievement,
    ComplicationHistory,
    QuestStage,
    ZoneConnection,
    LocationZonePlacement,
    ZoneDiscovery,
    LocationDiscovery,
    DigitalMapAccess,
    # Mid-level tables
    BodyInjury,
    CharacterMemory,
    MentalCondition,
    GriefCondition,
    EntityVitalState,
    CharacterNeeds,
    CharacterPreferences,
    LocationVisit,
    Fact,
    WorldEvent,
    Schedule,
    Task,
    Appointment,
    NPCGoal,
    Mystery,
    Conflict,
    Rumor,
    EconomicEvent,
    Prophesy,
    DestinyElement,
    Milestone,
    ContextSummary,
    MapItem,
    TransportMode,
    EntityReputation,
    FactionRelationship,
    EntityMagicProfile,
    # Parent tables (ordered for FK-safe deletion: children first)
    # Delete order: RelationshipArc → ... → Item → StorageLocation → Location → Entity → TimeState
    # Insert order (reversed): TimeState → Entity → Location → StorageLocation → Item → ...
    RelationshipArc,
    Relationship,
    StoryArc,
    Quest,
    Achievement,
    Faction,
    SpellDefinition,
    MarketPrice,
    TradeRoute,
    TerrainZone,
    # Item before StorageLocation (Item.storage_location_id → StorageLocation)
    # Both before Location (Item.owner_location_id → Location, StorageLocation.world_location_id → Location)
    # Note: StorageLocation.container_item_id → Item is nullable; handled by insert order
    Item,
    StorageLocation,
    Location,
    Entity,
    TimeState,
]

# Map table names to model classes for restoration
TABLE_TO_MODEL = {model.__tablename__: model for model in SESSION_SCOPED_MODELS}


class SnapshotManager(BaseManager):
    """Manager for capturing and restoring complete session state.

    Provides functionality to:
    - Capture complete session state at the start of each turn
    - Restore session to a previous snapshot
    - Prune old snapshots based on retention policy
    """

    def capture_snapshot(self, turn_number: int) -> SessionSnapshot:
        """Capture complete session state at the start of a turn.

        Args:
            turn_number: The turn number this snapshot is for.

        Returns:
            The created SessionSnapshot record.
        """
        data = {}

        for model in SESSION_SCOPED_MODELS:
            table_name = model.__tablename__

            # Check if model has session_id column
            if not hasattr(model, "session_id"):
                # Some models might be linked via entity_id instead
                if hasattr(model, "entity_id"):
                    # Get entities for this session first
                    entity_ids = [
                        e.id for e in self.db.query(Entity.id).filter(
                            Entity.session_id == self.session_id
                        ).all()
                    ]
                    if entity_ids:
                        records = self.db.query(model).filter(
                            model.entity_id.in_(entity_ids)
                        ).all()
                    else:
                        records = []
                else:
                    continue
            else:
                records = self.db.query(model).filter(
                    model.session_id == self.session_id
                ).all()

            data[table_name] = [self._model_to_dict(record) for record in records]

        snapshot = SessionSnapshot(
            session_id=self.session_id,
            turn_number=turn_number,
            snapshot_data=data,
        )
        self.db.add(snapshot)
        self.db.flush()

        return snapshot

    def restore_snapshot(self, turn_number: int) -> None:
        """Restore session to a previous snapshot.

        This deletes all current session data and replaces it with the snapshot.

        Args:
            turn_number: The turn number to restore to.

        Raises:
            ValueError: If no snapshot exists for the given turn.
        """
        snapshot = self.db.query(SessionSnapshot).filter(
            SessionSnapshot.session_id == self.session_id,
            SessionSnapshot.turn_number == turn_number,
        ).first()

        if not snapshot:
            raise ValueError(f"No snapshot found for turn {turn_number}")

        # 1. Delete ALL current session data (FK-safe order - children first)
        for model in SESSION_SCOPED_MODELS:
            if hasattr(model, "session_id"):
                self.db.query(model).filter(
                    model.session_id == self.session_id
                ).delete(synchronize_session="fetch")
            elif hasattr(model, "entity_id"):
                # Get entities for this session
                entity_ids = [
                    e.id for e in self.db.query(Entity.id).filter(
                        Entity.session_id == self.session_id
                    ).all()
                ]
                if entity_ids:
                    self.db.query(model).filter(
                        model.entity_id.in_(entity_ids)
                    ).delete(synchronize_session="fetch")

        self.db.flush()

        # 2. Insert snapshot data (reverse order - parents first)
        # Flush after each model type to enforce insertion order and avoid FK violations
        for model in reversed(SESSION_SCOPED_MODELS):
            table_name = model.__tablename__
            records_data = snapshot.snapshot_data.get(table_name, [])

            if records_data:
                for record_data in records_data:
                    record = self._dict_to_model(model, record_data)
                    self.db.add(record)
                self.db.flush()  # Flush each model type before moving to dependents

        # 3. Delete turns after target
        self.db.query(Turn).filter(
            Turn.session_id == self.session_id,
            Turn.turn_number > turn_number
        ).delete(synchronize_session="fetch")

        # 4. Update session
        self.game_session.total_turns = turn_number

        # 5. Delete snapshots after target
        self.db.query(SessionSnapshot).filter(
            SessionSnapshot.session_id == self.session_id,
            SessionSnapshot.turn_number > turn_number
        ).delete(synchronize_session="fetch")

        self.db.flush()

    def prune_snapshots(self, min_keep: int = 10) -> int:
        """Remove old snapshots based on retention policy.

        Keeps:
        - All snapshots since last milestone
        - At minimum, the most recent `min_keep` snapshots

        Args:
            min_keep: Minimum number of snapshots to retain.

        Returns:
            Number of snapshots deleted.
        """
        # Get all snapshots for this session, ordered by turn
        snapshots = self.db.query(SessionSnapshot).filter(
            SessionSnapshot.session_id == self.session_id
        ).order_by(SessionSnapshot.turn_number.desc()).all()

        if len(snapshots) <= min_keep:
            return 0

        # Find the last milestone turn
        last_milestone = self.db.query(Milestone).filter(
            Milestone.session_id == self.session_id
        ).order_by(Milestone.turn_number.desc()).first()

        milestone_turn = last_milestone.turn_number if last_milestone else 0

        # Keep snapshots since milestone and at least min_keep recent ones
        keep_turns = set()

        # Always keep the min_keep most recent
        for snapshot in snapshots[:min_keep]:
            keep_turns.add(snapshot.turn_number)

        # Keep all since milestone
        for snapshot in snapshots:
            if snapshot.turn_number >= milestone_turn:
                keep_turns.add(snapshot.turn_number)

        # Delete the rest
        deleted = 0
        for snapshot in snapshots:
            if snapshot.turn_number not in keep_turns:
                self.db.delete(snapshot)
                deleted += 1

        return deleted

    def get_available_snapshots(self) -> list[int]:
        """Get list of turn numbers with available snapshots.

        Returns:
            List of turn numbers that have snapshots, ordered ascending.
        """
        snapshots = self.db.query(SessionSnapshot.turn_number).filter(
            SessionSnapshot.session_id == self.session_id
        ).order_by(SessionSnapshot.turn_number.asc()).all()

        return [s.turn_number for s in snapshots]

    def get_snapshot(self, turn_number: int) -> SessionSnapshot | None:
        """Get a specific snapshot by turn number.

        Args:
            turn_number: The turn number to get snapshot for.

        Returns:
            The SessionSnapshot or None if not found.
        """
        return self.db.query(SessionSnapshot).filter(
            SessionSnapshot.session_id == self.session_id,
            SessionSnapshot.turn_number == turn_number,
        ).first()

    def _model_to_dict(self, record: Any) -> dict:
        """Convert a SQLAlchemy model instance to a dictionary.

        Args:
            record: The model instance to convert.

        Returns:
            Dictionary representation of the record.
        """
        result = {}
        mapper = inspect(record.__class__)

        for column in mapper.columns:
            value = getattr(record, column.key)

            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()

            # Handle enum serialization
            if hasattr(value, "value"):
                value = value.value

            result[column.key] = value

        return result

    def _dict_to_model(self, model_class: type, data: dict) -> Any:
        """Convert a dictionary back to a SQLAlchemy model instance.

        Args:
            model_class: The model class to instantiate.
            data: Dictionary of column values.

        Returns:
            New model instance (not yet added to session).
        """
        # Parse datetime strings back to datetime objects
        mapper = inspect(model_class)
        parsed_data = {}

        for column in mapper.columns:
            key = column.key
            if key not in data:
                continue

            value = data[key]

            # Parse datetime strings
            if value is not None and hasattr(column.type, "python_type"):
                if column.type.python_type == datetime and isinstance(value, str):
                    value = datetime.fromisoformat(value)

            parsed_data[key] = value

        return model_class(**parsed_data)
