"""Tests for database enumerations."""

import pytest

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
    RelationshipDimension,
    StorageLocationType,
    TaskCategory,
    VitalStatus,
)


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_type_values(self):
        """Verify all EntityType values."""
        assert EntityType.PLAYER.value == "player"
        assert EntityType.NPC.value == "npc"
        assert EntityType.MONSTER.value == "monster"
        assert EntityType.ANIMAL.value == "animal"

    def test_entity_type_count(self):
        """Verify expected number of entity types."""
        assert len(EntityType) == 4


class TestItemType:
    """Tests for ItemType enum."""

    def test_item_type_values(self):
        """Verify all ItemType values."""
        expected = {
            "clothing",
            "equipment",
            "accessory",
            "consumable",
            "container",
            "tool",
            "weapon",
            "armor",
            "misc",
        }
        actual = {e.value for e in ItemType}
        assert actual == expected

    def test_item_type_count(self):
        """Verify expected number of item types."""
        assert len(ItemType) == 9


class TestItemCondition:
    """Tests for ItemCondition enum."""

    def test_item_condition_values(self):
        """Verify all ItemCondition values."""
        expected = {"pristine", "good", "worn", "damaged", "broken"}
        actual = {e.value for e in ItemCondition}
        assert actual == expected

    def test_item_condition_count(self):
        """Verify expected number of conditions."""
        assert len(ItemCondition) == 5


class TestStorageLocationType:
    """Tests for StorageLocationType enum."""

    def test_storage_location_type_values(self):
        """Verify all StorageLocationType values."""
        assert StorageLocationType.ON_PERSON.value == "on_person"
        assert StorageLocationType.CONTAINER.value == "container"
        assert StorageLocationType.PLACE.value == "place"

    def test_storage_location_type_count(self):
        """Verify expected number of storage types."""
        assert len(StorageLocationType) == 3


class TestVitalStatus:
    """Tests for VitalStatus enum."""

    def test_vital_status_values(self):
        """Verify all VitalStatus values in progression order."""
        expected_order = [
            "healthy",
            "wounded",
            "critical",
            "dying",
            "dead",
            "clinically_dead",
            "permanently_dead",
        ]
        actual = [e.value for e in VitalStatus]
        assert actual == expected_order

    def test_vital_status_count(self):
        """Verify expected number of vital statuses."""
        assert len(VitalStatus) == 7


class TestInjuryType:
    """Tests for InjuryType enum."""

    def test_injury_type_categories(self):
        """Verify injury type categories exist."""
        # Tissue damage
        assert InjuryType.BRUISE.value == "bruise"
        assert InjuryType.CUT.value == "cut"
        assert InjuryType.LACERATION.value == "laceration"
        assert InjuryType.BURN.value == "burn"

        # Bone/joint
        assert InjuryType.SPRAIN.value == "sprain"
        assert InjuryType.STRAIN.value == "strain"
        assert InjuryType.FRACTURE.value == "fracture"
        assert InjuryType.DISLOCATION.value == "dislocation"

        # Muscle
        assert InjuryType.MUSCLE_SORE.value == "muscle_sore"
        assert InjuryType.MUSCLE_TEAR.value == "muscle_tear"
        assert InjuryType.MUSCLE_RUPTURE.value == "muscle_rupture"

        # Severe
        assert InjuryType.CONCUSSION.value == "concussion"
        assert InjuryType.INTERNAL_BLEEDING.value == "internal_bleeding"
        assert InjuryType.NERVE_DAMAGE.value == "nerve_damage"

    def test_injury_type_count(self):
        """Verify expected number of injury types."""
        assert len(InjuryType) == 14


class TestInjurySeverity:
    """Tests for InjurySeverity enum."""

    def test_injury_severity_values(self):
        """Verify all InjurySeverity values."""
        assert InjurySeverity.MINOR.value == "minor"
        assert InjurySeverity.MODERATE.value == "moderate"
        assert InjurySeverity.SEVERE.value == "severe"
        assert InjurySeverity.CRITICAL.value == "critical"

    def test_injury_severity_count(self):
        """Verify expected number of severities."""
        assert len(InjurySeverity) == 4


class TestBodyPart:
    """Tests for BodyPart enum."""

    def test_body_part_core(self):
        """Verify core body parts."""
        assert BodyPart.HEAD.value == "head"
        assert BodyPart.TORSO.value == "torso"
        assert BodyPart.BACK.value == "back"

    def test_body_part_arms(self):
        """Verify arm-related body parts."""
        arm_parts = [
            BodyPart.LEFT_SHOULDER,
            BodyPart.RIGHT_SHOULDER,
            BodyPart.LEFT_ARM,
            BodyPart.RIGHT_ARM,
            BodyPart.LEFT_HAND,
            BodyPart.RIGHT_HAND,
        ]
        assert len(arm_parts) == 6
        for part in arm_parts:
            assert part.value in [
                "left_shoulder",
                "right_shoulder",
                "left_arm",
                "right_arm",
                "left_hand",
                "right_hand",
            ]

    def test_body_part_legs(self):
        """Verify leg-related body parts."""
        leg_parts = [
            BodyPart.LEFT_HIP,
            BodyPart.RIGHT_HIP,
            BodyPart.LEFT_LEG,
            BodyPart.RIGHT_LEG,
            BodyPart.LEFT_FOOT,
            BodyPart.RIGHT_FOOT,
        ]
        assert len(leg_parts) == 6

    def test_body_part_sensory(self):
        """Verify sensory body parts."""
        assert BodyPart.EYES.value == "eyes"
        assert BodyPart.EARS.value == "ears"

    def test_body_part_count(self):
        """Verify expected number of body parts."""
        assert len(BodyPart) == 17


