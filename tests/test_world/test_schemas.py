"""Tests for Scene-First Architecture schemas.

These tests verify:
- All Pydantic models can be instantiated with valid data
- Required fields are enforced
- Default values work correctly
- Enum values are valid
- Helper methods work as expected
"""

import pytest
from pydantic import ValidationError

from src.world.schemas import (
    # Enums
    ItemVisibility,
    NarrationType,
    ObservationLevel,
    PresenceReason,
    # World Mechanics
    FactUpdate,
    NewElement,
    NPCMovement,
    NPCPlacement,
    NPCSpec,
    WorldEvent,
    WorldUpdate,
    # Scene Builder
    Atmosphere,
    FurnitureSpec,
    ItemSpec,
    SceneContents,
    SceneManifest,
    SceneNPC,
    # Narrator
    EntityRef,
    NarrationContext,
    NarrationResult,
    NarratorManifest,
    # Validation
    InvalidReference,
    UnkeyedReference,
    ValidationResult,
    # Resolution
    ResolutionResult,
    # Constraints
    ConstraintResult,
    SocialLimits,
    # Persistence
    PersistedItem,
    PersistedNPC,
    PersistedScene,
    PersistedWorldUpdate,
)


# =============================================================================
# Enum Tests
# =============================================================================


class TestPresenceReason:
    """Tests for PresenceReason enum."""

    def test_all_values_exist(self) -> None:
        """Test all expected values are present."""
        assert PresenceReason.LIVES_HERE == "lives_here"
        assert PresenceReason.SCHEDULE == "schedule"
        assert PresenceReason.EVENT == "event"
        assert PresenceReason.STORY == "story"
        assert PresenceReason.VISITING == "visiting"

    def test_is_string_enum(self) -> None:
        """Test enum values are strings."""
        assert isinstance(PresenceReason.LIVES_HERE.value, str)


class TestObservationLevel:
    """Tests for ObservationLevel enum."""

    def test_all_values_exist(self) -> None:
        """Test all expected values are present."""
        assert ObservationLevel.NONE == "none"
        assert ObservationLevel.ENTRY == "entry"
        assert ObservationLevel.LOOK == "look"
        assert ObservationLevel.SEARCH == "search"
        assert ObservationLevel.EXAMINE == "examine"


class TestItemVisibility:
    """Tests for ItemVisibility enum."""

    def test_all_values_exist(self) -> None:
        """Test all expected values are present."""
        assert ItemVisibility.OBVIOUS == "obvious"
        assert ItemVisibility.DISCOVERABLE == "discoverable"
        assert ItemVisibility.HIDDEN == "hidden"


class TestNarrationType:
    """Tests for NarrationType enum."""

    def test_all_values_exist(self) -> None:
        """Test all expected values are present."""
        assert NarrationType.SCENE_ENTRY == "scene_entry"
        assert NarrationType.ACTION_RESULT == "action_result"
        assert NarrationType.DIALOGUE == "dialogue"
        assert NarrationType.CLARIFICATION == "clarification"
        assert NarrationType.AMBIENT == "ambient"


# =============================================================================
# World Mechanics Schema Tests
# =============================================================================


class TestNPCSpec:
    """Tests for NPCSpec schema."""

    def test_minimal_creation(self) -> None:
        """Test creation with only required fields."""
        spec = NPCSpec(display_name="Marcus")
        assert spec.display_name == "Marcus"
        assert spec.gender is None
        assert spec.occupation is None
        assert spec.personality_hints == []
        assert spec.relationship_to_player is None
        assert spec.backstory_hints == []

    def test_full_creation(self) -> None:
        """Test creation with all fields."""
        spec = NPCSpec(
            display_name="Marcus",
            gender="male",
            occupation="blacksmith",
            personality_hints=["friendly", "hardworking"],
            relationship_to_player="childhood friend",
            backstory_hints=["grew up in village", "lost his father"],
        )
        assert spec.display_name == "Marcus"
        assert spec.gender == "male"
        assert spec.occupation == "blacksmith"
        assert len(spec.personality_hints) == 2
        assert spec.relationship_to_player == "childhood friend"
        assert len(spec.backstory_hints) == 2


