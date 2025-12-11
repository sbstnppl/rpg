"""Contested rolls and action economy.

Provides mechanics for opposed checks (grapple, stealth, etc.)
and action budget tracking for combat turns.
"""

from dataclasses import dataclass
from enum import Enum

from src.dice.roller import roll
from src.dice.types import AdvantageType


class ActionType(Enum):
    """Types of actions in combat."""

    STANDARD = "standard"  # Attack, cast spell, use item, etc.
    MOVE = "move"  # Move up to speed
    BONUS = "bonus"  # Quick actions (off-hand attack, some spells)
    REACTION = "reaction"  # Opportunity attack, counterspell, etc.
    FREE = "free"  # Drop item, speak, etc. (no limit)


@dataclass
class ContestResult:
    """Result of a contested roll."""

    attacker_roll: int
    defender_roll: int
    attacker_modifier: int
    defender_modifier: int
    attacker_total: int
    defender_total: int
    winner: str  # "attacker" or "defender"
    margin: int  # Positive = attacker advantage
    contest_type: str = "generic"
    attacker_skill: str | None = None
    defender_skill: str | None = None


def resolve_contest(attacker_total: int, defender_total: int) -> str:
    """Determine winner of a contest.

    Ties go to the defender (status quo maintained).

    Args:
        attacker_total: Attacker's total roll + modifier.
        defender_total: Defender's total roll + modifier.

    Returns:
        "attacker" or "defender"
    """
    if attacker_total > defender_total:
        return "attacker"
    return "defender"  # Ties go to defender


def contested_roll(
    attacker_modifier: int = 0,
    defender_modifier: int = 0,
    attacker_advantage: bool = False,
    attacker_disadvantage: bool = False,
    defender_advantage: bool = False,
    defender_disadvantage: bool = False,
    contest_type: str = "generic",
    attacker_skill: str | None = None,
    defender_skill: str | None = None,
) -> ContestResult:
    """Perform a contested roll between two parties.

    Both roll d20 + modifiers. Higher total wins. Ties go to defender.

    Args:
        attacker_modifier: Modifier for attacker (skill + ability).
        defender_modifier: Modifier for defender.
        attacker_advantage: Attacker rolls with advantage.
        attacker_disadvantage: Attacker rolls with disadvantage.
        defender_advantage: Defender rolls with advantage.
        defender_disadvantage: Defender rolls with disadvantage.
        contest_type: Type of contest for logging.
        attacker_skill: Name of attacker's skill used.
        defender_skill: Name of defender's skill used.

    Returns:
        ContestResult with both rolls and winner.
    """
    # Determine advantage type for attacker
    if attacker_advantage and not attacker_disadvantage:
        attacker_adv = AdvantageType.ADVANTAGE
    elif attacker_disadvantage and not attacker_advantage:
        attacker_adv = AdvantageType.DISADVANTAGE
    else:
        attacker_adv = AdvantageType.NORMAL

    # Determine advantage type for defender
    if defender_advantage and not defender_disadvantage:
        defender_adv = AdvantageType.ADVANTAGE
    elif defender_disadvantage and not defender_advantage:
        defender_adv = AdvantageType.DISADVANTAGE
    else:
        defender_adv = AdvantageType.NORMAL

    # Roll for attacker
    if attacker_adv == AdvantageType.ADVANTAGE:
        roll1 = roll("1d20").total
        roll2 = roll("1d20").total
        attacker_roll = max(roll1, roll2)
    elif attacker_adv == AdvantageType.DISADVANTAGE:
        roll1 = roll("1d20").total
        roll2 = roll("1d20").total
        attacker_roll = min(roll1, roll2)
    else:
        attacker_roll = roll("1d20").total

    # Roll for defender
    if defender_adv == AdvantageType.ADVANTAGE:
        roll1 = roll("1d20").total
        roll2 = roll("1d20").total
        defender_roll = max(roll1, roll2)
    elif defender_adv == AdvantageType.DISADVANTAGE:
        roll1 = roll("1d20").total
        roll2 = roll("1d20").total
        defender_roll = min(roll1, roll2)
    else:
        defender_roll = roll("1d20").total

    attacker_total = attacker_roll + attacker_modifier
    defender_total = defender_roll + defender_modifier
    winner = resolve_contest(attacker_total, defender_total)
    margin = attacker_total - defender_total

    return ContestResult(
        attacker_roll=attacker_roll,
        defender_roll=defender_roll,
        attacker_modifier=attacker_modifier,
        defender_modifier=defender_modifier,
        attacker_total=attacker_total,
        defender_total=defender_total,
        winner=winner,
        margin=margin,
        contest_type=contest_type,
        attacker_skill=attacker_skill,
        defender_skill=defender_skill,
    )


# Common contest types


