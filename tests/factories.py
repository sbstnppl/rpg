"""Factory functions for creating test models with sensible defaults."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from src.database.models.enums import (
    AlcoholTolerance,
    AppointmentStatus,
    BodyPart,
    ConnectionType,
    DayOfWeek,
    DiscoveryMethod,
    DriveLevel,
    EmotionalValence,
    EncounterFrequency,
    EntityType,
    FactCategory,
    GriefStage,
    InjurySeverity,
    InjuryType,
    IntimacyStyle,
    ItemCondition,
    ItemType,
    MapType,
    MemoryType,
    MentalConditionType,
    ModifierSource,
    PlacementType,
    QuestStatus,
    SocialTendency,
    StorageLocationType,
    TaskCategory,
    TerrainType,
    TransportType,
    VisibilityRange,
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
from src.database.models.character_state import CharacterNeeds
from src.database.models.character_memory import CharacterMemory
from src.database.models.character_preferences import (
    CharacterPreferences,
    NeedAdaptation,
    NeedModifier,
)
from src.database.models.injuries import ActivityRestriction, BodyInjury
from src.database.models.vital_state import EntityVitalState
from src.database.models.mental_state import GriefCondition, MentalCondition
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
    """Create CharacterNeeds with sensible defaults.

    All needs follow: 0 = bad (action required), 100 = good (no action needed).
    """
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "hunger": 80,
        "thirst": 80,
        "energy": 80,
        "hygiene": 80,
        "comfort": 70,
        "wellness": 100,
        "social_connection": 50,
        "morale": 70,
        "sense_of_purpose": 60,
        "intimacy": 80,
        # Craving modifiers (default to 0)
        "hunger_craving": 0,
        "thirst_craving": 0,
        "energy_craving": 0,
        "social_craving": 0,
        "intimacy_craving": 0,
    }
    defaults.update(overrides)
    needs = CharacterNeeds(**defaults)
    db.add(needs)
    db.flush()
    return needs


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


# =============================================================================
# Character Preferences Factories
# =============================================================================


def create_character_preferences(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> CharacterPreferences:
    """Create CharacterPreferences with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        # Food defaults
        "is_vegetarian": False,
        "is_vegan": False,
        "is_greedy_eater": False,
        "is_picky_eater": False,
        # Drink defaults
        "alcohol_tolerance": AlcoholTolerance.MODERATE,
        "is_alcoholic": False,
        "is_teetotaler": False,
        # Intimacy defaults
        "drive_level": DriveLevel.MODERATE,
        "drive_threshold": 50,
        "intimacy_style": IntimacyStyle.EMOTIONAL,
        "has_regular_partner": False,
        "is_actively_seeking": False,
        # Social defaults
        "social_tendency": SocialTendency.AMBIVERT,
        "preferred_group_size": 3,
        "is_social_butterfly": False,
        "is_loner": False,
        # Stamina defaults
        "has_high_stamina": False,
        "has_low_stamina": False,
        "is_insomniac": False,
        "is_heavy_sleeper": False,
    }
    defaults.update(overrides)
    prefs = CharacterPreferences(**defaults)
    db.add(prefs)
    db.flush()
    return prefs


def create_need_modifier(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> NeedModifier:
    """Create a NeedModifier with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "need_name": "hunger",
        "modifier_source": ModifierSource.TRAIT,
        "decay_rate_multiplier": 1.0,
        "satisfaction_multiplier": 1.0,
        "threshold_adjustment": 0,
        "is_active": True,
    }
    defaults.update(overrides)
    modifier = NeedModifier(**defaults)
    db.add(modifier)
    db.flush()
    return modifier


def create_need_adaptation(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> NeedAdaptation:
    """Create a NeedAdaptation with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "need_name": "social_connection",
        "adaptation_delta": -10,
        "reason": "Extended time in isolation",
        "started_turn": 1,
        "is_gradual": True,
        "is_reversible": True,
    }
    defaults.update(overrides)
    adaptation = NeedAdaptation(**defaults)
    db.add(adaptation)
    db.flush()
    return adaptation


# =============================================================================
# Navigation Factories
# =============================================================================


