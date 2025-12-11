"""Story Arc Manager for tracking narrative structure and progression.

This manager orchestrates story arcs through classic narrative phases,
tracks tension levels, manages Chekhov's guns (planted elements), and
provides pacing guidance to the GM.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.database.models.narrative import ArcPhase, ArcStatus, ArcType, StoryArc
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Phase progression order
PHASE_ORDER = [
    ArcPhase.SETUP,
    ArcPhase.RISING_ACTION,
    ArcPhase.MIDPOINT,
    ArcPhase.ESCALATION,
    ArcPhase.CLIMAX,
    ArcPhase.FALLING_ACTION,
    ArcPhase.RESOLUTION,
    ArcPhase.AFTERMATH,
]

# Suggested tension ranges per phase
PHASE_TENSION_RANGES = {
    ArcPhase.SETUP: (5, 25),
    ArcPhase.RISING_ACTION: (20, 50),
    ArcPhase.MIDPOINT: (40, 60),
    ArcPhase.ESCALATION: (55, 80),
    ArcPhase.CLIMAX: (75, 100),
    ArcPhase.FALLING_ACTION: (40, 70),
    ArcPhase.RESOLUTION: (10, 40),
    ArcPhase.AFTERMATH: (5, 20),
}

# Suggested minimum turns per phase
PHASE_MIN_TURNS = {
    ArcPhase.SETUP: 2,
    ArcPhase.RISING_ACTION: 3,
    ArcPhase.MIDPOINT: 1,
    ArcPhase.ESCALATION: 3,
    ArcPhase.CLIMAX: 2,
    ArcPhase.FALLING_ACTION: 1,
    ArcPhase.RESOLUTION: 2,
    ArcPhase.AFTERMATH: 1,
}


@dataclass
class PacingHint:
    """Suggestion for narrative pacing."""

    arc_key: str
    message: str
    urgency: str  # "low", "medium", "high"
    suggested_action: str | None = None


@dataclass
class ArcSummary:
    """Summary of a story arc for GM context."""

    arc_key: str
    title: str
    arc_type: str
    status: str
    phase: str
    tension: int
    turns_in_phase: int
    unresolved_elements: list[str]
    next_beat_hint: str | None
    stakes: str | None


class StoryArcManager(BaseManager):
    """Manages story arc progression and narrative structure.

    Story arcs provide dramatic structure by tracking:
    - Current phase (setup -> climax -> resolution)
    - Tension level (0-100)
    - Planted narrative elements (Chekhov's guns)
    - Pacing hints for the GM
    """

    def create_arc(
        self,
        arc_key: str,
        title: str,
        arc_type: ArcType,
        description: str | None = None,
        stakes: str | None = None,
        protagonist_id: int | None = None,
        antagonist_id: int | None = None,
        priority: int = 5,
        activate: bool = False,
    ) -> StoryArc:
        """Create a new story arc.

        Args:
            arc_key: Unique identifier for the arc (e.g., 'main_quest', 'romance_elara').
            title: Human-readable title.
            arc_type: Type of story arc (main_quest, romance, revenge, etc.).
            description: Overview of the arc.
            stakes: What's at stake in this arc.
            protagonist_id: Entity ID of the main character driving this arc.
            antagonist_id: Entity ID of the opposing force.
            priority: Importance 1-10 (higher = more important).
            activate: If True, immediately activate the arc.

        Returns:
            The created StoryArc.

        Raises:
            ValueError: If arc_key already exists for this session.
        """
        existing = self.get_arc(arc_key)
        if existing:
            raise ValueError(f"Story arc with key '{arc_key}' already exists")

        arc = StoryArc(
            session_id=self.session_id,
            arc_key=arc_key,
            title=title,
            arc_type=arc_type,
            description=description,
            stakes=stakes,
            protagonist_id=protagonist_id,
            antagonist_id=antagonist_id,
            priority=self._clamp(priority, 1, 10),
            status=ArcStatus.ACTIVE if activate else ArcStatus.DORMANT,
            started_turn=self.current_turn if activate else None,
            phase_started_turn=self.current_turn if activate else None,
        )
        self.db.add(arc)
        self.db.commit()
        self.db.refresh(arc)
        return arc

    def get_arc(self, arc_key: str) -> StoryArc | None:
        """Get a story arc by key.

        Args:
            arc_key: Unique identifier for the arc.

        Returns:
            The StoryArc if found, None otherwise.
        """
        return (
            self.db.query(StoryArc)
            .filter(
                and_(
                    StoryArc.session_id == self.session_id,
                    StoryArc.arc_key == arc_key,
                )
            )
            .first()
        )

    def get_active_arcs(self) -> list[StoryArc]:
        """Get all active story arcs, ordered by priority.

        Returns:
            List of active arcs, highest priority first.
        """
        return (
            self.db.query(StoryArc)
            .filter(
                and_(
                    StoryArc.session_id == self.session_id,
                    StoryArc.status == ArcStatus.ACTIVE,
                )
            )
            .order_by(StoryArc.priority.desc())
            .all()
        )

    def get_arcs_by_type(self, arc_type: ArcType) -> list[StoryArc]:
        """Get all arcs of a specific type.

        Args:
            arc_type: Type of arcs to retrieve.

        Returns:
            List of matching arcs.
        """
        return (
            self.db.query(StoryArc)
            .filter(
                and_(
                    StoryArc.session_id == self.session_id,
                    StoryArc.arc_type == arc_type,
                )
            )
            .all()
        )

    def activate_arc(self, arc_key: str) -> StoryArc:
        """Activate a dormant or paused arc.

        Args:
            arc_key: Unique identifier for the arc.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found or already completed/failed.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        if arc.status in (ArcStatus.COMPLETED, ArcStatus.FAILED, ArcStatus.ABANDONED):
            raise ValueError(f"Cannot activate arc with status '{arc.status.value}'")

        arc.status = ArcStatus.ACTIVE
        if arc.started_turn is None:
            arc.started_turn = self.current_turn
        if arc.phase_started_turn is None:
            arc.phase_started_turn = self.current_turn

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def pause_arc(self, arc_key: str) -> StoryArc:
        """Pause an active arc.

        Args:
            arc_key: Unique identifier for the arc.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found or not active.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        if arc.status != ArcStatus.ACTIVE:
            raise ValueError(f"Can only pause active arcs, current status: {arc.status.value}")

        arc.status = ArcStatus.PAUSED
        self.db.commit()
        self.db.refresh(arc)
        return arc

    def advance_phase(self, arc_key: str) -> StoryArc:
        """Advance an arc to the next narrative phase.

        Args:
            arc_key: Unique identifier for the arc.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found, not active, or already at final phase.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        if arc.status != ArcStatus.ACTIVE:
            raise ValueError(f"Can only advance active arcs, current status: {arc.status.value}")

        current_idx = PHASE_ORDER.index(arc.current_phase)
        if current_idx >= len(PHASE_ORDER) - 1:
            raise ValueError(f"Arc is already at final phase: {arc.current_phase.value}")

        arc.current_phase = PHASE_ORDER[current_idx + 1]
        arc.phase_started_turn = self.current_turn
        arc.turns_in_phase = 0

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def set_phase(self, arc_key: str, phase: ArcPhase) -> StoryArc:
        """Set an arc to a specific phase.

        Args:
            arc_key: Unique identifier for the arc.
            phase: The phase to set.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found or not active.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        if arc.status != ArcStatus.ACTIVE:
            raise ValueError(f"Can only set phase on active arcs, current status: {arc.status.value}")

        arc.current_phase = phase
        arc.phase_started_turn = self.current_turn
        arc.turns_in_phase = 0

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def update_tension(self, arc_key: str, delta: int) -> StoryArc:
        """Adjust tension level by a delta amount.

        Args:
            arc_key: Unique identifier for the arc.
            delta: Amount to change tension (positive or negative).

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        arc.tension_level = self._clamp(arc.tension_level + delta, 0, 100)
        self.db.commit()
        self.db.refresh(arc)
        return arc

    def set_tension(self, arc_key: str, level: int) -> StoryArc:
        """Set tension level to a specific value.

        Args:
            arc_key: Unique identifier for the arc.
            level: New tension level (0-100).

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        arc.tension_level = self._clamp(level, 0, 100)
        self.db.commit()
        self.db.refresh(arc)
        return arc

    def plant_element(
        self,
        arc_key: str,
        element: str,
        description: str | None = None,
    ) -> StoryArc:
        """Plant a narrative element (Chekhov's gun) that must pay off later.

        Args:
            arc_key: Unique identifier for the arc.
            element: Short identifier for the element (e.g., 'mysterious_letter').
            description: Longer description of what was planted.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        planted = list(arc.planted_elements or [])
        planted.append({
            "element": element,
            "description": description,
            "planted_turn": self.current_turn,
            "resolved": False,
        })
        arc.planted_elements = planted
        flag_modified(arc, "planted_elements")

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def resolve_element(
        self,
        arc_key: str,
        element: str,
        resolution: str | None = None,
    ) -> StoryArc:
        """Mark a planted element as resolved (paid off).

        Args:
            arc_key: Unique identifier for the arc.
            element: Short identifier for the element to resolve.
            resolution: Description of how it paid off.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc or element not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        planted = list(arc.planted_elements or [])
        found = False
        for item in planted:
            if item.get("element") == element and not item.get("resolved"):
                item["resolved"] = True
                item["resolved_turn"] = self.current_turn
                item["resolution"] = resolution
                found = True
                break

        if not found:
            raise ValueError(f"Unresolved element '{element}' not found in arc '{arc_key}'")

        arc.planted_elements = planted
        flag_modified(arc, "planted_elements")

        # Move to resolved_elements list
        resolved = list(arc.resolved_elements or [])
        resolved.append({
            "element": element,
            "resolution": resolution,
            "resolved_turn": self.current_turn,
        })
        arc.resolved_elements = resolved
        flag_modified(arc, "resolved_elements")

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def get_unresolved_elements(self, arc_key: str) -> list[dict[str, Any]]:
        """Get all unresolved planted elements for an arc.

        Args:
            arc_key: Unique identifier for the arc.

        Returns:
            List of unresolved element dicts.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return []

        planted = arc.planted_elements or []
        return [e for e in planted if not e.get("resolved")]

    def set_next_beat_hint(self, arc_key: str, hint: str) -> StoryArc:
        """Set a hint for the GM about what should happen next.

        Args:
            arc_key: Unique identifier for the arc.
            hint: Suggestion for next narrative beat.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        arc.next_beat_hint = hint
        self.db.commit()
        self.db.refresh(arc)
        return arc

    def complete_arc(
        self,
        arc_key: str,
        outcome: str | None = None,
        success: bool = True,
    ) -> StoryArc:
        """Mark an arc as completed or failed.

        Args:
            arc_key: Unique identifier for the arc.
            outcome: Description of how the arc ended.
            success: If True, mark as completed; if False, mark as failed.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        arc.status = ArcStatus.COMPLETED if success else ArcStatus.FAILED
        arc.completed_turn = self.current_turn
        arc.outcome = outcome

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def abandon_arc(self, arc_key: str, reason: str | None = None) -> StoryArc:
        """Mark an arc as abandoned by player choice.

        Args:
            arc_key: Unique identifier for the arc.
            reason: Why the arc was abandoned.

        Returns:
            The updated StoryArc.

        Raises:
            ValueError: If arc not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            raise ValueError(f"Story arc '{arc_key}' not found")

        arc.status = ArcStatus.ABANDONED
        arc.completed_turn = self.current_turn
        arc.outcome = reason or "Abandoned by player"

        self.db.commit()
        self.db.refresh(arc)
        return arc

    def increment_turn_count(self, arc_key: str | None = None) -> None:
        """Increment turns_in_phase for active arcs.

        Call this once per game turn to track pacing.

        Args:
            arc_key: If provided, only increment for this arc.
                     If None, increment for all active arcs.
        """
        if arc_key:
            arc = self.get_arc(arc_key)
            if arc and arc.status == ArcStatus.ACTIVE:
                arc.turns_in_phase += 1
        else:
            for arc in self.get_active_arcs():
                arc.turns_in_phase += 1

        self.db.commit()

    def get_pacing_hints(self) -> list[PacingHint]:
        """Generate pacing suggestions for active arcs.

        Analyzes tension levels, phase durations, and unresolved elements
        to suggest narrative actions.

        Returns:
            List of pacing hints for the GM.
        """
        hints: list[PacingHint] = []

        for arc in self.get_active_arcs():
            # Check tension vs phase
            suggested_range = PHASE_TENSION_RANGES.get(arc.current_phase, (0, 100))
            min_tension, max_tension = suggested_range

            if arc.tension_level < min_tension - 10:
                hints.append(PacingHint(
                    arc_key=arc.arc_key,
                    message=f"Tension ({arc.tension_level}) is low for {arc.current_phase.value} phase",
                    urgency="medium",
                    suggested_action="Introduce a complication or raise stakes",
                ))
            elif arc.tension_level > max_tension + 10:
                hints.append(PacingHint(
                    arc_key=arc.arc_key,
                    message=f"Tension ({arc.tension_level}) is very high for {arc.current_phase.value} phase",
                    urgency="high" if arc.current_phase != ArcPhase.CLIMAX else "low",
                    suggested_action="Consider advancing to next phase",
                ))

            # Check phase duration
            min_turns = PHASE_MIN_TURNS.get(arc.current_phase, 1)
            if arc.turns_in_phase >= min_turns * 2:
                hints.append(PacingHint(
                    arc_key=arc.arc_key,
                    message=f"Arc has been in {arc.current_phase.value} for {arc.turns_in_phase} turns",
                    urgency="medium" if arc.turns_in_phase < min_turns * 3 else "high",
                    suggested_action="Consider advancing the narrative",
                ))

            # Check unresolved elements
            unresolved = self.get_unresolved_elements(arc.arc_key)
            if unresolved and arc.current_phase in (
                ArcPhase.RESOLUTION,
                ArcPhase.AFTERMATH,
            ):
                element_names = [e.get("element", "unknown") for e in unresolved]
                hints.append(PacingHint(
                    arc_key=arc.arc_key,
                    message=f"Unresolved elements in late phase: {', '.join(element_names)}",
                    urgency="high",
                    suggested_action="Resolve planted elements before arc ends",
                ))

            # Check for climax readiness
            if arc.current_phase == ArcPhase.ESCALATION and arc.tension_level >= 75:
                hints.append(PacingHint(
                    arc_key=arc.arc_key,
                    message="Arc is ready for climax",
                    urgency="medium",
                    suggested_action="Trigger the climactic confrontation",
                ))

        return hints

    def get_arc_summary(self, arc_key: str) -> ArcSummary | None:
        """Get a summary of an arc for GM context.

        Args:
            arc_key: Unique identifier for the arc.

        Returns:
            ArcSummary if arc found, None otherwise.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        unresolved = self.get_unresolved_elements(arc_key)
        element_names = [e.get("element", "unknown") for e in unresolved]

        return ArcSummary(
            arc_key=arc.arc_key,
            title=arc.title,
            arc_type=arc.arc_type.value,
            status=arc.status.value,
            phase=arc.current_phase.value,
            tension=arc.tension_level,
            turns_in_phase=arc.turns_in_phase,
            unresolved_elements=element_names,
            next_beat_hint=arc.next_beat_hint,
            stakes=arc.stakes,
        )

    def get_active_arcs_context(self) -> str:
        """Generate context string for active arcs (for GM prompt).

        Returns:
            Formatted string with active arc summaries.
        """
        arcs = self.get_active_arcs()
        if not arcs:
            return ""

        lines = ["## Active Story Arcs"]
        for arc in arcs:
            summary = self.get_arc_summary(arc.arc_key)
            if summary:
                lines.append(f"\n### {summary.title} ({summary.arc_type})")
                lines.append(f"Phase: {summary.phase} | Tension: {summary.tension}/100")
                if summary.stakes:
                    lines.append(f"Stakes: {summary.stakes}")
                if summary.unresolved_elements:
                    lines.append(f"Unresolved: {', '.join(summary.unresolved_elements)}")
                if summary.next_beat_hint:
                    lines.append(f"Next beat: {summary.next_beat_hint}")

        return "\n".join(lines)
