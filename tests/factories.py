"""Factory functions for creating test models with sensible defaults."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from src.database.models.enums import (
    AppointmentStatus,
    BodyPart,
    DayOfWeek,
    DriveLevel,
    EntityType,
    FactCategory,
    GriefStage,
    InjurySeverity,
    InjuryType,
    IntimacyStyle,
    ItemCondition,
    ItemType,
    MentalConditionType,
    QuestStatus,
    StorageLocationType,
    TaskCategory,
    VitalStatus,
)
from src.database.models.session import GameSession, Turn
from src.database.models.entities import (
    Entity,
    EntityAttribute,
    EntitySkill,
    MonsterExtension,
    NPCExtension,
)
from src.database.models.relationships import Relationship, RelationshipChange
from src.database.models.items import Item, StorageLocation
from src.database.models.world import Fact, Location, Schedule, TimeState, WorldEvent
from src.database.models.tasks import Appointment, Quest, QuestStage, Task
from src.database.models.character_state import CharacterNeeds, IntimacyProfile
from src.database.models.injuries import ActivityRestriction, BodyInjury
from src.database.models.vital_state import EntityVitalState
from src.database.models.mental_state import GriefCondition, MentalCondition


def _unique_key(prefix: str = "test") -> str:
    """Generate a unique key for test entities."""
    return f"{prefix}_{uuid4().hex[:8]}"


# =============================================================================
# Session & Turn Factories
# =============================================================================


def create_game_session(db: Session, **overrides: Any) -> GameSession:
    """Create a GameSession with sensible defaults."""
    defaults = {
        "session_name": f"Test Session {_unique_key()}",
        "setting": "fantasy",
        "status": "active",
        "total_turns": 1,
        "llm_provider": "anthropic",
        "gm_model": "claude-sonnet-4-20250514",
    }
    defaults.update(overrides)
    session = GameSession(**defaults)
    db.add(session)
    db.flush()
    return session


def create_turn(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Turn:
    """Create a Turn with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "turn_number": game_session.total_turns,
        "player_input": "Test player input",
        "gm_response": "Test GM response",
    }
    defaults.update(overrides)
    turn = Turn(**defaults)
    db.add(turn)
    db.flush()
    return turn


# =============================================================================
# Entity Factories
# =============================================================================


def create_entity(
    db: Session,
    game_session: GameSession,
    entity_type: EntityType = EntityType.NPC,
    **overrides: Any,
) -> Entity:
    """Create an Entity with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_key": _unique_key("entity"),
        "display_name": "Test Entity",
        "entity_type": entity_type,
        "is_alive": True,
        "is_active": True,
    }
    defaults.update(overrides)
    entity = Entity(**defaults)
    db.add(entity)
    db.flush()
    return entity


def create_entity_attribute(
    db: Session,
    entity: Entity,
    **overrides: Any,
) -> EntityAttribute:
    """Create an EntityAttribute with sensible defaults."""
    defaults = {
        "entity_id": entity.id,
        "attribute_key": _unique_key("attr"),
        "value": 10,
        "temporary_modifier": 0,
    }
    defaults.update(overrides)
    attr = EntityAttribute(**defaults)
    db.add(attr)
    db.flush()
    return attr


def create_entity_skill(
    db: Session,
    entity: Entity,
    **overrides: Any,
) -> EntitySkill:
    """Create an EntitySkill with sensible defaults."""
    defaults = {
        "entity_id": entity.id,
        "skill_key": _unique_key("skill"),
        "proficiency_level": 1,
        "experience_points": 0,
    }
    defaults.update(overrides)
    skill = EntitySkill(**defaults)
    db.add(skill)
    db.flush()
    return skill


def create_npc_extension(
    db: Session,
    entity: Entity,
    **overrides: Any,
) -> NPCExtension:
    """Create an NPCExtension with sensible defaults."""
    defaults = {
        "entity_id": entity.id,
        "job": "Test Job",
        "current_mood": "neutral",
    }
    defaults.update(overrides)
    ext = NPCExtension(**defaults)
    db.add(ext)
    db.flush()
    return ext


def create_monster_extension(
    db: Session,
    entity: Entity,
    **overrides: Any,
) -> MonsterExtension:
    """Create a MonsterExtension with sensible defaults."""
    defaults = {
        "entity_id": entity.id,
        "is_hostile": True,
        "hit_points": 10,
        "max_hit_points": 10,
        "armor_class": 10,
    }
    defaults.update(overrides)
    ext = MonsterExtension(**defaults)
    db.add(ext)
    db.flush()
    return ext


# =============================================================================
# Relationship Factories
# =============================================================================


def create_relationship(
    db: Session,
    game_session: GameSession,
    from_entity: Entity,
    to_entity: Entity,
    **overrides: Any,
) -> Relationship:
    """Create a Relationship with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "from_entity_id": from_entity.id,
        "to_entity_id": to_entity.id,
        "trust": 50,
        "liking": 50,
        "respect": 50,
        "romantic_interest": 0,
        "familiarity": 10,
        "fear": 0,
        "social_debt": 0,
        "knows": True,
    }
    defaults.update(overrides)
    rel = Relationship(**defaults)
    db.add(rel)
    db.flush()
    return rel


