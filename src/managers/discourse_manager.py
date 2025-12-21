"""Discourse Manager for tracking entity mentions across conversation.

This module provides discourse-aware reference resolution by:
1. Pre-extracting entity mentions from GM responses
2. Tracking mentions with descriptors, gender, and group relationships
3. Computing pronoun candidates for resolution
4. Enabling just-in-time entity spawning when referenced

The key insight is that when the GM says "two guys - one is singing, the other
is playing guitar", we need to immediately track both entities with their
descriptors and group relationship, so that when the player says "I talk to
the other one", we can resolve it correctly.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models.session import GameSession, Turn
from src.llm.base import LLMProvider
from src.llm.message_types import Message

logger = logging.getLogger(__name__)


@dataclass
class EntityMention:
    """A single entity mention extracted from GM response.

    Attributes:
        reference_id: Unique ID for this mention (e.g., "guy_1", "merchant_abc123")
        display_text: How the entity was described (e.g., "the singing guy")
        descriptors: List of attributes (e.g., ["singing", "tall", "on the left"])
        gender: Inferred gender ("male", "female", or None)
        turn_number: Which turn this mention appeared in
        group_id: If part of a group (e.g., "two guys"), links members together
        contrast_with: For anaphoric references, points to the contrasting entity
        spawned_as: Entity key if this mention has been spawned as a real entity
        location: Where this entity was mentioned as being
    """

    reference_id: str
    display_text: str
    descriptors: list[str] = field(default_factory=list)
    gender: str | None = None
    turn_number: int = 0
    group_id: str | None = None
    contrast_with: str | None = None
    spawned_as: str | None = None
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "reference_id": self.reference_id,
            "display_text": self.display_text,
            "descriptors": self.descriptors,
            "gender": self.gender,
            "turn_number": self.turn_number,
            "group_id": self.group_id,
            "contrast_with": self.contrast_with,
            "spawned_as": self.spawned_as,
            "location": self.location,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityMention":
        """Create from dictionary."""
        return cls(
            reference_id=data.get("reference_id", ""),
            display_text=data.get("display_text", ""),
            descriptors=data.get("descriptors", []),
            gender=data.get("gender"),
            turn_number=data.get("turn_number", 0),
            group_id=data.get("group_id"),
            contrast_with=data.get("contrast_with"),
            spawned_as=data.get("spawned_as"),
            location=data.get("location"),
        )


class ExtractedEntity(BaseModel):
    """A single entity extracted by LLM from GM response."""

    display_text: str = Field(description="How the entity is referred to in the text")
    descriptors: list[str] = Field(
        default_factory=list,
        description="Attributes like 'tall', 'singing', 'wearing armor'",
    )
    gender: str | None = Field(
        default=None, description="Inferred gender: 'male', 'female', or null"
    )
    group_name: str | None = Field(
        default=None,
        description="If part of a group (e.g., 'two merchants'), the group name",
    )
    is_contrast: bool = Field(
        default=False,
        description="True if this is 'the other one' in a contrast pair",
    )
    location: str | None = Field(
        default=None, description="Where this entity is located if mentioned"
    )


class ExtractionResult(BaseModel):
    """Result of entity extraction from GM response."""

    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="Entities mentioned in the response"
    )


EXTRACTION_SYSTEM_PROMPT = """You are an entity extractor for a fantasy RPG game.
Your job is to identify NPCs and characters mentioned in the Game Master's response.

Extract entities that could be referenced by the player in their next action.
Focus on:
- Named characters (e.g., "Ursula", "the blacksmith")
- Unnamed but distinct individuals (e.g., "a tall guard", "the singing man")
- Groups that split into individuals (e.g., "two merchants" -> extract each)

For each entity, identify:
- display_text: How they're referred to
- descriptors: Visual/behavioral attributes (singing, tall, wearing red, etc.)
- gender: male/female if determinable, null if unclear
- group_name: If part of a group ("two guys", "the merchants")
- is_contrast: True if described as "the other one" in a pair
- location: Where they are if mentioned

