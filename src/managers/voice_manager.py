"""NPC voice template manager.

Manages voice templates that define speech patterns for NPCs.
Supports both LLM-generated voices and YAML-based example templates.

The LLM generates unique, setting-appropriate voices based on NPC
characteristics, using YAML templates as few-shot examples.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from src.agents.schemas.voice_generation import GeneratedVoiceTemplate
from src.database.models.session import GameSession
from src.llm.factory import get_cheap_provider
from src.llm.message_types import Message


@dataclass
class VoiceTemplate:
    """Combined voice template for an NPC.

    Merges base class, occupation, personality, and regional modifiers
    into a single coherent voice guide.
    """

    # Source identifiers
    base_class: str
    occupation: str | None = None
    personality: str | None = None
    region: str | None = None

    # Base characteristics
    vocabulary_level: str = "moderate"
    sentence_structure: str = "moderate"
    contractions: str = "occasional"
    swearing_style: str = "mild"

    # Phrase collections
    greetings: list[str] = field(default_factory=list)
    farewells: list[str] = field(default_factory=list)
    affirmatives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    filler_words: list[str] = field(default_factory=list)
    swear_examples: list[str] = field(default_factory=list)

    # Patterns and modifications
    speech_patterns: list[str] = field(default_factory=list)
    verbal_tics: list[str] = field(default_factory=list)
    additional_vocabulary: list[str] = field(default_factory=list)
    vocabulary_replacements: dict[str, str] = field(default_factory=dict)
    regional_expressions: list[str] = field(default_factory=list)

    # Example dialogue
    example_dialogue: dict[str, str] = field(default_factory=dict)
    occupation_phrases: dict[str, str] = field(default_factory=dict)

    # Speech modifications from personality
    speech_modifications: dict[str, Any] = field(default_factory=dict)


class VoiceManager:
    """Manages NPC voice templates.

    Loads YAML configuration files and provides methods to build
    combined voice templates for NPCs with various characteristics.
    """

    def __init__(self, templates_path: str | None = None):
        """Initialize the voice manager.

        Args:
            templates_path: Path to voice templates directory.
                           Defaults to data/templates/voices/.
        """
        if templates_path is None:
            # Default to project's data/templates/voices directory
            project_root = Path(__file__).parent.parent.parent
            templates_path = str(project_root / "data" / "templates" / "voices")

        self.templates_path = templates_path
        self.base_classes: dict[str, dict] = {}
        self.occupations: dict[str, dict] = {}
        self.personalities: dict[str, dict] = {}
        self.regions: dict[str, dict] = {}

        self._load_templates()

    def _load_templates(self) -> None:
        """Load all voice templates from YAML files."""
        templates_dir = Path(self.templates_path)

        if not templates_dir.exists():
            return

        # Load base classes
        base_path = templates_dir / "base_classes.yaml"
        if base_path.exists():
            with open(base_path) as f:
                self.base_classes = yaml.safe_load(f) or {}

        # Load occupations
        occupations_path = templates_dir / "occupations.yaml"
        if occupations_path.exists():
            with open(occupations_path) as f:
                self.occupations = yaml.safe_load(f) or {}

        # Load personalities
        personalities_path = templates_dir / "personalities.yaml"
        if personalities_path.exists():
            with open(personalities_path) as f:
                self.personalities = yaml.safe_load(f) or {}

        # Load regions
        regions_path = templates_dir / "regions.yaml"
        if regions_path.exists():
            with open(regions_path) as f:
                self.regions = yaml.safe_load(f) or {}

    def get_base_class(self, class_name: str) -> dict | None:
        """Get a base class template.

        Args:
            class_name: Name of the base class (noble, commoner, etc.).

        Returns:
            Template dictionary or None if not found.
        """
        return self.base_classes.get(class_name)

    def get_occupation(self, occupation_name: str) -> dict | None:
        """Get an occupation modifier.

        Args:
            occupation_name: Name of the occupation.

        Returns:
            Occupation modifier dictionary or None if not found.
        """
        return self.occupations.get(occupation_name)

    def get_personality(self, personality_name: str) -> dict | None:
        """Get a personality modifier.

        Args:
            personality_name: Name of the personality.

        Returns:
            Personality modifier dictionary or None if not found.
        """
        return self.personalities.get(personality_name)

    def get_region(self, region_name: str) -> dict | None:
        """Get a regional dialect.

        Args:
            region_name: Name of the region.

        Returns:
            Regional dialect dictionary or None if not found.
        """
        return self.regions.get(region_name)

    def build_voice_template(
        self,
        base_class: str,
        occupation: str | None = None,
        personality: str | None = None,
        region: str | None = None,
    ) -> VoiceTemplate | None:
        """Build a combined voice template.

        Merges base class with optional occupation, personality,
        and regional modifiers.

        Args:
            base_class: Base social class (noble, commoner, etc.).
            occupation: Optional occupation modifier.
            personality: Optional personality modifier.
            region: Optional regional dialect.

        Returns:
            VoiceTemplate or None if base class not found.
        """
        base = self.get_base_class(base_class)
        if not base:
            return None

        template = VoiceTemplate(
            base_class=base_class,
            occupation=occupation,
            personality=personality,
            region=region,
            # Base characteristics
            vocabulary_level=base.get("vocabulary_level", "moderate"),
            sentence_structure=base.get("sentence_structure", "moderate"),
            contractions=base.get("contractions", "occasional"),
            swearing_style=base.get("swearing_style", "mild"),
            # Phrase collections
            greetings=list(base.get("greetings", [])),
            farewells=list(base.get("farewells", [])),
            affirmatives=list(base.get("affirmatives", [])),
            negatives=list(base.get("negatives", [])),
            filler_words=list(base.get("filler_words", [])),
            swear_examples=list(base.get("swear_examples", [])),
            # Patterns
            speech_patterns=list(base.get("speech_patterns", [])),
            verbal_tics=[],
            additional_vocabulary=[],
            vocabulary_replacements={},
            regional_expressions=[],
            # Example dialogue
            example_dialogue=dict(base.get("example_dialogue", {})),
            occupation_phrases={},
            speech_modifications={},
        )

        # Apply occupation modifier
        if occupation:
            occ_data = self.get_occupation(occupation)
            if occ_data:
                template.additional_vocabulary.extend(occ_data.get("additional_vocabulary", []))
                template.verbal_tics.extend(occ_data.get("verbal_tics", []))
                template.speech_patterns.extend(occ_data.get("speech_patterns", []))
                template.occupation_phrases = dict(occ_data.get("occupation_phrases", {}))

        # Apply personality modifier
        if personality:
            pers_data = self.get_personality(personality)
            if pers_data:
                template.verbal_tics.extend(pers_data.get("verbal_tics", []))
                template.speech_patterns.extend(pers_data.get("speech_patterns", []))
                template.speech_modifications = dict(pers_data.get("speech_modifications", {}))
                # Merge example dialogue (personality examples can override)
                for key, value in pers_data.get("example_dialogue", {}).items():
                    template.example_dialogue[f"personality_{key}"] = value

        # Apply regional dialect
        if region:
            reg_data = self.get_region(region)
            if reg_data:
                template.vocabulary_replacements = dict(reg_data.get("vocabulary_replacements", {}))
                template.regional_expressions = list(reg_data.get("regional_expressions", []))

        return template

    def get_example_dialogue(
        self,
        base_class: str,
        situation: str,
    ) -> str | None:
        """Get example dialogue for a situation.

        Args:
            base_class: Base social class.
            situation: Situation key (greeting_stranger, refusing_request, etc.).

        Returns:
            Example dialogue string or None.
        """
        base = self.get_base_class(base_class)
        if not base:
            return None

        examples = base.get("example_dialogue", {})
        return examples.get(situation)

    def get_occupation_phrase(
        self,
        occupation: str,
        situation: str,
    ) -> str | None:
        """Get occupation-specific phrase.

        Args:
            occupation: Occupation name.
            situation: Situation key.

        Returns:
            Occupation phrase or None.
        """
        occ = self.get_occupation(occupation)
        if not occ:
            return None

        phrases = occ.get("occupation_phrases", {})
        return phrases.get(situation)

    def get_voice_context(
        self,
        base_class: str,
        occupation: str | None = None,
        personality: str | None = None,
        region: str | None = None,
        include_examples: bool = True,
    ) -> str:
        """Generate formatted voice context for GM.

        Creates a text description of the voice template that can
        be included in the GM's context for consistent NPC dialogue.

        Args:
            base_class: Base social class.
            occupation: Optional occupation.
            personality: Optional personality.
            region: Optional region.
            include_examples: Whether to include example dialogue.

        Returns:
            Formatted voice guidance string.
        """
        template = self.build_voice_template(
            base_class=base_class,
            occupation=occupation,
            personality=personality,
            region=region,
        )

        if not template:
            return f"Unknown voice template: {base_class}"

        lines = ["NPC Voice Guidelines:"]
        lines.append(f"  Base: {base_class.title()}")

        if occupation:
            lines.append(f"  Occupation: {occupation.title()}")
        if personality:
            lines.append(f"  Personality: {personality.title()}")
        if region:
            lines.append(f"  Region: {region.title()}")

        lines.append("")
        lines.append(f"  Vocabulary: {template.vocabulary_level}")
        lines.append(f"  Sentence structure: {template.sentence_structure}")
        lines.append(f"  Contractions: {template.contractions}")

        if template.speech_patterns:
            lines.append("")
            lines.append("  Speech patterns:")
            for pattern in template.speech_patterns[:5]:  # Limit to 5
                lines.append(f"    - {pattern}")

        if template.verbal_tics:
            lines.append("")
            lines.append(f"  Verbal tics: {', '.join(template.verbal_tics[:5])}")

        if template.vocabulary_replacements:
            lines.append("")
            lines.append("  Regional vocabulary:")
            for original, replacement in list(template.vocabulary_replacements.items())[:5]:
                lines.append(f"    - '{original}' → '{replacement}'")

        if template.regional_expressions:
            lines.append("")
            lines.append(f"  Regional expressions: {', '.join(template.regional_expressions[:3])}")

        if include_examples and template.example_dialogue:
            lines.append("")
            lines.append("  Example dialogue:")
            for situation, dialogue in list(template.example_dialogue.items())[:3]:
                lines.append(f"    [{situation}]: \"{dialogue}\"")

        return "\n".join(lines)

    def get_available_base_classes(self) -> list[str]:
        """Get list of available base classes.

        Returns:
            List of base class names.
        """
        return list(self.base_classes.keys())

    def get_available_occupations(self) -> list[str]:
        """Get list of available occupations.

        Returns:
            List of occupation names.
        """
        return list(self.occupations.keys())

    def get_available_personalities(self) -> list[str]:
        """Get list of available personalities.

        Returns:
            List of personality names.
        """
        return list(self.personalities.keys())

    def get_available_regions(self) -> list[str]:
        """Get list of available regions.

        Returns:
            List of region names.
        """
        return list(self.regions.keys())

    def _get_setting_guidance(self, setting: str) -> str:
        """Get setting-specific guidance for voice generation.

        Args:
            setting: The game setting (fantasy, contemporary, scifi).

        Returns:
            Setting-specific guidance text.
        """
        guidance = {
            "fantasy": """- Medieval-inspired speech with class distinctions
