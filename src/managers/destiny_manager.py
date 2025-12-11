"""DestinyManager for prophecy and destiny element tracking."""

from dataclasses import dataclass, field

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.database.models.destiny import (
    DestinyElement,
    DestinyElementType,
    Prophesy,
    ProphesyStatus,
)
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class ProphesyProgress:
    """Progress tracking for a prophecy.

    Attributes:
        prophesy_key: The prophecy's unique key.
        text: The prophecy text as player sees it.
        status: Current prophecy status.
        conditions_met: Number of fulfillment conditions met.
        conditions_total: Total number of fulfillment conditions.
        elements_manifested: List of element keys linked to this prophecy.
        hints_available: Available interpretation hints.
    """

    prophesy_key: str
    text: str
    status: str
    conditions_met: int
    conditions_total: int
    elements_manifested: list[str] = field(default_factory=list)
    hints_available: list[str] = field(default_factory=list)


class DestinyManager(BaseManager):
    """Manager for prophecy and destiny systems.

    Handles:
    - Prophecy creation and tracking
    - Destiny element (omens, signs, portents, visions) management
    - Progress tracking toward prophecy fulfillment
    - Prophecy resolution (fulfillment, subversion, abandonment)
    - Context generation for GM prompts
    """

    # Attribute to track met conditions (stored in fulfillment_conditions with prefix)
    MET_CONDITION_PREFIX = "MET:"

    # --- Prophesy Management ---

    def create_prophesy(
        self,
        prophesy_key: str,
        prophesy_text: str,
        true_meaning: str,
        source: str,
        fulfillment_conditions: list[str],
        subversion_conditions: list[str] | None = None,
        interpretation_hints: list[str] | None = None,
    ) -> Prophesy:
        """Create a new prophecy.

        Args:
            prophesy_key: Unique prophecy identifier.
            prophesy_text: Text as the player hears it.
            true_meaning: GM-only actual interpretation.
            source: Source of prophecy (oracle, scroll, seer, etc.).
            fulfillment_conditions: Conditions for fulfillment.
            subversion_conditions: Conditions for subversion.
            interpretation_hints: Clues for player interpretation.

        Returns:
            The created Prophesy.
        """
        prophesy = Prophesy(
            session_id=self.session_id,
            prophesy_key=prophesy_key,
            prophesy_text=prophesy_text,
            true_meaning=true_meaning,
            source=source,
            delivered_turn=self.current_turn,
            status=ProphesyStatus.ACTIVE.value,
            fulfillment_conditions=fulfillment_conditions,
            subversion_conditions=subversion_conditions or [],
            interpretation_hints=interpretation_hints or [],
        )
        self.db.add(prophesy)
        self.db.flush()
        return prophesy

    def get_prophesy(self, prophesy_key: str) -> Prophesy | None:
        """Get a prophecy by key.

        Args:
            prophesy_key: The prophecy's unique key.

        Returns:
            Prophesy if found, None otherwise.
        """
        return (
            self.db.query(Prophesy)
            .filter(
                and_(
                    Prophesy.session_id == self.session_id,
                    Prophesy.prophesy_key == prophesy_key,
                )
            )
            .first()
        )

    def get_active_prophesies(self) -> list[Prophesy]:
        """Get all active prophecies.

        Returns:
            List of active Prophesy records.
        """
        return (
            self.db.query(Prophesy)
            .filter(
                and_(
                    Prophesy.session_id == self.session_id,
                    Prophesy.status == ProphesyStatus.ACTIVE.value,
                )
            )
            .all()
        )

    def fulfill_prophesy(self, prophesy_key: str, description: str) -> None:
        """Mark a prophecy as fulfilled.

        Args:
            prophesy_key: The prophecy to fulfill.
            description: Description of how it was fulfilled.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if prophesy:
            prophesy.status = ProphesyStatus.FULFILLED.value
            prophesy.fulfilled_turn = self.current_turn
            prophesy.resolution_description = description
            self.db.flush()

    def subvert_prophesy(self, prophesy_key: str, description: str) -> None:
        """Mark a prophecy as subverted.

        Args:
            prophesy_key: The prophecy to subvert.
            description: Description of how it was subverted.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if prophesy:
            prophesy.status = ProphesyStatus.SUBVERTED.value
            prophesy.fulfilled_turn = self.current_turn
            prophesy.resolution_description = description
            self.db.flush()

    def abandon_prophesy(self, prophesy_key: str) -> None:
        """Mark a prophecy as abandoned.

        Args:
            prophesy_key: The prophecy to abandon.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if prophesy:
            prophesy.status = ProphesyStatus.ABANDONED.value
            prophesy.fulfilled_turn = self.current_turn
            self.db.flush()

    # --- Destiny Element Management ---

    def add_destiny_element(
        self,
        element_key: str,
        element_type: DestinyElementType,
        description: str,
        prophesy_key: str | None = None,
        witnessed_by: list[str] | None = None,
        significance: int = 3,
    ) -> DestinyElement:
        """Add a destiny element (omen, sign, portent, vision).

        Args:
            element_key: Unique element identifier.
            element_type: Type of element.
            description: Description of the element.
            prophesy_key: Optional linked prophecy key.
            witnessed_by: Entity keys of witnesses.
            significance: Importance level 1-5.

        Returns:
            The created DestinyElement.
        """
        prophesy_id = None
        if prophesy_key:
            prophesy = self.get_prophesy(prophesy_key)
            if prophesy:
                prophesy_id = prophesy.id

        element = DestinyElement(
            session_id=self.session_id,
            element_key=element_key,
            element_type=element_type.value if isinstance(element_type, DestinyElementType) else element_type,
            description=description,
            prophesy_id=prophesy_id,
            witnessed_by=witnessed_by or [],
            turn_occurred=self.current_turn,
            significance=significance,
            player_noticed=False,
        )
        self.db.add(element)
        self.db.flush()
        return element

    def get_destiny_element(self, element_key: str) -> DestinyElement | None:
        """Get a destiny element by key.

        Args:
            element_key: The element's unique key.

        Returns:
            DestinyElement if found, None otherwise.
        """
        return (
            self.db.query(DestinyElement)
            .filter(
                and_(
                    DestinyElement.session_id == self.session_id,
                    DestinyElement.element_key == element_key,
                )
            )
            .first()
        )

    def get_elements_for_prophesy(self, prophesy_key: str) -> list[DestinyElement]:
        """Get all elements linked to a prophecy.

        Args:
            prophesy_key: The prophecy key.

        Returns:
            List of linked DestinyElements.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if not prophesy:
            return []

        return (
            self.db.query(DestinyElement)
            .filter(
                and_(
                    DestinyElement.session_id == self.session_id,
                    DestinyElement.prophesy_id == prophesy.id,
                )
            )
            .all()
        )

    def mark_element_noticed(self, element_key: str) -> None:
        """Mark an element as noticed by the player.

        Args:
            element_key: The element to mark as noticed.
        """
        element = self.get_destiny_element(element_key)
        if element:
            element.player_noticed = True
            self.db.flush()

    def get_elements_by_type(self, element_type: DestinyElementType) -> list[DestinyElement]:
        """Get elements filtered by type.

        Args:
            element_type: The type to filter by.

        Returns:
            List of matching DestinyElements.
        """
        return (
            self.db.query(DestinyElement)
            .filter(
                and_(
                    DestinyElement.session_id == self.session_id,
                    DestinyElement.element_type == element_type.value,
                )
            )
            .all()
        )

    def get_unnoticed_elements(self) -> list[DestinyElement]:
        """Get elements that player hasn't noticed yet.

        Returns:
            List of unnoticed DestinyElements.
        """
        return (
            self.db.query(DestinyElement)
            .filter(
                and_(
                    DestinyElement.session_id == self.session_id,
                    DestinyElement.player_noticed == False,  # noqa: E712
                )
            )
            .all()
        )

    def get_recent_elements(
        self, limit: int = 10, min_significance: int = 1
    ) -> list[DestinyElement]:
        """Get recent destiny elements.

        Args:
            limit: Maximum number of elements to return.
            min_significance: Minimum significance level.

        Returns:
            List of recent DestinyElements, most recent first.
        """
        return (
            self.db.query(DestinyElement)
            .filter(
                and_(
                    DestinyElement.session_id == self.session_id,
                    DestinyElement.significance >= min_significance,
                )
            )
            .order_by(DestinyElement.turn_occurred.desc())
            .limit(limit)
            .all()
        )

    # --- Progress Tracking ---

    def check_prophesy_progress(self, prophesy_key: str) -> ProphesyProgress:
        """Check progress of a prophecy.

        Args:
            prophesy_key: The prophecy to check.

        Returns:
            ProphesyProgress with current status.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if not prophesy:
            return ProphesyProgress(
                prophesy_key=prophesy_key,
                text="",
                status="not_found",
                conditions_met=0,
                conditions_total=0,
            )

        # Count met conditions (marked with prefix)
        met_count = sum(
            1 for c in prophesy.fulfillment_conditions
            if c.startswith(self.MET_CONDITION_PREFIX)
        )
        total_conditions = len([
            c for c in prophesy.fulfillment_conditions
            if not c.startswith(self.MET_CONDITION_PREFIX)
        ]) + met_count

        # Get linked elements
        elements = self.get_elements_for_prophesy(prophesy_key)

        return ProphesyProgress(
            prophesy_key=prophesy_key,
            text=prophesy.prophesy_text,
            status=prophesy.status,
            conditions_met=met_count,
            conditions_total=total_conditions,
            elements_manifested=[e.element_key for e in elements],
            hints_available=list(prophesy.interpretation_hints),
        )

    def mark_condition_met(self, prophesy_key: str, condition: str) -> bool:
        """Mark a fulfillment condition as met.

        Args:
            prophesy_key: The prophecy key.
            condition: The condition that was met.

        Returns:
            True if condition was found and marked, False otherwise.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if not prophesy:
            return False

        if condition in prophesy.fulfillment_conditions:
            # Replace with met version
            new_conditions = [
                self.MET_CONDITION_PREFIX + c if c == condition else c
                for c in prophesy.fulfillment_conditions
            ]
            prophesy.fulfillment_conditions = new_conditions
            flag_modified(prophesy, "fulfillment_conditions")
            self.db.flush()
            return True

        return False

    def add_interpretation_hint(self, prophesy_key: str, hint: str) -> bool:
        """Add a new interpretation hint to a prophecy.

        Args:
            prophesy_key: The prophecy key.
            hint: The new hint to add.

        Returns:
            True if hint was added, False if prophecy not found.
        """
        prophesy = self.get_prophesy(prophesy_key)
        if not prophesy:
            return False

        prophesy.interpretation_hints = prophesy.interpretation_hints + [hint]
        flag_modified(prophesy, "interpretation_hints")
        self.db.flush()
        return True

    # --- Context Generation ---

    def get_destiny_context(self) -> str:
        """Generate destiny context for GM prompts.

        Returns:
            Formatted string describing active prophecies and recent elements.
        """
        prophesies = self.get_active_prophesies()
        if not prophesies:
            return ""

        lines = ["## Active Prophecies", ""]

        for prophesy in prophesies:
            progress = self.check_prophesy_progress(prophesy.prophesy_key)

            lines.append(f"### {prophesy.prophesy_key}")
            lines.append(f"**Text:** \"{prophesy.prophesy_text}\"")
            lines.append(f"**True Meaning:** {prophesy.true_meaning}")
            lines.append(f"**Source:** {prophesy.source}")
            lines.append(f"**Progress:** {progress.conditions_met}/{progress.conditions_total} conditions met")

            if progress.elements_manifested:
                lines.append(f"**Linked Elements:** {', '.join(progress.elements_manifested)}")

            lines.append("")

        # Add recent elements
        recent = self.get_recent_elements(limit=5, min_significance=3)
        if recent:
            lines.append("### Recent Destiny Elements")
            for element in recent:
                noticed = "(noticed)" if element.player_noticed else "(unnoticed)"
                lines.append(f"- [{element.element_type}] {element.description} {noticed}")

        return "\n".join(lines)