class TestNPCPlacement:
    """Tests for NPCPlacement schema."""

    def test_existing_npc_placement(self) -> None:
        """Test placement of existing NPC."""
        placement = NPCPlacement(
            entity_key="marcus_001",
            presence_reason=PresenceReason.SCHEDULE,
            presence_justification="Marcus works here",
            activity="hammering at the forge",
            position_in_scene="by the forge",
        )
        assert placement.entity_key == "marcus_001"
        assert placement.new_npc is None
        assert placement.mood == "neutral"
        assert placement.will_initiate_conversation is False

    def test_new_npc_placement(self) -> None:
        """Test placement of new NPC."""
        placement = NPCPlacement(
            new_npc=NPCSpec(display_name="Elena", gender="female"),
            presence_reason=PresenceReason.STORY,
            presence_justification="Elena is the player's childhood friend",
            activity="reading a book",
            mood="relaxed",
            position_in_scene="on the bed",
            will_initiate_conversation=True,
        )
        assert placement.entity_key is None
        assert placement.new_npc is not None
        assert placement.new_npc.display_name == "Elena"
        assert placement.will_initiate_conversation is True

    def test_requires_either_key_or_spec(self) -> None:
        """Test that either entity_key or new_npc must be provided."""
        with pytest.raises(ValueError, match="Either entity_key or new_npc"):
            NPCPlacement(
                presence_reason=PresenceReason.SCHEDULE,
                presence_justification="Missing NPC info",
                activity="standing",
                position_in_scene="somewhere",
            )


class TestNPCMovement:
    """Tests for NPCMovement schema."""

    def test_creation(self) -> None:
        """Test basic movement creation."""
        movement = NPCMovement(
            entity_key="marcus_001",
            from_location="forge",
            to_location="tavern",
            reason="End of workday",
        )
        assert movement.entity_key == "marcus_001"
        assert movement.from_location == "forge"
        assert movement.to_location == "tavern"


class TestNewElement:
    """Tests for NewElement schema."""

    def test_npc_element(self) -> None:
        """Test new NPC element."""
        element = NewElement(
            element_type="npc",
            specification={"display_name": "Marcus", "gender": "male"},
            justification="Player needs a friend in town",
            narrative_purpose="Provide quest hooks",
        )
        assert element.element_type == "npc"
        assert element.constraints_checked == []

    def test_fact_element(self) -> None:
        """Test new fact element."""
        element = NewElement(
            element_type="fact",
            specification={
                "subject": "village",
                "predicate": "has_problem",
                "value": "wolf attacks",
            },
            justification="Sets up adventure hook",
            constraints_checked=["physical_plausibility"],
            narrative_purpose="Create tension",
        )
        assert element.element_type == "fact"
        assert len(element.constraints_checked) == 1


class TestWorldEvent:
    """Tests for WorldEvent schema."""

    def test_minimal_event(self) -> None:
        """Test event with minimal fields."""
        event = WorldEvent(
            event_type="arrival",
            event_key="arrival_001",
            description="A merchant arrives",
            location="market",
        )
        assert event.npcs_involved == []
        assert event.items_involved == []
        assert event.immediate_effects == []
        assert event.player_will_notice is True

    def test_complex_event(self) -> None:
        """Test event with all fields."""
        event = WorldEvent(
            event_type="intrusion",
            event_key="intrusion_001",
            description="Thieves break into the shop",
            npcs_involved=["thief_001", "thief_002"],
            items_involved=["gold_pouch", "jewel_box"],
            location="shop",
            immediate_effects=["window broken", "alarm raised"],
            player_will_notice=True,
        )
        assert len(event.npcs_involved) == 2
        assert len(event.items_involved) == 2


class TestFactUpdate:
    """Tests for FactUpdate schema."""

    def test_creation(self) -> None:
        """Test fact update creation."""
        fact = FactUpdate(
            subject="marcus_001",
            predicate="mood",
            value="happy",
            source="world_mechanics",
        )
        assert fact.subject == "marcus_001"
        assert fact.predicate == "mood"


