"""Pattern-based command parsing for player input.

This module provides regex patterns for recognizing player commands
and natural language intents, converting them to Action objects.
"""

import re
from dataclasses import dataclass

from src.parser.action_types import Action, ActionType, ParsedIntent


@dataclass
class PatternMatch:
    """Result of a pattern match."""

    action_type: ActionType
    target: str | None = None
    indirect_target: str | None = None
    manner: str | None = None
    match_confidence: float = 1.0  # 1.0 for exact commands, lower for fuzzy


# Explicit slash command patterns - highest priority
# Format: (pattern, action_type, capture_groups_meaning)
COMMAND_PATTERNS: list[tuple[str, ActionType, list[str]]] = [
    # Movement
    (r"^/go\s+(.+)$", ActionType.MOVE, ["target"]),
    (r"^/move\s+(.+)$", ActionType.MOVE, ["target"]),
    (r"^/enter\s+(.+)$", ActionType.ENTER, ["target"]),
    (r"^/exit$", ActionType.EXIT, []),
    (r"^/leave$", ActionType.EXIT, []),
    # Items
    (r"^/take\s+(.+)$", ActionType.TAKE, ["target"]),
    (r"^/get\s+(.+)$", ActionType.TAKE, ["target"]),
    (r"^/drop\s+(.+)$", ActionType.DROP, ["target"]),
    (r"^/give\s+(.+?)\s+to\s+(.+)$", ActionType.GIVE, ["target", "indirect_target"]),
    (r"^/use\s+(.+?)(?:\s+on\s+(.+))?$", ActionType.USE, ["target", "indirect_target"]),
    (r"^/equip\s+(.+)$", ActionType.EQUIP, ["target"]),
    (r"^/wear\s+(.+)$", ActionType.EQUIP, ["target"]),
    (r"^/unequip\s+(.+)$", ActionType.UNEQUIP, ["target"]),
    (r"^/remove\s+(.+)$", ActionType.UNEQUIP, ["target"]),
    (r"^/examine\s+(.+)$", ActionType.EXAMINE, ["target"]),
    (r"^/look\s+at\s+(.+)$", ActionType.EXAMINE, ["target"]),
    (r"^/open\s+(.+)$", ActionType.OPEN, ["target"]),
    (r"^/close\s+(.+)$", ActionType.CLOSE, ["target"]),
    # Combat
    (r"^/attack\s+(.+)$", ActionType.ATTACK, ["target"]),
    (r"^/hit\s+(.+)$", ActionType.ATTACK, ["target"]),
    (r"^/defend$", ActionType.DEFEND, []),
    (r"^/flee$", ActionType.FLEE, []),
    (r"^/run$", ActionType.FLEE, []),
    # Social
    (r"^/talk\s+(?:to\s+)?(.+)$", ActionType.TALK, ["target"]),
    (r"^/speak\s+(?:to\s+)?(.+)$", ActionType.TALK, ["target"]),
    (r"^/ask\s+(.+?)\s+about\s+(.+)$", ActionType.ASK, ["target", "indirect_target"]),
    (r"^/tell\s+(.+?)\s+(?:about\s+)?(.+)$", ActionType.TELL, ["target", "indirect_target"]),
    (r"^/trade\s+(?:with\s+)?(.+)$", ActionType.TRADE, ["target"]),
    (r"^/persuade\s+(.+)$", ActionType.PERSUADE, ["target"]),
    (r"^/intimidate\s+(.+)$", ActionType.INTIMIDATE, ["target"]),
    # World
    (r"^/search(?:\s+(.+))?$", ActionType.SEARCH, ["target"]),
    (r"^/rest$", ActionType.REST, []),
    (r"^/wait(?:\s+(\d+))?$", ActionType.WAIT, ["target"]),  # target = minutes
    (r"^/sleep$", ActionType.SLEEP, []),
    # Consumption
    (r"^/eat\s+(.+)$", ActionType.EAT, ["target"]),
    (r"^/drink\s+(.+)$", ActionType.DRINK, ["target"]),
    # Skills
    (r"^/craft\s+(.+)$", ActionType.CRAFT, ["target"]),
    (r"^/lockpick\s+(.+)$", ActionType.LOCKPICK, ["target"]),
    (r"^/sneak$", ActionType.SNEAK, []),
    (r"^/climb\s+(.+)$", ActionType.CLIMB, ["target"]),
    (r"^/swim(?:\s+(?:to\s+)?(.+))?$", ActionType.SWIM, ["target"]),
    # Meta
    (r"^/look$", ActionType.LOOK, []),
    (r"^/l$", ActionType.LOOK, []),
    (r"^/inventory$", ActionType.INVENTORY, []),
    (r"^/inv$", ActionType.INVENTORY, []),
    (r"^/i$", ActionType.INVENTORY, []),
    (r"^/status$", ActionType.STATUS, []),
    (r"^/stats$", ActionType.STATUS, []),
]