def grapple_contest(
    grappler_athletics: int,
    target_athletics: int,
    target_acrobatics: int,
    grappler_advantage: bool = False,
    grappler_disadvantage: bool = False,
    target_advantage: bool = False,
    target_disadvantage: bool = False,
) -> ContestResult:
    """Resolve a grapple attempt.

    Grappler uses Athletics. Target uses Athletics OR Acrobatics (their choice).

    Args:
        grappler_athletics: Grappler's Athletics modifier.
        target_athletics: Target's Athletics modifier.
        target_acrobatics: Target's Acrobatics modifier.
        grappler_advantage: Grappler has advantage.
        grappler_disadvantage: Grappler has disadvantage.
        target_advantage: Target has advantage.
        target_disadvantage: Target has disadvantage.

    Returns:
        ContestResult with grapple outcome.
    """
    # Target picks better skill
    if target_acrobatics >= target_athletics:
        defender_mod = target_acrobatics
        defender_skill = "acrobatics"
    else:
        defender_mod = target_athletics
        defender_skill = "athletics"

    return contested_roll(
        attacker_modifier=grappler_athletics,
        defender_modifier=defender_mod,
        attacker_advantage=grappler_advantage,
        attacker_disadvantage=grappler_disadvantage,
        defender_advantage=target_advantage,
        defender_disadvantage=target_disadvantage,
        contest_type="grapple",
        attacker_skill="athletics",
        defender_skill=defender_skill,
    )


def escape_grapple_contest(
    escapee_athletics: int,
    escapee_acrobatics: int,
    grappler_athletics: int,
    escapee_advantage: bool = False,
    escapee_disadvantage: bool = False,
    grappler_advantage: bool = False,
    grappler_disadvantage: bool = False,
) -> ContestResult:
    """Resolve an escape from grapple attempt.

    Escapee uses Athletics OR Acrobatics. Grappler uses Athletics.

    Args:
        escapee_athletics: Escapee's Athletics modifier.
        escapee_acrobatics: Escapee's Acrobatics modifier.
        grappler_athletics: Grappler's Athletics modifier.
        escapee_advantage: Escapee has advantage.
        escapee_disadvantage: Escapee has disadvantage.
        grappler_advantage: Grappler has advantage.
        grappler_disadvantage: Grappler has disadvantage.

    Returns:
        ContestResult with escape outcome.
    """
    # Escapee picks better skill
    if escapee_acrobatics >= escapee_athletics:
        attacker_mod = escapee_acrobatics
        attacker_skill = "acrobatics"
    else:
        attacker_mod = escapee_athletics
        attacker_skill = "athletics"

    return contested_roll(
        attacker_modifier=attacker_mod,
        defender_modifier=grappler_athletics,
        attacker_advantage=escapee_advantage,
        attacker_disadvantage=escapee_disadvantage,
        defender_advantage=grappler_advantage,
        defender_disadvantage=grappler_disadvantage,
        contest_type="escape_grapple",
        attacker_skill=attacker_skill,
        defender_skill="athletics",
    )


def shove_contest(
    shover_athletics: int,
    target_athletics: int,
    target_acrobatics: int,
    shover_advantage: bool = False,
    shover_disadvantage: bool = False,
    target_advantage: bool = False,
    target_disadvantage: bool = False,
) -> ContestResult:
    """Resolve a shove attempt.

    Shover uses Athletics. Target uses Athletics OR Acrobatics.

    Args:
        shover_athletics: Shover's Athletics modifier.
        target_athletics: Target's Athletics modifier.
        target_acrobatics: Target's Acrobatics modifier.
        shover_advantage: Shover has advantage.
        shover_disadvantage: Shover has disadvantage.
        target_advantage: Target has advantage.
        target_disadvantage: Target has disadvantage.

    Returns:
        ContestResult with shove outcome.
    """
    # Target picks better skill
    if target_acrobatics >= target_athletics:
        defender_mod = target_acrobatics
        defender_skill = "acrobatics"
    else:
        defender_mod = target_athletics
        defender_skill = "athletics"

    return contested_roll(
        attacker_modifier=shover_athletics,
        defender_modifier=defender_mod,
        attacker_advantage=shover_advantage,
        attacker_disadvantage=shover_disadvantage,
        defender_advantage=target_advantage,
        defender_disadvantage=target_disadvantage,
        contest_type="shove",
        attacker_skill="athletics",
        defender_skill=defender_skill,
    )