def create_terrain_zone(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> TerrainZone:
    """Create a TerrainZone with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "zone_key": _unique_key("zone"),
        "display_name": "Test Zone",
        "terrain_type": TerrainType.PLAINS,
        "description": "A test terrain zone.",
        "base_travel_cost": 10,
        "visibility_range": VisibilityRange.MEDIUM,
        "encounter_frequency": EncounterFrequency.LOW,
        "is_accessible": True,
    }
    defaults.update(overrides)
    zone = TerrainZone(**defaults)
    db.add(zone)
    db.flush()
    return zone


def create_zone_connection(
    db: Session,
    game_session: GameSession,
    from_zone: TerrainZone,
    to_zone: TerrainZone,
    **overrides: Any,
) -> ZoneConnection:
    """Create a ZoneConnection with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "from_zone_id": from_zone.id,
        "to_zone_id": to_zone.id,
        "connection_type": ConnectionType.OPEN,
        "crossing_minutes": 5,
        "is_bidirectional": True,
        "is_passable": True,
        "is_visible": True,
    }
    defaults.update(overrides)
    connection = ZoneConnection(**defaults)
    db.add(connection)
    db.flush()
    return connection


def create_location_zone_placement(
    db: Session,
    game_session: GameSession,
    location: Location,
    zone: TerrainZone,
    **overrides: Any,
) -> LocationZonePlacement:
    """Create a LocationZonePlacement with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "location_id": location.id,
        "zone_id": zone.id,
        "placement_type": PlacementType.WITHIN,
        "visibility": "visible_from_zone",
    }
    defaults.update(overrides)
    placement = LocationZonePlacement(**defaults)
    db.add(placement)
    db.flush()
    return placement


def create_transport_mode(
    db: Session,
    **overrides: Any,
) -> TransportMode:
    """Create a TransportMode with sensible defaults."""
    defaults = {
        "mode_key": _unique_key("transport"),
        "display_name": "Test Transport",
        "transport_type": TransportType.WALKING,
        "terrain_costs": {"plains": 1.0, "forest": 2.0, "road": 0.8},
        "fatigue_rate": 1.0,
        "encounter_modifier": 1.0,
    }
    defaults.update(overrides)
    mode = TransportMode(**defaults)
    db.add(mode)
    db.flush()
    return mode


def create_zone_discovery(
    db: Session,
    game_session: GameSession,
    zone: TerrainZone,
    **overrides: Any,
) -> ZoneDiscovery:
    """Create a ZoneDiscovery with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "zone_id": zone.id,
        "discovered_turn": 1,
        "discovery_method": DiscoveryMethod.VISITED,
    }
    defaults.update(overrides)
    discovery = ZoneDiscovery(**defaults)
    db.add(discovery)
    db.flush()
    return discovery


def create_location_discovery(
    db: Session,
    game_session: GameSession,
    location: Location,
    **overrides: Any,
) -> LocationDiscovery:
    """Create a LocationDiscovery with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "location_id": location.id,
        "discovered_turn": 1,
        "discovery_method": DiscoveryMethod.VISITED,
    }
    defaults.update(overrides)
    discovery = LocationDiscovery(**defaults)
    db.add(discovery)
    db.flush()
    return discovery


def create_map_item(
    db: Session,
    game_session: GameSession,
    item: Item,
    **overrides: Any,
) -> MapItem:
    """Create a MapItem with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "item_id": item.id,
        "map_type": MapType.REGIONAL,
        "is_complete": True,
    }
    defaults.update(overrides)
    map_item = MapItem(**defaults)
    db.add(map_item)
    db.flush()
    return map_item


def create_digital_map_access(
    db: Session,
    game_session: GameSession,
    **overrides: Any,
) -> DigitalMapAccess:
    """Create a DigitalMapAccess with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "service_key": _unique_key("service"),
        "display_name": "Test Map Service",
        "requires_device": True,
        "requires_connection": True,
        "coverage_map_type": MapType.REGIONAL,
        "is_available": True,
    }
    defaults.update(overrides)
    access = DigitalMapAccess(**defaults)
    db.add(access)
    db.flush()
    return access


# =============================================================================
# Character Memory Factories
# =============================================================================


def create_character_memory(
    db: Session,
    game_session: GameSession,
    entity: Entity,
    **overrides: Any,
) -> CharacterMemory:
    """Create a CharacterMemory with sensible defaults."""
    defaults = {
        "session_id": game_session.id,
        "entity_id": entity.id,
        "subject": "mother's hat",
        "subject_type": MemoryType.ITEM,
        "keywords": ["hat", "wide-brimmed", "straw"],
        "valence": EmotionalValence.NEGATIVE,
        "emotion": "grief",
        "context": "Mother wore this hat every summer before she died.",
        "source": "backstory",
        "intensity": 7,
        "created_turn": None,
        "last_triggered_turn": None,
        "trigger_count": 0,
    }
    defaults.update(overrides)
    memory = CharacterMemory(**defaults)
    db.add(memory)
    db.flush()
    return memory
