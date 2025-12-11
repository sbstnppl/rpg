"""Mystery Manager for tracking mysteries, clues, and revelations.

This manager handles mysteries that create engagement through:
- Hidden truths to uncover
- Clues that can be discovered
- Red herrings to mislead
- Revelation conditions and triggers
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.database.models.narrative import Mystery, StoryArc
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class Clue:
    """A clue for a mystery."""

    clue_id: str
    description: str
    location: str | None = None
    discovered: bool = False
    discovered_turn: int | None = None
    importance: str = "medium"  # low, medium, high, critical


@dataclass
class RedHerring:
    """A false lead to misdirect the player."""

    suspect: str
    evidence: str
    revealed_as_false: bool = False


@dataclass
class MysteryStatus:
    """Current status of a mystery."""

    mystery_key: str
    title: str
    clues_discovered: int
    total_clues: int
    progress_percentage: float
    is_solved: bool
    player_theory: str | None
    unresolved_clues: list[str]


class MysteryManager(BaseManager):
    """Manages mysteries, clues, and revelations.

    Mysteries create engagement through:
    - A hidden truth to uncover
    - Clues that can be discovered
    - Red herrings to mislead
    - Revelation conditions
    """

    def create_mystery(
        self,
        mystery_key: str,
        title: str,
        truth: str,
        truth_summary: str | None = None,
        clues: list[dict[str, Any]] | None = None,
        red_herrings: list[dict[str, Any]] | None = None,
        revelation_conditions: str | None = None,
        story_arc_id: int | None = None,
    ) -> Mystery:
        """Create a new mystery.

        Args:
            mystery_key: Unique identifier for the mystery.
            title: Human-readable title.
            truth: What actually happened (GM only).
            truth_summary: Short summary for quick reference.
            clues: List of clue dicts with 'clue_id', 'description', etc.
            red_herrings: List of false leads.
            revelation_conditions: What must happen for truth to be revealed.
            story_arc_id: Optional link to a story arc.

        Returns:
            The created Mystery.

        Raises:
            ValueError: If mystery_key already exists.
        """
        existing = self.get_mystery(mystery_key)
        if existing:
            raise ValueError(f"Mystery with key '{mystery_key}' already exists")

        # Ensure clues have required fields
        processed_clues = []
        if clues:
            for i, clue in enumerate(clues):
                processed_clues.append({
                    "clue_id": clue.get("clue_id", f"clue_{i}"),
                    "description": clue.get("description", ""),
                    "location": clue.get("location"),
                    "discovered": clue.get("discovered", False),
                    "discovered_turn": clue.get("discovered_turn"),
                    "importance": clue.get("importance", "medium"),
                })

        mystery = Mystery(
            session_id=self.session_id,
            mystery_key=mystery_key,
            title=title,
            truth=truth,
            truth_summary=truth_summary,
            clues=processed_clues if processed_clues else None,
            red_herrings=red_herrings,
            total_clues=len(processed_clues),
            clues_discovered=sum(1 for c in processed_clues if c.get("discovered")),
            revelation_conditions=revelation_conditions,
            story_arc_id=story_arc_id,
            created_turn=self.current_turn,
        )
        self.db.add(mystery)
        self.db.commit()
        self.db.refresh(mystery)
        return mystery

    def get_mystery(self, mystery_key: str) -> Mystery | None:
        """Get a mystery by key.

        Args:
            mystery_key: Unique identifier for the mystery.

        Returns:
            The Mystery if found, None otherwise.
        """
        return (
            self.db.query(Mystery)
            .filter(
                and_(
                    Mystery.session_id == self.session_id,
                    Mystery.mystery_key == mystery_key,
                )
            )
            .first()
        )

    def get_unsolved_mysteries(self) -> list[Mystery]:
        """Get all unsolved mysteries.

        Returns:
            List of unsolved mysteries.
        """
        return (
            self.db.query(Mystery)
            .filter(
                and_(
                    Mystery.session_id == self.session_id,
                    Mystery.is_solved == False,  # noqa: E712
                )
            )
            .all()
        )

    def get_mysteries_by_arc(self, story_arc_id: int) -> list[Mystery]:
        """Get all mysteries linked to a story arc.

        Args:
            story_arc_id: ID of the story arc.

        Returns:
            List of linked mysteries.
        """
        return (
            self.db.query(Mystery)
            .filter(
                and_(
                    Mystery.session_id == self.session_id,
                    Mystery.story_arc_id == story_arc_id,
                )
            )
            .all()
        )

    def add_clue(
        self,
        mystery_key: str,
        clue_id: str,
        description: str,
        location: str | None = None,
        importance: str = "medium",
        discovered: bool = False,
    ) -> Mystery:
        """Add a new clue to a mystery.

        Args:
            mystery_key: Unique identifier for the mystery.
            clue_id: Unique identifier for the clue.
            description: Description of the clue.
            location: Where the clue can be found.
            importance: How important this clue is (low/medium/high/critical).
            discovered: Whether already discovered.

        Returns:
            The updated Mystery.

        Raises:
            ValueError: If mystery not found or clue_id already exists.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        clues = list(mystery.clues or [])

        # Check for duplicate clue_id
        if any(c.get("clue_id") == clue_id for c in clues):
            raise ValueError(f"Clue '{clue_id}' already exists in mystery '{mystery_key}'")

        clues.append({
            "clue_id": clue_id,
            "description": description,
            "location": location,
            "importance": importance,
            "discovered": discovered,
            "discovered_turn": self.current_turn if discovered else None,
        })

        mystery.clues = clues
        mystery.total_clues = len(clues)
        if discovered:
            mystery.clues_discovered += 1
        flag_modified(mystery, "clues")

        self.db.commit()
        self.db.refresh(mystery)
        return mystery

    def discover_clue(
        self,
        mystery_key: str,
        clue_id: str,
    ) -> tuple[Mystery, dict[str, Any]]:
        """Mark a clue as discovered.

        Args:
            mystery_key: Unique identifier for the mystery.
            clue_id: Identifier of the clue to discover.

        Returns:
            Tuple of (updated Mystery, discovered clue dict).

        Raises:
            ValueError: If mystery or clue not found, or already discovered.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        clues = list(mystery.clues or [])
        discovered_clue = None

        for clue in clues:
            if clue.get("clue_id") == clue_id:
                if clue.get("discovered"):
                    raise ValueError(f"Clue '{clue_id}' already discovered")
                clue["discovered"] = True
                clue["discovered_turn"] = self.current_turn
                discovered_clue = clue
                break

        if not discovered_clue:
            raise ValueError(f"Clue '{clue_id}' not found in mystery '{mystery_key}'")

        mystery.clues = clues
        mystery.clues_discovered += 1
        flag_modified(mystery, "clues")

        self.db.commit()
        self.db.refresh(mystery)
        return mystery, discovered_clue

    def get_discovered_clues(self, mystery_key: str) -> list[dict[str, Any]]:
        """Get all discovered clues for a mystery.

        Args:
            mystery_key: Unique identifier for the mystery.

        Returns:
            List of discovered clue dicts.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            return []

        clues = mystery.clues or []
        return [c for c in clues if c.get("discovered")]

    def get_undiscovered_clues(self, mystery_key: str) -> list[dict[str, Any]]:
        """Get all undiscovered clues for a mystery.

        Args:
            mystery_key: Unique identifier for the mystery.

        Returns:
            List of undiscovered clue dicts.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            return []

        clues = mystery.clues or []
        return [c for c in clues if not c.get("discovered")]

    def add_red_herring(
        self,
        mystery_key: str,
        suspect: str,
        evidence: str,
    ) -> Mystery:
        """Add a red herring to misdirect the player.

        Args:
            mystery_key: Unique identifier for the mystery.
            suspect: Who or what the false lead points to.
            evidence: The misleading evidence.

        Returns:
            The updated Mystery.

        Raises:
            ValueError: If mystery not found.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        red_herrings = list(mystery.red_herrings or [])
        red_herrings.append({
            "suspect": suspect,
            "evidence": evidence,
            "revealed_as_false": False,
        })

        mystery.red_herrings = red_herrings
        flag_modified(mystery, "red_herrings")

        self.db.commit()
        self.db.refresh(mystery)
        return mystery

    def reveal_red_herring(
        self,
        mystery_key: str,
        suspect: str,
    ) -> Mystery:
        """Mark a red herring as revealed to be false.

        Args:
            mystery_key: Unique identifier for the mystery.
            suspect: The suspect to reveal as false lead.

        Returns:
            The updated Mystery.

        Raises:
            ValueError: If mystery or red herring not found.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        red_herrings = list(mystery.red_herrings or [])
        found = False

        for herring in red_herrings:
            if herring.get("suspect") == suspect:
                herring["revealed_as_false"] = True
                herring["revealed_turn"] = self.current_turn
                found = True
                break

        if not found:
            raise ValueError(f"Red herring with suspect '{suspect}' not found")

        mystery.red_herrings = red_herrings
        flag_modified(mystery, "red_herrings")

        self.db.commit()
        self.db.refresh(mystery)
        return mystery

    def set_player_theory(
        self,
        mystery_key: str,
        theory: str,
    ) -> Mystery:
        """Set the player's current theory about the mystery.

        Args:
            mystery_key: Unique identifier for the mystery.
            theory: What the player currently believes.

        Returns:
            The updated Mystery.

        Raises:
            ValueError: If mystery not found.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        mystery.player_theory = theory
        self.db.commit()
        self.db.refresh(mystery)
        return mystery

    def solve_mystery(
        self,
        mystery_key: str,
    ) -> Mystery:
        """Mark a mystery as solved.

        Args:
            mystery_key: Unique identifier for the mystery.

        Returns:
            The updated Mystery.

        Raises:
            ValueError: If mystery not found or already solved.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        if mystery.is_solved:
            raise ValueError(f"Mystery '{mystery_key}' is already solved")

        mystery.is_solved = True
        mystery.solved_turn = self.current_turn

        self.db.commit()
        self.db.refresh(mystery)
        return mystery

    def check_revelation_ready(self, mystery_key: str) -> bool:
        """Check if a mystery is ready for revelation.

        A mystery is ready for revelation when:
        - All critical clues have been discovered
        - OR a high percentage of clues discovered (>= 75%)

        Args:
            mystery_key: Unique identifier for the mystery.

        Returns:
            True if ready for revelation.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery or mystery.is_solved:
            return False

        clues = mystery.clues or []
        if not clues:
            return True  # No clues means truth can be revealed anytime

        # Check if all critical clues discovered
        critical_clues = [c for c in clues if c.get("importance") == "critical"]
        if critical_clues:
            all_critical_discovered = all(c.get("discovered") for c in critical_clues)
            if all_critical_discovered:
                return True

        # Check percentage threshold
        if mystery.total_clues > 0:
            percentage = mystery.clues_discovered / mystery.total_clues
            return percentage >= 0.75

        return False

    def get_mystery_status(self, mystery_key: str) -> MysteryStatus | None:
        """Get the current status of a mystery.

        Args:
            mystery_key: Unique identifier for the mystery.

        Returns:
            MysteryStatus if found, None otherwise.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            return None

        undiscovered = self.get_undiscovered_clues(mystery_key)
        progress = 0.0
        if mystery.total_clues > 0:
            progress = (mystery.clues_discovered / mystery.total_clues) * 100

        return MysteryStatus(
            mystery_key=mystery.mystery_key,
            title=mystery.title,
            clues_discovered=mystery.clues_discovered,
            total_clues=mystery.total_clues,
            progress_percentage=round(progress, 1),
            is_solved=mystery.is_solved,
            player_theory=mystery.player_theory,
            unresolved_clues=[c.get("clue_id", "unknown") for c in undiscovered],
        )

    def get_mysteries_context(self) -> str:
        """Generate context string for unsolved mysteries (for GM prompt).

        Returns:
            Formatted string with mystery summaries.
        """
        mysteries = self.get_unsolved_mysteries()
        if not mysteries:
            return ""

        lines = ["## Active Mysteries"]
        for mystery in mysteries:
            status = self.get_mystery_status(mystery.mystery_key)
            if status:
                lines.append(f"\n### {mystery.title}")
                lines.append(f"Progress: {status.clues_discovered}/{status.total_clues} clues ({status.progress_percentage}%)")
                if status.player_theory:
                    lines.append(f"Player believes: {status.player_theory}")
                if self.check_revelation_ready(mystery.mystery_key):
                    lines.append("**Ready for revelation!**")

        return "\n".join(lines)

    def get_clue_at_location(
        self,
        mystery_key: str,
        location: str,
    ) -> list[dict[str, Any]]:
        """Get undiscovered clues at a specific location.

        Args:
            mystery_key: Unique identifier for the mystery.
            location: Location to check.

        Returns:
            List of undiscovered clues at this location.
        """
        undiscovered = self.get_undiscovered_clues(mystery_key)
        return [c for c in undiscovered if c.get("location") == location]

    def get_all_clues_at_location(self, location: str) -> list[tuple[str, dict[str, Any]]]:
        """Get all undiscovered clues at a location across all mysteries.

        Args:
            location: Location to check.

        Returns:
            List of (mystery_key, clue_dict) tuples.
        """
        result = []
        for mystery in self.get_unsolved_mysteries():
            clues = self.get_clue_at_location(mystery.mystery_key, location)
            for clue in clues:
                result.append((mystery.mystery_key, clue))
        return result

    def link_to_story_arc(
        self,
        mystery_key: str,
        story_arc_id: int,
    ) -> Mystery:
        """Link a mystery to a story arc.

        Args:
            mystery_key: Unique identifier for the mystery.
            story_arc_id: ID of the story arc.

        Returns:
            The updated Mystery.

        Raises:
            ValueError: If mystery not found.
        """
        mystery = self.get_mystery(mystery_key)
        if not mystery:
            raise ValueError(f"Mystery '{mystery_key}' not found")

        mystery.story_arc_id = story_arc_id
        self.db.commit()
        self.db.refresh(mystery)
        return mystery