class TestGriefStage:
    """Tests for GriefStage enum (Kübler-Ross model)."""

    def test_grief_stage_sequence(self):
        """Verify grief stages in order."""
        expected_order = [
            "shock",
            "denial",
            "anger",
            "bargaining",
            "depression",
            "acceptance",
        ]
        actual = [e.value for e in GriefStage]
        assert actual == expected_order

    def test_grief_stage_count(self):
        """Verify expected number of grief stages."""
        assert len(GriefStage) == 6


class TestMentalConditionType:
    """Tests for MentalConditionType enum."""

    def test_mental_condition_values(self):
        """Verify all mental condition types."""
        expected = {
            "ptsd_combat",
            "ptsd_near_death",
            "ptsd_trauma",
            "depression",
            "anxiety",
            "phobia",
            "death_anxiety",
            "survivors_guilt",
            "existential_crisis",
        }
        actual = {e.value for e in MentalConditionType}
        assert actual == expected

    def test_mental_condition_count(self):
        """Verify expected number of mental conditions."""
        assert len(MentalConditionType) == 9


class TestRelationshipDimension:
    """Tests for RelationshipDimension enum."""

    def test_relationship_dimension_values(self):
        """Verify all relationship dimensions."""
        expected = {
            "trust",
            "liking",
            "respect",
            "romantic_interest",
            "familiarity",
            "fear",
            "social_debt",
        }
        actual = {e.value for e in RelationshipDimension}
        assert actual == expected

    def test_relationship_dimension_count(self):
        """Verify expected number of dimensions."""
        assert len(RelationshipDimension) == 7


class TestDayOfWeek:
    """Tests for DayOfWeek enum."""

    def test_day_of_week_standard_days(self):
        """Verify standard weekdays."""
        standard_days = [
            DayOfWeek.MONDAY,
            DayOfWeek.TUESDAY,
            DayOfWeek.WEDNESDAY,
            DayOfWeek.THURSDAY,
            DayOfWeek.FRIDAY,
            DayOfWeek.SATURDAY,
            DayOfWeek.SUNDAY,
        ]
        assert len(standard_days) == 7

    def test_day_of_week_patterns(self):
        """Verify day pattern shortcuts."""
        assert DayOfWeek.WEEKDAY.value == "weekday"
        assert DayOfWeek.WEEKEND.value == "weekend"
        assert DayOfWeek.DAILY.value == "daily"

    def test_day_of_week_count(self):
        """Verify expected number of day options."""
        assert len(DayOfWeek) == 10


class TestFactCategory:
    """Tests for FactCategory enum."""

    def test_fact_category_values(self):
        """Verify all fact categories."""
        expected = {
            "personal",
            "secret",
            "preference",
            "skill",
            "history",
            "relationship",
            "location",
            "world",
        }
        actual = {e.value for e in FactCategory}
        assert actual == expected

    def test_fact_category_count(self):
        """Verify expected number of categories."""
        assert len(FactCategory) == 8


class TestTaskCategory:
    """Tests for TaskCategory enum."""

    def test_task_category_values(self):
        """Verify all task categories."""
        assert TaskCategory.APPOINTMENT.value == "appointment"
        assert TaskCategory.GOAL.value == "goal"
        assert TaskCategory.REMINDER.value == "reminder"
        assert TaskCategory.QUEST.value == "quest"

    def test_task_category_count(self):
        """Verify expected number of task categories."""
        assert len(TaskCategory) == 4


class TestAppointmentStatus:
    """Tests for AppointmentStatus enum."""

    def test_appointment_status_values(self):
        """Verify all appointment statuses."""
        expected = {"scheduled", "completed", "cancelled", "missed", "rescheduled"}
        actual = {e.value for e in AppointmentStatus}
        assert actual == expected

    def test_appointment_status_count(self):
        """Verify expected number of statuses."""
        assert len(AppointmentStatus) == 5


class TestQuestStatus:
    """Tests for QuestStatus enum."""

    def test_quest_status_values(self):
        """Verify all quest statuses."""
        assert QuestStatus.AVAILABLE.value == "available"
        assert QuestStatus.ACTIVE.value == "active"
        assert QuestStatus.COMPLETED.value == "completed"
        assert QuestStatus.FAILED.value == "failed"

    def test_quest_status_count(self):
        """Verify expected number of quest statuses."""
        assert len(QuestStatus) == 4


class TestIntimacyStyle:
    """Tests for IntimacyStyle enum."""

    def test_intimacy_style_values(self):
        """Verify all intimacy styles."""
        expected = {"casual", "emotional", "monogamous", "polyamorous"}
        actual = {e.value for e in IntimacyStyle}
        assert actual == expected

    def test_intimacy_style_count(self):
        """Verify expected number of styles."""
        assert len(IntimacyStyle) == 4


class TestDriveLevel:
    """Tests for DriveLevel enum."""

    def test_drive_level_values(self):
        """Verify all drive levels."""
        expected = {"asexual", "very_low", "low", "moderate", "high", "very_high"}
        actual = {e.value for e in DriveLevel}
        assert actual == expected

    def test_drive_level_count(self):
        """Verify expected number of drive levels."""
        assert len(DriveLevel) == 6
