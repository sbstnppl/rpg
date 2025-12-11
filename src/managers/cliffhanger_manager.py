"""Cliffhanger Manager for detecting dramatic stopping points.

This manager analyzes scene state for dramatic tension and identifies
ideal session stopping points that leave players eager for more.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.narrative import (
    ArcPhase,
    ArcStatus,
    ConflictLevel,
    StoryArc,
    Conflict,
    Mystery,
)
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Dramatic tension scores by arc phase
PHASE_TENSION_SCORES = {
    ArcPhase.SETUP: 20,
    ArcPhase.RISING_ACTION: 40,
    ArcPhase.MIDPOINT: 60,
    ArcPhase.ESCALATION: 75,
    ArcPhase.CLIMAX: 95,
    ArcPhase.FALLING_ACTION: 50,
    ArcPhase.RESOLUTION: 30,
    ArcPhase.AFTERMATH: 15,
}

# Conflict level tension scores
CONFLICT_TENSION_SCORES = {
    ConflictLevel.TENSION: 15,
    ConflictLevel.DISPUTE: 30,
    ConflictLevel.CONFRONTATION: 50,
    ConflictLevel.HOSTILITY: 70,
    ConflictLevel.CRISIS: 90,
    ConflictLevel.WAR: 100,
}


@dataclass
class DramaticMoment:
    """A detected dramatic moment in the scene."""

    source: str  # "story_arc", "conflict", "mystery", "custom"
    source_key: str  # arc_key, conflict_key, etc.
    description: str
    tension_score: int  # 0-100
    cliffhanger_potential: str  # "low", "medium", "high", "perfect"


@dataclass
class CliffhangerSuggestion:
    """A suggestion for a session-ending cliffhanger."""

    hook_type: str  # "revelation", "threat", "choice", "mystery", "arrival"
    description: str
    tension_level: int  # 0-100
    why_effective: str
    follow_up_hook: str  # What to tease for next session


@dataclass
class SceneTensionAnalysis:
    """Analysis of current scene tension."""

    overall_tension: int  # 0-100
    primary_source: str  # What's driving the tension
    dramatic_moments: list[DramaticMoment]
    is_good_stopping_point: bool
    stopping_recommendation: str
    suggested_cliffhangers: list[CliffhangerSuggestion]


class CliffhangerManager(BaseManager):
    """Detects dramatic tension and identifies cliffhanger opportunities.

    Analyzes:
    - Story arc phases and tension levels
    - Active conflicts and their escalation
    - Mystery progress and revelation readiness
    - Scene context for dramatic potential
    """

    def analyze_scene_tension(
        self,
        scene_keywords: list[str] | None = None,
        recent_events: list[str] | None = None,
    ) -> SceneTensionAnalysis:
        """Analyze current scene for dramatic tension.

        Args:
            scene_keywords: Keywords describing current scene.
            recent_events: Recent events that might affect tension.

        Returns:
            Complete tension analysis with cliffhanger suggestions.
        """
        dramatic_moments: list[DramaticMoment] = []
        tension_scores: list[int] = []

        # Analyze story arcs
        arc_moments = self._analyze_story_arcs()
        dramatic_moments.extend(arc_moments)
        tension_scores.extend(m.tension_score for m in arc_moments)

        # Analyze conflicts
        conflict_moments = self._analyze_conflicts()
        dramatic_moments.extend(conflict_moments)
        tension_scores.extend(m.tension_score for m in conflict_moments)

        # Analyze mysteries
        mystery_moments = self._analyze_mysteries()
        dramatic_moments.extend(mystery_moments)
        tension_scores.extend(m.tension_score for m in mystery_moments)

        # Calculate overall tension
        overall_tension = 0
        if tension_scores:
            # Weight towards highest tensions
            sorted_scores = sorted(tension_scores, reverse=True)
            if len(sorted_scores) >= 3:
                overall_tension = int(
                    sorted_scores[0] * 0.5 +
                    sorted_scores[1] * 0.3 +
                    sorted_scores[2] * 0.2
                )
            elif len(sorted_scores) == 2:
                overall_tension = int(sorted_scores[0] * 0.6 + sorted_scores[1] * 0.4)
            else:
                overall_tension = sorted_scores[0]

        # Determine primary tension source
        primary_source = "none"
        if dramatic_moments:
            highest = max(dramatic_moments, key=lambda m: m.tension_score)
            primary_source = f"{highest.source}: {highest.source_key}"

        # Determine if good stopping point
        is_good_stopping_point = self._is_good_stopping_point(
            dramatic_moments, overall_tension
        )

        # Generate stopping recommendation
        stopping_recommendation = self._generate_stopping_recommendation(
            dramatic_moments, overall_tension, is_good_stopping_point
        )

        # Generate cliffhanger suggestions
        suggested_cliffhangers = self._generate_cliffhanger_suggestions(
            dramatic_moments, overall_tension
        )

        return SceneTensionAnalysis(
            overall_tension=overall_tension,
            primary_source=primary_source,
            dramatic_moments=dramatic_moments,
            is_good_stopping_point=is_good_stopping_point,
            stopping_recommendation=stopping_recommendation,
            suggested_cliffhangers=suggested_cliffhangers,
        )

    def get_cliffhanger_hooks(self) -> list[CliffhangerSuggestion]:
        """Get cliffhanger suggestions based on current game state.

        Returns:
            List of cliffhanger suggestions ordered by effectiveness.
        """
        analysis = self.analyze_scene_tension()
        return sorted(
            analysis.suggested_cliffhangers,
            key=lambda c: c.tension_level,
            reverse=True,
        )

    def is_cliffhanger_ready(self) -> tuple[bool, str]:
        """Check if current state is good for a session-ending cliffhanger.

        Returns:
            Tuple of (is_ready, reason).
        """
        analysis = self.analyze_scene_tension()
        if analysis.overall_tension >= 70:
            return True, f"High tension ({analysis.overall_tension}/100) from {analysis.primary_source}"
        elif analysis.overall_tension >= 50 and analysis.is_good_stopping_point:
            return True, "Moderate tension with good dramatic moment"
        else:
            return False, f"Tension too low ({analysis.overall_tension}/100) for impactful cliffhanger"

    def _analyze_story_arcs(self) -> list[DramaticMoment]:
        """Analyze active story arcs for dramatic moments."""
        moments: list[DramaticMoment] = []

        arcs = (
            self.db.query(StoryArc)
            .filter(
                StoryArc.session_id == self.session_id,
                StoryArc.status == ArcStatus.ACTIVE,
            )
            .all()
        )

        for arc in arcs:
            phase_score = PHASE_TENSION_SCORES.get(arc.current_phase, 30)
            # Blend phase score with arc's own tension
            blended_score = int(phase_score * 0.4 + arc.tension_level * 0.6)

            # Determine cliffhanger potential
            potential = "low"
            if arc.current_phase in (ArcPhase.ESCALATION, ArcPhase.CLIMAX):
                potential = "perfect"
            elif arc.current_phase == ArcPhase.MIDPOINT:
                potential = "high"
            elif arc.current_phase == ArcPhase.RISING_ACTION and arc.tension_level >= 50:
                potential = "medium"

            moments.append(DramaticMoment(
                source="story_arc",
                source_key=arc.arc_key,
                description=f"{arc.title} - {arc.current_phase.value} phase, tension {arc.tension_level}%",
                tension_score=blended_score,
                cliffhanger_potential=potential,
            ))

        return moments

    def _analyze_conflicts(self) -> list[DramaticMoment]:
        """Analyze active conflicts for dramatic moments."""
        moments: list[DramaticMoment] = []

        conflicts = (
            self.db.query(Conflict)
            .filter(
                Conflict.session_id == self.session_id,
                Conflict.is_active == True,  # noqa: E712
            )
            .all()
        )

        for conflict in conflicts:
            score = CONFLICT_TENSION_SCORES.get(conflict.current_level, 30)

            potential = "low"
            if conflict.current_level in (ConflictLevel.CRISIS, ConflictLevel.WAR):
                potential = "perfect"
            elif conflict.current_level == ConflictLevel.HOSTILITY:
                potential = "high"
            elif conflict.current_level == ConflictLevel.CONFRONTATION:
                potential = "medium"

            moments.append(DramaticMoment(
                source="conflict",
                source_key=conflict.conflict_key,
                description=f"{conflict.title} - {conflict.current_level.value} level",
                tension_score=score,
                cliffhanger_potential=potential,
            ))

        return moments

    def _analyze_mysteries(self) -> list[DramaticMoment]:
        """Analyze unsolved mysteries for dramatic moments."""
        moments: list[DramaticMoment] = []

        mysteries = (
            self.db.query(Mystery)
            .filter(
                Mystery.session_id == self.session_id,
                Mystery.is_solved == False,  # noqa: E712
            )
            .all()
        )

        for mystery in mysteries:
            # Calculate tension based on clue discovery progress
            progress = 0
            if mystery.total_clues > 0:
                progress = mystery.clues_discovered / mystery.total_clues

            # Mysteries near revelation are high tension
            if progress >= 0.75:
                score = 80
                potential = "perfect"  # Revelation cliffhanger!
            elif progress >= 0.5:
                score = 55
                potential = "high"
            elif progress >= 0.25:
                score = 35
                potential = "medium"
            else:
                score = 20
                potential = "low"

            moments.append(DramaticMoment(
                source="mystery",
                source_key=mystery.mystery_key,
                description=f"{mystery.title} - {mystery.clues_discovered}/{mystery.total_clues} clues",
                tension_score=score,
                cliffhanger_potential=potential,
            ))

        return moments

    def _is_good_stopping_point(
        self,
        moments: list[DramaticMoment],
        overall_tension: int,
    ) -> bool:
        """Determine if current state is a good stopping point."""
        # Good stopping points have high-potential cliffhangers
        perfect_moments = [m for m in moments if m.cliffhanger_potential == "perfect"]
        high_moments = [m for m in moments if m.cliffhanger_potential == "high"]

        if perfect_moments:
            return True
        if high_moments and overall_tension >= 50:
            return True
        if overall_tension >= 70:
            return True

        return False

    def _generate_stopping_recommendation(
        self,
        moments: list[DramaticMoment],
        overall_tension: int,
        is_good_stopping_point: bool,
    ) -> str:
        """Generate a recommendation about stopping the session."""
        if not moments:
            return "No active dramatic elements. Any stopping point is fine."

        if not is_good_stopping_point:
            return f"Tension is low ({overall_tension}/100). Continue to build drama before stopping."

        # Find the best moment to leverage
        best = max(moments, key=lambda m: m.tension_score)

        if best.cliffhanger_potential == "perfect":
            return f"PERFECT cliffhanger opportunity! Use {best.source_key}: {best.description}"
        elif best.cliffhanger_potential == "high":
            return f"Strong cliffhanger potential from {best.source_key}. Good time to stop."
        else:
            return f"Moderate tension ({overall_tension}/100). Can stop here or build more drama."

    def _generate_cliffhanger_suggestions(
        self,
        moments: list[DramaticMoment],
        overall_tension: int,
    ) -> list[CliffhangerSuggestion]:
        """Generate specific cliffhanger suggestions."""
        suggestions: list[CliffhangerSuggestion] = []

        for moment in moments:
            if moment.cliffhanger_potential in ("perfect", "high"):
                if moment.source == "story_arc":
                    suggestions.append(CliffhangerSuggestion(
                        hook_type="revelation",
                        description=f"End on a revelation in {moment.source_key}",
                        tension_level=moment.tension_score,
                        why_effective="Story arc at peak tension creates anticipation",
                        follow_up_hook=f"What happens next in {moment.source_key}?",
                    ))

                elif moment.source == "conflict":
                    suggestions.append(CliffhangerSuggestion(
                        hook_type="threat",
                        description=f"End as {moment.source_key} reaches breaking point",
                        tension_level=moment.tension_score,
                        why_effective="Unresolved conflict creates urgency to return",
                        follow_up_hook="Will they choose fight or flight?",
                    ))

                elif moment.source == "mystery":
                    suggestions.append(CliffhangerSuggestion(
                        hook_type="mystery",
                        description=f"End just before solving {moment.source_key}",
                        tension_level=moment.tension_score,
                        why_effective="Near-solved mystery creates 'need to know' compulsion",
                        follow_up_hook="The truth is almost within reach...",
                    ))

        # Add generic suggestions if we have tension but no specific hooks
        if overall_tension >= 50 and not suggestions:
            suggestions.append(CliffhangerSuggestion(
                hook_type="choice",
                description="End on a difficult choice",
                tension_level=overall_tension,
                why_effective="Unresolved decisions create player investment",
                follow_up_hook="What will they decide?",
            ))

            suggestions.append(CliffhangerSuggestion(
                hook_type="arrival",
                description="End with an unexpected arrival or discovery",
                tension_level=overall_tension,
                why_effective="New elements create curiosity",
                follow_up_hook="Who or what has appeared?",
            ))

        return suggestions

    def get_tension_context(self) -> str:
        """Generate GM context for current dramatic tension.

        Returns:
            Formatted string with tension analysis.
        """
        analysis = self.analyze_scene_tension()

        if analysis.overall_tension == 0:
            return ""

        lines = [f"## Dramatic Tension: {analysis.overall_tension}/100"]

        if analysis.primary_source != "none":
            lines.append(f"Primary Source: {analysis.primary_source}")

        if analysis.is_good_stopping_point:
            lines.append(f"\n**Session Ending Opportunity:** {analysis.stopping_recommendation}")

        if analysis.suggested_cliffhangers:
            lines.append("\n### Cliffhanger Options:")
            for hook in analysis.suggested_cliffhangers[:3]:  # Top 3
                lines.append(f"- [{hook.hook_type.upper()}] {hook.description}")
                lines.append(f"  *{hook.why_effective}*")

        return "\n".join(lines)
