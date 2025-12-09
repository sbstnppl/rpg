"""Tests for SceneInterpreter service."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.character_memory import CharacterMemory
from src.database.models.enums import EmotionalValence, MemoryType
from src.services.scene_interpreter import (
    ReactionType,
    SceneInterpreter,
    SceneReaction,
)
from tests.factories import (
    create_character_memory,
    create_character_needs,
    create_entity,
    create_entity_skill,
    create_game_session,
    create_item,
)


class TestSceneInterpreterNeedStimuli:
    """Tests for need-based stimulus detection."""

    def test_hunger_stimulus_from_food_keywords(
        self, db_session: Session, game_session
    ) -> None:
        """Test hunger craving triggered by food-related words."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, hunger=30)

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A delicious roast chicken sits on the plate, surrounded by fresh bread and cheese.",
            character_needs=needs,
        )

        # Should detect hunger stimulus
        hunger_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.CRAVING and r.need_affected == "hunger"
        ]
        assert len(hunger_reactions) == 1
        assert hunger_reactions[0].craving_boost > 0
        assert "appetite" in hunger_reactions[0].narrative_hint.lower()

    def test_thirst_stimulus_from_drink_keywords(
        self, db_session: Session, game_session
    ) -> None:
        """Test thirst craving triggered by drink-related words."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, thirst=25)

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="The tavern keeper pours a cold ale from a large tankard.",
            character_needs=needs,
        )

        thirst_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.CRAVING and r.need_affected == "thirst"
        ]
        assert len(thirst_reactions) == 1
        assert thirst_reactions[0].craving_boost > 0

    def test_energy_stimulus_from_rest_keywords(
        self, db_session: Session, game_session
    ) -> None:
        """Test energy craving triggered by rest-related words."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, energy=20)

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A comfortable bed with soft pillows awaits in the cozy bedroom.",
            character_needs=needs,
        )

        energy_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.CRAVING and r.need_affected == "energy"
        ]
        assert len(energy_reactions) == 1
        assert energy_reactions[0].craving_boost > 0
        assert "fatigue" in energy_reactions[0].narrative_hint.lower()

    def test_social_stimulus_from_gathering(
        self, db_session: Session, game_session
    ) -> None:
        """Test social craving triggered by social atmosphere."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session, game_session, entity, social_connection=15
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A lively celebration with friends and family fills the hall with laughter.",
            character_needs=needs,
        )

        social_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.CRAVING
            and r.need_affected == "social_connection"
        ]
        assert len(social_reactions) == 1
        assert social_reactions[0].craving_boost > 0

    def test_intimacy_stimulus_from_romantic_scene(
        self, db_session: Session, game_session
    ) -> None:
        """Test intimacy craving triggered by romantic atmosphere."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, intimacy=20)

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A beautiful woman gives you a seductive smile, her alluring charm undeniable.",
            character_needs=needs,
        )

        intimacy_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.CRAVING and r.need_affected == "intimacy"
        ]
        assert len(intimacy_reactions) == 1
        assert intimacy_reactions[0].craving_boost > 0

    def test_no_craving_when_need_is_high(
        self, db_session: Session, game_session
    ) -> None:
        """Test that well-fed character doesn't crave food."""
        entity = create_entity(db_session, game_session)
        # High hunger value = well fed, low craving potential
        needs = create_character_needs(db_session, game_session, entity, hunger=95)

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A delicious feast is spread across the table.",
            character_needs=needs,
        )

        # Craving boost should be minimal (below threshold)
        hunger_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.CRAVING and r.need_affected == "hunger"
        ]
        assert len(hunger_reactions) == 0

    def test_craving_boost_calculation(
        self, db_session: Session, game_session
    ) -> None:
        """Test that craving boost increases with lower need."""
        # Create two separate entities for the comparison
        entity_hungry = create_entity(db_session, game_session, entity_key="hungry_char")
        entity_medium = create_entity(db_session, game_session, entity_key="medium_char")

        interpreter = SceneInterpreter(db_session, game_session)

        # Test with hungry character (low hunger)
        needs_hungry = create_character_needs(
            db_session, game_session, entity_hungry, hunger=10
        )
        reactions_hungry = interpreter.analyze_scene(
            scene_description="Fresh bread and cheese on the table.",
            character_needs=needs_hungry,
        )

        # Test with satisfied character (medium hunger)
        needs_medium = create_character_needs(
            db_session, game_session, entity_medium, hunger=50
        )
        reactions_medium = interpreter.analyze_scene(
            scene_description="Fresh bread and cheese on the table.",
            character_needs=needs_medium,
        )

        hungry_boost = next(
            (r.craving_boost for r in reactions_hungry if r.need_affected == "hunger"),
            0
        )
        medium_boost = next(
            (r.craving_boost for r in reactions_medium if r.need_affected == "hunger"),
            0
        )

        # Hungry character should have higher craving boost
        assert hungry_boost > medium_boost

    def test_multiple_stimuli_in_scene(
        self, db_session: Session, game_session
    ) -> None:
        """Test detecting multiple need stimuli in same scene."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session, game_session, entity,
            hunger=20,
            thirst=20,
            energy=20,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="The tavern offers ale, roast meat, and a comfortable bed upstairs.",
            character_needs=needs,
        )

        # Should detect all three stimuli
        needs_affected = {r.need_affected for r in reactions if r.need_affected}
        assert "hunger" in needs_affected
        assert "thirst" in needs_affected
        assert "energy" in needs_affected


class TestSceneInterpreterMemoryTriggers:
    """Tests for memory trigger detection."""

    def test_negative_memory_triggered(
        self, db_session: Session, game_session
    ) -> None:
        """Test negative memory (grief) triggered by matching item."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="mother's hat",
            keywords=["hat", "wide-brimmed", "straw"],
            valence=EmotionalValence.NEGATIVE,
            emotion="grief",
            intensity=8,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A wide-brimmed straw hat hangs on a hook by the door.",
            character=entity,
            character_memories=[memory],
        )

        memory_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.MEMORY_NEGATIVE
        ]
        assert len(memory_reactions) == 1
        assert memory_reactions[0].memory_id == memory.id
        assert memory_reactions[0].emotion == "grief"
        assert memory_reactions[0].morale_change < 0  # Negative morale impact
        assert "mother's hat" in memory_reactions[0].narrative_hint

    def test_positive_memory_triggered(
        self, db_session: Session, game_session
    ) -> None:
        """Test positive memory triggered by matching item."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="grandmother's cookies",
            keywords=["cookie", "chocolate", "baking"],
            valence=EmotionalValence.POSITIVE,
            emotion="nostalgia",
            intensity=6,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="The smell of fresh-baked chocolate cookies fills the air.",
            character=entity,
            character_memories=[memory],
        )

        memory_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.MEMORY_POSITIVE
        ]
        assert len(memory_reactions) == 1
        assert memory_reactions[0].morale_change > 0  # Positive morale impact
        assert "fond memories" in memory_reactions[0].narrative_hint.lower()

    def test_mixed_memory_triggered(
        self, db_session: Session, game_session
    ) -> None:
        """Test mixed/bittersweet memory triggered."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="childhood home",
            keywords=["cottage", "garden", "village"],
            valence=EmotionalValence.MIXED,
            emotion="bittersweet",
            intensity=7,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A small cottage with a flower garden sits in the village square.",
            character=entity,
            character_memories=[memory],
        )

        memory_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.MEMORY_MIXED
        ]
        assert len(memory_reactions) == 1
        assert memory_reactions[0].morale_change == 0  # Mixed feelings cancel out
        assert "complex feelings" in memory_reactions[0].narrative_hint.lower()

    def test_trauma_causes_stat_penalty(
        self, db_session: Session, game_session
    ) -> None:
        """Test intense trauma causes WIS penalty."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="house fire",
            keywords=["fire", "flames", "burning"],
            valence=EmotionalValence.NEGATIVE,
            emotion="terror",
            intensity=9,  # High intensity trauma
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="Flames leap from the burning building, smoke filling the air.",
            character=entity,
            character_memories=[memory],
        )

        memory_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.MEMORY_NEGATIVE
        ]
        assert len(memory_reactions) == 1
        assert memory_reactions[0].stat_effects.get("WIS") == -1

    def test_memory_not_triggered_without_keywords(
        self, db_session: Session, game_session
    ) -> None:
        """Test memory is not triggered when keywords don't match."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="mother's hat",
            keywords=["hat", "wide-brimmed", "straw"],
            valence=EmotionalValence.NEGATIVE,
            emotion="grief",
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A sword and shield hang on the wall.",
            character=entity,
            character_memories=[memory],
        )

        memory_reactions = [
            r for r in reactions
            if r.memory_id is not None
        ]
        assert len(memory_reactions) == 0

    def test_memory_trigger_recorded(
        self, db_session: Session, game_session
    ) -> None:
        """Test that memory trigger is recorded in database."""
        entity = create_entity(db_session, game_session)
        memory = create_character_memory(
            db_session,
            game_session,
            entity,
            subject="mother's hat",
            keywords=["hat", "wide-brimmed", "straw"],
            valence=EmotionalValence.NEGATIVE,
        )

        initial_count = memory.trigger_count

        interpreter = SceneInterpreter(db_session, game_session)
        interpreter.analyze_scene(
            scene_description="A wide-brimmed straw hat hangs on the wall.",
            character=entity,
            character_memories=[memory],
        )

        db_session.refresh(memory)
        assert memory.trigger_count == initial_count + 1