def create_relationship_change(
    db: Session,
    relationship: Relationship,
    **overrides: Any,
) -> RelationshipChange:
    """Create a RelationshipChange with sensible defaults."""
    defaults = {
        "relationship_id": relationship.id,
        "dimension": "trust",
        "old_value": 50,
        "new_value": 60,
        "delta": 10,
        "reason": "Test reason",
        "turn_number": 1,
    }
    defaults.update(overrides)
    change = RelationshipChange(**defaults)
    db.add(change)
    db.flush()
    return change


# =============================================================================
# Item Factories
# =============================================================================


def create_storage_location(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> StorageLocation:
    """Create a StorageLocation with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "location_key": _unique_key("storage"),
        "location_type": StorageLocationType.ON_PERSON,
    }
    defaults.update(overrides)
    loc = StorageLocation(**defaults)
    db.add(loc)
    db.flush()
    return loc


def create_item(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Item:
    """Create an Item with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "item_key": _unique_key("item"),
        "display_name": "Test Item",
        "item_type": ItemType.MISC,
        "condition": ItemCondition.GOOD,  # Field is 'condition', not 'item_condition'
        "quantity": 1,
        "is_stackable": False,
    }
    defaults.update(overrides)
    item = Item(**defaults)
    db.add(item)
    db.flush()
    return item


# =============================================================================
# World Factories
# =============================================================================


def create_location(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Location:
    """Create a Location with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "location_key": _unique_key("location"),
        "display_name": "Test Location",
        "description": "A test location for testing.",
        "is_accessible": True,
    }
    defaults.update(overrides)
    loc = Location(**defaults)
    db.add(loc)
    db.flush()
    return loc


def create_schedule(
    db: Session,
    entity: Entity,
    **overrides: Any,
) -> Schedule:
    """Create a Schedule with sensible defaults."""
    defaults = {
        "entity_id": entity.id,
        "day_pattern": DayOfWeek.DAILY,
        "start_time": "09:00",
        "end_time": "17:00",
        "activity": "Working",
        "priority": 5,
    }
    defaults.update(overrides)
    schedule = Schedule(**defaults)
    db.add(schedule)
    db.flush()
    return schedule


def create_time_state(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> TimeState:
    """Create a TimeState with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "current_day": 1,
        "current_time": "08:00",
        "day_of_week": DayOfWeek.MONDAY,
    }
    defaults.update(overrides)
    state = TimeState(**defaults)
    db.add(state)
    db.flush()
    return state


def create_fact(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Fact:
    """Create a Fact with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "subject_type": "entity",
        "subject_key": "test_subject",
        "predicate": "has_property",
        "value": "test_value",
        "category": FactCategory.PERSONAL,
        "source_turn": 1,
        "confidence": 100,
        "is_secret": False,
    }
    defaults.update(overrides)
    fact = Fact(**defaults)
    db.add(fact)
    db.flush()
    return fact


def create_world_event(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> WorldEvent:
    """Create a WorldEvent with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "event_type": "test_event",
        "summary": "A test event occurred.",
        "game_day": 1,
        "turn_created": 1,
        "is_known_to_player": True,
        "is_processed": False,
    }
    defaults.update(overrides)
    event = WorldEvent(**defaults)
    db.add(event)
    db.flush()
    return event


# =============================================================================
# Task Factories
# =============================================================================


def create_task(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Task:
    """Create a Task with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "description": "Test task description",
        "category": TaskCategory.GOAL,
        "priority": 2,
        "created_turn": 1,
        "completed": False,
    }
    defaults.update(overrides)
    task = Task(**defaults)
    db.add(task)
    db.flush()
    return task


def create_appointment(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Appointment:
    """Create an Appointment with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "description": "Test appointment",
        "game_day": 1,
        "game_time": "14:00",
        "participants": "npc_1, player",  # Comma-separated string, not list
        "status": AppointmentStatus.SCHEDULED,
        "created_turn": 1,
    }
    defaults.update(overrides)
    appt = Appointment(**defaults)
    db.add(appt)
    db.flush()
    return appt


