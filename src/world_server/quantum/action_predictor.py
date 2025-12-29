"""Action Predictor for Quantum Branching.

Predicts likely player actions based on the current scene manifest.
These predictions are used to pre-generate outcome branches before
the player acts.

The predictor analyzes:
- NPCs present (likely interaction targets)
- Items visible (likely manipulation targets)
- Exits available (likely movement destinations)
- Recent turns (action patterns and mentioned targets)
"""

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.database.models.session import GameSession, Turn
from src.gm.grounding import GroundingManifest, GroundedEntity
from src.world_server.schemas import PredictionReason
from src.world_server.quantum.schemas import ActionType, ActionPrediction

logger = logging.getLogger(__name__)


# Base probabilities for action types
DEFAULT_PROBABILITIES = {
    ActionType.INTERACT_NPC: 0.25,
    ActionType.MANIPULATE_ITEM: 0.15,
    ActionType.MOVE: 0.20,
    ActionType.OBSERVE: 0.15,
    ActionType.DIALOGUE: 0.10,
    ActionType.SKILL_USE: 0.10,
    ActionType.WAIT: 0.05,
}

# Probability boosts
RECENTLY_MENTIONED_BOOST = 0.15
QUEST_RELATED_BOOST = 0.20
FOCUS_NPC_BOOST = 0.10
VALUABLE_ITEM_BOOST = 0.10


@dataclass
class PredictionContext:
    """Context gathered for making predictions."""

    recent_inputs: list[str] = field(default_factory=list)
    recent_targets: set[str] = field(default_factory=set)
    mentioned_entities: set[str] = field(default_factory=set)
    current_quest_targets: set[str] = field(default_factory=set)