class TestSceneInterpreterProfessionalInterest:
    """Tests for professional interest detection."""

    def test_fisherman_notices_fishing_gear(
        self, db_session: Session, game_session
    ) -> None:
        """Test fisherman notices fishing-related items."""
        entity = create_entity(db_session, game_session)
        fishing_skill = create_entity_skill(
            db_session, entity,
            skill_key="fishing",
            proficiency_level=5,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A fine fishing rod with a quality reel and fresh bait sits by the dock.",
            character_skills=[fishing_skill],
        )

        professional_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.PROFESSIONAL_INTEREST
        ]
        assert len(professional_reactions) == 1
        assert professional_reactions[0].skill_key == "fishing"
        assert professional_reactions[0].morale_change > 0
        assert "skilled" in professional_reactions[0].narrative_hint.lower()

    def test_blacksmith_notices_forge(
        self, db_session: Session, game_session
    ) -> None:
        """Test blacksmith notices metalworking items."""
        entity = create_entity(db_session, game_session)
        smithing_skill = create_entity_skill(
            db_session, entity,
            skill_key="blacksmithing",
            proficiency_level=4,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="The forge glows hot, an anvil and hammer ready for the smith.",
            character_skills=[smithing_skill],
        )

        professional_reactions = [
            r for r in reactions
            if r.reaction_type == ReactionType.PROFESSIONAL_INTEREST
        ]
        assert len(professional_reactions) == 1
        assert professional_reactions[0].skill_key == "blacksmithing"

    def test_no_professional_interest_without_skill(
        self, db_session: Session, game_session
    ) -> None:
        """Test no professional interest when character lacks skill."""
        entity = create_entity(db_session, game_session)
        # No fishing skill
        cooking_skill = create_entity_skill(
            db_session, entity,
            skill_key="cooking",
            proficiency_level=3,
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A fine fishing rod sits by the dock.",
            character_skills=[cooking_skill],
        )

        fishing_reactions = [
            r for r in reactions
            if r.skill_key == "fishing"
        ]
        assert len(fishing_reactions) == 0

    def test_higher_proficiency_more_excitement(
        self, db_session: Session, game_session
    ) -> None:
        """Test higher skill proficiency creates stronger reaction."""
        # Create separate entities for each skill level to avoid duplicate skills
        entity_low = create_entity(db_session, game_session, entity_key="smith_low")
        entity_high = create_entity(db_session, game_session, entity_key="smith_high")

        scene = "The forge glows hot, an anvil and hammer ready for the smith."

        # Low proficiency
        low_skill = create_entity_skill(
            db_session, entity_low,
            skill_key="blacksmithing",
            proficiency_level=1,
        )
        interpreter = SceneInterpreter(db_session, game_session)
        reactions_low = interpreter.analyze_scene(
            scene_description=scene,
            character_skills=[low_skill],
        )
        low_intensity = next(
            (r.intensity for r in reactions_low
             if r.reaction_type == ReactionType.PROFESSIONAL_INTEREST),
            0
        )

        # High proficiency
        high_skill = create_entity_skill(
            db_session, entity_high,
            skill_key="blacksmithing",
            proficiency_level=7,
        )
        reactions_high = interpreter.analyze_scene(
            scene_description=scene,
            character_skills=[high_skill],
        )
        high_intensity = next(
            (r.intensity for r in reactions_high
             if r.reaction_type == ReactionType.PROFESSIONAL_INTEREST),
            0
        )

        assert high_intensity > low_intensity