- Nobles avoid contractions, use formal address
- Commoners use colloquialisms, dropped letters
- Regional dialects (northern cold/hard, southern warm/slow)
- Occupational vocabulary (smiths, soldiers, merchants)
- Avoid modern slang or technology references""",
            "contemporary": """- Modern American/British speech patterns
- Professional jargon based on occupation
- Regional accents (West Coast casual, Southern drawl, New York direct)
- Age-appropriate slang
- Texting/social media language for younger characters
- Corporate speak for business characters""",
            "scifi": """- Technical terminology based on role
- Alien species may have unusual speech patterns
- Corporate/military formality where appropriate
- Futuristic slang and expressions
- AI/android voices may be precise, measured
- Colony/station dialects based on isolation""",
        }
        return guidance.get(setting, guidance["fantasy"])

    def _format_example_templates(self) -> str:
        """Format YAML templates as examples for the LLM prompt.

        Returns:
            Formatted example templates string.
        """
        examples = []

        # Include one base class example
        if "noble" in self.base_classes:
            noble = self.base_classes["noble"]
            examples.append(f"""**Noble (base class)**:
- Vocabulary: {noble.get('vocabulary_level', 'sophisticated')}
- Contractions: {noble.get('contractions', 'never')}
- Greetings: {', '.join(noble.get('greetings', [])[:2])}
- Speech patterns: {'; '.join(noble.get('speech_patterns', [])[:2])}""")

        if "commoner" in self.base_classes:
            commoner = self.base_classes["commoner"]
            examples.append(f"""**Commoner (base class)**:
