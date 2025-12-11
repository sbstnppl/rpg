"""Tests for VoiceManager."""

import pytest

from src.managers.voice_manager import VoiceManager, VoiceTemplate


class TestLoadTemplates:
    """Tests for loading voice templates."""

    def test_load_base_classes(self):
        """Test loading base class templates."""
        manager = VoiceManager()

        assert "noble" in manager.base_classes
        assert "commoner" in manager.base_classes
        assert "merchant" in manager.base_classes
        assert "scholar" in manager.base_classes

    def test_load_occupations(self):
        """Test loading occupation modifiers."""
        manager = VoiceManager()

        assert "soldier" in manager.occupations
        assert "innkeeper" in manager.occupations
        assert "blacksmith" in manager.occupations
        assert "healer" in manager.occupations

    def test_load_personalities(self):
        """Test loading personality modifiers."""
        manager = VoiceManager()

        assert "nervous" in manager.personalities
        assert "confident" in manager.personalities
        assert "friendly" in manager.personalities
        assert "hostile" in manager.personalities

    def test_load_regions(self):
        """Test loading regional dialects."""
        manager = VoiceManager()

        assert "northern" in manager.regions
        assert "southern" in manager.regions
        assert "coastal" in manager.regions


class TestGetBaseTemplate:
    """Tests for getting base class templates."""

    def test_get_noble_template(self):
        """Test getting noble base template."""
        manager = VoiceManager()

        template = manager.get_base_class("noble")

        assert template is not None
        assert template["vocabulary_level"] == "sophisticated"
        assert template["contractions"] == "never"
        assert len(template["greetings"]) > 0

    def test_get_commoner_template(self):
        """Test getting commoner base template."""
        manager = VoiceManager()

        template = manager.get_base_class("commoner")

        assert template is not None
        assert template["vocabulary_level"] == "simple"
        assert template["contractions"] == "frequent"
        assert "Aye" in template["affirmatives"]

    def test_get_unknown_base_class(self):
        """Test getting non-existent base class."""
        manager = VoiceManager()

        template = manager.get_base_class("unknown")

        assert template is None


class TestGetOccupation:
    """Tests for getting occupation modifiers."""

    def test_get_soldier_occupation(self):
        """Test getting soldier occupation modifier."""
        manager = VoiceManager()

        occupation = manager.get_occupation("soldier")

        assert occupation is not None
        assert "orders" in occupation["additional_vocabulary"]
        assert "duty" in occupation["additional_vocabulary"]
        assert len(occupation["occupation_phrases"]) > 0

    def test_get_innkeeper_occupation(self):
        """Test getting innkeeper occupation modifier."""
        manager = VoiceManager()

        occupation = manager.get_occupation("innkeeper")

        assert occupation is not None
        assert "ale" in occupation["additional_vocabulary"]
        assert "weary traveler" in occupation["verbal_tics"]


class TestGetPersonality:
    """Tests for getting personality modifiers."""

    def test_get_nervous_personality(self):
        """Test getting nervous personality modifier."""
        manager = VoiceManager()

        personality = manager.get_personality("nervous")

        assert personality is not None
        assert "um" in personality["verbal_tics"]
        assert personality["speech_modifications"]["pause_frequency"] == "high"

    def test_get_confident_personality(self):
        """Test getting confident personality modifier."""
        manager = VoiceManager()

        personality = manager.get_personality("confident")

        assert personality is not None
        assert "obviously" in personality["verbal_tics"]


class TestGetRegion:
    """Tests for getting regional dialects."""

    def test_get_northern_region(self):
        """Test getting northern regional dialect."""
        manager = VoiceManager()

        region = manager.get_region("northern")

        assert region is not None
        assert region["vocabulary_replacements"]["friend"] == "kinsman"
        assert "By the frost" in region["regional_expressions"]

    def test_get_coastal_region(self):
        """Test getting coastal regional dialect."""
        manager = VoiceManager()

        region = manager.get_region("coastal")

        assert region is not None
        assert region["vocabulary_replacements"]["friend"] == "mate"