class TestSceneInterpreterAnalysis:
    """Tests for overall scene analysis functionality."""

    def test_analyze_empty_scene(
        self, db_session: Session, game_session
    ) -> None:
        """Test analyzing scene with no triggers."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session, game_session, entity,
            hunger=80,  # Not hungry
            thirst=80,  # Not thirsty
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="You stand in an empty stone corridor.",
            character_needs=needs,
        )

        assert len(reactions) == 0

    def test_reactions_sorted_by_intensity(
        self, db_session: Session, game_session
    ) -> None:
        """Test that reactions are sorted by intensity/importance."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(
            db_session, game_session, entity,
            hunger=10,  # Very hungry
            thirst=60,  # Slightly thirsty
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A large feast of food and drink awaits.",
            character_needs=needs,
        )

        if len(reactions) >= 2:
            # Most intense reaction should be first
            assert reactions[0].intensity >= reactions[-1].intensity

    def test_items_included_in_analysis(
        self, db_session: Session, game_session
    ) -> None:
        """Test that item descriptions are analyzed."""
        entity = create_entity(db_session, game_session)
        needs = create_character_needs(db_session, game_session, entity, hunger=20)

        item = create_item(
            db_session, game_session,
            item_key="roast_chicken",
            display_name="Roast Chicken",
            description="A delicious herb-roasted chicken."
        )

        interpreter = SceneInterpreter(db_session, game_session)
        reactions = interpreter.analyze_scene(
            scene_description="A plate sits on the table.",
            scene_items=[item],
            character_needs=needs,
        )

        # Should trigger hunger from item description
        hunger_reactions = [
            r for r in reactions
            if r.need_affected == "hunger"
        ]
        assert len(hunger_reactions) == 1

    def test_get_reactions_summary_empty(
        self, db_session: Session, game_session
    ) -> None:
        """Test reactions summary with no reactions."""
        interpreter = SceneInterpreter(db_session, game_session)
        summary = interpreter.get_reactions_summary([])

        assert summary["has_reactions"] is False
        assert summary["total_reactions"] == 0
        assert summary["narrative_hints"] == []

    def test_get_reactions_summary_with_reactions(
        self, db_session: Session, game_session
    ) -> None:
        """Test reactions summary aggregation."""
        reactions = [
            SceneReaction(
                trigger="food",
                reaction_type=ReactionType.CRAVING,
                need_affected="hunger",
                craving_boost=20,
                morale_change=0,
                narrative_hint="Food hint",
            ),
            SceneReaction(
                trigger="memory",
                reaction_type=ReactionType.MEMORY_NEGATIVE,
                memory_id=1,
                morale_change=-10,
                intensity=7,
                narrative_hint="Memory hint",
            ),
        ]

        interpreter = SceneInterpreter(db_session, game_session)
        summary = interpreter.get_reactions_summary(reactions)

        assert summary["has_reactions"] is True
        assert summary["total_reactions"] == 2
        assert summary["by_type"]["craving"] == 1
        assert summary["by_type"]["memory_negative"] == 1
        assert summary["total_morale_change"] == -10
        assert summary["cravings_to_apply"]["hunger"] == 20
        assert len(summary["narrative_hints"]) == 2