- Vocabulary: {commoner.get('vocabulary_level', 'simple')}
- Contractions: {commoner.get('contractions', 'frequent')}
- Greetings: {', '.join(commoner.get('greetings', [])[:2])}
- Speech patterns: {'; '.join(commoner.get('speech_patterns', [])[:2])}""")

        return "\n\n".join(examples) if examples else "No examples available."

    async def generate_voice_template(
        self,
        display_name: str,
        setting: str,
        occupation: str | None = None,
        social_status: str | None = None,
        age: int | None = None,
        age_apparent: str | None = None,
        gender: str | None = None,
        species: str | None = None,
        personality_traits: str | None = None,
        origin: str | None = None,
        background_summary: str | None = None,
        voice_description: str | None = None,
        scene_context: str | None = None,
    ) -> GeneratedVoiceTemplate:
        """Generate a unique voice template using LLM.

        Creates a distinctive voice for an NPC based on their characteristics
        and the game setting.

        Args:
            display_name: NPC's name.
            setting: Game setting (fantasy, contemporary, scifi).
            occupation: NPC's occupation.
            social_status: Social standing (noble, commoner, etc.).
            age: Actual age.
            age_apparent: How old they appear.
            gender: Gender identity.
            species: Species (for non-human characters).
            personality_traits: Personality description.
            origin: Where they're from.
            background_summary: Brief background.
            voice_description: Physical voice characteristics.
            scene_context: Current scene for context.

        Returns:
            GeneratedVoiceTemplate with the unique voice.
        """
        # Load prompt template
        template_path = Path(__file__).parent.parent.parent / "data" / "templates" / "voice_generator.md"
        with open(template_path) as f:
            prompt_template = f.read()

        # Format the prompt
        prompt = prompt_template.format(
            setting=setting,
            display_name=display_name,
            age=age or "Unknown",
            age_apparent=age_apparent or "Unknown",
            gender=gender or "Unknown",
            species=species or "Human",
            occupation=occupation or "Unknown",
            occupation_years="Unknown",
            social_status=social_status or "Common",
            personality_traits=personality_traits or "Not specified",
            origin=origin or "Unknown",
            background_summary=background_summary or "Not specified",
            voice_description=voice_description or "Not specified",
            scene_context=scene_context or "General interaction",
            setting_guidance=self._get_setting_guidance(setting),
        )

        # Call LLM
        provider = get_cheap_provider()
        response = await provider.complete_structured(
            messages=[Message.user(prompt)],
            response_schema=GeneratedVoiceTemplate,
            temperature=0.8,  # Creative voice generation
        )

        return response.parsed_content

    def format_generated_voice_context(
        self,
        voice: GeneratedVoiceTemplate,
        npc_name: str,
    ) -> str:
        """Format a generated voice template for GM context.

        Args:
            voice: The generated voice template.
            npc_name: The NPC's name.

        Returns:
            Formatted voice guidance string for GM.
        """
        lines = [f"Voice Guidelines for {npc_name}:"]
        lines.append(f"  Summary: {voice.voice_summary}")
        lines.append("")
        lines.append(f"  Vocabulary: {voice.vocabulary_level}")
        lines.append(f"  Sentences: {voice.sentence_structure}")
        lines.append(f"  Formality: {voice.formality}")
        lines.append(f"  Pace: {voice.speaking_pace}")

        if voice.verbal_tics:
            lines.append("")
            lines.append(f"  Verbal tics: {', '.join(voice.verbal_tics[:4])}")

        if voice.speech_patterns:
            lines.append("")
            lines.append("  Speech patterns:")
            for pattern in voice.speech_patterns[:4]:
                lines.append(f"    - {pattern}")

        if voice.favorite_expressions:
            lines.append("")
            lines.append(f"  Expressions: {', '.join(voice.favorite_expressions[:3])}")

        if voice.accent_notes:
            lines.append("")
            lines.append(f"  Accent: {voice.accent_notes}")

        if voice.example_dialogue:
            lines.append("")
            lines.append("  Example dialogue:")
            for situation, line in list(voice.example_dialogue.items())[:4]:
                lines.append(f"    [{situation}]: \"{line}\"")

        if voice.stress_context_changes:
            lines.append("")
            lines.append(f"  Under stress: {voice.stress_context_changes}")

        return "\n".join(lines)

    @staticmethod
    def voice_template_from_dict(data: dict) -> GeneratedVoiceTemplate:
        """Create a GeneratedVoiceTemplate from a dictionary.

        Useful for loading stored voice templates from the database.

        Args:
            data: Dictionary with voice template data.

        Returns:
            GeneratedVoiceTemplate instance.
        """
        return GeneratedVoiceTemplate.model_validate(data)
