"""Pydantic schemas for LLM-generated NPC voice templates.

These schemas define the structured output format for the voice generator
when creating distinctive speech patterns for NPCs based on their
characteristics and the game setting.
"""

from pydantic import BaseModel, Field


class GeneratedVoiceTemplate(BaseModel):
    """LLM-generated voice template for an NPC.

    Defines speech patterns, vocabulary, and example dialogue that the GM
    can use to maintain consistent NPC characterization across interactions.
    """

    # Core speech characteristics
    vocabulary_level: str = Field(
        description="Vocabulary sophistication: 'simple', 'moderate', 'sophisticated', 'technical', 'archaic', 'street_slang', 'mixed'",
    )
    sentence_structure: str = Field(
        description="Typical sentence patterns: 'short_direct', 'moderate', 'complex_flowing', 'fragmented', 'rambling'",
    )
    formality: str = Field(
        description="Speech formality: 'casual', 'neutral', 'formal', 'extremely_formal', 'varies_by_audience'",
    )
    speaking_pace: str = Field(
        description="How fast they typically speak: 'slow_deliberate', 'measured', 'quick', 'variable'",
    )

    # Verbal patterns and tics
    verbal_tics: list[str] = Field(
        min_length=1,
        max_length=5,
        description="Recurring verbal habits (e.g., 'um', 'y'know', 'indeed', clearing throat, trailing off)",
    )
    speech_patterns: list[str] = Field(
        min_length=2,
        max_length=6,
        description="General speech habits (e.g., 'uses nautical metaphors', 'asks rhetorical questions', 'speaks in third person')",
    )
    filler_words: list[str] = Field(
        min_length=1,
        max_length=5,
        description="Words used to fill pauses (e.g., 'well', 'so', 'like', 'hmm')",
    )

    # Vocabulary and expressions
    favorite_expressions: list[str] = Field(
        min_length=2,
        max_length=6,
        description="Characteristic phrases this NPC uses frequently",
    )
    greetings: list[str] = Field(
        min_length=2,
        max_length=5,
        description="How they typically say hello",
    )
    farewells: list[str] = Field(
        min_length=2,
        max_length=5,
        description="How they typically say goodbye",
    )
    affirmatives: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Ways they say yes or agree",
    )
    negatives: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Ways they say no or disagree",
    )
    swearing_style: str = Field(
        description="How/if they swear (e.g., 'never', 'mild_euphemisms', 'occupational_curses', 'frequent_and_creative')",
    )
    swear_examples: list[str] | None = Field(
        default=None,
        max_length=4,
        description="Specific swear words or exclamations they use (if any)",
    )

    # Example dialogue for GM reference
    example_dialogue: dict[str, str] = Field(
        description="Situation -> example line mapping. Include: 'greeting_stranger', 'greeting_friend', 'angry', 'nervous', 'pleased', 'refusing_request'",
    )

    # Accent and dialect notes
    accent_notes: str | None = Field(
        default=None,
        description="Description of accent or pronunciation quirks",
    )
    dialect_features: list[str] | None = Field(
        default=None,
        max_length=5,
        description="Specific dialect features (e.g., 'drops final g', 'th -> d', 'double negatives')",
    )
    vocabulary_notes: str | None = Field(
        default=None,
        description="Notes on vocabulary choices (e.g., 'uses technical medical terms', 'avoids contractions')",
    )

    # Context-specific variations
    formal_context_changes: str | None = Field(
        default=None,
        description="How their speech changes in formal situations (e.g., 'becomes stiff and overly polite')",
    )
    stress_context_changes: str | None = Field(
        default=None,
        description="How their speech changes under stress (e.g., 'stutters', 'becomes clipped', 'talks faster')",
    )

    # Summary for quick reference
    voice_summary: str = Field(
        description="One-sentence summary of this NPC's voice for quick GM reference",
    )