class TestWorldUpdate:
    """Tests for WorldUpdate schema."""

    def test_empty_update(self) -> None:
        """Test empty world update."""
        update = WorldUpdate()
        assert update.scheduled_movements == []
        assert update.npcs_at_location == []
        assert update.new_elements == []
        assert update.events == []
        assert update.fact_updates == []

    def test_full_update(self) -> None:
        """Test world update with all fields populated."""
        update = WorldUpdate(
            scheduled_movements=[
                NPCMovement(
                    entity_key="marcus_001",
                    from_location="forge",
                    to_location="tavern",
                    reason="End of work",
                )
            ],
            npcs_at_location=[
                NPCPlacement(
                    entity_key="elena_001",
                    presence_reason=PresenceReason.LIVES_HERE,
                    presence_justification="Lives here",
                    activity="reading",
                    position_in_scene="on bed",
                )
            ],
            events=[
                WorldEvent(
                    event_type="arrival",
                    event_key="event_001",
                    description="Visitor arrives",
                    location="home",
                )
            ],
            fact_updates=[
                FactUpdate(
                    subject="world",
                    predicate="time",
                    value="evening",
                    source="clock",
                )
            ],
        )
        assert len(update.scheduled_movements) == 1
        assert len(update.npcs_at_location) == 1
        assert len(update.events) == 1
        assert len(update.fact_updates) == 1


# =============================================================================
# Scene Builder Schema Tests
# =============================================================================


class TestFurnitureSpec:
    """Tests for FurnitureSpec schema."""

    def test_simple_furniture(self) -> None:
        """Test simple furniture creation."""
        furniture = FurnitureSpec(
            furniture_key="bed_001",
            display_name="a wooden bed",
            furniture_type="bed",
            position_in_room="center",
        )
        assert furniture.material == "wood"
        assert furniture.condition == "good"
        assert furniture.is_container is False
        assert furniture.container_state is None

    def test_container_furniture(self) -> None:
        """Test container furniture creation."""
        furniture = FurnitureSpec(
            furniture_key="closet_001",
            display_name="an oak closet",
            furniture_type="closet",
            material="oak",
            condition="worn",
            position_in_room="by wall",
            is_container=True,
            container_state="closed",
            description_hints=["old", "creaky doors"],
        )
        assert furniture.is_container is True
        assert furniture.container_state == "closed"
        assert len(furniture.description_hints) == 2


class TestItemSpec:
    """Tests for ItemSpec schema."""

    def test_obvious_item(self) -> None:
        """Test obvious item creation."""
        item = ItemSpec(
            item_key="book_001",
            display_name="a leather-bound journal",
            item_type="book",
            position="on desk",
        )
        assert item.visibility == ItemVisibility.OBVIOUS
        assert item.material is None
        assert item.properties == {}

    def test_hidden_item(self) -> None:
        """Test hidden item creation."""
        item = ItemSpec(
            item_key="key_001",
            display_name="a small brass key",
            item_type="key",
            position="under mattress",
            visibility=ItemVisibility.HIDDEN,
            material="brass",
            properties={"unlocks": "chest_001"},
            description_hints=["old", "ornate"],
        )
        assert item.visibility == ItemVisibility.HIDDEN
        assert item.properties["unlocks"] == "chest_001"


class TestAtmosphere:
    """Tests for Atmosphere schema."""

    def test_minimal_atmosphere(self) -> None:
        """Test atmosphere with minimal fields."""
        atmo = Atmosphere(
            lighting="bright daylight",
            lighting_source="windows",
        )
        assert atmo.sounds == []
        assert atmo.smells == []
        assert atmo.temperature == "comfortable"
        assert atmo.overall_mood == "neutral"

    def test_full_atmosphere(self) -> None:
        """Test atmosphere with all fields."""
        atmo = Atmosphere(
            lighting="dim candlelight",
            lighting_source="candles",
            sounds=["fire crackling", "wind outside"],
            smells=["wood smoke", "lavender"],
            temperature="warm",
            weather_effects="rain pattering on window",
            time_of_day_notes="Evening shadows lengthening",
            overall_mood="cozy",
        )
        assert len(atmo.sounds) == 2
        assert len(atmo.smells) == 2
        assert atmo.overall_mood == "cozy"


class TestSceneContents:
    """Tests for SceneContents schema."""

    def test_creation(self) -> None:
        """Test scene contents creation."""
        contents = SceneContents(
            furniture=[
                FurnitureSpec(
                    furniture_key="bed_001",
                    display_name="a bed",
                    furniture_type="bed",
                    position_in_room="center",
                )
            ],
            items=[
                ItemSpec(
                    item_key="book_001",
                    display_name="a book",
                    item_type="book",
                    position="on desk",
                )
            ],
            atmosphere=Atmosphere(lighting="bright", lighting_source="window"),
            discoverable_hints=["something under the bed"],
        )
        assert len(contents.furniture) == 1
        assert len(contents.items) == 1
        assert len(contents.discoverable_hints) == 1