IMPORTANT for groups:
When the text says "two guys, one is singing, the other is playing guitar":
- Extract TWO entities, not one
- First entity: descriptors=["singing"], is_contrast=false
- Second entity: descriptors=["playing guitar"], is_contrast=true
- Both share the same group_name

Do NOT extract:
- The player character
- Generic crowds ("some villagers" without individual distinction)
- Abstract concepts
- Items (only people/creatures)
"""


def _build_extraction_prompt(gm_response: str) -> str:
    """Build the extraction prompt."""
    return f"""Extract all referenceable entities from this GM response:

"{gm_response}"

Return the entities that a player might want to interact with or refer to."""


class DiscourseManager:
    """Manages entity mentions across conversation turns.

    PARTIALLY DEPRECATED: In the scene-first architecture, entity resolution
    is handled by ReferenceResolver using the NarratorManifest. The resolve_reference()
    and mark_as_spawned() methods are deprecated. The extract_and_store() method
    may still be used to feed entity mentions into World Mechanics for story-driven
    NPC placement, but this is optional.

    For system-authority pipeline, this manager is still used for:
    - Tracking entities mentioned in GM responses
    - Pronoun and reference resolution
    - Just-in-time spawning from mentions

    Example:
        manager = DiscourseManager(db, game_session, llm_provider)

        # After GM response
        await manager.extract_and_store(gm_response, turn_number)

        # When resolving player reference (DEPRECATED - use ReferenceResolver instead)
        mention = manager.resolve_reference("the other one")
        if mention and not mention.spawned_as:
            # Spawn the entity
            entity = spawn_from_mention(mention)
            manager.mark_as_spawned(mention.reference_id, entity.entity_key)
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider | None = None,
    ):
        """Initialize the discourse manager.

        Args:
            db: Database session.
            game_session: Current game session.
            llm_provider: LLM provider for entity extraction (should be haiku for speed).
        """
        self.db = db
        self.game_session = game_session
        self.llm_provider = llm_provider

        # Cache of recent mentions (loaded lazily)
        self._mentions_cache: list[EntityMention] | None = None
        self._cache_turn: int = -1

    def _load_recent_mentions(self, lookback_turns: int = 10) -> list[EntityMention]:
        """Load mentions from recent turns.

        Args:
            lookback_turns: How many turns to look back.

        Returns:
            List of EntityMention objects, most recent first.
        """
        recent_turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .filter(Turn.mentioned_entities.isnot(None))
            .order_by(Turn.turn_number.desc())
            .limit(lookback_turns)
            .all()
        )

        mentions = []
        for turn in recent_turns:
            if turn.mentioned_entities:
                for entity_data in turn.mentioned_entities:
                    mention = EntityMention.from_dict(entity_data)
                    mention.turn_number = turn.turn_number
                    mentions.append(mention)

        return mentions

    def get_recent_mentions(
        self, lookback_turns: int = 10, force_reload: bool = False
    ) -> list[EntityMention]:
        """Get recent entity mentions.

        Args:
            lookback_turns: How many turns to look back.
            force_reload: Force reload from database.

        Returns:
            List of EntityMention objects, most recent first.
        """
        current_turn = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )
        current_turn_num = current_turn.turn_number if current_turn else 0

        if (
            force_reload
            or self._mentions_cache is None
            or self._cache_turn != current_turn_num
        ):
            self._mentions_cache = self._load_recent_mentions(lookback_turns)
            self._cache_turn = current_turn_num

        return self._mentions_cache

    def get_pronoun_candidates(self) -> dict[str, EntityMention]:
        """Compute pronoun candidates from recent mentions.

        Returns a mapping of pronouns to the most likely entity:
        - "she/her" -> most recent female entity (only if unambiguous)
        - "he/him" -> most recent male entity (only if unambiguous)
        - "the other one" -> entity with is_contrast=True in most recent group

        IMPORTANT: When multiple same-gender entities exist in the scene,
        pronouns for that gender are NOT resolved. This allows the scene-first
        ReferenceResolver to properly detect ambiguity and ask for clarification.

        Returns:
            Dict mapping pronoun patterns to EntityMention.
        """
        mentions = self.get_recent_mentions()
        candidates: dict[str, EntityMention] = {}

        # Count entities by gender to detect ambiguity
        male_mentions = [m for m in mentions if m.gender == "male"]
        female_mentions = [m for m in mentions if m.gender == "female"]

        # Only provide pronoun resolution when unambiguous (single candidate)
        if len(female_mentions) == 1:
            candidates["she"] = female_mentions[0]
            candidates["her"] = female_mentions[0]

        if len(male_mentions) == 1:
            candidates["he"] = male_mentions[0]
            candidates["him"] = male_mentions[0]

        # Track "the other one" from contrast pairs
        for mention in mentions:
            if mention.contrast_with and "the other one" not in candidates:
                candidates["the other one"] = mention
                candidates["the other"] = mention
                break

        return candidates

    def resolve_reference(self, reference: str) -> EntityMention | None:
        """Resolve a reference to an entity mention.

        DEPRECATED: In scene-first architecture, use ReferenceResolver with
        NarratorManifest instead. This method is kept for system-authority
        pipeline backward compatibility.

        Handles:
        - Pronouns: "she", "he", "her", "him"
        - Anaphoric: "the other one", "the other"
        - Descriptive: "the singing guy", "the tall merchant"
        - Direct: entity reference_id or display_text match

        Args:
            reference: The reference to resolve.

        Returns:
            Matching EntityMention or None if not found.
        """
        reference_lower = reference.lower().strip()
        mentions = self.get_recent_mentions()

        # 1. Check pronoun candidates
        pronouns = self.get_pronoun_candidates()
        if reference_lower in pronouns:
            return pronouns[reference_lower]

        # 2. Check direct reference_id match
        for mention in mentions:
            if mention.reference_id.lower() == reference_lower:
                return mention

        # 3. Check display_text match (exact or partial)
        for mention in mentions:
            if mention.display_text.lower() == reference_lower:
                return mention
            if reference_lower in mention.display_text.lower():
                return mention

        # 4. Check descriptor match
        for mention in mentions:
            for descriptor in mention.descriptors:
                if descriptor.lower() in reference_lower:
                    return mention
                if reference_lower in descriptor.lower():
                    return mention

        return None

    async def extract_and_store(
        self, gm_response: str, turn_number: int
    ) -> list[EntityMention]:
        """Extract entities from GM response and store in the turn.

        This is called after each GM response to pre-extract entities
        for later reference resolution.

        Args:
            gm_response: The GM's response text.
            turn_number: Current turn number.

        Returns:
            List of extracted EntityMention objects.
        """
        if not self.llm_provider:
            logger.warning("No LLM provider for entity extraction")
            return []

        # Get the current turn to store results
        turn = (
            self.db.query(Turn)
            .filter(
                Turn.session_id == self.game_session.id,
                Turn.turn_number == turn_number,
            )
            .first()
        )

        if not turn:
            logger.warning(f"Turn {turn_number} not found for entity extraction")
            return []

        # Extract entities using LLM
        try:
            prompt = _build_extraction_prompt(gm_response)
            messages = [Message.user(prompt)]

            response = await self.llm_provider.complete_structured(
                messages=messages,
                response_schema=ExtractionResult,
                temperature=0.0,
                max_tokens=500,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )

            if response.parsed_content is None:
                logger.debug("No entities extracted from GM response")
                return []

            # Handle both dict and Pydantic model
            if isinstance(response.parsed_content, dict):
                result = ExtractionResult(**response.parsed_content)
            else:
                result = response.parsed_content

            # Convert to EntityMention objects
            mentions = []
            group_first: dict[str, EntityMention] = {}  # Track first entity per group

            for i, entity in enumerate(result.entities):
                # Generate unique reference ID
                ref_id = f"entity_{turn_number}_{i}_{uuid.uuid4().hex[:6]}"

                mention = EntityMention(
                    reference_id=ref_id,
                    display_text=entity.display_text,
                    descriptors=entity.descriptors,
                    gender=entity.gender,
                    turn_number=turn_number,
                    group_id=entity.group_name,
                    location=entity.location,
                )

                # Handle contrast relationships within groups
                if entity.group_name:
                    if entity.is_contrast and entity.group_name in group_first:
                        # This is "the other one" - link to first entity
                        mention.contrast_with = group_first[entity.group_name].reference_id
                    elif not entity.is_contrast:
                        # This is the first entity in the group
                        group_first[entity.group_name] = mention

                mentions.append(mention)

            # Store in turn
            turn.mentioned_entities = [m.to_dict() for m in mentions]
            self.db.flush()

            # Invalidate cache
            self._mentions_cache = None

            logger.debug(
                f"Extracted {len(mentions)} entities from turn {turn_number}: "
                f"{[m.display_text for m in mentions]}"
            )

            return mentions

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return []

    def mark_as_spawned(self, reference_id: str, entity_key: str) -> bool:
        """Mark a mention as having been spawned as a real entity.

        This updates the stored mention so future references can use
        the real entity_key directly.

        Args:
            reference_id: The mention's reference_id.
            entity_key: The spawned entity's key.

        Returns:
            True if successfully updated, False otherwise.
        """
        # Find the turn containing this mention
        turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .filter(Turn.mentioned_entities.isnot(None))
            .order_by(Turn.turn_number.desc())
            .limit(20)
            .all()
        )

        for turn in turns:
            if not turn.mentioned_entities:
                continue

            updated = False
            entities = list(turn.mentioned_entities)

            for entity in entities:
                if entity.get("reference_id") == reference_id:
                    entity["spawned_as"] = entity_key
                    updated = True
                    break

            if updated:
                turn.mentioned_entities = entities
                self.db.flush()
                self._mentions_cache = None  # Invalidate cache
                logger.debug(f"Marked {reference_id} as spawned: {entity_key}")
                return True

        return False

    def format_for_classifier(self) -> str:
        """Format mentions for the classifier prompt.

        Returns a structured text representation of recent mentions
        that the classifier can use for reference resolution.

        Returns:
            Formatted string for classifier prompt.
        """
        mentions = self.get_recent_mentions(lookback_turns=5)

        if not mentions:
            return ""

        lines = ["## Entity Mentions (from recent conversation)", ""]

        # Group by turn
        by_turn: dict[int, list[EntityMention]] = {}
        for mention in mentions:
            if mention.turn_number not in by_turn:
                by_turn[mention.turn_number] = []
            by_turn[mention.turn_number].append(mention)

        for turn_num in sorted(by_turn.keys(), reverse=True):
            lines.append(f"Turn {turn_num}:")
            for mention in by_turn[turn_num]:
                desc = ", ".join(mention.descriptors) if mention.descriptors else ""
                gender = f", {mention.gender}" if mention.gender else ""
                spawned = f" → {mention.spawned_as}" if mention.spawned_as else ""
                group = f" [group: {mention.group_id}]" if mention.group_id else ""
                contrast = (
                    f" (contrasts with {mention.contrast_with})"
                    if mention.contrast_with
                    else ""
                )

                lines.append(
                    f"  - [{mention.reference_id}] \"{mention.display_text}\""
                    f" ({desc}{gender}){group}{contrast}{spawned}"
                )
            lines.append("")

        # Add pronoun resolution guide
        pronouns = self.get_pronoun_candidates()
        if pronouns:
            lines.append("## Reference Resolution Guide")
            for pronoun, mention in pronouns.items():
                spawned = f" ({mention.spawned_as})" if mention.spawned_as else ""
                lines.append(f"  - \"{pronoun}\" → [{mention.reference_id}]{spawned}")
            lines.append("")

        return "\n".join(lines)
