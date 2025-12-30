"""Action Matcher for Quantum Branching.

Fuzzy matches player input to predicted actions. Uses multiple
matching strategies:
1. Regex pattern matching (from ActionPrediction.input_patterns)
2. Target name fuzzy matching (entity display names)
3. Action verb extraction and matching
4. Semantic similarity (future: embeddings)

The matcher returns the best matching prediction with a confidence
score, or None if no good match is found.
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.gm.grounding import GroundingManifest
from src.world_server.quantum.schemas import ActionType, ActionPrediction

logger = logging.getLogger(__name__)


# Action verb -> ActionType mapping
ACTION_VERBS = {
    # NPC interaction
    "talk": ActionType.INTERACT_NPC,
    "speak": ActionType.INTERACT_NPC,
    "ask": ActionType.INTERACT_NPC,
    "tell": ActionType.INTERACT_NPC,
    "greet": ActionType.INTERACT_NPC,
    "chat": ActionType.INTERACT_NPC,
    "converse": ActionType.INTERACT_NPC,
    "approach": ActionType.INTERACT_NPC,
    # Item manipulation
    "take": ActionType.MANIPULATE_ITEM,
    "grab": ActionType.MANIPULATE_ITEM,
    "pick": ActionType.MANIPULATE_ITEM,
    "get": ActionType.MANIPULATE_ITEM,
    "use": ActionType.MANIPULATE_ITEM,
    "equip": ActionType.MANIPULATE_ITEM,
    "drop": ActionType.MANIPULATE_ITEM,
    "put": ActionType.MANIPULATE_ITEM,
    "give": ActionType.MANIPULATE_ITEM,
    "drink": ActionType.MANIPULATE_ITEM,
    "eat": ActionType.MANIPULATE_ITEM,
    "read": ActionType.MANIPULATE_ITEM,
    "open": ActionType.MANIPULATE_ITEM,
    "close": ActionType.MANIPULATE_ITEM,
    # Movement
    "go": ActionType.MOVE,
    "walk": ActionType.MOVE,
    "head": ActionType.MOVE,
    "travel": ActionType.MOVE,
    "enter": ActionType.MOVE,
    "leave": ActionType.MOVE,
    "exit": ActionType.MOVE,
    "move": ActionType.MOVE,
    "run": ActionType.MOVE,
    # Observation
    "look": ActionType.OBSERVE,
    "examine": ActionType.OBSERVE,
    "inspect": ActionType.OBSERVE,
    "observe": ActionType.OBSERVE,
    "search": ActionType.OBSERVE,
    "check": ActionType.OBSERVE,
    "scan": ActionType.OBSERVE,
    # Skill use
    "pick": ActionType.SKILL_USE,  # pick lock
    "climb": ActionType.SKILL_USE,
    "sneak": ActionType.SKILL_USE,
    "hide": ActionType.SKILL_USE,
    "lockpick": ActionType.SKILL_USE,
    "steal": ActionType.SKILL_USE,
    # Combat
    "attack": ActionType.COMBAT,
    "fight": ActionType.COMBAT,
    "hit": ActionType.COMBAT,
    "strike": ActionType.COMBAT,
    "defend": ActionType.COMBAT,
    "block": ActionType.COMBAT,
    "flee": ActionType.COMBAT,
    # Wait
    "wait": ActionType.WAIT,
    "rest": ActionType.WAIT,
    "sleep": ActionType.WAIT,
    "pause": ActionType.WAIT,
}

# Stopwords to ignore in matching
STOPWORDS = {"the", "a", "an", "to", "at", "in", "on", "with", "and", "or", "i", "my"}


@dataclass
class MatchResult:
    """Result of matching player input to a prediction."""

    prediction: ActionPrediction
    confidence: float
    match_reason: str  # "pattern", "target", "verb", "semantic"

    def __lt__(self, other: "MatchResult") -> bool:
        """Allow sorting by confidence."""
        return self.confidence < other.confidence


class ActionMatcher:
    """Fuzzy matches player input to predicted actions.

    Uses multiple matching strategies with weighted scoring:
    - Pattern match: 0.4 weight
    - Target match: 0.4 weight
    - Verb match: 0.2 weight
    """

    def __init__(
        self,
        pattern_weight: float = 0.4,
        target_weight: float = 0.4,
        verb_weight: float = 0.2,
    ):
        """Initialize the matcher.

        Args:
            pattern_weight: Weight for regex pattern matching
            target_weight: Weight for target name fuzzy matching
            verb_weight: Weight for action verb matching
        """
        self.pattern_weight = pattern_weight
        self.target_weight = target_weight
        self.verb_weight = verb_weight

    def match(
        self,
        player_input: str,
        predictions: list[ActionPrediction],
        manifest: GroundingManifest,
        min_confidence: float = 0.5,
    ) -> MatchResult | None:
        """Match player input to the best prediction.

        Args:
            player_input: Raw player input text
            predictions: List of action predictions to match against
            manifest: Grounding manifest for entity lookup
            min_confidence: Minimum confidence threshold

        Returns:
            MatchResult if a good match found, None otherwise
        """
        if not player_input or not predictions:
            return None

        # Normalize input
        normalized = self._normalize(player_input)

        # Extract action verb and target
        verb, target_text = self._extract_verb_and_target(normalized)

        # Score each prediction
        results: list[MatchResult] = []

        for pred in predictions:
            score, reason = self._score_prediction(
                normalized, verb, target_text, pred, manifest
            )

            if score >= min_confidence:
                results.append(MatchResult(
                    prediction=pred,
                    confidence=score,
                    match_reason=reason,
                ))

        if not results:
            return None

        # Return best match
        results.sort(reverse=True)
        best = results[0]

        logger.debug(
            f"Matched '{player_input}' to {best.prediction.action_type.value}:"
            f"{best.prediction.target_key} (confidence={best.confidence:.2f}, "
            f"reason={best.match_reason})"
        )

        return best

    def match_all(
        self,
        player_input: str,
        predictions: list[ActionPrediction],
        manifest: GroundingManifest,
        min_confidence: float = 0.3,
        max_results: int = 5,
    ) -> list[MatchResult]:
        """Match player input to multiple predictions.

        Useful when the input is ambiguous and multiple interpretations
        are possible.

        Args:
            player_input: Raw player input text
            predictions: List of action predictions
            manifest: Grounding manifest
            min_confidence: Minimum confidence threshold
            max_results: Maximum number of results to return

        Returns:
            List of MatchResult sorted by confidence
        """
        if not player_input or not predictions:
            return []

        normalized = self._normalize(player_input)
        verb, target_text = self._extract_verb_and_target(normalized)

        results: list[MatchResult] = []

        for pred in predictions:
            score, reason = self._score_prediction(
                normalized, verb, target_text, pred, manifest
            )

            if score >= min_confidence:
                results.append(MatchResult(
                    prediction=pred,
                    confidence=score,
                    match_reason=reason,
                ))

        results.sort(reverse=True)
        return results[:max_results]

    def _normalize(self, text: str) -> str:
        """Normalize input text for matching.

        Args:
            text: Raw input text

        Returns:
            Normalized lowercase text with extra whitespace removed
        """
        # Lowercase and strip
        text = text.lower().strip()

        # Remove punctuation except apostrophes
        text = re.sub(r"[^\w\s']", " ", text)

        # Collapse whitespace and strip trailing
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def _extract_verb_and_target(
        self, normalized: str
    ) -> tuple[str | None, str | None]:
        """Extract action verb and target from input.

        Args:
            normalized: Normalized input text

        Returns:
            Tuple of (verb, target_text) - either may be None
        """
        words = normalized.split()
        if not words:
            return None, None

        verb = None
        target_start = 0

        # Find first action verb
        for i, word in enumerate(words):
            if word in ACTION_VERBS:
                verb = word
                target_start = i + 1
                break

        # Extract target (rest of sentence minus stopwords)
        if target_start < len(words):
            target_words = [
                w for w in words[target_start:]
                if w not in STOPWORDS
            ]
            target_text = " ".join(target_words) if target_words else None
        else:
            target_text = None

        return verb, target_text

    def _score_prediction(
        self,
        normalized: str,
        verb: str | None,
        target_text: str | None,
        pred: ActionPrediction,
        manifest: GroundingManifest,
    ) -> tuple[float, str]:
        """Score how well a prediction matches the input.

        Args:
            normalized: Normalized input text
            verb: Extracted action verb
            target_text: Extracted target text
            pred: Prediction to score
            manifest: Grounding manifest

        Returns:
            Tuple of (score, primary_match_reason)
        """
        scores = {
            "pattern": 0.0,
            "target": 0.0,
            "verb": 0.0,
        }

        # Pattern matching
        for pattern in pred.input_patterns:
            try:
                if re.search(pattern, normalized, re.IGNORECASE):
                    scores["pattern"] = 1.0
                    break
            except re.error:
                # Invalid regex pattern
                continue

        # Partial pattern matching (if no exact match)
        if scores["pattern"] == 0.0:
            scores["pattern"] = self._partial_pattern_score(normalized, pred.input_patterns)

        # Target matching
        if pred.target_key and target_text:
            entity = manifest.get_entity(pred.target_key)
            if entity:
                scores["target"] = self._fuzzy_match_score(
                    target_text, entity.display_name.lower()
                )

        # Verb matching
        if verb:
            expected_type = ACTION_VERBS.get(verb)
            if expected_type == pred.action_type:
                scores["verb"] = 1.0
            elif expected_type is None:
                # Unknown verb - don't penalize
                scores["verb"] = 0.5

        # Calculate weighted score
        total_score = (
            scores["pattern"] * self.pattern_weight +
            scores["target"] * self.target_weight +
            scores["verb"] * self.verb_weight
        )

        # Determine primary match reason
        if scores["pattern"] > 0.8:
            reason = "pattern"
        elif scores["target"] > 0.8:
            reason = "target"
        elif scores["verb"] > 0.8:
            reason = "verb"
        else:
            reason = "combined"

        return total_score, reason

    def _partial_pattern_score(
        self, text: str, patterns: list[str]
    ) -> float:
        """Score partial pattern matches.

        Args:
            text: Input text
            patterns: List of regex patterns

        Returns:
            Score between 0.0 and 0.7 (capped for partial matches)
        """
        best_score = 0.0

        for pattern in patterns:
            try:
                # Extract key words from pattern
                # Remove regex syntax to get plain words
                plain = re.sub(r"[\\^$.*+?{}|()\[\]]", " ", pattern)
                plain = re.sub(r"\s+", " ", plain).strip()
                pattern_words = set(plain.split()) - STOPWORDS

                if not pattern_words:
                    continue

                text_words = set(text.split()) - STOPWORDS

                # Calculate word overlap
                overlap = len(pattern_words & text_words)
                if overlap > 0:
                    score = overlap / len(pattern_words)
                    best_score = max(best_score, score)

            except Exception:
                continue

        # Cap partial matches at 0.7
        return min(best_score, 0.7)

    def _fuzzy_match_score(self, text1: str, text2: str) -> float:
        """Calculate fuzzy string similarity.

        Args:
            text1: First string
            text2: Second string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0

        # Exact match
        if text1 == text2:
            return 1.0

        # Check if one contains the other
        if text1 in text2 or text2 in text1:
            return 0.9

        # Use SequenceMatcher for fuzzy matching
        ratio = SequenceMatcher(None, text1, text2).ratio()

        # Also check word-level matching
        words1 = set(text1.split())
        words2 = set(text2.split())

        if words1 and words2:
            word_overlap = len(words1 & words2) / max(len(words1), len(words2))
            # Combine character and word matching
            return max(ratio, word_overlap)

        return ratio

    def identify_action_type(self, player_input: str) -> ActionType | None:
        """Identify the action type from input without predictions.

        Useful for quick classification before full matching.

        Args:
            player_input: Raw player input

        Returns:
            ActionType if identifiable, None otherwise
        """
        normalized = self._normalize(player_input)
        verb, _ = self._extract_verb_and_target(normalized)

        if verb:
            return ACTION_VERBS.get(verb)

        return None

    def extract_target_reference(
        self, player_input: str, manifest: GroundingManifest
    ) -> str | None:
        """Extract entity reference from player input.

        Attempts to find which entity in the manifest the player
        is referring to.

        Args:
            player_input: Raw player input
            manifest: Grounding manifest

        Returns:
            Entity key if found, None otherwise
        """
        normalized = self._normalize(player_input)
        _, target_text = self._extract_verb_and_target(normalized)

        if not target_text:
            return None

        best_key = None
        best_score = 0.5  # Minimum threshold

        for key, entity in manifest.all_entities().items():
            score = self._fuzzy_match_score(target_text, entity.display_name.lower())
            if score > best_score:
                best_score = score
                best_key = key

        return best_key