class TestBuildVoiceTemplate:
    """Tests for building combined voice templates."""

    def test_build_simple_template(self):
        """Test building template with just base class."""
        manager = VoiceManager()

        template = manager.build_voice_template(base_class="noble")

        assert template is not None
        assert template.base_class == "noble"
        assert template.vocabulary_level == "sophisticated"
        assert len(template.greetings) > 0

    def test_build_template_with_occupation(self):
        """Test building template with base class and occupation."""
        manager = VoiceManager()

        template = manager.build_voice_template(
            base_class="commoner",
            occupation="soldier",
        )

        assert template is not None
        assert template.base_class == "commoner"
        assert template.occupation == "soldier"
        assert "orders" in template.additional_vocabulary
        # Should still have commoner base patterns
        assert template.contractions == "frequent"

    def test_build_template_with_personality(self):
        """Test building template with personality modifier."""
        manager = VoiceManager()

        template = manager.build_voice_template(
            base_class="merchant",
            personality="nervous",
        )

        assert template is not None
        assert template.personality == "nervous"
        assert "um" in template.verbal_tics

    def test_build_template_with_region(self):
        """Test building template with regional dialect."""
        manager = VoiceManager()

        template = manager.build_voice_template(
            base_class="commoner",
            region="northern",
        )

        assert template is not None
        assert template.region == "northern"
        assert "kinsman" in template.vocabulary_replacements.values()

    def test_build_full_template(self):
        """Test building template with all modifiers."""
        manager = VoiceManager()

        template = manager.build_voice_template(
            base_class="noble",
            occupation="soldier",
            personality="confident",
            region="northern",
        )

        assert template is not None
        assert template.base_class == "noble"
        assert template.occupation == "soldier"
        assert template.personality == "confident"
        assert template.region == "northern"

    def test_build_template_unknown_base_returns_none(self):
        """Test that unknown base class returns None."""
        manager = VoiceManager()

        template = manager.build_voice_template(base_class="unknown")

        assert template is None


class TestGetExampleDialogue:
    """Tests for getting example dialogue."""

    def test_get_greeting_example(self):
        """Test getting greeting example dialogue."""
        manager = VoiceManager()

        example = manager.get_example_dialogue("noble", "greeting_stranger")

        assert example is not None
        assert len(example) > 0

    def test_get_occupation_phrase(self):
        """Test getting occupation-specific phrase."""
        manager = VoiceManager()

        phrase = manager.get_occupation_phrase("soldier", "warning")

        assert phrase is not None
        assert "warning" in phrase.lower() or "won't be" in phrase.lower()


class TestGetVoiceContext:
    """Tests for generating voice context for GM."""

    def test_get_voice_context_basic(self):
        """Test generating basic voice context."""
        manager = VoiceManager()

        context = manager.get_voice_context(base_class="noble")

        assert len(context) > 0
        assert "noble" in context.lower()
        assert "vocabulary" in context.lower() or "sophisticated" in context.lower()

    def test_get_voice_context_full(self):
        """Test generating full voice context with all modifiers."""
        manager = VoiceManager()

        context = manager.get_voice_context(
            base_class="commoner",
            occupation="innkeeper",
            personality="friendly",
            region="southern",
        )

        assert len(context) > 0
        assert "commoner" in context.lower()
        assert "innkeeper" in context.lower()
        assert "friendly" in context.lower()
        assert "southern" in context.lower()

    def test_get_voice_context_includes_examples(self):
        """Test that voice context includes example dialogue."""
        manager = VoiceManager()

        context = manager.get_voice_context(
            base_class="merchant",
            include_examples=True,
        )

        assert "example" in context.lower() or "dialogue" in context.lower()


class TestVoiceTemplateDataclass:
    """Tests for VoiceTemplate dataclass."""

    def test_voice_template_has_all_fields(self):
        """Test that VoiceTemplate has all expected fields."""
        manager = VoiceManager()

        template = manager.build_voice_template(
            base_class="noble",
            occupation="soldier",
            personality="confident",
            region="northern",
        )

        assert hasattr(template, "base_class")
        assert hasattr(template, "occupation")
        assert hasattr(template, "personality")
        assert hasattr(template, "region")
        assert hasattr(template, "vocabulary_level")
        assert hasattr(template, "sentence_structure")
        assert hasattr(template, "contractions")
        assert hasattr(template, "greetings")
        assert hasattr(template, "farewells")
        assert hasattr(template, "speech_patterns")
        assert hasattr(template, "verbal_tics")
        assert hasattr(template, "additional_vocabulary")
        assert hasattr(template, "vocabulary_replacements")