class ActionPredictor:
    """Predicts likely player actions based on scene context.

    Uses the grounding manifest to identify all possible action targets,
    then assigns probabilities based on context and recent history.
    """

    def __init__(self, db: Session, game_session: GameSession):
        """Initialize the predictor.

        Args:
            db: Database session
            game_session: Current game session
        """
        self.db = db
        self.game_session = game_session

    def predict_actions(
        self,
        location_key: str,
        manifest: GroundingManifest,
        max_predictions: int = 10,
        recent_turns: int = 5,
    ) -> list[ActionPrediction]:
        """Predict likely player actions for the current scene.

        Args:
            location_key: Current player location
            manifest: Grounding manifest with all valid entities
            max_predictions: Maximum number of predictions to return
            recent_turns: Number of recent turns to analyze

        Returns:
            List of ActionPrediction sorted by probability (highest first)
        """
        # Gather context from recent turns
        context = self._gather_context(recent_turns)

        predictions: list[ActionPrediction] = []

        # Predict NPC interactions
        predictions.extend(self._predict_npc_interactions(manifest, context))

        # Predict item manipulations
        predictions.extend(self._predict_item_manipulations(manifest, context))

        # Predict movement
        predictions.extend(self._predict_movement(manifest, context))

        # Predict observation (always available)
        predictions.append(self._predict_observation(manifest, context))

        # Predict waiting (low priority)
        predictions.append(self._predict_wait(context))

        # Sort by probability and limit
        predictions.sort(key=lambda p: p.probability, reverse=True)
        return predictions[:max_predictions]

    def _gather_context(self, num_turns: int) -> PredictionContext:
        """Gather context from recent turns.

        Args:
            num_turns: Number of recent turns to analyze

        Returns:
            PredictionContext with gathered information
        """
        context = PredictionContext()

        # Get recent turns
        turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .order_by(Turn.turn_number.desc())
            .limit(num_turns)
            .all()
        )

        for turn in turns:
            context.recent_inputs.append(turn.player_input.lower())

            # Extract entity keys mentioned in player input
            # Pattern: references to entities, names, etc.
            if turn.entities_extracted:
                for entity_type, entities in turn.entities_extracted.items():
                    if isinstance(entities, list):
                        for entity in entities:
                            if isinstance(entity, dict) and "key" in entity:
                                context.mentioned_entities.add(entity["key"])

            # Track NPCs present in recent turns
            if turn.npcs_present_at_turn:
                for npc in turn.npcs_present_at_turn:
                    if isinstance(npc, str):
                        context.recent_targets.add(npc)
                    elif isinstance(npc, dict) and "key" in npc:
                        context.recent_targets.add(npc["key"])

        # TODO: Get active quest targets from QuestManager
        # context.current_quest_targets = self._get_quest_targets()

        return context

    def _predict_npc_interactions(
        self,
        manifest: GroundingManifest,
        context: PredictionContext,
    ) -> list[ActionPrediction]:
        """Predict NPC interaction actions.

        Args:
            manifest: Scene manifest with NPCs
            context: Prediction context

        Returns:
            List of NPC interaction predictions
        """
        predictions = []

        for npc_key, npc in manifest.npcs.items():
            base_prob = DEFAULT_PROBABILITIES[ActionType.INTERACT_NPC]

            # Boost if recently mentioned or interacted with
            if npc_key in context.mentioned_entities:
                base_prob += RECENTLY_MENTIONED_BOOST

            # Boost if quest-related
            if npc_key in context.current_quest_targets:
                base_prob += QUEST_RELATED_BOOST

            # Build input patterns for matching
            patterns = self._build_npc_patterns(npc)

            predictions.append(ActionPrediction(
                action_type=ActionType.INTERACT_NPC,
                target_key=npc_key,
                input_patterns=patterns,
                probability=min(base_prob, 0.95),  # Cap at 95%
                reason=PredictionReason.ADJACENT,
                display_name=f"Talk to {npc.display_name}",
                context={"npc_description": npc.short_description},
            ))

        return predictions

    def _predict_item_manipulations(
        self,
        manifest: GroundingManifest,
        context: PredictionContext,
    ) -> list[ActionPrediction]:
        """Predict item manipulation actions.

        Args:
            manifest: Scene manifest with items
            context: Prediction context

        Returns:
            List of item manipulation predictions
        """
        predictions = []

        # Items at location (can be taken)
        for item_key, item in manifest.items_at_location.items():
            base_prob = DEFAULT_PROBABILITIES[ActionType.MANIPULATE_ITEM]

            # Boost if recently mentioned
            if item_key in context.mentioned_entities:
                base_prob += RECENTLY_MENTIONED_BOOST

            patterns = self._build_item_patterns(item, action="take")

            predictions.append(ActionPrediction(
                action_type=ActionType.MANIPULATE_ITEM,
                target_key=item_key,
                input_patterns=patterns,
                probability=min(base_prob, 0.95),
                reason=PredictionReason.MENTIONED if item_key in context.mentioned_entities else PredictionReason.ADJACENT,
                display_name=f"Take {item.display_name}",
                context={"item_type": item.entity_type, "action": "take"},
            ))

        # Inventory items (can be used, dropped, examined)
        for item_key, item in manifest.inventory.items():
            base_prob = DEFAULT_PROBABILITIES[ActionType.MANIPULATE_ITEM] * 0.7

            patterns = self._build_item_patterns(item, action="use")

            predictions.append(ActionPrediction(
                action_type=ActionType.MANIPULATE_ITEM,
                target_key=item_key,
                input_patterns=patterns,
                probability=min(base_prob, 0.95),
                reason=PredictionReason.ADJACENT,
                display_name=f"Use {item.display_name}",
                context={"item_type": item.entity_type, "action": "use"},
            ))

        return predictions

    def _predict_movement(
        self,
        manifest: GroundingManifest,
        context: PredictionContext,
    ) -> list[ActionPrediction]:
        """Predict movement actions.

        Args:
            manifest: Scene manifest with exits
            context: Prediction context

        Returns:
            List of movement predictions
        """
        predictions = []

        for exit_key, exit_entity in manifest.exits.items():
            base_prob = DEFAULT_PROBABILITIES[ActionType.MOVE]

            # Boost if quest target
            if exit_key in context.current_quest_targets:
                base_prob += QUEST_RELATED_BOOST

            # Boost if recently mentioned
            if exit_key in context.mentioned_entities:
                base_prob += RECENTLY_MENTIONED_BOOST

            patterns = self._build_movement_patterns(exit_entity)

            predictions.append(ActionPrediction(
                action_type=ActionType.MOVE,
                target_key=exit_key,
                input_patterns=patterns,
                probability=min(base_prob, 0.95),
                reason=PredictionReason.ADJACENT,
                display_name=f"Go to {exit_entity.display_name}",
                context={"destination": exit_entity.display_name},
            ))

        return predictions

    def _predict_observation(
        self,
        manifest: GroundingManifest,
        context: PredictionContext,
    ) -> ActionPrediction:
        """Predict observation action (always available).

        Args:
            manifest: Scene manifest
            context: Prediction context

        Returns:
            Observation prediction
        """
        patterns = [
            r"^look\b",
            r"^examine\b",
            r"^observe\b",
            r"^search\b",
            r"^inspect\b",
            r"look around",
            r"what do i see",
            r"describe",
        ]

        return ActionPrediction(
            action_type=ActionType.OBSERVE,
            target_key=None,
            input_patterns=patterns,
            probability=DEFAULT_PROBABILITIES[ActionType.OBSERVE],
            reason=PredictionReason.ADJACENT,
            display_name="Look around",
        )

    def _predict_wait(self, context: PredictionContext) -> ActionPrediction:
        """Predict wait action (low priority).

        Args:
            context: Prediction context

        Returns:
            Wait prediction
        """
        patterns = [
            r"^wait\b",
            r"^rest\b",
            r"^sleep\b",
            r"do nothing",
            r"pass time",
            r"take a break",
        ]

        return ActionPrediction(
            action_type=ActionType.WAIT,
            target_key=None,
            input_patterns=patterns,
            probability=DEFAULT_PROBABILITIES[ActionType.WAIT],
            reason=PredictionReason.ADJACENT,
            display_name="Wait",
        )

    def _build_npc_patterns(self, npc: GroundedEntity) -> list[str]:
        """Build regex patterns for NPC interaction matching.

        Args:
            npc: NPC entity

        Returns:
            List of regex patterns
        """
        name = re.escape(npc.display_name.lower())
        name_parts = npc.display_name.lower().split()

        patterns = [
            # Direct address
            rf"talk\s+(to\s+)?{name}",
            rf"speak\s+(to\s+|with\s+)?{name}",
            rf"ask\s+{name}",
            rf"tell\s+{name}",
            rf"greet\s+{name}",
            # By first name only
            rf"talk\s+(to\s+)?{re.escape(name_parts[0])}",
            rf"speak\s+(to\s+|with\s+)?{re.escape(name_parts[0])}",
        ]

        # Add role-based patterns if description available
        if npc.short_description:
            desc = npc.short_description.lower()
            # Extract role words (innkeeper, blacksmith, guard, etc.)
            role_words = ["innkeeper", "blacksmith", "guard", "merchant",
                         "bartender", "priest", "farmer", "soldier"]
            for role in role_words:
                if role in desc:
                    patterns.append(rf"talk\s+(to\s+)?.*{role}")
                    patterns.append(rf"speak\s+(to\s+|with\s+)?.*{role}")

        return patterns

    def _build_item_patterns(
        self,
        item: GroundedEntity,
        action: str = "take",
    ) -> list[str]:
        """Build regex patterns for item manipulation matching.

        Args:
            item: Item entity
            action: Primary action (take, use, drop)

        Returns:
            List of regex patterns
        """
        name = re.escape(item.display_name.lower())

        if action == "take":
            patterns = [
                rf"take\s+(the\s+)?{name}",
                rf"grab\s+(the\s+)?{name}",
                rf"pick\s+up\s+(the\s+)?{name}",
                rf"get\s+(the\s+)?{name}",
            ]
        elif action == "use":
            patterns = [
                rf"use\s+(the\s+)?{name}",
                rf"equip\s+(the\s+)?{name}",
                rf"drink\s+(the\s+)?{name}",
                rf"eat\s+(the\s+)?{name}",
                rf"read\s+(the\s+)?{name}",
            ]
        else:  # drop
            patterns = [
                rf"drop\s+(the\s+)?{name}",
                rf"put\s+down\s+(the\s+)?{name}",
                rf"leave\s+(the\s+)?{name}",
            ]

        return patterns

    def _build_movement_patterns(self, exit_entity: GroundedEntity) -> list[str]:
        """Build regex patterns for movement matching.

        Args:
            exit_entity: Exit/location entity

        Returns:
            List of regex patterns
        """
        name = re.escape(exit_entity.display_name.lower())

        patterns = [
            rf"go\s+(to\s+)?(the\s+)?{name}",
            rf"head\s+(to\s+)?(the\s+)?{name}",
            rf"walk\s+(to\s+)?(the\s+)?{name}",
            rf"travel\s+(to\s+)?(the\s+)?{name}",
            rf"enter\s+(the\s+)?{name}",
            rf"leave\s+.*{name}",
            rf"go\s+(outside|inside)",
        ]

        # Add directional patterns if applicable
        directions = ["north", "south", "east", "west", "up", "down", "outside", "inside"]
        for direction in directions:
            if direction in name:
                patterns.append(rf"go\s+{direction}")
                patterns.append(rf"head\s+{direction}")

        return patterns

    def get_prediction_stats(self) -> dict:
        """Get statistics about predictions.

        Returns:
            Dict with prediction statistics
        """
        return {
            "recent_turns_analyzed": 5,
            "base_probabilities": {k.value: v for k, v in DEFAULT_PROBABILITIES.items()},
        }
