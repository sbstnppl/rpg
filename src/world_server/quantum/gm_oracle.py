"""GM Decision Oracle for Quantum Branching.

Predicts which GM "twists" or complications are possible for a given
action, based on the current world state. Twists must be GROUNDED in
facts - no arbitrary complications.

Example grounded twists:
- "theft_accusation": Requires recent_theft fact + player_is_stranger fact
- "monster_warning": Requires beast_activity fact at destination
- "npc_recognition": Requires prior_meeting fact between player and NPC

The oracle returns a list of possible GM decisions with probabilities,
which the BranchGenerator uses to create outcome branches.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.database.models.world import Fact
from src.gm.grounding import GroundingManifest
from src.world_server.quantum.schemas import ActionType, ActionPrediction, GMDecision

logger = logging.getLogger(__name__)


# Twist type definitions with required facts
@dataclass
class TwistDefinition:
    """Definition of a possible GM twist."""

    twist_type: str
    description: str
    base_probability: float
    required_facts: list[tuple[str, str]]  # [(subject_pattern, predicate), ...]
    optional_facts: list[tuple[str, str]] = field(default_factory=list)
    probability_boost_per_optional: float = 0.05
    applicable_actions: list[ActionType] = field(default_factory=list)
    cooldown_turns: int = 5  # Don't repeat same twist within N turns


# Predefined twist types
TWIST_DEFINITIONS = [
    # Movement twists
    TwistDefinition(
        twist_type="theft_accusation",
        description="NPC accuses player of recent theft",
        base_probability=0.12,
        required_facts=[
            ("location:*", "recent_theft"),
            ("player", "is_stranger"),
        ],
        optional_facts=[
            ("location:*", "vigilant_guards"),
        ],
        applicable_actions=[ActionType.MOVE, ActionType.INTERACT_NPC],
    ),
    TwistDefinition(
        twist_type="monster_warning",
        description="NPC warns about dangerous creature ahead",
        base_probability=0.15,
        required_facts=[
            ("location:*", "beast_activity"),
        ],
        optional_facts=[
            ("location:*", "recent_attack"),
        ],
        applicable_actions=[ActionType.MOVE],
    ),
    TwistDefinition(
        twist_type="npc_recognition",
        description="NPC recognizes player from previous encounter",
        base_probability=0.20,
        required_facts=[
            ("npc:*", "met_player"),
        ],
        applicable_actions=[ActionType.INTERACT_NPC],
    ),
    TwistDefinition(
        twist_type="item_cursed",
        description="Item has hidden curse or complication",
        base_probability=0.08,
        required_facts=[
            ("item:*", "is_cursed"),
        ],
        applicable_actions=[ActionType.MANIPULATE_ITEM],
    ),
    TwistDefinition(
        twist_type="npc_busy",
        description="NPC is occupied and can't talk now",
        base_probability=0.10,
        required_facts=[
            ("npc:*", "current_task"),
        ],
        applicable_actions=[ActionType.INTERACT_NPC],
    ),
    TwistDefinition(
        twist_type="location_changed",
        description="Location has changed since last visit",
        base_probability=0.10,
        required_facts=[
            ("location:*", "recent_event"),
        ],
        applicable_actions=[ActionType.MOVE, ActionType.OBSERVE],
    ),
    TwistDefinition(
        twist_type="weather_complication",
        description="Weather affects the action",
        base_probability=0.08,
        required_facts=[
            ("world", "severe_weather"),
        ],
        applicable_actions=[ActionType.MOVE, ActionType.OBSERVE, ActionType.SKILL_USE],
    ),
    TwistDefinition(
        twist_type="rival_appears",
        description="A rival or enemy shows up",
        base_probability=0.10,
        required_facts=[
            ("player", "has_rival"),
        ],
        optional_facts=[
            ("rival:*", "seeking_player"),
        ],
        applicable_actions=[ActionType.MOVE, ActionType.INTERACT_NPC],
    ),
    TwistDefinition(
        twist_type="hidden_opportunity",
        description="Action reveals unexpected opportunity",
        base_probability=0.15,
        required_facts=[
            ("location:*", "hidden_secret"),
        ],
        applicable_actions=[ActionType.OBSERVE, ActionType.MANIPULATE_ITEM],
    ),
]


class GMDecisionOracle:
    """Predicts GM decisions (twists) based on world state.

    The oracle queries the fact store to determine which twists are
    grounded in the current world state. Only grounded twists are
    returned as possible GM decisions.
    """

    # Base probability for "no twist" (straightforward outcome)
    NO_TWIST_PROBABILITY = 0.70

    def __init__(self, db: Session, game_session: GameSession):
        """Initialize the oracle.

        Args:
            db: Database session
            game_session: Current game session
        """
        self.db = db
        self.game_session = game_session

    def predict_decisions(
        self,
        action: ActionPrediction,
        manifest: GroundingManifest,
        max_decisions: int = 3,
    ) -> list[GMDecision]:
        """Predict possible GM decisions for an action.

        Always includes "no_twist" as the default decision. Additional
        twists are only included if they are grounded in facts.

        Args:
            action: The predicted action
            manifest: Grounding manifest for the scene
            max_decisions: Maximum number of decisions to return

        Returns:
            List of GMDecision sorted by probability (highest first)
        """
        decisions = []

        # Always include "no_twist" as default
        decisions.append(GMDecision(
            decision_type="no_twist",
            probability=self.NO_TWIST_PROBABILITY,
            grounding_facts=[],
            context={"description": "Straightforward outcome, no complications"},
        ))

        # Check each twist definition for grounding
        for twist_def in TWIST_DEFINITIONS:
            # Skip if not applicable to this action type
            if twist_def.applicable_actions and action.action_type not in twist_def.applicable_actions:
                continue

            # Check if twist is grounded
            grounding_result = self._check_twist_grounding(
                twist_def, action, manifest
            )

            if grounding_result:
                grounding_facts, probability = grounding_result

                decisions.append(GMDecision(
                    decision_type=twist_def.twist_type,
                    probability=probability,
                    grounding_facts=grounding_facts,
                    context={
                        "description": twist_def.description,
                        "target_key": action.target_key,
                    },
                ))

        # Sort by probability and limit
        decisions.sort(key=lambda d: d.probability, reverse=True)

        # Normalize probabilities so they sum to 1.0
        decisions = self._normalize_probabilities(decisions[:max_decisions])

        return decisions

    def _check_twist_grounding(
        self,
        twist_def: TwistDefinition,
        action: ActionPrediction,
        manifest: GroundingManifest,
    ) -> tuple[list[str], float] | None:
        """Check if a twist is grounded in facts.

        Args:
            twist_def: Twist definition to check
            action: The predicted action
            manifest: Scene manifest

        Returns:
            Tuple of (grounding_facts, probability) if grounded, None otherwise
        """
        grounding_facts = []
        matched_required = 0
        matched_optional = 0

        # Check required facts
        for subject_pattern, predicate in twist_def.required_facts:
            fact = self._find_matching_fact(subject_pattern, predicate, action, manifest)
            if fact:
                grounding_facts.append(f"{fact.subject_key}:{fact.predicate}={fact.value}")
                matched_required += 1
            else:
                # Missing required fact - twist not grounded
                return None

        # Check optional facts for probability boost
        for subject_pattern, predicate in twist_def.optional_facts:
            fact = self._find_matching_fact(subject_pattern, predicate, action, manifest)
            if fact:
                grounding_facts.append(f"{fact.subject_key}:{fact.predicate}={fact.value}")
                matched_optional += 1

        # Calculate probability
        probability = twist_def.base_probability
        probability += matched_optional * twist_def.probability_boost_per_optional

        # Cap at 30% for any single twist
        probability = min(probability, 0.30)

        return grounding_facts, probability

    def _find_matching_fact(
        self,
        subject_pattern: str,
        predicate: str,
        action: ActionPrediction,
        manifest: GroundingManifest,
    ) -> Fact | None:
        """Find a fact matching the pattern.

        Patterns:
        - "player" -> Match facts about the player
        - "location:*" -> Match facts about current or target location
        - "npc:*" -> Match facts about target NPC (if applicable)
        - "item:*" -> Match facts about target item (if applicable)
        - "world" -> Match global world facts

        Args:
            subject_pattern: Pattern for subject matching
            predicate: Predicate to match
            action: The predicted action
            manifest: Scene manifest

        Returns:
            Matching Fact if found, None otherwise
        """
        subject_keys = []

        if subject_pattern == "player":
            subject_keys = [manifest.player_key]
        elif subject_pattern == "world":
            subject_keys = ["world"]
        elif subject_pattern == "location:*":
            # Check current location and target location (for movement)
            subject_keys = [manifest.location_key]
            if action.action_type == ActionType.MOVE and action.target_key:
                subject_keys.append(action.target_key)
        elif subject_pattern == "npc:*":
            # Check target NPC
            if action.action_type == ActionType.INTERACT_NPC and action.target_key:
                subject_keys = [action.target_key]
        elif subject_pattern == "item:*":
            # Check target item
            if action.action_type == ActionType.MANIPULATE_ITEM and action.target_key:
                subject_keys = [action.target_key]
        elif subject_pattern.startswith("rival:"):
            # Check for any rival entity
            subject_keys = self._get_rival_keys()

        # Query for matching facts
        for subject_key in subject_keys:
            fact = (
                self.db.query(Fact)
                .filter(
                    Fact.session_id == self.game_session.id,
                    Fact.subject_key == subject_key,
                    Fact.predicate == predicate,
                )
                .first()
            )
            if fact:
                return fact

        return None

    def _get_rival_keys(self) -> list[str]:
        """Get entity keys of player's rivals.

        Returns:
            List of rival entity keys
        """
        rival_facts = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.game_session.id,
                Fact.subject_key == "player",
                Fact.predicate == "rival",
            )
            .all()
        )
        return [f.value for f in rival_facts]

    def _normalize_probabilities(
        self, decisions: list[GMDecision]
    ) -> list[GMDecision]:
        """Normalize probabilities to sum to 1.0.

        Args:
            decisions: List of decisions

        Returns:
            Decisions with normalized probabilities
        """
        if not decisions:
            return decisions

        total = sum(d.probability for d in decisions)
        if total == 0:
            return decisions

        for decision in decisions:
            decision.probability = decision.probability / total

        return decisions

    def get_applicable_twists(
        self, action_type: ActionType
    ) -> list[TwistDefinition]:
        """Get twist definitions applicable to an action type.

        Useful for understanding what twists might occur.

        Args:
            action_type: The action type

        Returns:
            List of applicable twist definitions
        """
        return [
            twist for twist in TWIST_DEFINITIONS
            if not twist.applicable_actions or action_type in twist.applicable_actions
        ]

    def record_twist_used(
        self, twist_type: str, turn_number: int
    ) -> None:
        """Record that a twist was used (for cooldown tracking).

        Args:
            twist_type: Type of twist used
            turn_number: Turn number when used
        """
        # Record as a fact for cooldown tracking
        from src.managers.fact_manager import FactManager

        fact_manager = FactManager(
            self.db, self.game_session, current_turn=turn_number
        )
        fact_manager.record_fact(
            subject_type="world",
            subject_key="twist_history",
            predicate=f"last_{twist_type}",
            value=str(turn_number),
        )
