"""Tests for LLM-based NPC extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.narrator.npc_extractor import (
    ExtractedNPC,
    NPCExtractionResult,
    NPCExtractor,
    NPCImportance,
)


class TestExtractedNPC:
    """Tests for ExtractedNPC dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        npc = ExtractedNPC(
            name="Master Aldric",
            importance=NPCImportance.CRITICAL,
        )

        assert npc.name == "Master Aldric"
        assert npc.importance == NPCImportance.CRITICAL
        assert npc.description == ""
        assert npc.context == ""
        assert npc.location == ""
        assert npc.is_named is False
        assert npc.gender_hint is None
        assert npc.occupation_hint is None
        assert npc.role_hint is None
        assert npc.is_new is True

    def test_full_values(self) -> None:
        """Test all values are stored correctly."""
        npc = ExtractedNPC(
            name="Marta",
            importance=NPCImportance.SUPPORTING,
            description="A warm, plump woman with flour-dusted apron",
            context="kneading bread in the kitchen",
            location="farmhouse kitchen",
            is_named=True,
            gender_hint="female",
            occupation_hint="farmer's wife",
            role_hint="employer's wife",
            is_new=False,
        )

        assert npc.name == "Marta"
        assert npc.importance == NPCImportance.SUPPORTING
        assert npc.description == "A warm, plump woman with flour-dusted apron"
        assert npc.context == "kneading bread in the kitchen"
        assert npc.location == "farmhouse kitchen"
        assert npc.is_named is True
        assert npc.gender_hint == "female"
        assert npc.occupation_hint == "farmer's wife"
        assert npc.role_hint == "employer's wife"
        assert npc.is_new is False


class TestNPCImportance:
    """Tests for NPCImportance enum."""

    def test_enum_values(self) -> None:
        """Test enum string values."""
        assert NPCImportance.CRITICAL.value == "critical"
        assert NPCImportance.SUPPORTING.value == "supporting"
        assert NPCImportance.BACKGROUND.value == "background"
        assert NPCImportance.REFERENCE.value == "reference"

    def test_enum_from_string(self) -> None:
        """Test enum creation from string."""
        assert NPCImportance("critical") == NPCImportance.CRITICAL
        assert NPCImportance("supporting") == NPCImportance.SUPPORTING
        assert NPCImportance("background") == NPCImportance.BACKGROUND
        assert NPCImportance("reference") == NPCImportance.REFERENCE


