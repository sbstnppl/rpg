"""Rumor system manager.

Manages the creation, spreading, and decay of rumors through the game world.
Rumors propagate through social networks and can become distorted over time.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models.rumors import Rumor, RumorKnowledge, RumorSentiment
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class RumorInfo:
    """Information about a rumor."""

    rumor_key: str
    subject_entity_key: str
    content: str
    truth_value: float
    intensity: float
    sentiment: str
    tags: list[str]
    origin_location_key: str
    origin_turn: int
    known_by_count: int
    is_active: bool


@dataclass
class RumorSpreadResult:
    """Result of attempting to spread a rumor."""

    spread_successful: bool
    rumor_key: str
    from_entity_key: str
    to_entity_key: str
    reason: str | None = None
    distortion_applied: bool = False


class RumorManager(BaseManager):
    """Manages rumors in the game world.

    Handles creation, spreading, decay, and querying of rumors.
    Rumors originate from events or player actions and propagate
    through NPC social networks.
    """

    def __init__(self, db: Session, game_session: GameSession):
        """Initialize the rumor manager.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)

    def create_rumor(
        self,
        rumor_key: str,
        subject_entity_key: str,
        content: str,
        origin_location_key: str,
        origin_turn: int,
        truth_value: float = 1.0,
        spread_rate: float = 0.5,
        decay_rate: float = 0.05,
        intensity: float = 1.0,
        sentiment: RumorSentiment = RumorSentiment.NEUTRAL,
        tags: list[str] | None = None,
        original_event_id: int | None = None,
    ) -> Rumor:
        """Create a new rumor.

        Args:
            rumor_key: Unique identifier for the rumor.
            subject_entity_key: Who/what the rumor is about.
            content: The rumor text.
            origin_location_key: Where the rumor started.
            origin_turn: When the rumor started.
            truth_value: How true the rumor is (0.0-1.0).
            spread_rate: How fast it propagates (0.1-1.0).
            decay_rate: How fast it fades per day (0.01-0.1).
            intensity: Initial strength (0.0-1.0).
            sentiment: Tone of the rumor.
            tags: Categorization tags.
            original_event_id: Link to WorldEvent that spawned it.

        Returns:
            The created Rumor.
        """
        rumor = Rumor(
            session_id=self.game_session.id,
            rumor_key=rumor_key,
            subject_entity_key=subject_entity_key,
            content=content,
            truth_value=truth_value,
            original_event_id=original_event_id,
            origin_location_key=origin_location_key,
            origin_turn=origin_turn,
            spread_rate=spread_rate,
            decay_rate=decay_rate,
            intensity=intensity,
            sentiment=sentiment,
            tags=tags or [],
        )
        self.db.add(rumor)
        self.db.commit()
        return rumor

    def get_rumor(self, rumor_key: str) -> Rumor | None:
        """Get a rumor by key.

        Args:
            rumor_key: The rumor's unique key.

        Returns:
            The Rumor or None if not found.
        """
        stmt = select(Rumor).where(
            Rumor.session_id == self.game_session.id,
            Rumor.rumor_key == rumor_key,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_rumors_about(self, entity_key: str) -> list[Rumor]:
        """Get all rumors about a specific entity.

        Args:
            entity_key: The entity the rumors are about.

        Returns:
            List of rumors about the entity.
        """
        stmt = select(Rumor).where(
            Rumor.session_id == self.game_session.id,
            Rumor.subject_entity_key == entity_key,
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_active_rumors(self) -> list[Rumor]:
        """Get all active rumors.

        Returns:
            List of active rumors.
        """
        stmt = select(Rumor).where(
            Rumor.session_id == self.game_session.id,
            Rumor.is_active == True,  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_rumors_originating_at(self, location_key: str) -> list[Rumor]:
        """Get rumors that originated at a location.

        Args:
            location_key: The location key.

        Returns:
            List of rumors from that location.
        """
        stmt = select(Rumor).where(
            Rumor.session_id == self.game_session.id,
            Rumor.origin_location_key == location_key,
        )
        return list(self.db.execute(stmt).scalars().all())

    def add_knowledge(
        self,
        rumor_key: str,
        entity_key: str,
        learned_turn: int,
        believed: bool = True,
        will_spread: bool = True,
        local_distortion: str | None = None,
    ) -> RumorKnowledge:
        """Add knowledge of a rumor to an entity.

        Args:
            rumor_key: The rumor's key.
            entity_key: The entity learning the rumor.
            learned_turn: When they learned it.
            believed: Whether they believe it.
            will_spread: Whether they'll spread it.
            local_distortion: Their personal version.

        Returns:
            The created RumorKnowledge.
        """
        rumor = self.get_rumor(rumor_key)
        if not rumor:
            raise ValueError(f"Rumor not found: {rumor_key}")

        knowledge = RumorKnowledge(
            session_id=self.game_session.id,
            rumor_id=rumor.id,
            entity_key=entity_key,
            learned_turn=learned_turn,
            believed=believed,
            will_spread=will_spread,
            local_distortion=local_distortion,
        )
        self.db.add(knowledge)
        self.db.commit()
        return knowledge

    def get_rumors_known_by(self, entity_key: str) -> list[Rumor]:
        """Get all rumors known by an entity.

        Args:
            entity_key: The entity's key.

        Returns:
            List of rumors the entity knows.
        """
        stmt = (
            select(Rumor)
            .join(RumorKnowledge, RumorKnowledge.rumor_id == Rumor.id)
            .where(
                Rumor.session_id == self.game_session.id,
                RumorKnowledge.entity_key == entity_key,
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def entity_knows_rumor(self, entity_key: str, rumor_key: str) -> bool:
        """Check if an entity knows a specific rumor.

        Args:
            entity_key: The entity's key.
            rumor_key: The rumor's key.

        Returns:
            True if the entity knows the rumor.
        """
        rumor = self.get_rumor(rumor_key)
        if not rumor:
            return False

        stmt = select(RumorKnowledge).where(
            RumorKnowledge.session_id == self.game_session.id,
            RumorKnowledge.rumor_id == rumor.id,
            RumorKnowledge.entity_key == entity_key,
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def decay_rumors(self, days: int = 1) -> list[Rumor]:
        """Decay all active rumors over time.

        Reduces intensity based on decay_rate. Rumors that fall
        below threshold (0.1) become inactive.

        Args:
            days: Number of days to decay.

        Returns:
            List of rumors that became inactive.
        """
        deactivated = []
        active_rumors = self.get_active_rumors()

        for rumor in active_rumors:
            rumor.intensity -= rumor.decay_rate * days
            if rumor.intensity < 0.1:
                rumor.intensity = max(0.0, rumor.intensity)
                rumor.is_active = False
                deactivated.append(rumor)

        self.db.commit()
        return deactivated

    def spread_rumor_to_entity(
        self,
        rumor_key: str,
        from_entity_key: str,
        to_entity_key: str,
        current_turn: int,
        distortion_chance: float = 0.0,
    ) -> RumorSpreadResult:
        """Spread a rumor from one entity to another.

        Args:
            rumor_key: The rumor to spread.
            from_entity_key: Entity spreading the rumor.
            to_entity_key: Entity receiving the rumor.
            current_turn: Current game turn.
            distortion_chance: Chance of introducing distortion (0.0-1.0).

        Returns:
            RumorSpreadResult indicating success/failure.
        """
        import random

        rumor = self.get_rumor(rumor_key)
        if not rumor:
            return RumorSpreadResult(
                spread_successful=False,
                rumor_key=rumor_key,
                from_entity_key=from_entity_key,
                to_entity_key=to_entity_key,
                reason="rumor_not_found",
            )

        # Check if target already knows
        if self.entity_knows_rumor(to_entity_key, rumor_key):
            return RumorSpreadResult(
                spread_successful=False,
                rumor_key=rumor_key,
                from_entity_key=from_entity_key,
                to_entity_key=to_entity_key,
                reason="already_known",
            )

        # Apply distortion chance
        distortion_applied = False
        if random.random() < distortion_chance:
            distortion_applied = True
            # Reduce truth value slightly when distortion occurs
            rumor.truth_value = max(0.0, rumor.truth_value - 0.1)

        # Add knowledge to target
        self.add_knowledge(
            rumor_key=rumor_key,
            entity_key=to_entity_key,
            learned_turn=current_turn,
        )

        self.db.commit()

        return RumorSpreadResult(
            spread_successful=True,
            rumor_key=rumor_key,
            from_entity_key=from_entity_key,
            to_entity_key=to_entity_key,
            distortion_applied=distortion_applied,
        )

    def get_rumor_info(self, rumor_key: str) -> RumorInfo | None:
        """Get detailed information about a rumor.

        Args:
            rumor_key: The rumor's key.

        Returns:
            RumorInfo or None if not found.
        """
        rumor = self.get_rumor(rumor_key)
        if not rumor:
            return None

        # Count how many know it
        stmt = select(RumorKnowledge).where(
            RumorKnowledge.session_id == self.game_session.id,
            RumorKnowledge.rumor_id == rumor.id,
        )
        knowledge_count = len(list(self.db.execute(stmt).scalars().all()))

        return RumorInfo(
            rumor_key=rumor.rumor_key,
            subject_entity_key=rumor.subject_entity_key,
            content=rumor.content,
            truth_value=rumor.truth_value,
            intensity=rumor.intensity,
            sentiment=rumor.sentiment.value if isinstance(rumor.sentiment, RumorSentiment) else rumor.sentiment,
            tags=rumor.tags,
            origin_location_key=rumor.origin_location_key,
            origin_turn=rumor.origin_turn,
            known_by_count=knowledge_count,
            is_active=rumor.is_active,
        )

    def get_rumor_context_for_entity(self, entity_key: str) -> str:
        """Get formatted rumor context for an NPC.

        Used to inform the GM about what rumors an NPC knows
        that might influence their behavior toward the player.

        Args:
            entity_key: The NPC's entity key.

        Returns:
            Formatted string of rumors the NPC knows.
        """
        rumors = self.get_rumors_known_by(entity_key)
        if not rumors:
            return ""

        lines = [f"Rumors known by {entity_key}:"]
        for rumor in rumors:
            sentiment = rumor.sentiment.value if isinstance(rumor.sentiment, RumorSentiment) else rumor.sentiment
            lines.append(f"  - [{sentiment}] {rumor.content} (intensity: {rumor.intensity:.1f})")

        return "\n".join(lines)

    def get_rumors_context(self) -> str:
        """Get formatted context of all active rumors for GM.

        Returns:
            Formatted string of active rumors.
        """
        rumors = self.get_active_rumors()
        if not rumors:
            return "No active rumors circulating."

        # Sort by intensity
        rumors.sort(key=lambda r: r.intensity, reverse=True)

        lines = ["Active Rumors:"]
        for rumor in rumors[:10]:  # Limit to top 10
            sentiment = rumor.sentiment.value if isinstance(rumor.sentiment, RumorSentiment) else rumor.sentiment
            lines.append(
                f"  - [{sentiment}] About {rumor.subject_entity_key}: "
                f"{rumor.content} (intensity: {rumor.intensity:.1f})"
            )

        return "\n".join(lines)