def stealth_contest(
    hider_stealth: int,
    seeker_perception: int,
    hider_advantage: bool = False,
    hider_disadvantage: bool = False,
    seeker_advantage: bool = False,
    seeker_disadvantage: bool = False,
) -> ContestResult:
    """Resolve a stealth vs perception contest.

    Hider uses Stealth. Seeker uses Perception.

    Args:
        hider_stealth: Hider's Stealth modifier.
        seeker_perception: Seeker's Perception modifier.
        hider_advantage: Hider has advantage.
        hider_disadvantage: Hider has disadvantage.
        seeker_advantage: Seeker has advantage.
        seeker_disadvantage: Seeker has disadvantage.

    Returns:
        ContestResult with stealth outcome.
    """
    return contested_roll(
        attacker_modifier=hider_stealth,
        defender_modifier=seeker_perception,
        attacker_advantage=hider_advantage,
        attacker_disadvantage=hider_disadvantage,
        defender_advantage=seeker_advantage,
        defender_disadvantage=seeker_disadvantage,
        contest_type="stealth",
        attacker_skill="stealth",
        defender_skill="perception",
    )


def social_contest(
    actor_skill: int,
    actor_skill_name: str,
    observer_insight: int,
    actor_advantage: bool = False,
    actor_disadvantage: bool = False,
    observer_advantage: bool = False,
    observer_disadvantage: bool = False,
) -> ContestResult:
    """Resolve a social contest (deception, persuasion, etc.).

    Actor uses their social skill. Observer uses Insight.

    Args:
        actor_skill: Actor's social skill modifier.
        actor_skill_name: Name of skill (deception, persuasion, etc.).
        observer_insight: Observer's Insight modifier.
        actor_advantage: Actor has advantage.
        actor_disadvantage: Actor has disadvantage.
        observer_advantage: Observer has advantage.
        observer_disadvantage: Observer has disadvantage.

    Returns:
        ContestResult with social contest outcome.
    """
    return contested_roll(
        attacker_modifier=actor_skill,
        defender_modifier=observer_insight,
        attacker_advantage=actor_advantage,
        attacker_disadvantage=actor_disadvantage,
        defender_advantage=observer_advantage,
        defender_disadvantage=observer_disadvantage,
        contest_type="social",
        attacker_skill=actor_skill_name,
        defender_skill="insight",
    )


# Action Economy


@dataclass
class ActionBudget:
    """Tracks available actions for a combat turn."""

    standard_actions: int = 1
    move_actions: int = 1
    bonus_actions: int = 1
    reaction: int = 1
    _standard_used: int = 0
    _move_used: int = 0
    _bonus_used: int = 0
    _reaction_used: int = 0

    def can_use(self, action_type: ActionType) -> bool:
        """Check if an action type is available.

        Args:
            action_type: Type of action to check.

        Returns:
            True if action is available.
        """
        if action_type == ActionType.FREE:
            return True
        if action_type == ActionType.STANDARD:
            return self._standard_used < self.standard_actions
        if action_type == ActionType.MOVE:
            return self._move_used < self.move_actions
        if action_type == ActionType.BONUS:
            return self._bonus_used < self.bonus_actions
        if action_type == ActionType.REACTION:
            return self._reaction_used < self.reaction
        return False

    def use(self, action_type: ActionType) -> bool:
        """Use an action.

        Args:
            action_type: Type of action to use.

        Returns:
            True if action was used, False if not available.
        """
        if not self.can_use(action_type):
            return False

        if action_type == ActionType.FREE:
            return True  # Free actions always succeed
        if action_type == ActionType.STANDARD:
            self._standard_used += 1
        elif action_type == ActionType.MOVE:
            self._move_used += 1
        elif action_type == ActionType.BONUS:
            self._bonus_used += 1
        elif action_type == ActionType.REACTION:
            self._reaction_used += 1

        return True

    def reset(self) -> None:
        """Reset all actions for a new turn."""
        self._standard_used = 0
        self._move_used = 0
        self._bonus_used = 0
        self._reaction_used = 0

    def can_convert_standard_to_move(self) -> bool:
        """Check if standard action can be converted to move.

        Returns:
            True if conversion is possible.
        """
        return self._standard_used < self.standard_actions

    def convert_standard_to_move(self) -> bool:
        """Convert standard action to additional move action.

        Returns:
            True if conversion succeeded.
        """
        if not self.can_convert_standard_to_move():
            return False
        self._standard_used += 1
        self._move_used = max(0, self._move_used - 1)  # Refund move action
        return True

    def get_remaining_string(self) -> str:
        """Get human-readable string of remaining actions.

        Returns:
            Formatted string of available actions.
        """
        parts = []
        remaining_standard = self.standard_actions - self._standard_used
        remaining_move = self.move_actions - self._move_used
        remaining_bonus = self.bonus_actions - self._bonus_used
        remaining_reaction = self.reaction - self._reaction_used

        if remaining_standard > 0:
            parts.append(f"Standard: {remaining_standard}")
        if remaining_move > 0:
            parts.append(f"Move: {remaining_move}")
        if remaining_bonus > 0:
            parts.append(f"Bonus: {remaining_bonus}")
        if remaining_reaction > 0:
            parts.append(f"Reaction: {remaining_reaction}")

        return ", ".join(parts) if parts else "No actions remaining"
