"""Action classifier for minimal context mode.

Classifies player input into action categories to determine
which context to pre-fetch for local LLMs.
"""

from enum import Enum


class ActionCategory(Enum):
    """Categories of player actions for context pre-fetching."""

    LOOK = "look"  # Observation actions
    TAKE_DROP = "take_drop"  # Item manipulation
    NEEDS = "needs"  # Need satisfaction (eat, drink, rest)
    SOCIAL = "social"  # NPC interaction
    COMBAT = "combat"  # Combat actions
    MOVEMENT = "movement"  # Travel/movement
    DEFAULT = "default"  # Fallback for unknown actions


class ActionClassifier:
    """Keyword-based action classifier.

    Analyzes player input to determine the likely action category,
    which determines what context to pre-fetch for the LLM.
    """

    # Keywords that indicate each action category
    KEYWORDS: dict[ActionCategory, set[str]] = {
        ActionCategory.LOOK: {
            "look",
            "examine",
            "inspect",
            "search",
            "observe",
            "check",
            "see",
            "watch",
            "scan",
            "peer",
            "gaze",
            "study",
            "investigate",
        },
        ActionCategory.TAKE_DROP: {
            "take",
            "pick",
            "grab",
            "drop",
            "put",
            "pocket",
            "store",
            "place",
            "set",
            "leave",
            "discard",
            "throw",
        },
        ActionCategory.NEEDS: {
            "eat",
            "drink",
            "rest",
            "sleep",
            "bathe",
            "wash",
            "nap",
            "relax",
            "doze",
            "snack",
            "dine",
            "sip",
            "gulp",
            "shower",
            "clean",
        },
        ActionCategory.SOCIAL: {
            "talk",
            "ask",
            "say",
            "tell",
            "greet",
            "speak",
            "chat",
            "converse",
            "inquire",
            "question",
            "hello",
            "hi",
            "goodbye",
            "thank",
        },
        ActionCategory.COMBAT: {
            "attack",
            "fight",
            "hit",
            "strike",
            "stab",
            "shoot",
            "swing",
            "slash",
            "punch",
            "kick",
            "block",
            "parry",
            "dodge",
            "defend",
        },
        ActionCategory.MOVEMENT: {
            "go",
            "walk",
            "move",
            "travel",
            "head",
            "enter",
            "leave",
            "exit",
            "run",
            "return",
            "approach",
            "step",
            "climb",
            "descend",
        },
    }

    @classmethod
    def classify(cls, player_input: str) -> ActionCategory:
        """Classify player input into an action category.

        Args:
            player_input: The player's input text.

        Returns:
            The detected ActionCategory, or DEFAULT if no match.
        """
        # Normalize input: lowercase and extract words
        words = set(player_input.lower().split())

        # Also check for word stems (e.g., "eating" -> "eat")
        stems = set()
        for word in words:
            # Simple stemming: remove common suffixes
            if word.endswith("ing"):
                stems.add(word[:-3])
            elif word.endswith("ed"):
                stems.add(word[:-2])
            elif word.endswith("s") and len(word) > 3:
                stems.add(word[:-1])

        all_words = words | stems

        # Check each category for keyword matches
        for category, keywords in cls.KEYWORDS.items():
            if all_words & keywords:
                return category

        return ActionCategory.DEFAULT

    @classmethod
    def get_keywords(cls, category: ActionCategory) -> set[str]:
        """Get keywords for a specific category.

        Args:
            category: The action category.

        Returns:
            Set of keywords for that category.
        """
        return cls.KEYWORDS.get(category, set())