class TestSceneNPC:
    """Tests for SceneNPC schema."""

    def test_creation(self) -> None:
        """Test scene NPC creation."""
        npc = SceneNPC(
            entity_key="marcus_001",
            display_name="Marcus",
            gender="male",
            presence_reason=PresenceReason.SCHEDULE,
            activity="reading",
            mood="relaxed",
            position_in_scene="by window",
            appearance_notes="wearing simple clothes",
            will_initiate=True,
            pronouns="he/him",
        )
        assert npc.entity_key == "marcus_001"
        assert npc.pronouns == "he/him"


class TestSceneManifest:
    """Tests for SceneManifest schema."""

    def test_minimal_manifest(self) -> None:
        """Test scene manifest with minimal fields."""
        manifest = SceneManifest(
            location_key="bedroom_001",
            location_display="Your Bedroom",
            location_type="bedroom",
            atmosphere=Atmosphere(lighting="bright", lighting_source="window"),
        )
        assert manifest.furniture == []
        assert manifest.items == []
        assert manifest.npcs == []
        assert manifest.observation_level == ObservationLevel.ENTRY
        assert manifest.is_first_visit is True

    def test_full_manifest(self) -> None:
        """Test scene manifest with all fields."""
        manifest = SceneManifest(
            location_key="bedroom_001",
            location_display="Your Bedroom",
            location_type="bedroom",
            furniture=[
                FurnitureSpec(
                    furniture_key="bed_001",
                    display_name="a bed",
                    furniture_type="bed",
                    position_in_room="center",
                )
            ],
            items=[
                ItemSpec(
                    item_key="book_001",
                    display_name="a book",
                    item_type="book",
                    position="on desk",
                )
            ],
            npcs=[
                SceneNPC(
                    entity_key="marcus_001",
                    display_name="Marcus",
                    presence_reason=PresenceReason.VISITING,
                    activity="sitting",
                    mood="happy",
                    position_in_scene="on chair",
                )
            ],
            atmosphere=Atmosphere(lighting="bright", lighting_source="window"),
            observation_level=ObservationLevel.LOOK,
            undiscovered_hints=["something under bed"],
            is_first_visit=False,
            generated_at="2024-01-15T10:30:00Z",
        )
        assert len(manifest.furniture) == 1
        assert len(manifest.npcs) == 1
        assert manifest.observation_level == ObservationLevel.LOOK


# =============================================================================
# Narrator Schema Tests
# =============================================================================


class TestEntityRef:
    """Tests for EntityRef schema."""

    def test_npc_ref(self) -> None:
        """Test NPC entity reference."""
        ref = EntityRef(
            key="marcus_001",
            display_name="Marcus",
            entity_type="npc",
            short_description="your friend",
            pronouns="he/him",
            position="by window",
        )
        assert ref.key == "marcus_001"
        assert ref.pronouns == "he/him"

    def test_item_ref(self) -> None:
        """Test item entity reference."""
        ref = EntityRef(
            key="book_001",
            display_name="a leather journal",
            entity_type="item",
            short_description="an old journal",
        )
        assert ref.pronouns is None
        assert ref.position is None


class TestNarratorManifest:
    """Tests for NarratorManifest schema."""

    def test_empty_manifest(self) -> None:
        """Test empty narrator manifest."""
        manifest = NarratorManifest(
            location_key="bedroom_001",
            location_display="Your Bedroom",
            atmosphere=Atmosphere(lighting="bright", lighting_source="window"),
        )
        assert manifest.entities == {}
        assert manifest.world_events == []

    def test_get_reference_guide_empty(self) -> None:
        """Test reference guide with no entities."""
        manifest = NarratorManifest(
            location_key="bedroom_001",
            location_display="Your Bedroom",
            atmosphere=Atmosphere(lighting="bright", lighting_source="window"),
        )
        guide = manifest.get_reference_guide()
        assert "Entities You May Reference" in guide
        assert "[key:displayed_text]" in guide  # New format with display text

    def test_get_reference_guide_with_entities(self) -> None:
        """Test reference guide with entities."""
        manifest = NarratorManifest(
            location_key="bedroom_001",
            location_display="Your Bedroom",
            entities={
                "marcus_001": EntityRef(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                    short_description="your friend",
                    pronouns="he/him",
                    position="by window",
                ),
                "bed_001": EntityRef(
                    key="bed_001",
                    display_name="a wooden bed",
                    entity_type="furniture",
                    short_description="a sturdy bed",
                    position="center",
                ),
                "book_001": EntityRef(
                    key="book_001",
                    display_name="a journal",
                    entity_type="item",
                    short_description="a leather journal",
                    position="on desk",
                ),
            },
            atmosphere=Atmosphere(lighting="bright", lighting_source="window"),
        )
        guide = manifest.get_reference_guide()
        assert "**NPCs:**" in guide
        assert "[marcus_001:Marcus]" in guide  # Format: [key:display_name]
        assert "(he/him)" in guide
        assert "**Furniture:**" in guide
        assert "[bed_001:a wooden bed]" in guide
        assert "**Items:**" in guide
        assert "[book_001:a journal]" in guide