# Natural language patterns - lower priority, more flexible
# Format: (pattern, action_type, capture_groups_meaning, confidence)
# Patterns should be ordered from most specific to least specific
NATURAL_LANGUAGE_PATTERNS: list[tuple[str, ActionType, list[str], float]] = [
    # Movement - high confidence patterns
    # Stop capturing at punctuation or common clause starters like "in order to", "to look", etc.
    (
        r"\b(?:go|walk|head|move|travel|run)\s+(?:to|towards?|into|over\s+to)\s+(?:the\s+)?([^.?!]+?)(?:\s+(?:in\s+order\s+to|to\s+(?:look|find|see|get|search|check)|and\s+|then\s+)|[.?!]|$)",
        ActionType.MOVE,
        ["target"],
        0.9,
    ),
    (
        r"\benter\s+(?:the\s+)?(.+)",
        ActionType.ENTER,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:leave|exit)\s+(?:the\s+)?(.+)",
        ActionType.EXIT,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:leave|exit)(?:\s+here)?$",
        ActionType.EXIT,
        [],
        0.85,
    ),
    # Item interactions - high confidence
    (
        r"\b(?:pick\s+up|take|grab|get|collect)\s+(?:the\s+)?(.+)",
        ActionType.TAKE,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:drop|put\s+down|set\s+down|leave|discard)\s+(?:the\s+)?(.+)",
        ActionType.DROP,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:give|hand|pass)\s+(?:the\s+)?(.+?)\s+to\s+(.+)",
        ActionType.GIVE,
        ["target", "indirect_target"],
        0.9,
    ),
    (
        r"\buse\s+(?:the\s+)?(.+?)\s+on\s+(.+)",
        ActionType.USE,
        ["target", "indirect_target"],
        0.9,
    ),
    (
        r"\buse\s+(?:the\s+)?(.+)",
        ActionType.USE,
        ["target"],
        0.8,
    ),
    (
        r"\b(?:equip|wield|wear|put\s+on)\s+(?:the\s+)?(.+)",
        ActionType.EQUIP,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:unequip|remove|take\s+off)\s+(?:the\s+)?(.+)",
        ActionType.UNEQUIP,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:examine|inspect|look\s+at|study|check)\s+(?:the\s+)?(.+)",
        ActionType.EXAMINE,
        ["target"],
        0.9,
    ),
    (
        r"\bopen\s+(?:the\s+)?(.+)",
        ActionType.OPEN,
        ["target"],
        0.9,
    ),
    (
        r"\bclose\s+(?:the\s+)?(.+)",
        ActionType.CLOSE,
        ["target"],
        0.9,
    ),
    # Combat
    (
        r"\b(?:attack|hit|strike|fight|punch|kick|slash|stab)\s+(?:the\s+)?(.+)",
        ActionType.ATTACK,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:defend|block|parry|brace)(?:\s+myself)?",
        ActionType.DEFEND,
        [],
        0.85,
    ),
    (
        r"\b(?:flee|escape|run\s+away|retreat)",
        ActionType.FLEE,
        [],
        0.85,
    ),
    # Social
    (
        r"\b(?:talk|speak|chat)\s+(?:to|with)\s+(.+)",
        ActionType.TALK,
        ["target"],
        0.9,
    ),
    (
        r"\bask\s+(.+?)\s+about\s+(.+)",
        ActionType.ASK,
        ["target", "indirect_target"],
        0.9,
    ),
    (
        r"\btell\s+(.+?)\s+(?:about|that)\s+(.+)",
        ActionType.TELL,
        ["target", "indirect_target"],
        0.9,
    ),
    (
        r"\b(?:trade|barter|bargain)\s+(?:with\s+)?(.+)",
        ActionType.TRADE,
        ["target"],
        0.85,
    ),
    (
        r"\b(?:persuade|convince|talk\s+.+\s+into)\s+(.+)",
        ActionType.PERSUADE,
        ["target"],
        0.85,
    ),
    (
        r"\b(?:intimidate|threaten|scare)\s+(.+)",
        ActionType.INTIMIDATE,
        ["target"],
        0.85,
    ),
    # World interaction
    # Note: "look around" is handled by LOOK pattern, not SEARCH
    (
        r"\b(?:search|investigate)(?:\s+(?:the\s+)?(.+))?",
        ActionType.SEARCH,
        ["target"],
        0.8,
    ),
    (
        r"\b(?:rest|take\s+a\s+break|sit\s+down)",
        ActionType.REST,
        [],
        0.85,
    ),
    (
        r"\b(?:wait|stay|remain)(?:\s+(?:for\s+)?(\d+)\s*(?:minutes?|mins?)?)?",
        ActionType.WAIT,
        ["target"],
        0.8,
    ),
    (
        r"\b(?:sleep|go\s+to\s+sleep|take\s+a\s+nap)",
        ActionType.SLEEP,
        [],
        0.85,
    ),
    # Consumption
    (
        r"\b(?:eat|consume|devour)\s+(?:the\s+)?(.+)",
        ActionType.EAT,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:drink|sip|gulp)\s+(?:the\s+)?(.+)",
        ActionType.DRINK,
        ["target"],
        0.9,
    ),
    # Skills
    (
        r"\b(?:craft|make|create|build)\s+(?:a\s+)?(.+)",
        ActionType.CRAFT,
        ["target"],
        0.85,
    ),
    (
        r"\b(?:pick\s+the\s+lock|lockpick|pick\s+lock)\s+(?:on\s+)?(?:the\s+)?(.+)",
        ActionType.LOCKPICK,
        ["target"],
        0.9,
    ),
    (
        r"\b(?:sneak|move\s+quietly|stealth)",
        ActionType.SNEAK,
        [],
        0.85,
    ),
    (
        r"\b(?:climb|scale)\s+(?:the\s+)?(.+)",
        ActionType.CLIMB,
        ["target"],
        0.9,
    ),
    (
        r"\bswim(?:\s+(?:to|across|through)\s+(?:the\s+)?(.+))?",
        ActionType.SWIM,
        ["target"],
        0.85,
    ),
    # Meta - very high confidence since these are simple
    (
        r"^(?:look\s+around|look$|l$)",
        ActionType.LOOK,
        [],
        0.95,
    ),
    (
        r"^(?:where\s+am\s+i|where\s+is\s+this|what\s+(?:is\s+this\s+place|place\s+is\s+this))\??$",
        ActionType.LOOK,
        [],
        0.95,
    ),
    (
        r"^(?:inventory|inv|i|check\s+(?:my\s+)?(?:inventory|items|stuff))$",
        ActionType.INVENTORY,
        [],
        0.95,
    ),
    (
        r"^(?:status|stats|check\s+(?:my\s+)?(?:status|health|stats))$",
        ActionType.STATUS,
        [],
        0.95,
    ),
]

