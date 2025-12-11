"""Conflict Manager for tracking conflicts and escalation levels.

This manager handles conflicts that can escalate or de-escalate through:
- Tracking escalation levels (tension → war)
- Defining triggers for escalation/de-escalation
- Suggesting interventions
- Linking to story arcs
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.database.models.narrative import Conflict, ConflictLevel
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Level progression order
LEVEL_ORDER = [
    ConflictLevel.TENSION,
    ConflictLevel.DISPUTE,
    ConflictLevel.CONFRONTATION,
    ConflictLevel.HOSTILITY,
    ConflictLevel.CRISIS,
    ConflictLevel.WAR,
]

# Numeric values for levels
LEVEL_NUMERIC = {
    ConflictLevel.TENSION: 1,
    ConflictLevel.DISPUTE: 2,
    ConflictLevel.CONFRONTATION: 3,
    ConflictLevel.HOSTILITY: 4,
    ConflictLevel.CRISIS: 5,
    ConflictLevel.WAR: 6,
}

# Default level descriptions
DEFAULT_LEVEL_DESCRIPTIONS = {
    "tension": "Underlying friction and distrust between parties.",
    "dispute": "Open disagreement and verbal confrontations.",
    "confrontation": "Direct opposition and refusal to cooperate.",
    "hostility": "Active antagonism and occasional violence.",
    "crisis": "Critical breaking point with major incidents.",
    "war": "Full-scale open conflict.",
}


@dataclass
class EscalationEvent:
    """Record of an escalation or de-escalation."""

    from_level: str
    to_level: str
    turn: int
    trigger: str | None = None


@dataclass
class ConflictStatus:
    """Current status of a conflict."""

    conflict_key: str
    title: str
    level: str
    level_numeric: int
    is_active: bool
    is_resolved: bool
    party_a: str | None
    party_b: str | None
    current_description: str | None
    escalation_risk: list[str]  # Triggered escalation triggers
    de_escalation_opportunity: list[str]  # Triggered de-escalation triggers


class ConflictManager(BaseManager):
    """Manages conflicts and escalation dynamics.

    Conflicts drive drama by:
    - Tracking escalation levels
    - Defining triggers for escalation/de-escalation
    - Suggesting interventions
    """

    def create_conflict(
        self,
        conflict_key: str,
        title: str,
        description: str | None = None,
        party_a_key: str | None = None,
        party_b_key: str | None = None,
        initial_level: ConflictLevel = ConflictLevel.TENSION,
        escalation_triggers: list[str] | None = None,
        de_escalation_triggers: list[str] | None = None,
        level_descriptions: dict[str, str] | None = None,
        story_arc_id: int | None = None,
    ) -> Conflict:
        """Create a new conflict.

        Args:
            conflict_key: Unique identifier for the conflict.
            title: Human-readable title.
            description: Overview of the conflict.
            party_a_key: Entity/faction key for first party.
            party_b_key: Entity/faction key for second party.
            initial_level: Starting escalation level.
            escalation_triggers: Conditions that escalate the conflict.
            de_escalation_triggers: Conditions that reduce tension.
            level_descriptions: Custom descriptions for each level.
            story_arc_id: Optional link to a story arc.

        Returns:
            The created Conflict.

        Raises:
            ValueError: If conflict_key already exists.
        """
        existing = self.get_conflict(conflict_key)
        if existing:
            raise ValueError(f"Conflict with key '{conflict_key}' already exists")

        conflict = Conflict(
            session_id=self.session_id,
            conflict_key=conflict_key,
            title=title,
            description=description,
            party_a_key=party_a_key,
            party_b_key=party_b_key,
            current_level=initial_level,
            level_numeric=LEVEL_NUMERIC[initial_level],
            escalation_triggers=escalation_triggers,
            de_escalation_triggers=de_escalation_triggers,
            level_descriptions=level_descriptions or DEFAULT_LEVEL_DESCRIPTIONS.copy(),
            story_arc_id=story_arc_id,
            started_turn=self.current_turn,
        )
        self.db.add(conflict)
        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def get_conflict(self, conflict_key: str) -> Conflict | None:
        """Get a conflict by key.

        Args:
            conflict_key: Unique identifier for the conflict.

        Returns:
            The Conflict if found, None otherwise.
        """
        return (
            self.db.query(Conflict)
            .filter(
                and_(
                    Conflict.session_id == self.session_id,
                    Conflict.conflict_key == conflict_key,
                )
            )
            .first()
        )

    def get_active_conflicts(self) -> list[Conflict]:
        """Get all active conflicts.

        Returns:
            List of active conflicts.
        """
        return (
            self.db.query(Conflict)
            .filter(
                and_(
                    Conflict.session_id == self.session_id,
                    Conflict.is_active == True,  # noqa: E712
                )
            )
            .order_by(Conflict.level_numeric.desc())
            .all()
        )

    def get_conflicts_by_party(self, party_key: str) -> list[Conflict]:
        """Get all conflicts involving a specific party.

        Args:
            party_key: Entity/faction key.

        Returns:
            List of conflicts involving this party.
        """
        return (
            self.db.query(Conflict)
            .filter(
                and_(
                    Conflict.session_id == self.session_id,
                    (Conflict.party_a_key == party_key) | (Conflict.party_b_key == party_key),
                )
            )
            .all()
        )

    def get_conflicts_at_level(self, level: ConflictLevel) -> list[Conflict]:
        """Get all active conflicts at a specific level.

        Args:
            level: Escalation level to filter by.

        Returns:
            List of conflicts at this level.
        """
        return (
            self.db.query(Conflict)
            .filter(
                and_(
                    Conflict.session_id == self.session_id,
                    Conflict.is_active == True,  # noqa: E712
                    Conflict.current_level == level,
                )
            )
            .all()
        )

    def escalate(
        self,
        conflict_key: str,
        trigger: str | None = None,
    ) -> tuple[Conflict, EscalationEvent | None]:
        """Escalate a conflict to the next level.

        Args:
            conflict_key: Unique identifier for the conflict.
            trigger: What caused the escalation.

        Returns:
            Tuple of (updated Conflict, EscalationEvent or None if already at max).

        Raises:
            ValueError: If conflict not found or not active.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        if not conflict.is_active:
            raise ValueError(f"Conflict '{conflict_key}' is not active")

        current_idx = LEVEL_ORDER.index(conflict.current_level)
        if current_idx >= len(LEVEL_ORDER) - 1:
            return conflict, None  # Already at maximum

        old_level = conflict.current_level
        new_level = LEVEL_ORDER[current_idx + 1]

        conflict.current_level = new_level
        conflict.level_numeric = LEVEL_NUMERIC[new_level]
        conflict.last_escalation_turn = self.current_turn

        self.db.commit()
        self.db.refresh(conflict)

        event = EscalationEvent(
            from_level=old_level.value,
            to_level=new_level.value,
            turn=self.current_turn,
            trigger=trigger,
        )
        return conflict, event

    def de_escalate(
        self,
        conflict_key: str,
        trigger: str | None = None,
    ) -> tuple[Conflict, EscalationEvent | None]:
        """De-escalate a conflict to a lower level.

        Args:
            conflict_key: Unique identifier for the conflict.
            trigger: What caused the de-escalation.

        Returns:
            Tuple of (updated Conflict, EscalationEvent or None if already at min).

        Raises:
            ValueError: If conflict not found or not active.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        if not conflict.is_active:
            raise ValueError(f"Conflict '{conflict_key}' is not active")

        current_idx = LEVEL_ORDER.index(conflict.current_level)
        if current_idx <= 0:
            return conflict, None  # Already at minimum

        old_level = conflict.current_level
        new_level = LEVEL_ORDER[current_idx - 1]

        conflict.current_level = new_level
        conflict.level_numeric = LEVEL_NUMERIC[new_level]

        self.db.commit()
        self.db.refresh(conflict)

        event = EscalationEvent(
            from_level=old_level.value,
            to_level=new_level.value,
            turn=self.current_turn,
            trigger=trigger,
        )
        return conflict, event

    def set_level(
        self,
        conflict_key: str,
        level: ConflictLevel,
    ) -> Conflict:
        """Set conflict to a specific level.

        Args:
            conflict_key: Unique identifier for the conflict.
            level: Level to set.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        conflict.current_level = level
        conflict.level_numeric = LEVEL_NUMERIC[level]
        conflict.last_escalation_turn = self.current_turn

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def add_escalation_trigger(
        self,
        conflict_key: str,
        trigger: str,
    ) -> Conflict:
        """Add an escalation trigger.

        Args:
            conflict_key: Unique identifier for the conflict.
            trigger: Condition that could escalate the conflict.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        triggers = list(conflict.escalation_triggers or [])
        triggers.append(trigger)
        conflict.escalation_triggers = triggers
        flag_modified(conflict, "escalation_triggers")

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def add_de_escalation_trigger(
        self,
        conflict_key: str,
        trigger: str,
    ) -> Conflict:
        """Add a de-escalation trigger.

        Args:
            conflict_key: Unique identifier for the conflict.
            trigger: Condition that could de-escalate the conflict.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        triggers = list(conflict.de_escalation_triggers or [])
        triggers.append(trigger)
        conflict.de_escalation_triggers = triggers
        flag_modified(conflict, "de_escalation_triggers")

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def set_level_description(
        self,
        conflict_key: str,
        level: ConflictLevel,
        description: str,
    ) -> Conflict:
        """Set custom description for a specific level.

        Args:
            conflict_key: Unique identifier for the conflict.
            level: Level to describe.
            description: Description of what this level looks like.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        descriptions = dict(conflict.level_descriptions or {})
        descriptions[level.value] = description
        conflict.level_descriptions = descriptions
        flag_modified(conflict, "level_descriptions")

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def resolve_conflict(
        self,
        conflict_key: str,
        resolution: str,
    ) -> Conflict:
        """Mark a conflict as resolved.

        Args:
            conflict_key: Unique identifier for the conflict.
            resolution: How the conflict was resolved.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found or already resolved.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        if conflict.is_resolved:
            raise ValueError(f"Conflict '{conflict_key}' is already resolved")

        conflict.is_active = False
        conflict.is_resolved = True
        conflict.resolution = resolution
        conflict.resolved_turn = self.current_turn

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def pause_conflict(self, conflict_key: str) -> Conflict:
        """Pause an active conflict without resolving it.

        Args:
            conflict_key: Unique identifier for the conflict.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found or not active.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        if not conflict.is_active:
            raise ValueError(f"Conflict '{conflict_key}' is not active")

        conflict.is_active = False

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def reactivate_conflict(self, conflict_key: str) -> Conflict:
        """Reactivate a paused conflict.

        Args:
            conflict_key: Unique identifier for the conflict.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found or already resolved.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        if conflict.is_resolved:
            raise ValueError(f"Cannot reactivate resolved conflict '{conflict_key}'")

        conflict.is_active = True

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    def get_conflict_status(self, conflict_key: str) -> ConflictStatus | None:
        """Get current status of a conflict.

        Args:
            conflict_key: Unique identifier for the conflict.

        Returns:
            ConflictStatus if found, None otherwise.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            return None

        descriptions = conflict.level_descriptions or {}
        current_desc = descriptions.get(conflict.current_level.value)

        return ConflictStatus(
            conflict_key=conflict.conflict_key,
            title=conflict.title,
            level=conflict.current_level.value,
            level_numeric=conflict.level_numeric,
            is_active=conflict.is_active,
            is_resolved=conflict.is_resolved,
            party_a=conflict.party_a_key,
            party_b=conflict.party_b_key,
            current_description=current_desc,
            escalation_risk=list(conflict.escalation_triggers or []),
            de_escalation_opportunity=list(conflict.de_escalation_triggers or []),
        )

    def get_high_tension_conflicts(self) -> list[Conflict]:
        """Get conflicts at crisis or war level.

        Returns:
            List of high-tension conflicts.
        """
        return (
            self.db.query(Conflict)
            .filter(
                and_(
                    Conflict.session_id == self.session_id,
                    Conflict.is_active == True,  # noqa: E712
                    Conflict.level_numeric >= LEVEL_NUMERIC[ConflictLevel.CRISIS],
                )
            )
            .all()
        )

    def get_conflicts_context(self) -> str:
        """Generate context string for active conflicts (for GM prompt).

        Returns:
            Formatted string with conflict summaries.
        """
        conflicts = self.get_active_conflicts()
        if not conflicts:
            return ""

        lines = ["## Active Conflicts"]
        for conflict in conflicts:
            status = self.get_conflict_status(conflict.conflict_key)
            if status:
                parties = ""
                if status.party_a and status.party_b:
                    parties = f" ({status.party_a} vs {status.party_b})"
                elif status.party_a:
                    parties = f" (involving {status.party_a})"

                lines.append(f"\n### {conflict.title}{parties}")
                lines.append(f"Level: {status.level.upper()} ({status.level_numeric}/6)")
                if status.current_description:
                    lines.append(f"Status: {status.current_description}")
                if status.level_numeric >= 5:
                    lines.append("**CRITICAL - Immediate attention needed!**")

        return "\n".join(lines)

    def link_to_story_arc(
        self,
        conflict_key: str,
        story_arc_id: int,
    ) -> Conflict:
        """Link a conflict to a story arc.

        Args:
            conflict_key: Unique identifier for the conflict.
            story_arc_id: ID of the story arc.

        Returns:
            The updated Conflict.

        Raises:
            ValueError: If conflict not found.
        """
        conflict = self.get_conflict(conflict_key)
        if not conflict:
            raise ValueError(f"Conflict '{conflict_key}' not found")

        conflict.story_arc_id = story_arc_id
        self.db.commit()
        self.db.refresh(conflict)
        return conflict