class TestNarrationContext:
    """Tests for NarrationContext schema."""

    def test_empty_context(self) -> None:
        """Test empty narration context."""
        context = NarrationContext()
        assert context.turn_history == []
        assert context.player_action is None
        assert context.previous_errors == []

    def test_with_errors(self) -> None:
        """Test adding errors to context."""
        context = NarrationContext(
            player_action={"action": "look"},
            previous_errors=["error 1"],
        )
        new_context = context.with_errors(["error 2", "error 3"])
        assert len(new_context.previous_errors) == 3
        assert "error 1" in new_context.previous_errors
        assert "error 2" in new_context.previous_errors
        # Original should be unchanged
        assert len(context.previous_errors) == 1


class TestNarrationResult:
    """Tests for NarrationResult schema."""

    def test_creation(self) -> None:
        """Test narration result creation."""
        result = NarrationResult(
            display_text="You see Marcus sitting by the window.",
            raw_output="You see [marcus_001] sitting by the [window_001].",
            entity_references=[
                EntityRef(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                    short_description="your friend",
                )
            ],
            validation_passed=True,
        )
        assert len(result.entity_references) == 1
        assert result.validation_passed is True


# =============================================================================
# Validation Schema Tests
# =============================================================================


class TestInvalidReference:
    """Tests for InvalidReference schema."""

    def test_creation(self) -> None:
        """Test invalid reference creation."""
        ref = InvalidReference(
            key="unknown_001",
            position=25,
            context="...sitting on [unknown_001]...",
            error="Entity 'unknown_001' not found in manifest",
        )
        assert ref.key == "unknown_001"
        assert ref.position == 25


class TestUnkeyedReference:
    """Tests for UnkeyedReference schema."""

    def test_creation(self) -> None:
        """Test unkeyed reference creation."""
        ref = UnkeyedReference(
            entity_key="marcus_001",
            display_name="Marcus",
            error="Entity 'Marcus' mentioned without [key] format",
        )
        assert ref.entity_key == "marcus_001"


class TestValidationResult:
    """Tests for ValidationResult schema."""

    def test_valid_result(self) -> None:
        """Test valid validation result."""
        result = ValidationResult(
            valid=True,
            references=[
                EntityRef(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                    short_description="friend",
                )
            ],
        )
        assert result.valid is True
        assert result.errors == []
        assert result.error_messages == []

    def test_invalid_result(self) -> None:
        """Test invalid validation result."""
        result = ValidationResult(
            valid=False,
            errors=[
                InvalidReference(
                    key="bad_001",
                    position=10,
                    context="...[bad_001]...",
                    error="Not found",
                ),
                UnkeyedReference(
                    entity_key="marcus_001",
                    display_name="Marcus",
                    error="Missing key format",
                ),
            ],
        )
        assert result.valid is False
        assert len(result.errors) == 2
        assert len(result.error_messages) == 2


# =============================================================================
# Resolution Schema Tests
# =============================================================================


class TestResolutionResult:
    """Tests for ResolutionResult schema."""

    def test_successful_resolution(self) -> None:
        """Test successful resolution."""
        result = ResolutionResult(
            resolved=True,
            entity_key="marcus_001",
            entity_type="npc",
        )
        assert result.resolved is True
        assert result.ambiguous is False

    def test_ambiguous_resolution(self) -> None:
        """Test ambiguous resolution."""
        result = ResolutionResult(
            resolved=False,
            ambiguous=True,
            candidates=[
                EntityRef(
                    key="marcus_001",
                    display_name="Marcus",
                    entity_type="npc",
                    short_description="friend",
                ),
                EntityRef(
                    key="max_001",
                    display_name="Max",
                    entity_type="npc",
                    short_description="stranger",
                ),
            ],
            clarification_needed="Which person do you mean?",
        )
        assert result.resolved is False
        assert result.ambiguous is True
        assert len(result.candidates) == 2

    def test_failed_resolution(self) -> None:
        """Test failed resolution."""
        result = ResolutionResult(
            resolved=False,
            error="No matching entity found",
        )
        assert result.resolved is False
        assert result.error is not None