def create_quest(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> Quest:
    """Create a Quest with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "quest_key": _unique_key("quest"),
        "name": "Test Quest",
        "description": "A test quest for testing.",
        "status": QuestStatus.AVAILABLE,
        "current_stage": 0,
    }
    defaults.update(overrides)
    quest = Quest(**defaults)
    db.add(quest)
    db.flush()
    return quest


def create_quest_stage(
    db: Session,
    quest: Quest,
    **overrides: Any,
) -> QuestStage:
    """Create a QuestStage with sensible defaults."""
    defaults = {
        "quest_id": quest.id,
        "stage_order": 0,
        "name": "Stage 1",
        "description": "First stage of the quest.",
        "objective": "Complete the objective.",
        "is_completed": False,
    }
    defaults.update(overrides)
    stage = QuestStage(**defaults)
    db.add(stage)
    db.flush()
    return stage


# =============================================================================
# Character State Factories
# =============================================================================


def create_character_needs(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> CharacterNeeds:
    """Create CharacterNeeds with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "hunger": 80,
        "fatigue": 20,
        "hygiene": 80,
        "comfort": 70,
        "pain": 0,
        "social_connection": 50,
        "morale": 70,
        "sense_of_purpose": 60,
        "intimacy": 20,
    }
    defaults.update(overrides)
    needs = CharacterNeeds(**defaults)
    db.add(needs)
    db.flush()
    return needs


def create_intimacy_profile(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> IntimacyProfile:
    """Create an IntimacyProfile with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "drive_level": DriveLevel.MODERATE,
        "intimacy_style": IntimacyStyle.EMOTIONAL,
        "has_regular_partner": False,
        "is_actively_seeking": False,
    }
    defaults.update(overrides)
    profile = IntimacyProfile(**defaults)
    db.add(profile)
    db.flush()
    return profile


# =============================================================================
# Injury Factories
# =============================================================================


def create_body_injury(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> BodyInjury:
    """Create a BodyInjury with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "body_part": BodyPart.LEFT_ARM,
        "injury_type": InjuryType.BRUISE,
        "severity": InjurySeverity.MINOR,
        "caused_by": "Test cause",
        "occurred_turn": 1,
        "base_recovery_days": 3,
        "adjusted_recovery_days": 3,
        "recovery_progress_days": 0,
        "is_healed": False,
        "received_medical_care": False,
        "current_pain_level": 10,
    }
    defaults.update(overrides)
    injury = BodyInjury(**defaults)
    db.add(injury)
    db.flush()
    return injury


def create_activity_restriction(
    db: Session,
    **overrides: Any,
) -> ActivityRestriction:
    """Create an ActivityRestriction with sensible defaults."""
    defaults = {
        "body_part": BodyPart.LEFT_ARM,
        "injury_type": InjuryType.BRUISE,
        "severity": InjurySeverity.MINOR,
        "activity_name": "lifting",  # Field is 'activity_name' not 'activity'
        "impact_type": "penalty",
        "impact_value": 25,  # Field is 'impact_value' not 'penalty_percent'
    }
    defaults.update(overrides)
    restriction = ActivityRestriction(**defaults)
    db.add(restriction)
    db.flush()
    return restriction


# =============================================================================
# Vital State Factories
# =============================================================================


def create_entity_vital_state(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> EntityVitalState:
    """Create an EntityVitalState with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "vital_status": VitalStatus.HEALTHY,
        "death_saves_remaining": 3,
        "death_saves_failed": 0,
        "is_dead": False,
        "has_been_revived": False,
        "revival_count": 0,
    }
    defaults.update(overrides)
    state = EntityVitalState(**defaults)
    db.add(state)
    db.flush()
    return state


# =============================================================================
# Mental State Factories
# =============================================================================


def create_mental_condition(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> MentalCondition:
    """Create a MentalCondition with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "condition_type": MentalConditionType.ANXIETY,
        "severity": 30,
        "acquired_turn": 1,
        "acquired_reason": "Test reason",
        "is_permanent": False,
        "is_active": True,
        "can_be_treated": True,
        "treatment_progress": 0,
    }
    defaults.update(overrides)
    condition = MentalCondition(**defaults)
    db.add(condition)
    db.flush()
    return condition


def create_grief_condition(
    db: Session,
    game_session: GameSession,
    grieving_entity: Entity,
    deceased_entity: Entity,
    **overrides: Any,
) -> GriefCondition:
    """Create a GriefCondition with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": grieving_entity.id,
        "deceased_entity_id": deceased_entity.id,
        "grief_stage": GriefStage.SHOCK,  # Field is 'grief_stage' not 'current_stage'
        "started_turn": 1,
        "current_stage_started_turn": 1,
        "intensity": 50,
        "morale_modifier": -20,
        "expected_duration_days": 30,
        "is_resolved": False,
    }
    defaults.update(overrides)
    condition = GriefCondition(**defaults)
    db.add(condition)
    db.flush()
    return condition
