"""FactManager for SPV (Subject-Predicate-Value) fact store."""

from sqlalchemy.orm import Session

from src.database.models.enums import FactCategory
from src.database.models.session import GameSession
from src.database.models.world import Fact
from src.managers.base import BaseManager


class FactManager(BaseManager):
    """Manager for fact store operations.

    Handles:
    - Recording and updating facts (SPV pattern)
    - Querying facts by subject, predicate, or category
    - Secret management
    - Foreshadowing mechanics (rule of three)
    """

    def record_fact(
        self,
        subject_type: str,
        subject_key: str,
        predicate: str,
        value: str,
        category: FactCategory = FactCategory.PERSONAL,
        is_secret: bool = False,
        confidence: int = 80,
    ) -> Fact:
        """Record a new fact or update existing.

        If a fact with same subject_key and predicate exists,
        updates the value. Otherwise creates a new fact.

        Args:
            subject_type: Type of subject (entity, location, world, item, group).
            subject_key: Key of the subject.
            predicate: What aspect (job, allergic_to, likes, etc.).
            value: The value.
            category: Fact category.
            is_secret: Whether GM-only.
            confidence: Confidence level (0-100).

        Returns:
            Created or updated Fact.
        """
        existing = self.get_fact(subject_key, predicate)

        if existing is not None:
            existing.value = value
            existing.category = category
            existing.is_secret = is_secret
            existing.confidence = confidence
            self.db.flush()
            return existing

        fact = Fact(
            session_id=self.session_id,
            subject_type=subject_type,
            subject_key=subject_key,
            predicate=predicate,
            value=value,
            category=category,
            is_secret=is_secret,
            confidence=confidence,
            source_turn=self.current_turn,
        )
        self.db.add(fact)
        self.db.flush()
        return fact

    def get_fact(self, subject_key: str, predicate: str) -> Fact | None:
        """Get a specific fact by subject and predicate.

        Args:
            subject_key: Subject key.
            predicate: Predicate.

        Returns:
            Fact if found, None otherwise.
        """
        return (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == subject_key,
                Fact.predicate == predicate,
            )
            .first()
        )

    def get_facts_about(
        self, subject_key: str, include_secrets: bool = False
    ) -> list[Fact]:
        """Get all facts about a subject.

        Args:
            subject_key: Subject key.
            include_secrets: Whether to include secret facts.

        Returns:
            List of Facts about the subject.
        """
        query = self.db.query(Fact).filter(
            Fact.session_id == self.session_id,
            Fact.subject_key == subject_key,
        )

        if not include_secrets:
            query = query.filter(Fact.is_secret == False)

        return query.all()

    def get_facts_by_predicate(self, predicate: str) -> list[Fact]:
        """Get all facts with a specific predicate.

        Args:
            predicate: Predicate to search for (e.g., 'allergic_to').

        Returns:
            List of Facts with the predicate.
        """
        return (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.predicate == predicate,
            )
            .all()
        )

    def get_facts_by_category(self, category: FactCategory) -> list[Fact]:
        """Get all facts in a category.

        Args:
            category: FactCategory to filter by.

        Returns:
            List of Facts in the category.
        """
        return (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.category == category,
            )
            .all()
        )

    def get_secrets(self) -> list[Fact]:
        """Get all secret facts (GM-only knowledge).

        Returns:
            List of secret Facts.
        """
        return (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_secret == True,
            )
            .all()
        )

    def get_player_known_facts(self) -> list[Fact]:
        """Get all facts known to the player (non-secret).

        Returns:
            List of non-secret Facts.
        """
        return (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_secret == False,
            )
            .all()
        )

    def update_certainty(self, fact_id: int, certainty: int) -> Fact:
        """Update confidence level of a fact.

        Args:
            fact_id: Fact ID.
            certainty: New confidence level (0-100).

        Returns:
            Updated Fact.

        Raises:
            ValueError: If fact not found.
        """
        fact = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.id == fact_id,
            )
            .first()
        )

        if fact is None:
            raise ValueError(f"Fact not found: {fact_id}")

        fact.confidence = self._clamp(certainty, 0, 100)
        self.db.flush()
        return fact

    def contradict_fact(
        self, fact_id: int, new_value: str, reason: str
    ) -> Fact:
        """Contradict an existing fact with a new value.

        Marks the old fact as not current (by setting is_secret or similar)
        and creates a new fact with the corrected value.

        Args:
            fact_id: Fact ID to contradict.
            new_value: Correct value.
            reason: Reason for the contradiction.

        Returns:
            New Fact with correct value.

        Raises:
            ValueError: If fact not found.
        """
        old_fact = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.id == fact_id,
            )
            .first()
        )

        if old_fact is None:
            raise ValueError(f"Fact not found: {fact_id}")

        # Record what the player used to believe (old value)
        if old_fact.player_believes is None:
            old_fact.player_believes = old_fact.value

        # Create new fact with corrected value
        new_fact = Fact(
            session_id=self.session_id,
            subject_type=old_fact.subject_type,
            subject_key=old_fact.subject_key,
            predicate=old_fact.predicate,
            value=new_value,
            category=old_fact.category,
            is_secret=False,
            confidence=100,
            source_turn=self.current_turn,
        )

        # Delete the old fact (it's been replaced)
        self.db.delete(old_fact)
        self.db.add(new_fact)
        self.db.flush()
        return new_fact

    def reveal_secret(self, fact_id: int) -> Fact:
        """Mark a secret as known to player.

        Args:
            fact_id: Fact ID.

        Returns:
            Updated Fact.

        Raises:
            ValueError: If fact not found.
        """
        fact = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.id == fact_id,
            )
            .first()
        )

        if fact is None:
            raise ValueError(f"Fact not found: {fact_id}")

        fact.is_secret = False
        self.db.flush()
        return fact

    def set_player_belief(self, fact_id: int, belief: str) -> Fact:
        """Set what player believes (if different from actual).

        Args:
            fact_id: Fact ID.
            belief: What player believes.

        Returns:
            Updated Fact.

        Raises:
            ValueError: If fact not found.
        """
        fact = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.id == fact_id,
            )
            .first()
        )

        if fact is None:
            raise ValueError(f"Fact not found: {fact_id}")

        fact.player_believes = belief
        self.db.flush()
        return fact

    def record_foreshadowing(
        self,
        subject_key: str,
        predicate: str,
        value: str,
        foreshadow_target: str,
    ) -> Fact:
        """Record a foreshadowing fact for future payoff.

        Args:
            subject_key: Subject key.
            predicate: Predicate.
            value: The hint value.
            foreshadow_target: What this foreshadows.

        Returns:
            Created Fact with foreshadowing fields set.
        """
        fact = Fact(
            session_id=self.session_id,
            subject_type="narrative",
            subject_key=subject_key,
            predicate=predicate,
            value=value,
            category=FactCategory.HISTORY,
            is_foreshadowing=True,
            foreshadow_target=foreshadow_target,
            times_mentioned=1,
            source_turn=self.current_turn,
        )
        self.db.add(fact)
        self.db.flush()
        return fact

    def increment_mention(self, fact_id: int) -> Fact:
        """Increment times_mentioned for rule of three.

        Args:
            fact_id: Fact ID.

        Returns:
            Updated Fact.

        Raises:
            ValueError: If fact not found.
        """
        fact = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.id == fact_id,
            )
            .first()
        )

        if fact is None:
            raise ValueError(f"Fact not found: {fact_id}")

        fact.times_mentioned += 1
        self.db.flush()
        return fact

    def get_unfulfilled_foreshadowing(self, min_mentions: int = 3) -> list[Fact]:
        """Get foreshadowing hints that have been planted enough times.

        Args:
            min_mentions: Minimum times mentioned to be considered ready.

        Returns:
            List of foreshadowing Facts ready for payoff.
        """
        return (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_foreshadowing == True,
                Fact.times_mentioned >= min_mentions,
            )
            .all()
        )

    def delete_fact(self, subject_key: str, predicate: str) -> bool:
        """Delete a fact.

        Args:
            subject_key: Subject key.
            predicate: Predicate.

        Returns:
            True if fact was deleted, False if not found.
        """
        fact = self.get_fact(subject_key, predicate)
        if fact is None:
            return False

        self.db.delete(fact)
        self.db.flush()
        return True