class TestNPCExtractionResult:
    """Tests for NPCExtractionResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = NPCExtractionResult()

        assert result.npcs == []
        assert result.reasoning == ""

    def test_with_npcs(self) -> None:
        """Test result with NPCs."""
        npcs = [
            ExtractedNPC(name="Aldric", importance=NPCImportance.CRITICAL),
            ExtractedNPC(name="Marta", importance=NPCImportance.SUPPORTING),
        ]
        result = NPCExtractionResult(
            npcs=npcs,
            reasoning="Found 2 NPCs in farmhouse scene",
        )

        assert len(result.npcs) == 2
        assert result.npcs[0].name == "Aldric"
        assert result.npcs[1].name == "Marta"
        assert result.reasoning == "Found 2 NPCs in farmhouse scene"


class TestNPCExtractor:
    """Tests for NPCExtractor."""

    def test_no_llm_provider_returns_empty(self) -> None:
        """Test that without LLM provider, returns empty result."""
        extractor = NPCExtractor(llm_provider=None)

        import asyncio
        result = asyncio.run(extractor.extract(
            "Master Aldric greets you at the door."
        ))

        assert result.npcs == []
        assert "No LLM provider" in result.reasoning

    def test_short_narrative_returns_empty(self) -> None:
        """Test that very short narratives return empty result."""
        mock_provider = MagicMock()
        extractor = NPCExtractor(llm_provider=mock_provider)

        import asyncio
        result = asyncio.run(extractor.extract("You wait."))

        assert result.npcs == []
        assert "too short" in result.reasoning

    @pytest.mark.asyncio
    async def test_parses_valid_json_response(self) -> None:
        """Test parsing valid JSON response from LLM."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {
                    "name": "Master Aldric",
                    "importance": "critical",
                    "description": "A weathered farmer in his fifties",
                    "context": "greeting you at the door",
                    "location": "farmhouse entrance",
                    "is_named": true,
                    "gender_hint": "male",
                    "occupation_hint": "farmer",
                    "role_hint": "employer",
                    "is_new": true
                },
                {
                    "name": "Marta",
                    "importance": "supporting",
                    "description": "Aldric's wife",
                    "context": "cooking in the kitchen",
                    "location": "kitchen",
                    "is_named": true,
                    "gender_hint": "female",
                    "occupation_hint": "farmer's wife",
                    "role_hint": "employer's wife",
                    "is_new": true
                }
            ],
            "reasoning": "Found 2 NPCs in the farmhouse scene"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "Master Aldric greets you at the door. His wife Marta is cooking in the kitchen.",
            current_location="farmhouse",
            player_name="Finn",
        )

        assert len(result.npcs) == 2
        assert result.npcs[0].name == "Master Aldric"
        assert result.npcs[0].importance == NPCImportance.CRITICAL
        assert result.npcs[0].is_named is True
        assert result.npcs[0].role_hint == "employer"
        assert result.npcs[1].name == "Marta"
        assert result.npcs[1].importance == NPCImportance.SUPPORTING
        assert result.npcs[1].gender_hint == "female"

    @pytest.mark.asyncio
    async def test_parses_empty_npcs_response(self) -> None:
        """Test parsing response with no NPCs."""
        mock_response = MagicMock()
        mock_response.content = '{"npcs": [], "reasoning": "No NPCs in scene - only player"}'

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "You stand alone in the empty field, contemplating the horizon.",
            current_location="field",
            player_name="Finn",
        )

        assert result.npcs == []
        assert "No NPCs" in result.reasoning

    @pytest.mark.asyncio
    async def test_handles_json_with_extra_text(self) -> None:
        """Test parsing JSON even when surrounded by extra text."""
        mock_response = MagicMock()
        mock_response.content = '''Here's my analysis:
        {
            "npcs": [{"name": "the merchant", "importance": "supporting", "description": "an old man behind a counter", "context": "selling wares", "location": "shop", "is_named": false, "is_new": true}],
            "reasoning": "One unnamed NPC found"
        }
        Hope this helps!'''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "The merchant behind the counter watches you enter.",
            current_location="shop",
        )

        assert len(result.npcs) == 1
        assert result.npcs[0].name == "the merchant"
        assert result.npcs[0].is_named is False

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self) -> None:
        """Test graceful handling of invalid JSON."""
        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all"

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "Master Aldric greets you warmly.",
            current_location="farmhouse",
        )

        assert result.npcs == []
        assert "no JSON found" in result.reasoning

    @pytest.mark.asyncio
    async def test_handles_malformed_npcs(self) -> None:
        """Test graceful handling of malformed NPC data."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {"name": "", "importance": "critical"},
                {"name": "Aldric", "importance": "invalid_importance"},
                {"name": "Marta", "importance": "supporting", "is_named": true}
            ],
            "reasoning": "Mixed quality data"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "Some narrative text here with NPCs.",
            current_location="farmhouse",
        )

        # Empty name should be skipped, invalid importance should default to SUPPORTING
        assert len(result.npcs) == 2
        assert result.npcs[0].name == "Aldric"
        assert result.npcs[0].importance == NPCImportance.SUPPORTING  # defaulted
        assert result.npcs[1].name == "Marta"
        assert result.npcs[1].importance == NPCImportance.SUPPORTING

    @pytest.mark.asyncio
    async def test_handles_null_values(self) -> None:
        """Test handling of null/unknown values in response."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {
                    "name": "the guard",
                    "importance": "supporting",
                    "description": "a bored-looking guard",
                    "context": "leaning against the wall",
                    "location": "null",
                    "is_named": false,
                    "gender_hint": "unknown",
                    "occupation_hint": null,
                    "role_hint": "",
                    "is_new": true
                }
            ],
            "reasoning": "One guard NPC"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "A guard leans against the wall near the gate.",
            current_location="gate",
        )

        assert len(result.npcs) == 1
        npc = result.npcs[0]
        assert npc.location == ""  # "null" should become ""
        assert npc.gender_hint is None  # "unknown" should become None
        assert npc.occupation_hint is None
        assert npc.role_hint is None  # empty string should become None

    @pytest.mark.asyncio
    async def test_handles_llm_exception(self) -> None:
        """Test graceful handling of LLM exceptions."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=Exception("LLM error"))

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "Master Aldric greets you at the door.",
            current_location="farmhouse",
        )

        assert result.npcs == []
        assert "failed" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_uses_configured_model(self) -> None:
        """Test that the configured model is used."""
        mock_response = MagicMock()
        mock_response.content = '{"npcs": [], "reasoning": "None"}'

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(
            llm_provider=mock_provider,
            model="claude-3-5-haiku-20241022",
            temperature=0.1,
        )
        await extractor.extract(
            "Some narrative text here about NPCs.",
            current_location="tavern",
        )

        # Verify the correct model and temperature were passed
        call_kwargs = mock_provider.complete.call_args.kwargs
        assert call_kwargs["model"] == "claude-3-5-haiku-20241022"
        assert call_kwargs["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_known_npcs_passed_to_prompt(self) -> None:
        """Test that known NPCs are passed to the prompt."""
        mock_response = MagicMock()
        mock_response.content = '{"npcs": [], "reasoning": "All NPCs already known"}'

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        await extractor.extract(
            "Master Aldric and Marta work in the field.",
            current_location="farmhouse",
            player_name="Finn",
            known_npcs=["Master Aldric", "Marta"],
        )

        # Verify known NPCs are in the prompt
        call_args = mock_provider.complete.call_args
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0].content
        assert "Master Aldric, Marta" in prompt_content

    @pytest.mark.asyncio
    async def test_player_name_excluded(self) -> None:
        """Test that player name is passed to prompt for exclusion."""
        mock_response = MagicMock()
        mock_response.content = '{"npcs": [], "reasoning": "Only player mentioned"}'

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        await extractor.extract(
            "Finn walks through the empty village.",
            current_location="village",
            player_name="Finn",
        )

        # Verify player name is in the prompt
        call_args = mock_provider.complete.call_args
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0].content
        assert "Finn" in prompt_content


class TestNPCExtractorImportanceClassification:
    """Tests for NPC importance classification logic."""

    @pytest.mark.asyncio
    async def test_critical_importance_for_direct_interaction(self) -> None:
        """Test that NPCs initiating interaction get CRITICAL importance."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {
                    "name": "the guard",
                    "importance": "critical",
                    "description": "A stern-looking guard",
                    "context": "stopping you at the gate",
                    "location": "gate",
                    "is_named": false,
                    "is_new": true
                }
            ],
            "reasoning": "Guard is blocking player progress"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "A guard blocks your path. 'Halt! State your business!'",
            current_location="gate",
        )

        assert len(result.npcs) == 1
        assert result.npcs[0].importance == NPCImportance.CRITICAL

    @pytest.mark.asyncio
    async def test_background_importance_for_unnamed_atmosphere(self) -> None:
        """Test that unnamed atmospheric NPCs get BACKGROUND importance."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {
                    "name": "an old woman",
                    "importance": "background",
                    "description": "An elderly woman in simple clothes",
                    "context": "sweeping the street",
                    "location": "village street",
                    "is_named": false,
                    "is_new": true
                }
            ],
            "reasoning": "Unnamed atmospheric NPC"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "An old woman sweeps the dusty street as you pass by.",
            current_location="village",
        )

        assert len(result.npcs) == 1
        assert result.npcs[0].importance == NPCImportance.BACKGROUND
        assert result.npcs[0].is_named is False

    @pytest.mark.asyncio
    async def test_reference_importance_for_absent_npcs(self) -> None:
        """Test that NPCs only mentioned but not present get REFERENCE importance."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {
                    "name": "Lord Blackwood",
                    "importance": "reference",
                    "description": "The feared lord of the region",
                    "context": "mentioned in conversation",
                    "location": "not present - in his castle",
                    "is_named": true,
                    "is_new": true
                }
            ],
            "reasoning": "NPC only mentioned, not physically present"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "The villagers speak in hushed tones about Lord Blackwood's cruelty.",
            current_location="village",
        )

        assert len(result.npcs) == 1
        assert result.npcs[0].importance == NPCImportance.REFERENCE
        assert result.npcs[0].name == "Lord Blackwood"