class TestSceneInterpreterHelpers:
    """Tests for helper methods."""

    def test_count_keyword_matches(
        self, db_session: Session, game_session
    ) -> None:
        """Test keyword counting."""
        interpreter = SceneInterpreter(db_session, game_session)

        text = "a delicious roast chicken with bread"
        count = interpreter._count_keyword_matches(text, {"chicken", "bread", "soup"})

        assert count == 2

    def test_calculate_craving_boost_caps_at_50(
        self, db_session: Session, game_session
    ) -> None:
        """Test craving boost is capped at 50."""
        interpreter = SceneInterpreter(db_session, game_session)

        # Maximum possible inputs
        boost = interpreter._calculate_craving_boost(
            base_craving=100,  # Very hungry
            relevance=1.0,
            attention=1.0,
        )

        assert boost <= 50

    def test_calculate_craving_boost_scales_with_inputs(
        self, db_session: Session, game_session
    ) -> None:
        """Test craving boost scales properly."""
        interpreter = SceneInterpreter(db_session, game_session)

        low = interpreter._calculate_craving_boost(30, 0.3)
        high = interpreter._calculate_craving_boost(90, 1.0)

        assert high > low

    def test_build_analysis_text_combines_sources(
        self, db_session: Session, game_session
    ) -> None:
        """Test text building from multiple sources."""
        entity = create_entity(
            db_session, game_session,
            display_name="Guard",
            distinguishing_features="A stern-looking veteran with a scar"
        )
        item = create_item(
            db_session, game_session,
            display_name="Sword",
            description="A sharp blade"
        )

        interpreter = SceneInterpreter(db_session, game_session)
        text = interpreter._build_analysis_text(
            "You enter the room.",
            [item],
            [entity],
        )

        assert "you enter the room" in text
        assert "sword" in text
        assert "sharp blade" in text
        assert "guard" in text
        assert "stern-looking veteran" in text

    def test_get_craving_hint_intensity_wording(
        self, db_session: Session, game_session
    ) -> None:
        """Test craving hints have appropriate intensity wording."""
        interpreter = SceneInterpreter(db_session, game_session)

        mild = interpreter._get_craving_hint("hunger", 10)
        moderate = interpreter._get_craving_hint("hunger", 20)
        strong = interpreter._get_craving_hint("hunger", 35)

        assert "slightly" in mild
        assert "noticeably" in moderate
        assert "strongly" in strong

    def test_get_memory_hint_valence_phrases(
        self, db_session: Session, game_session
    ) -> None:
        """Test memory hints have appropriate valence phrases."""
        entity = create_entity(db_session, game_session)

        # Test positive
        pos_memory = create_character_memory(
            db_session, game_session, entity,
            subject="happy place",
            valence=EmotionalValence.POSITIVE,
            context="Good times",
        )
        interpreter = SceneInterpreter(db_session, game_session)
        pos_hint = interpreter._get_memory_hint(pos_memory)
        assert "fond memories" in pos_hint.lower()

        # Test negative
        neg_memory = create_character_memory(
            db_session, game_session, entity,
            subject="bad place",
            valence=EmotionalValence.NEGATIVE,
            context="Bad times",
        )
        neg_hint = interpreter._get_memory_hint(neg_memory)
        assert "painfully" in neg_hint.lower()