# Manner/adverb patterns that modify how an action is performed
MANNER_PATTERNS: list[tuple[str, str]] = [
    (r"\bcarefully\b", "carefully"),
    (r"\bquickly\b", "quickly"),
    (r"\bslowly\b", "slowly"),
    (r"\bquietly\b", "quietly"),
    (r"\bloudly\b", "loudly"),
    (r"\bstealthily\b", "stealthily"),
    (r"\bnervously\b", "nervously"),
    (r"\bconfidently\b", "confidently"),
    (r"\bcautiously\b", "cautiously"),
    (r"\brecklessly\b", "recklessly"),
    (r"\bforcefully\b", "forcefully"),
    (r"\bgently\b", "gently"),
    (r"\baggressively\b", "aggressively"),
    (r"\bpolitely\b", "politely"),
    (r"\brudely\b", "rudely"),
]


def _clean_target(target: str | None) -> str | None:
    """Clean up a captured target string."""
    if target is None:
        return None
    # Remove common trailing words and punctuation
    cleaned = target.strip()
    # Remove trailing punctuation
    cleaned = re.sub(r"[.,!?;:]+$", "", cleaned)
    # Remove trailing "please" or similar
    cleaned = re.sub(r"\s+please$", "", cleaned, flags=re.IGNORECASE)
    return cleaned if cleaned else None


