"""Tests for DestinyManager."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.destiny import (
    DestinyElement,
    DestinyElementType,
    Prophesy,
    ProphesyStatus,
)
from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.managers.destiny_manager import (
    DestinyManager,
    ProphesyProgress,
)


@pytest.fixture
def destiny_manager(db_session: Session, game_session: GameSession) -> DestinyManager:
    """Create a DestinyManager fixture."""
    return DestinyManager(db=db_session, game_session=game_session)


@pytest.fixture
def hero_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a hero entity fixture."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="hero_chosen_one",
        display_name="The Chosen One",
        entity_type=EntityType.PLAYER,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def sample_prophesy(
    db_session: Session, game_session: GameSession
) -> Prophesy:
    """Create a sample prophecy fixture."""
    prophesy = Prophesy(
        session_id=game_session.id,
        prophesy_key="dragon_doom",
        prophesy_text="When the moon turns red, the dragon shall awaken and doom shall fall upon the land.",
        true_meaning="A lunar eclipse will trigger the ancient dragon's resurrection.",
        source="ancient_scroll",
        delivered_turn=1,
        status=ProphesyStatus.ACTIVE.value,
        fulfillment_conditions=[
            "lunar_eclipse_occurs",
            "dragon_awakens",
            "destruction_begins",
        ],
        subversion_conditions=[
            "destroy_dragon_egg",
            "seal_dragon_cave",
        ],
        interpretation_hints=[
            "The eclipse is coming soon",
            "The dragon sleeps beneath the mountain",
        ],
    )
    db_session.add(prophesy)
    db_session.flush()
    return prophesy


# --- Prophesy Creation Tests ---


class TestProphesyCreation:
    """Tests for prophecy creation."""

    def test_create_prophesy(self, destiny_manager: DestinyManager):
        """Test creating a basic prophecy."""
        prophesy = destiny_manager.create_prophesy(
            prophesy_key="hero_rises",
            prophesy_text="A hero shall rise from humble beginnings.",
            true_meaning="The farm boy will become the legendary warrior.",
            source="oracle_vision",
            fulfillment_conditions=["hero_defeats_evil", "hero_crowned_king"],
        )

        assert prophesy.prophesy_key == "hero_rises"
        assert prophesy.status == ProphesyStatus.ACTIVE.value
        assert len(prophesy.fulfillment_conditions) == 2

    def test_create_prophesy_with_all_fields(self, destiny_manager: DestinyManager):
        """Test creating a prophecy with all optional fields."""
        prophesy = destiny_manager.create_prophesy(
            prophesy_key="dark_lord_returns",
            prophesy_text="The Dark Lord shall return when three stars align.",
            true_meaning="Three magical artifacts must be gathered.",
            source="dying_seer",
            fulfillment_conditions=["gather_artifacts", "perform_ritual"],
            subversion_conditions=["destroy_artifacts", "kill_cultists"],
            interpretation_hints=["The stars may be objects", "Alignment means unity"],
        )

        assert len(prophesy.subversion_conditions) == 2
        assert len(prophesy.interpretation_hints) == 2

    def test_get_prophesy(
        self, destiny_manager: DestinyManager, sample_prophesy: Prophesy
    ):
        """Test retrieving a prophecy by key."""
        prophesy = destiny_manager.get_prophesy("dragon_doom")

        assert prophesy is not None
        assert prophesy.id == sample_prophesy.id
        assert prophesy.source == "ancient_scroll"

    def test_get_prophesy_not_found(self, destiny_manager: DestinyManager):
        """Test retrieving non-existent prophecy."""
        prophesy = destiny_manager.get_prophesy("nonexistent")
        assert prophesy is None

    def test_get_active_prophesies(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test getting all active prophecies."""
        # Add another active prophecy
        prophesy2 = Prophesy(
            session_id=game_session.id,
            prophesy_key="second_prophesy",
            prophesy_text="Another prophecy.",
            true_meaning="Hidden meaning.",
            source="oracle",
            delivered_turn=2,
            status=ProphesyStatus.ACTIVE.value,
            fulfillment_conditions=[],
            subversion_conditions=[],
            interpretation_hints=[],
        )
        db_session.add(prophesy2)
        db_session.flush()

        active = destiny_manager.get_active_prophesies()

        assert len(active) == 2

    def test_get_active_prophesies_excludes_fulfilled(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test that fulfilled prophecies are excluded from active list."""
        sample_prophesy.status = ProphesyStatus.FULFILLED.value

        active = destiny_manager.get_active_prophesies()

        assert len(active) == 0


# --- Prophesy Resolution Tests ---


class TestProphesyResolution:
    """Tests for prophecy fulfillment and subversion."""

    def test_fulfill_prophesy(
        self, destiny_manager: DestinyManager, sample_prophesy: Prophesy
    ):
        """Test fulfilling a prophecy."""
        destiny_manager.fulfill_prophesy(
            prophesy_key="dragon_doom",
            description="The dragon awakened during the blood moon and devastated the kingdom.",
        )

        prophesy = destiny_manager.get_prophesy("dragon_doom")
        assert prophesy.status == ProphesyStatus.FULFILLED.value
        assert prophesy.resolution_description is not None
        assert prophesy.fulfilled_turn is not None

    def test_subvert_prophesy(
        self, destiny_manager: DestinyManager, sample_prophesy: Prophesy
    ):
        """Test subverting a prophecy."""
        destiny_manager.subvert_prophesy(
            prophesy_key="dragon_doom",
            description="The heroes sealed the dragon's cave before the eclipse.",
        )

        prophesy = destiny_manager.get_prophesy("dragon_doom")
        assert prophesy.status == ProphesyStatus.SUBVERTED.value
        assert "sealed" in prophesy.resolution_description

    def test_abandon_prophesy(
        self, destiny_manager: DestinyManager, sample_prophesy: Prophesy
    ):
        """Test abandoning a prophecy."""
        destiny_manager.abandon_prophesy("dragon_doom")

        prophesy = destiny_manager.get_prophesy("dragon_doom")
        assert prophesy.status == ProphesyStatus.ABANDONED.value


# --- Destiny Element Tests ---


class TestDestinyElements:
    """Tests for destiny element management."""

    def test_add_destiny_element(self, destiny_manager: DestinyManager):
        """Test adding a destiny element."""
        element = destiny_manager.add_destiny_element(
            element_key="red_comet",
            element_type=DestinyElementType.OMEN,
            description="A red comet streaks across the night sky.",
            witnessed_by=["hero_chosen_one"],
            significance=4,
        )

        assert element.element_key == "red_comet"
        assert element.element_type == DestinyElementType.OMEN.value
        assert element.significance == 4

    def test_add_destiny_element_linked_to_prophesy(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test adding an element linked to a prophecy."""
        element = destiny_manager.add_destiny_element(
            element_key="moon_reddening",
            element_type=DestinyElementType.SIGN,
            description="The moon takes on a reddish hue.",
            prophesy_key="dragon_doom",
            significance=5,
        )

        assert element.prophesy_id == sample_prophesy.id

    def test_get_destiny_element(
        self,
        destiny_manager: DestinyManager,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test retrieving a destiny element."""
        element = DestinyElement(
            session_id=game_session.id,
            element_key="dark_omen",
            element_type=DestinyElementType.OMEN.value,
            description="A crow caws three times.",
            witnessed_by=[],
            turn_occurred=1,
            significance=2,
        )
        db_session.add(element)
        db_session.flush()

        retrieved = destiny_manager.get_destiny_element("dark_omen")

        assert retrieved is not None
        assert retrieved.significance == 2

    def test_get_elements_for_prophesy(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test getting all elements linked to a prophecy."""
        # Add two elements linked to the prophecy
        destiny_manager.add_destiny_element(
            element_key="element_1",
            element_type=DestinyElementType.SIGN,
            description="First sign",
            prophesy_key="dragon_doom",
        )
        destiny_manager.add_destiny_element(
            element_key="element_2",
            element_type=DestinyElementType.PORTENT,
            description="Major portent",
            prophesy_key="dragon_doom",
        )

        elements = destiny_manager.get_elements_for_prophesy("dragon_doom")

        assert len(elements) == 2

    def test_mark_element_noticed(
        self,
        destiny_manager: DestinyManager,
    ):
        """Test marking an element as noticed by player."""
        element = destiny_manager.add_destiny_element(
            element_key="subtle_sign",
            element_type=DestinyElementType.SIGN,
            description="A subtle sign.",
        )

        assert element.player_noticed is False

        destiny_manager.mark_element_noticed("subtle_sign")

        element = destiny_manager.get_destiny_element("subtle_sign")
        assert element.player_noticed is True

    def test_get_elements_by_type(
        self,
        destiny_manager: DestinyManager,
    ):
        """Test getting elements filtered by type."""
        destiny_manager.add_destiny_element(
            element_key="omen_1",
            element_type=DestinyElementType.OMEN,
            description="An omen.",
        )
        destiny_manager.add_destiny_element(
            element_key="vision_1",
            element_type=DestinyElementType.VISION,
            description="A vision.",
        )
        destiny_manager.add_destiny_element(
            element_key="omen_2",
            element_type=DestinyElementType.OMEN,
            description="Another omen.",
        )

        omens = destiny_manager.get_elements_by_type(DestinyElementType.OMEN)
        visions = destiny_manager.get_elements_by_type(DestinyElementType.VISION)

        assert len(omens) == 2
        assert len(visions) == 1

    def test_get_unnoticed_elements(
        self,
        destiny_manager: DestinyManager,
    ):
        """Test getting elements that player hasn't noticed yet."""
        destiny_manager.add_destiny_element(
            element_key="noticed_omen",
            element_type=DestinyElementType.OMEN,
            description="Noticed.",
        )
        destiny_manager.add_destiny_element(
            element_key="hidden_sign",
            element_type=DestinyElementType.SIGN,
            description="Hidden.",
        )
        destiny_manager.mark_element_noticed("noticed_omen")

        unnoticed = destiny_manager.get_unnoticed_elements()

        assert len(unnoticed) == 1
        assert unnoticed[0].element_key == "hidden_sign"


# --- Prophesy Progress Tests ---


class TestProphesyProgress:
    """Tests for tracking prophecy progress."""

    def test_check_prophesy_progress(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test checking progress of a prophecy."""
        # Add some elements
        destiny_manager.add_destiny_element(
            element_key="sign_1",
            element_type=DestinyElementType.SIGN,
            description="First sign",
            prophesy_key="dragon_doom",
        )

        progress = destiny_manager.check_prophesy_progress("dragon_doom")

        assert isinstance(progress, ProphesyProgress)
        assert progress.prophesy_key == "dragon_doom"
        assert progress.status == ProphesyStatus.ACTIVE.value
        assert progress.conditions_total == 3
        assert len(progress.elements_manifested) == 1

    def test_check_prophesy_progress_with_hints(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test that progress includes available hints."""
        progress = destiny_manager.check_prophesy_progress("dragon_doom")

        assert len(progress.hints_available) == 2

    def test_mark_condition_met(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test marking a fulfillment condition as met."""
        destiny_manager.mark_condition_met("dragon_doom", "lunar_eclipse_occurs")

        progress = destiny_manager.check_prophesy_progress("dragon_doom")
        assert progress.conditions_met == 1

    def test_mark_multiple_conditions_met(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test marking multiple conditions as met."""
        destiny_manager.mark_condition_met("dragon_doom", "lunar_eclipse_occurs")
        destiny_manager.mark_condition_met("dragon_doom", "dragon_awakens")

        progress = destiny_manager.check_prophesy_progress("dragon_doom")
        assert progress.conditions_met == 2

    def test_add_interpretation_hint(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test adding a new interpretation hint."""
        destiny_manager.add_interpretation_hint(
            "dragon_doom",
            "The cave entrance is hidden by illusion magic",
        )

        progress = destiny_manager.check_prophesy_progress("dragon_doom")
        assert len(progress.hints_available) == 3


# --- Context Generation Tests ---


class TestDestinyContext:
    """Tests for destiny context generation."""

    def test_get_destiny_context(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test generating destiny context for GM prompts."""
        destiny_manager.add_destiny_element(
            element_key="omen_1",
            element_type=DestinyElementType.OMEN,
            description="An ominous sign.",
            prophesy_key="dragon_doom",
            significance=4,
        )

        context = destiny_manager.get_destiny_context()

        assert "dragon_doom" in context.lower() or "prophecy" in context.lower()
        assert "omen" in context.lower()

    def test_get_destiny_context_no_prophesies(
        self,
        destiny_manager: DestinyManager,
    ):
        """Test context with no active prophecies."""
        context = destiny_manager.get_destiny_context()
        assert context == ""

    def test_get_destiny_context_includes_progress(
        self,
        destiny_manager: DestinyManager,
        sample_prophesy: Prophesy,
    ):
        """Test that context includes prophecy progress info."""
        destiny_manager.mark_condition_met("dragon_doom", "lunar_eclipse_occurs")

        context = destiny_manager.get_destiny_context()

        # Should mention progress
        assert "1" in context  # At least one condition met


# --- Session Isolation Tests ---


class TestSessionIsolation:
    """Tests for session isolation."""

    def test_prophesies_isolated_by_session(
        self,
        db_session: Session,
        game_session: GameSession,
        game_session_2: GameSession,
    ):
        """Test that prophecies are isolated between sessions."""
        manager1 = DestinyManager(db=db_session, game_session=game_session)
        manager2 = DestinyManager(db=db_session, game_session=game_session_2)

        manager1.create_prophesy(
            prophesy_key="unique_prophesy",
            prophesy_text="Session 1 prophecy.",
            true_meaning="Hidden.",
            source="oracle",
            fulfillment_conditions=[],
        )

        # Should not be visible in session 2
        prophesy = manager2.get_prophesy("unique_prophesy")
        assert prophesy is None

    def test_elements_isolated_by_session(
        self,
        db_session: Session,
        game_session: GameSession,
        game_session_2: GameSession,
    ):
        """Test that destiny elements are isolated between sessions."""
        manager1 = DestinyManager(db=db_session, game_session=game_session)
        manager2 = DestinyManager(db=db_session, game_session=game_session_2)

        manager1.add_destiny_element(
            element_key="session1_omen",
            element_type=DestinyElementType.OMEN,
            description="Session 1 omen.",
        )

        # Should not be visible in session 2
        element = manager2.get_destiny_element("session1_omen")
        assert element is None


# --- Recent Elements Tests ---


class TestRecentElements:
    """Tests for retrieving recent destiny elements."""

    def test_get_recent_elements(
        self,
        destiny_manager: DestinyManager,
        game_session: GameSession,
    ):
        """Test getting recent elements limited by count."""
        # Create multiple elements at different turns
        game_session.total_turns = 5

        for i in range(5):
            destiny_manager.add_destiny_element(
                element_key=f"element_{i}",
                element_type=DestinyElementType.SIGN,
                description=f"Element {i}",
            )
            game_session.total_turns += 1

        recent = destiny_manager.get_recent_elements(limit=3)

        assert len(recent) == 3

    def test_get_recent_significant_elements(
        self,
        destiny_manager: DestinyManager,
    ):
        """Test getting only significant recent elements."""
        destiny_manager.add_destiny_element(
            element_key="minor_omen",
            element_type=DestinyElementType.OMEN,
            description="Minor.",
            significance=2,
        )
        destiny_manager.add_destiny_element(
            element_key="major_portent",
            element_type=DestinyElementType.PORTENT,
            description="Major.",
            significance=5,
        )

        significant = destiny_manager.get_recent_elements(min_significance=4)

        assert len(significant) == 1
        assert significant[0].element_key == "major_portent"