# =============================================================================
# Constraint Schema Tests
# =============================================================================


class TestSocialLimits:
    """Tests for SocialLimits schema."""

    def test_defaults(self) -> None:
        """Test default social limits."""
        limits = SocialLimits()
        assert limits.max_close_friends == 5
        assert limits.max_casual_friends == 15
        assert limits.max_acquaintances == 50
        assert limits.max_new_relationships_per_week == 3
        assert limits.min_interactions_for_friendship == 5

    def test_for_extrovert(self) -> None:
        """Test extrovert personality limits."""
        limits = SocialLimits.for_player("extrovert")
        assert limits.max_close_friends == 8
        assert limits.max_casual_friends == 25
        assert limits.max_new_relationships_per_week == 5

    def test_for_introvert(self) -> None:
        """Test introvert personality limits."""
        limits = SocialLimits.for_player("introvert")
        assert limits.max_close_friends == 3
        assert limits.max_casual_friends == 8
        assert limits.max_new_relationships_per_week == 1

    def test_for_default_personality(self) -> None:
        """Test default personality (None)."""
        limits = SocialLimits.for_player(None)
        assert limits.max_close_friends == 5

    def test_for_unknown_personality(self) -> None:
        """Test unknown personality falls back to default."""
        limits = SocialLimits.for_player("weird")
        assert limits.max_close_friends == 5


class TestConstraintResult:
    """Tests for ConstraintResult schema."""

    def test_allowed(self) -> None:
        """Test allowed constraint result."""
        result = ConstraintResult(allowed=True)
        assert result.allowed is True
        assert result.reason is None
        assert result.violated_constraint is None
        assert result.suggestion is None

    def test_not_allowed(self) -> None:
        """Test not allowed constraint result."""
        result = ConstraintResult(
            allowed=False,
            reason="Too many friends",
            violated_constraint="max_close_friends",
            suggestion="Use casual friend instead",
        )
        assert result.allowed is False
        assert result.reason is not None
        assert result.violated_constraint == "max_close_friends"


# =============================================================================
# Persistence Schema Tests
# =============================================================================


class TestPersistedNPC:
    """Tests for PersistedNPC schema."""

    def test_creation(self) -> None:
        """Test persisted NPC creation."""
        npc = PersistedNPC(
            entity_key="marcus_001",
            entity_id=42,
            was_created=True,
        )
        assert npc.entity_key == "marcus_001"
        assert npc.entity_id == 42
        assert npc.was_created is True


class TestPersistedItem:
    """Tests for PersistedItem schema."""

    def test_creation(self) -> None:
        """Test persisted item creation."""
        item = PersistedItem(
            item_key="book_001",
            item_id=99,
            storage_location_id=5,
            was_created=True,
        )
        assert item.item_key == "book_001"
        assert item.storage_location_id == 5


class TestPersistedWorldUpdate:
    """Tests for PersistedWorldUpdate schema."""

    def test_creation(self) -> None:
        """Test persisted world update creation."""
        update = PersistedWorldUpdate(
            npcs=[
                PersistedNPC(entity_key="npc1", entity_id=1, was_created=True),
                PersistedNPC(entity_key="npc2", entity_id=2, was_created=False),
            ],
            events_created=["event_001"],
            facts_stored=3,
        )
        assert len(update.npcs) == 2
        assert len(update.events_created) == 1
        assert update.facts_stored == 3


class TestPersistedScene:
    """Tests for PersistedScene schema."""

    def test_creation(self) -> None:
        """Test persisted scene creation."""
        scene = PersistedScene(
            furniture=[
                PersistedItem(item_key="bed_001", item_id=1, was_created=True),
            ],
            items=[
                PersistedItem(item_key="book_001", item_id=2, was_created=True),
            ],
            location_marked_generated=True,
        )
        assert len(scene.furniture) == 1
        assert len(scene.items) == 1
        assert scene.location_marked_generated is True