def _extract_manner(text: str) -> str | None:
    """Extract manner/adverb from text."""
    for pattern, manner in MANNER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return manner
    return None


def parse_command(text: str) -> PatternMatch | None:
    """Try to parse text as an explicit slash command.

    Args:
        text: Player input text.

    Returns:
        PatternMatch if a command was recognized, None otherwise.
    """
    text = text.strip()

    for pattern, action_type, group_names in COMMAND_PATTERNS:
        if match := re.match(pattern, text, re.IGNORECASE):
            result = PatternMatch(action_type=action_type, match_confidence=1.0)

            # Extract capture groups
            for i, name in enumerate(group_names, 1):
                try:
                    value = _clean_target(match.group(i))
                    if name == "target":
                        result.target = value
                    elif name == "indirect_target":
                        result.indirect_target = value
                except IndexError:
                    pass

            return result

    return None


def parse_natural_language(text: str) -> list[PatternMatch]:
    """Parse natural language for action intents.

    This can return multiple matches if the text contains multiple actions.

    Args:
        text: Player input text.

    Returns:
        List of PatternMatch objects for recognized actions.
    """
    text = text.strip()
    matches: list[PatternMatch] = []
    manner = _extract_manner(text)

    for pattern, action_type, group_names, confidence in NATURAL_LANGUAGE_PATTERNS:
        if match := re.search(pattern, text, re.IGNORECASE):
            result = PatternMatch(
                action_type=action_type,
                manner=manner,
                match_confidence=confidence,
            )

            # Extract capture groups
            for i, name in enumerate(group_names, 1):
                try:
                    value = _clean_target(match.group(i))
                    if name == "target":
                        result.target = value
                    elif name == "indirect_target":
                        result.indirect_target = value
                except IndexError:
                    pass

            matches.append(result)

    # Sort by confidence and remove duplicates (same action type + target)
    seen = set()
    unique_matches = []
    matches.sort(key=lambda m: m.match_confidence, reverse=True)

    for m in matches:
        key = (m.action_type, m.target)
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    return unique_matches


def parse_input(text: str) -> ParsedIntent:
    """Parse player input into a ParsedIntent.

    First tries explicit slash commands, then falls back to natural language
    pattern matching. This is the fast path - for complex inputs that don't
    match patterns, use the LLM classifier.

    Args:
        text: Raw player input.

    Returns:
        ParsedIntent with recognized actions.
    """
    text = text.strip()

    if not text:
        return ParsedIntent(raw_input=text)

    # Try explicit command first
    if text.startswith("/"):
        if command_match := parse_command(text):
            action = Action(
                type=command_match.action_type,
                target=command_match.target,
                indirect_target=command_match.indirect_target,
                manner=command_match.manner,
            )
            return ParsedIntent(actions=[action], raw_input=text)
        else:
            # Unrecognized command - might want to surface this
            return ParsedIntent(
                raw_input=text,
                needs_clarification=True,
                clarification_prompt=f"Unknown command. Type /help for available commands.",
            )

    # Try natural language patterns
    nl_matches = parse_natural_language(text)

    if nl_matches:
        actions = [
            Action(
                type=m.action_type,
                target=m.target,
                indirect_target=m.indirect_target,
                manner=m.manner,
            )
            for m in nl_matches
        ]

        # Extract ambient flavor (anything that's not part of the action)
        ambient = _extract_manner(text)

        return ParsedIntent(
            actions=actions,
            ambient_flavor=ambient,
            raw_input=text,
        )

    # No patterns matched - mark for LLM classification
    return ParsedIntent(
        raw_input=text,
        actions=[],  # No actions recognized
    )
