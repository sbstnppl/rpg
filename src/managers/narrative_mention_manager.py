"""Manager for tracking narrative mentions to prevent repetition.

This manager tracks various types of mentions in the narrative:
- Equipment states (torn clothes, damaged items)
- Injuries (limp, bandaged arm)
- Relationship dynamics (tension with NPC)
- Environmental observations (weather, time of day)

It prevents the narrator from repeatedly describing the same stable
conditions every turn.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.context_summary import NarrativeMentionLog
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Hours (in-game time) before a stable condition should be reminded
DEFAULT_REMINDER_HOURS = 4

# Mention types and their typical reminder intervals (in-game hours)
MENTION_TYPE_INTERVALS = {
    "equipment": 6,      # Clothing/equipment state
    "injury": 4,         # Physical injuries
    "appearance": 8,     # Appearance changes
    "relationship": 12,  # Relationship status
    "environment": 2,    # Weather, time of day
    "need_state": 2,     # Needs states (backup to NeedsCommunicationManager)
}


class NarrativeMentionManager(BaseManager):
    """Manages tracking of narrative mentions to prevent repetition.

    This complements NeedsCommunicationManager by tracking broader
    categories of stable conditions that shouldn't be repeated every turn.
    """

    def record_mention(
        self,
        mention_type: str,
        subject_key: str,
        mention_value: str,
        turn: int,
        game_time: datetime,
    ) -> NarrativeMentionLog:
        """Record that something was mentioned in the narrative.

        Args:
            mention_type: Category of mention (equipment, injury, etc.)
            subject_key: Identifier for the subject (entity_key, item_key, etc.)
            mention_value: The specific value/state mentioned (e.g., "torn")
            turn: Turn number when mentioned
            game_time: In-game datetime when mentioned

        Returns:
            The created or updated NarrativeMentionLog
        """
        # Upsert pattern
        existing = (
            self.db.query(NarrativeMentionLog)
            .filter(
                NarrativeMentionLog.session_id == self.session_id,
                NarrativeMentionLog.mention_type == mention_type,
                NarrativeMentionLog.subject_key == subject_key,
            )
            .first()
        )

        if existing:
            existing.mention_value = mention_value
            existing.mentioned_turn = turn
            existing.mentioned_game_time = game_time
            self.db.flush()
            return existing

        log = NarrativeMentionLog(
            session_id=self.session_id,
            mention_type=mention_type,
            subject_key=subject_key,
            mention_value=mention_value,
            mentioned_turn=turn,
            mentioned_game_time=game_time,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def was_recently_mentioned(
        self,
        mention_type: str,
        subject_key: str,
        current_turn: int,
        current_game_time: datetime,
        hours_threshold: float | None = None,
    ) -> bool:
        """Check if something was recently mentioned.

        Args:
            mention_type: Category of mention
            subject_key: Identifier for the subject
            current_turn: Current turn number
            current_game_time: Current in-game datetime
            hours_threshold: Hours before considered stale (default from MENTION_TYPE_INTERVALS)

        Returns:
            True if mentioned within the threshold time
        """
        if hours_threshold is None:
            hours_threshold = MENTION_TYPE_INTERVALS.get(
                mention_type, DEFAULT_REMINDER_HOURS
            )

        log = (
            self.db.query(NarrativeMentionLog)
            .filter(
                NarrativeMentionLog.session_id == self.session_id,
                NarrativeMentionLog.mention_type == mention_type,
                NarrativeMentionLog.subject_key == subject_key,
            )
            .first()
        )

        if not log:
            return False

        hours_since = (
            current_game_time - log.mentioned_game_time
        ).total_seconds() / 3600

        return hours_since < hours_threshold

    def get_last_mention(
        self,
        mention_type: str,
        subject_key: str,
    ) -> NarrativeMentionLog | None:
        """Get the last mention of a subject.

        Args:
            mention_type: Category of mention
            subject_key: Identifier for the subject

        Returns:
            NarrativeMentionLog or None if never mentioned
        """
        return (
            self.db.query(NarrativeMentionLog)
            .filter(
                NarrativeMentionLog.session_id == self.session_id,
                NarrativeMentionLog.mention_type == mention_type,
                NarrativeMentionLog.subject_key == subject_key,
            )
            .first()
        )

    def get_stale_mentions(
        self,
        current_turn: int,
        current_game_time: datetime,
    ) -> list[NarrativeMentionLog]:
        """Get all mentions that are stale and might need reminding.

        Args:
            current_turn: Current turn number
            current_game_time: Current in-game datetime

        Returns:
            List of NarrativeMentionLog entries that are stale
        """
        all_mentions = (
            self.db.query(NarrativeMentionLog)
            .filter(NarrativeMentionLog.session_id == self.session_id)
            .all()
        )

        stale = []
        for mention in all_mentions:
            threshold = MENTION_TYPE_INTERVALS.get(
                mention.mention_type, DEFAULT_REMINDER_HOURS
            )
            hours_since = (
                current_game_time - mention.mentioned_game_time
            ).total_seconds() / 3600

            if hours_since >= threshold:
                stale.append(mention)

        return stale

    def get_mentions_by_type(
        self,
        mention_type: str,
    ) -> list[NarrativeMentionLog]:
        """Get all mentions of a specific type.

        Args:
            mention_type: Category of mention

        Returns:
            List of NarrativeMentionLog entries for that type
        """
        return (
            self.db.query(NarrativeMentionLog)
            .filter(
                NarrativeMentionLog.session_id == self.session_id,
                NarrativeMentionLog.mention_type == mention_type,
            )
            .all()
        )

    def clear_mention(
        self,
        mention_type: str,
        subject_key: str,
    ) -> bool:
        """Clear a mention (e.g., when the condition no longer applies).

        Args:
            mention_type: Category of mention
            subject_key: Identifier for the subject

        Returns:
            True if a mention was deleted, False otherwise
        """
        deleted = (
            self.db.query(NarrativeMentionLog)
            .filter(
                NarrativeMentionLog.session_id == self.session_id,
                NarrativeMentionLog.mention_type == mention_type,
                NarrativeMentionLog.subject_key == subject_key,
            )
            .delete()
        )
        self.db.flush()
        return deleted > 0

    def get_stable_conditions_for_context(
        self,
        current_turn: int,
        current_game_time: datetime,
    ) -> dict[str, list[dict]]:
        """Get stable conditions categorized for context injection.

        Returns conditions that are stable (not stale) and shouldn't be
        re-described in detail, but might be referenced.

        Args:
            current_turn: Current turn number
            current_game_time: Current in-game datetime

        Returns:
            Dict mapping mention_type to list of condition dicts
        """
        all_mentions = (
            self.db.query(NarrativeMentionLog)
            .filter(NarrativeMentionLog.session_id == self.session_id)
            .all()
        )

        result: dict[str, list[dict]] = {}

        for mention in all_mentions:
            threshold = MENTION_TYPE_INTERVALS.get(
                mention.mention_type, DEFAULT_REMINDER_HOURS
            )
            hours_since = (
                current_game_time - mention.mentioned_game_time
            ).total_seconds() / 3600

            condition = {
                "subject": mention.subject_key,
                "value": mention.mention_value,
                "hours_since": round(hours_since, 1),
                "is_stale": hours_since >= threshold,
            }

            if mention.mention_type not in result:
                result[mention.mention_type] = []
            result[mention.mention_type].append(condition)

        return result

    def format_stable_conditions(
        self,
        current_turn: int,
        current_game_time: datetime,
    ) -> str:
        """Format stable conditions for narrator context.

        Args:
            current_turn: Current turn number
            current_game_time: Current in-game datetime

        Returns:
            Formatted string for narrator context
        """
        conditions = self.get_stable_conditions_for_context(
            current_turn, current_game_time
        )

        if not conditions:
            return ""

        lines = ["## Stable Conditions (do NOT re-describe unless [REMIND])"]

        for mention_type, items in conditions.items():
            if not items:
                continue

            lines.append(f"\n### {mention_type.title()}")
            for item in items:
                if item["is_stale"]:
                    lines.append(
                        f"- [REMIND] {item['subject']}: {item['value']} "
                        f"({item['hours_since']}h since mentioned)"
                    )
                else:
                    lines.append(f"- {item['subject']}: {item['value']}")

        return "\n".join(lines)
