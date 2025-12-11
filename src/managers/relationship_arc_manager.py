"""Relationship arc manager.

Manages narrative arcs tracking relationship development between characters.
Supports both predefined arc templates and LLM-generated custom arcs.

Arcs serve as GM GUIDANCE (inspiration, not script) - player actions
always determine actual outcomes.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.agents.schemas.arc_generation import GeneratedArcTemplate
from src.database.models.relationship_arcs import (
    RelationshipArc,
    RelationshipArcPhase,
    WellKnownArcType,
)
from src.database.models.session import GameSession
from src.llm.factory import get_cheap_provider
from src.llm.message_types import Message
from src.managers.base import BaseManager

# Backward compatibility alias
RelationshipArcType = WellKnownArcType

# Default phase order for predefined arcs
DEFAULT_PHASE_ORDER = [
    "introduction",
    "development",
    "crisis",
    "climax",
    "resolution",
]

# Old enum-based phase order for backward compatibility
PHASE_ORDER = [
    RelationshipArcPhase.INTRODUCTION,
    RelationshipArcPhase.DEVELOPMENT,
    RelationshipArcPhase.CRISIS,
    RelationshipArcPhase.CLIMAX,
    RelationshipArcPhase.RESOLUTION,
]


# Arc templates with suggested scenes for each phase
ARC_TEMPLATES = {
    RelationshipArcType.ENEMIES_TO_LOVERS: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Initial antagonism established",
            "milestones": ["first_conflict", "verbal_sparring", "physical_confrontation"],
            "suggested_scenes": [
                "First hostile encounter",
                "Public disagreement",
                "Forced to acknowledge each other",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Grudging respect develops",
            "milestones": ["acknowledge_skill", "share_vulnerability", "defend_reputation"],
            "suggested_scenes": [
                "Forced to work together",
                "See them in a new light",
                "Learn their backstory",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Feelings surface, must be addressed",
            "milestones": ["jealousy_moment", "almost_kiss", "confession_interrupted"],
            "suggested_scenes": [
                "Third party romantic interest",
                "Separation threat",
                "Moment of vulnerability",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Declaration or rejection",
            "milestones": ["love_confession", "grand_gesture"],
            "suggested_scenes": [
                "Life-threatening situation",
                "Choice between duty and love",
                "Public declaration",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "New relationship status established",
            "milestones": ["relationship_defined", "future_discussed"],
            "suggested_scenes": [
                "Quiet moment together",
                "Public acknowledgment",
                "Planning future",
            ],
        },
    },
    RelationshipArcType.MENTORS_FALL: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Admiration and respect established",
            "milestones": ["first_lesson", "trust_established", "show_of_power"],
            "suggested_scenes": [
                "Mentor demonstrates mastery",
                "First teaching moment",
                "Student shows promise",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Learning and growing together",
            "milestones": ["breakthrough_moment", "shared_hardship", "secret_shared"],
            "suggested_scenes": [
                "Difficult training",
                "Mentor's past revealed",
                "Student surpasses expectation",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Mentor's flaw revealed",
            "milestones": ["flaw_witnessed", "trust_shaken", "confrontation"],
            "suggested_scenes": [
                "Mentor makes grave mistake",
                "Hidden truth exposed",
                "Student questions everything",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Must choose: forgive or abandon",
            "milestones": ["final_confrontation", "choice_made"],
            "suggested_scenes": [
                "Mentor at lowest point",
                "Student's intervention",
                "Ultimate test of values",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "New dynamic established",
            "milestones": ["relationship_redefined", "lessons_applied"],
            "suggested_scenes": [
                "Student becomes equal",
                "Mentor accepts change",
                "Passing of the torch",
            ],
        },
    },
    RelationshipArcType.BETRAYAL: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Trust building begins",
            "milestones": ["meet_cute", "first_favor", "bond_formed"],
            "suggested_scenes": [
                "Helpful stranger",
                "Shared interest",
                "Quick friendship",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Deepening trust, hidden agenda hints",
            "milestones": ["secret_kept", "rely_on_them", "strange_moment"],
            "suggested_scenes": [
                "Private conversations",
                "Small inconsistencies",
                "Moments alone with MacGuffin",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Betrayal executed",
            "milestones": ["betrayal_revealed", "confrontation", "escape_or_capture"],
            "suggested_scenes": [
                "Knife in the back moment",
                "True allegiance revealed",
                "Everything was a lie",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Confrontation with betrayer",
            "milestones": ["face_to_face", "explanation_given", "justice_or_mercy"],
            "suggested_scenes": [
                "Why they did it",
                "Chance for revenge",
                "Tables turned",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "Aftermath and new status",
            "milestones": ["consequences_felt", "trust_rebuilt_or_not"],
            "suggested_scenes": [
                "Living with consequences",
                "New understanding",
                "Forever changed",
            ],
        },
    },
    RelationshipArcType.REDEMPTION: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Villain/gray character introduced",
            "milestones": ["villainy_witnessed", "spark_of_good", "first_doubt"],
            "suggested_scenes": [
                "See their cruelty",
                "Unexpected kindness",
                "Hint of regret",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Player's influence grows",
            "milestones": ["dialogue_opened", "small_change", "backstory_revealed"],
            "suggested_scenes": [
                "Conversation about choices",
                "Small act of good",
                "Why they became this way",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Crisis point - old vs new",
            "milestones": ["old_loyalties_call", "test_of_change", "crucial_choice"],
            "suggested_scenes": [
                "Former allies demand return",
                "Must choose sides",
                "Prove they've changed",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Redemption or rejection",
            "milestones": ["final_choice", "sacrifice_or_selfishness"],
            "suggested_scenes": [
                "Ultimate sacrifice opportunity",
                "Face their victims",
                "Point of no return",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "New path established",
            "milestones": ["acceptance_or_exile", "making_amends"],
            "suggested_scenes": [
                "Community acceptance",
                "Ongoing penance",
                "New purpose",
            ],
        },
    },
    RelationshipArcType.RIVALRY: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Competition begins",
            "milestones": ["first_competition", "mutual_recognition", "stakes_raised"],
            "suggested_scenes": [
                "Same goal, different methods",
                "Public comparison",
                "First contest",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Escalating competition",
            "milestones": ["one_upmanship", "respect_grows", "personal_stake"],
            "suggested_scenes": [
                "Series of contests",
                "Grudging admiration",
                "Stakes become personal",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Must work together or destroy each other",
            "milestones": ["forced_alliance", "betrayal_temptation", "common_enemy"],
            "suggested_scenes": [
                "Greater threat appears",
                "One could sabotage other",
                "Trust despite rivalry",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Final contest or alliance",
            "milestones": ["final_showdown", "true_feelings_revealed"],
            "suggested_scenes": [
                "Ultimate competition",
                "Choose rivalry or friendship",
                "Mutual sacrifice",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "New relationship established",
            "milestones": ["respect_or_enmity", "future_dynamic"],
            "suggested_scenes": [
                "Friendly rivals",
                "Bitter enemies",
                "Unexpected friendship",
            ],
        },
    },
    RelationshipArcType.FOUND_FAMILY: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Strangers meet",
            "milestones": ["first_meeting", "reluctant_help", "shared_circumstance"],
            "suggested_scenes": [
                "Chance encounter",
                "Forced proximity",
                "Initial wariness",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Bonds forming through hardship",
            "milestones": ["shared_meal", "protect_each_other", "inside_joke"],
            "suggested_scenes": [
                "Face danger together",
                "Share personal stories",
                "Small traditions begin",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Bond tested",
            "milestones": ["serious_disagreement", "almost_leave", "choose_to_stay"],
            "suggested_scenes": [
                "Values conflict",
                "One considers leaving",
                "Prove commitment",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Family bond acknowledged",
            "milestones": ["explicit_declaration", "sacrifice_for_family"],
            "suggested_scenes": [
                "Risk everything for each other",
                "'You're my family' moment",
                "United against threat",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "Family established",
            "milestones": ["routine_established", "future_together"],
            "suggested_scenes": [
                "Daily life together",
                "Plan shared future",
                "Welcome new members",
            ],
        },
    },
    RelationshipArcType.LOST_LOVE_REKINDLED: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Past connection revealed",
            "milestones": ["reunion", "awkward_memories", "why_it_ended"],
            "suggested_scenes": [
                "Unexpected reunion",
                "Memories flood back",
                "Others notice tension",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Old feelings resurface",
            "milestones": ["reminisce", "changed_but_same", "new_attraction"],
            "suggested_scenes": [
                "Share how they've changed",
                "Old chemistry returns",
                "Others from past appear",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Old obstacles return",
            "milestones": ["original_issue_resurfaces", "new_complications", "must_choose"],
            "suggested_scenes": [
                "Why they broke up matters again",
                "Current life complications",
                "Second chance or move on",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Resolve or repeat",
            "milestones": ["confront_past", "choose_future"],
            "suggested_scenes": [
                "Address what went wrong",
                "Prove they've changed",
                "Final choice",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "New beginning or closure",
            "milestones": ["together_or_apart", "at_peace"],
            "suggested_scenes": [
                "Start fresh together",
                "Part as friends",
                "Closure achieved",
            ],
        },
    },
    RelationshipArcType.CORRUPTION: {
        RelationshipArcPhase.INTRODUCTION: {
            "description": "Innocent ally introduced",
            "milestones": ["meet_innocent", "see_their_goodness", "first_temptation"],
            "suggested_scenes": [
                "Pure-hearted character",
                "Player's darker knowledge",
                "Small moral compromise",
            ],
        },
        RelationshipArcPhase.DEVELOPMENT: {
            "description": "Slow moral erosion",
            "milestones": ["justify_small_evil", "enjoy_power", "lose_something_good"],
            "suggested_scenes": [
                "End justifies means",
                "Taste of dark power",
                "Old values fade",
            ],
        },
        RelationshipArcPhase.CRISIS: {
            "description": "Point of no return approaches",
            "milestones": ["major_moral_violation", "face_consequences", "last_chance"],
            "suggested_scenes": [
                "Cross serious line",
                "Victims confront them",
                "Mirror held up",
            ],
        },
        RelationshipArcPhase.CLIMAX: {
            "description": "Save or condemn",
            "milestones": ["intervention_attempt", "final_choice"],
            "suggested_scenes": [
                "Player's last appeal",
                "Accept darkness or fight it",
                "Dramatic confrontation",
            ],
        },
        RelationshipArcPhase.RESOLUTION: {
            "description": "New state established",
            "milestones": ["saved_or_lost", "living_with_result"],
            "suggested_scenes": [
                "Redemption path begun",
                "Fall complete",
                "Changed forever",
            ],
        },
    },
}


@dataclass
class ArcInfo:
    """Information about a relationship arc."""

    arc_key: str
    arc_type: str
    arc_description: str | None
    entity1_key: str
    entity2_key: str
    current_phase: str
    phase_progress: int
    arc_tension: int
    milestones_hit: list[str]
    is_active: bool
    started_turn: int
    completed_turn: int | None
    is_custom: bool  # True if LLM-generated, False if predefined


@dataclass
class ArcBeatSuggestion:
    """Suggested dramatic beat for an arc."""

    arc_key: str
    arc_type: str
    current_phase: str
    phase_description: str
    suggested_milestones: list[str]
    suggested_scenes: list[str]
    custom_beat: str | None
    potential_endings: list[str] | None = None
    tension_triggers: list[str] | None = None


class RelationshipArcManager(BaseManager):
    """Manages relationship arcs between characters.

    Provides template-based narrative scaffolding for relationship
    development with suggested beats and milestone tracking.
    """

    def __init__(self, db: Session, game_session: GameSession):
        """Initialize the relationship arc manager.

        Args:
            db: Database session.
            game_session: Current game session.
        """
        super().__init__(db, game_session)

    def create_arc(
        self,
        arc_key: str,
        arc_type: str | WellKnownArcType,
        entity1_key: str,
        entity2_key: str,
        started_turn: int,
        initial_tension: int = 0,
        arc_template: dict | None = None,
        arc_description: str | None = None,
    ) -> RelationshipArc:
        """Create a new relationship arc.

        Args:
            arc_key: Unique identifier for the arc.
            arc_type: Type of arc - either a WellKnownArcType or custom string.
            entity1_key: First entity (usually the player).
            entity2_key: Second entity (usually an NPC).
            started_turn: When the arc begins.
            initial_tension: Starting tension level (0-100).
            arc_template: LLM-generated template dict (optional for custom arcs).
            arc_description: Description of the arc (optional).

        Returns:
            The created RelationshipArc.
        """
        # Convert enum to string if needed
        arc_type_str = arc_type.value if isinstance(arc_type, WellKnownArcType) else arc_type

        # Determine initial phase
        initial_phase = "introduction"
        if arc_template and "phases" in arc_template:
            phases = arc_template.get("phases", [])
            if phases:
                initial_phase = phases[0].get("phase_key", "introduction")

        arc = RelationshipArc(
            session_id=self.game_session.id,
            arc_key=arc_key,
            arc_type=arc_type_str,
            arc_template=arc_template,
            arc_description=arc_description,
            entity1_key=entity1_key,
            entity2_key=entity2_key,
            current_phase=initial_phase,
            phase_progress=0,
            arc_tension=initial_tension,
            milestones_hit=[],
            started_turn=started_turn,
        )
        self.db.add(arc)
        self.db.commit()
        return arc

    def create_arc_from_generated(
        self,
        arc_key: str,
        entity1_key: str,
        entity2_key: str,
        started_turn: int,
        generated_template: GeneratedArcTemplate,
        initial_tension: int = 0,
    ) -> RelationshipArc:
        """Create an arc from an LLM-generated template.

        Args:
            arc_key: Unique identifier for the arc.
            entity1_key: First entity (usually the player).
            entity2_key: Second entity (usually an NPC).
            started_turn: When the arc begins.
            generated_template: The LLM-generated template.
            initial_tension: Starting tension level (0-100).

        Returns:
            The created RelationshipArc.
        """
        # Convert Pydantic model to dict for storage
        template_dict = generated_template.model_dump()

        return self.create_arc(
            arc_key=arc_key,
            arc_type=generated_template.arc_type_name,
            entity1_key=entity1_key,
            entity2_key=entity2_key,
            started_turn=started_turn,
            initial_tension=initial_tension,
            arc_template=template_dict,
            arc_description=generated_template.arc_description,
        )

    def get_arc(self, arc_key: str) -> RelationshipArc | None:
        """Get an arc by key.

        Args:
            arc_key: The arc's unique key.

        Returns:
            The RelationshipArc or None if not found.
        """
        stmt = select(RelationshipArc).where(
            RelationshipArc.session_id == self.game_session.id,
            RelationshipArc.arc_key == arc_key,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_arcs(self) -> list[RelationshipArc]:
        """Get all active arcs.

        Returns:
            List of active relationship arcs.
        """
        stmt = select(RelationshipArc).where(
            RelationshipArc.session_id == self.game_session.id,
            RelationshipArc.is_active == True,  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_arcs_for_entity(self, entity_key: str) -> list[RelationshipArc]:
        """Get all arcs involving an entity.

        Args:
            entity_key: The entity's key.

        Returns:
            List of arcs involving the entity.
        """
        stmt = select(RelationshipArc).where(
            RelationshipArc.session_id == self.game_session.id,
            or_(
                RelationshipArc.entity1_key == entity_key,
                RelationshipArc.entity2_key == entity_key,
            ),
        )
        return list(self.db.execute(stmt).scalars().all())

    def _get_phase_order(self, arc: RelationshipArc) -> list[str]:
        """Get the phase order for an arc.

        For custom arcs, extracts phases from arc_template.
        For predefined arcs, uses DEFAULT_PHASE_ORDER.

        Args:
            arc: The relationship arc.

        Returns:
            List of phase keys in order.
        """
        if arc.arc_template and "phases" in arc.arc_template:
            return [p.get("phase_key", "") for p in arc.arc_template.get("phases", [])]
        return DEFAULT_PHASE_ORDER

    def advance_phase(self, arc_key: str) -> RelationshipArc | None:
        """Advance an arc to its next phase.

        Args:
            arc_key: The arc's key.

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        phase_order = self._get_phase_order(arc)

        try:
            current_index = phase_order.index(arc.current_phase)
            if current_index < len(phase_order) - 1:
                arc.current_phase = phase_order[current_index + 1]
                arc.phase_progress = 0
                self.db.commit()
        except ValueError:
            # Current phase not in order, try default
            if arc.current_phase in DEFAULT_PHASE_ORDER:
                current_index = DEFAULT_PHASE_ORDER.index(arc.current_phase)
                if current_index < len(DEFAULT_PHASE_ORDER) - 1:
                    arc.current_phase = DEFAULT_PHASE_ORDER[current_index + 1]
                    arc.phase_progress = 0
                    self.db.commit()

        return arc

    def update_phase_progress(self, arc_key: str, progress: int) -> RelationshipArc | None:
        """Update progress within current phase.

        Args:
            arc_key: The arc's key.
            progress: New progress value (0-100).

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        arc.phase_progress = max(0, min(100, progress))
        self.db.commit()
        return arc

    def update_tension(self, arc_key: str, tension: int) -> RelationshipArc | None:
        """Update arc tension level.

        Args:
            arc_key: The arc's key.
            tension: New tension value (0-100).

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        arc.arc_tension = max(0, min(100, tension))
        self.db.commit()
        return arc

    def hit_milestone(self, arc_key: str, milestone: str) -> RelationshipArc | None:
        """Record a milestone being hit.

        Args:
            arc_key: The arc's key.
            milestone: The milestone identifier.

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        if milestone not in arc.milestones_hit:
            arc.milestones_hit.append(milestone)
            flag_modified(arc, "milestones_hit")
            self.db.commit()

        return arc

    def has_milestone(self, arc_key: str, milestone: str) -> bool:
        """Check if a milestone has been hit.

        Args:
            arc_key: The arc's key.
            milestone: The milestone to check.

        Returns:
            True if the milestone was hit.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return False
        return milestone in arc.milestones_hit

    def complete_arc(self, arc_key: str, completed_turn: int) -> RelationshipArc | None:
        """Complete an arc.

        Args:
            arc_key: The arc's key.
            completed_turn: When the arc ended.

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        arc.is_active = False
        arc.completed_turn = completed_turn
        arc.current_phase = RelationshipArcPhase.RESOLUTION
        self.db.commit()
        return arc

    def abandon_arc(self, arc_key: str) -> RelationshipArc | None:
        """Abandon an arc without completing it.

        Args:
            arc_key: The arc's key.

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        arc.is_active = False
        self.db.commit()
        return arc

    def set_suggested_beat(self, arc_key: str, beat: str) -> RelationshipArc | None:
        """Set a custom suggested beat for an arc.

        Args:
            arc_key: The arc's key.
            beat: The suggested next dramatic beat.

        Returns:
            The updated arc or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        arc.suggested_next_beat = beat
        self.db.commit()
        return arc

    def get_arc_beat_suggestion(self, arc_key: str) -> ArcBeatSuggestion | None:
        """Get suggested next beat for an arc.

        Uses stored arc_template if available (LLM-generated arcs),
        otherwise falls back to predefined ARC_TEMPLATES.

        Args:
            arc_key: The arc's key.

        Returns:
            ArcBeatSuggestion or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        # Check if this is a custom arc with stored template
        if arc.arc_template and "phases" in arc.arc_template:
            # Find current phase in template
            current_phase_data = None
            for phase in arc.arc_template.get("phases", []):
                if phase.get("phase_key") == arc.current_phase:
                    current_phase_data = phase
                    break

            if current_phase_data:
                return ArcBeatSuggestion(
                    arc_key=arc.arc_key,
                    arc_type=arc.arc_type,
                    current_phase=arc.current_phase,
                    phase_description=current_phase_data.get("description", ""),
                    suggested_milestones=current_phase_data.get("suggested_milestones", []),
                    suggested_scenes=current_phase_data.get("suggested_scenes", []),
                    custom_beat=arc.suggested_next_beat,
                    potential_endings=arc.arc_template.get("potential_endings"),
                    tension_triggers=arc.arc_template.get("tension_triggers"),
                )

        # Fall back to predefined templates
        try:
            arc_type_enum = WellKnownArcType(arc.arc_type)
            phase_enum = RelationshipArcPhase(arc.current_phase)
            template = ARC_TEMPLATES.get(arc_type_enum, {}).get(phase_enum, {})

            return ArcBeatSuggestion(
                arc_key=arc.arc_key,
                arc_type=arc.arc_type,
                current_phase=arc.current_phase,
                phase_description=template.get("description", ""),
                suggested_milestones=template.get("milestones", []),
                suggested_scenes=template.get("suggested_scenes", []),
                custom_beat=arc.suggested_next_beat,
            )
        except ValueError:
            # Unknown arc type or phase, return minimal suggestion
            return ArcBeatSuggestion(
                arc_key=arc.arc_key,
                arc_type=arc.arc_type,
                current_phase=arc.current_phase,
                phase_description=arc.arc_description or "",
                suggested_milestones=[],
                suggested_scenes=[],
                custom_beat=arc.suggested_next_beat,
            )

    def get_arc_info(self, arc_key: str) -> ArcInfo | None:
        """Get detailed information about an arc.

        Args:
            arc_key: The arc's key.

        Returns:
            ArcInfo or None if not found.
        """
        arc = self.get_arc(arc_key)
        if not arc:
            return None

        # Determine if this is a custom (LLM-generated) arc
        is_custom = arc.arc_template is not None

        return ArcInfo(
            arc_key=arc.arc_key,
            arc_type=arc.arc_type,
            arc_description=arc.arc_description,
            entity1_key=arc.entity1_key,
            entity2_key=arc.entity2_key,
            current_phase=arc.current_phase,
            phase_progress=arc.phase_progress,
            arc_tension=arc.arc_tension,
            milestones_hit=arc.milestones_hit,
            is_active=arc.is_active,
            started_turn=arc.started_turn,
            completed_turn=arc.completed_turn,
            is_custom=is_custom,
        )

    def get_arc_context(self) -> str:
        """Get formatted context of all active arcs for GM.

        Returns:
            Formatted string of active arcs.
        """
        arcs = self.get_active_arcs()
        if not arcs:
            return ""

        lines = ["Active Relationship Arcs:"]
        for arc in arcs:
            arc_type = arc.arc_type.value if isinstance(arc.arc_type, RelationshipArcType) else arc.arc_type
            phase = arc.current_phase.value if isinstance(arc.current_phase, RelationshipArcPhase) else arc.current_phase

            lines.append(
                f"  - {arc.entity1_key} & {arc.entity2_key}: {arc_type.replace('_', ' ').title()}"
            )
            lines.append(f"    Phase: {phase} (progress: {arc.phase_progress}%, tension: {arc.arc_tension})")
            if arc.suggested_next_beat:
                lines.append(f"    Suggested: {arc.suggested_next_beat}")

        return "\n".join(lines)

    def get_arc_context_for_entity(self, entity_key: str) -> str:
        """Get formatted arc context for a specific entity.

        Args:
            entity_key: The entity's key.

        Returns:
            Formatted string of arcs involving the entity.
        """
        arcs = self.get_arcs_for_entity(entity_key)
        if not arcs:
            return ""

        lines = [f"Relationship arcs involving {entity_key}:"]
        for arc in arcs:
            other = arc.entity2_key if arc.entity1_key == entity_key else arc.entity1_key
            arc_type = arc.arc_type.value if isinstance(arc.arc_type, RelationshipArcType) else arc.arc_type
            phase = arc.current_phase.value if isinstance(arc.current_phase, RelationshipArcPhase) else arc.current_phase

            lines.append(
                f"  - With {other}: {arc_type.replace('_', ' ').title()} ({phase}, tension: {arc.arc_tension})"
            )

        return "\n".join(lines)

    async def generate_arc_for_relationship(
        self,
        entity1_key: str,
        entity2_key: str,
        entity1_description: str,
        entity2_description: str,
        relationship_context: dict | None = None,
    ) -> GeneratedArcTemplate:
        """Generate a custom arc template using LLM.

        Based on the current relationship dynamics between two characters,
        generates a unique arc with phases, milestones, and suggested scenes.

        Args:
            entity1_key: First entity key (usually the player).
            entity2_key: Second entity key (usually an NPC).
            entity1_description: Description of entity 1.
            entity2_description: Description of entity 2.
            relationship_context: Optional dict with relationship values
                (trust, liking, respect, romantic, fear, familiarity, meeting_count).

        Returns:
            GeneratedArcTemplate with the custom arc.
        """
        # Load prompt template
        template_path = Path(__file__).parent.parent.parent / "data" / "templates" / "arc_generator.md"
        with open(template_path) as f:
            prompt_template = f.read()

        # Set defaults for relationship context
        ctx = relationship_context or {}
        trust = ctx.get("trust", 50)
        liking = ctx.get("liking", 50)
        respect = ctx.get("respect", 50)
        romantic = ctx.get("romantic", 0)
        fear = ctx.get("fear", 0)
        familiarity = ctx.get("familiarity", 10)
        meeting_count = ctx.get("meeting_count", 1)
        recent_interactions = ctx.get("recent_interactions", "Just met")

        # Generate interpretations
        def interpret(value: int, low: str, mid: str, high: str) -> str:
            if value < 30:
                return low
            elif value < 70:
                return mid
            return high

        # Format prompt
        prompt = prompt_template.format(
            setting=self.game_session.setting or "fantasy",
            entity1_name=entity1_key,
            entity1_type=ctx.get("entity1_type", "character"),
            entity1_description=entity1_description,
            entity1_personality=ctx.get("entity1_personality", "Unknown"),
            entity1_occupation=ctx.get("entity1_occupation", "Unknown"),
            entity2_name=entity2_key,
            entity2_type=ctx.get("entity2_type", "NPC"),
            entity2_description=entity2_description,
            entity2_personality=ctx.get("entity2_personality", "Unknown"),
            entity2_occupation=ctx.get("entity2_occupation", "Unknown"),
            trust=trust,
            trust_interpretation=interpret(trust, "Distrustful", "Neutral", "Trusting"),
            liking=liking,
            liking_interpretation=interpret(liking, "Hostile", "Neutral", "Friendly"),
            respect=respect,
            respect_interpretation=interpret(respect, "Dismissive", "Neutral", "Respectful"),
            romantic=romantic,
            romantic_interpretation=interpret(romantic, "None", "Curious", "Interested"),
            fear=fear,
            fear_interpretation=interpret(fear, "Unafraid", "Wary", "Fearful"),
            familiarity=familiarity,
            familiarity_interpretation=interpret(familiarity, "Strangers", "Acquainted", "Well-known"),
            meeting_count=meeting_count,
            relationship_duration=f"{meeting_count} meeting(s)",
            recent_interactions=recent_interactions,
        )

        # Call LLM
        provider = get_cheap_provider()
        response = await provider.complete_structured(
            messages=[Message.user(prompt)],
            response_schema=GeneratedArcTemplate,
            temperature=0.8,  # Some creativity for arc generation
        )

        return response.parsed_content