class TestNPCExtractorEdgeCases:
    """Tests for edge cases in NPC extraction."""

    @pytest.mark.asyncio
    async def test_no_extraction_for_groups(self) -> None:
        """Test that group references are not extracted as individual NPCs."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [],
            "reasoning": "Only group references found (the crowd, some farmers) - not individual NPCs"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "The crowd parts as you approach. Some farmers watch from nearby.",
            current_location="market",
        )

        assert result.npcs == []

    @pytest.mark.asyncio
    async def test_extraction_with_family_relationships(self) -> None:
        """Test extraction of NPCs with family relationship hints."""
        mock_response = MagicMock()
        mock_response.content = '''
        {
            "npcs": [
                {
                    "name": "Elsa",
                    "importance": "supporting",
                    "description": "A young girl about 8 years old",
                    "context": "playing in the yard",
                    "location": "farmhouse yard",
                    "is_named": true,
                    "gender_hint": "female",
                    "occupation_hint": null,
                    "role_hint": "employer's daughter",
                    "is_new": true
                }
            ],
            "reasoning": "Child NPC mentioned by name"
        }
        '''

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        extractor = NPCExtractor(llm_provider=mock_provider)
        result = await extractor.extract(
            "Their daughter Elsa plays in the yard, chasing butterflies.",
            current_location="farmhouse",
            player_name="Finn",
        )

        assert len(result.npcs) == 1
        assert result.npcs[0].name == "Elsa"
        assert result.npcs[0].role_hint == "employer's daughter"
        assert result.npcs[0].gender_hint == "female"
