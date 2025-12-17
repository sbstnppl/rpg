"""Summary manager for layered context summaries.

This manager handles:
- Story summary: From start to last milestone (regenerate at milestones)
- Recent summary: From last milestone to last night (regenerate daily)
- Raw turns: Full text since last night
"""

from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.context_summary import (
    ContextSummary,
    Milestone,
    SummaryType,
)
from src.database.models.session import GameSession, Turn
from src.database.models.world import TimeState
from src.llm.base import LLMProvider
from src.llm.message_types import Message, MessageRole
from src.managers.base import BaseManager
from src.managers.milestone_manager import MilestoneManager


# LLM prompts for summary generation
STORY_SUMMARY_SYSTEM = """You are a narrative summarizer for an RPG game.
Your task is to write a concise summary of the story so far.

Guidelines:
- Focus on key events, decisions, and character developments
- Include important NPCs the player has met
- Note major choices the player has made
- Keep it factual and chronological
- Maximum 400-600 words
- Write in third person past tense
"""

STORY_SUMMARY_PROMPT = """Summarize the story so far based on these milestones and events:

MILESTONES:
{milestones}

RECENT EVENTS (turns {from_turn} to {to_turn}):
{turn_summaries}

Write a narrative summary that captures:
1. Who the player character is and their current situation
2. Key events that have occurred
3. Important NPCs and relationships
4. Major decisions the player has made
5. Current objectives or goals

Keep the summary under 500 words."""

RECENT_SUMMARY_SYSTEM = """You are a narrative summarizer for an RPG game.
Your task is to summarize recent events since the last major milestone.

Guidelines:
- Focus on what happened recently (the "yesterday" and days before)
- Include interactions with NPCs
- Note any discoveries or progress
- Keep it factual
- Maximum 300-500 words
- Write in third person past tense
"""

RECENT_SUMMARY_PROMPT = """Summarize recent events from the last milestone until yesterday.

LAST MILESTONE: {milestone_description}
(Turn {milestone_turn}, Day {milestone_day})

EVENTS SINCE MILESTONE (turns {from_turn} to {to_turn}):
{turn_summaries}

Write a summary of what happened since the milestone, focusing on:
1. Key interactions and conversations
2. Discoveries or items found
3. Progress toward goals
4. Any notable events

Keep the summary under 400 words."""


class SummaryManager(BaseManager):
    """Manages layered context summaries.

    Three layers:
    1. Story summary (start → last milestone)
    2. Recent summary (last milestone → last night)
    3. Raw turns (since last night)
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        """Initialize with optional LLM provider for summary generation.

        Args:
            db: Database session
            game_session: Current game session
            llm_provider: LLM provider for generating summaries (lazy loaded if None)
        """
        super().__init__(db, game_session)
        self._llm_provider = llm_provider
        self._milestone_manager: MilestoneManager | None = None

    @property
    def llm_provider(self) -> LLMProvider:
        """Get or create LLM provider."""
        if self._llm_provider is None:
            from src.llm.factory import get_cheap_provider
            self._llm_provider = get_cheap_provider()
        return self._llm_provider

    @property
    def milestone_manager(self) -> MilestoneManager:
        """Get or create milestone manager."""
        if self._milestone_manager is None:
            self._milestone_manager = MilestoneManager(self.db, self.game_session)
        return self._milestone_manager

    def _get_current_day(self) -> int:
        """Get current in-game day."""
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )
        return time_state.current_day if time_state else 1

    def _get_summary(self, summary_type: SummaryType) -> ContextSummary | None:
        """Get existing summary of given type."""
        return (
            self.db.query(ContextSummary)
            .filter(
                ContextSummary.session_id == self.session_id,
                ContextSummary.summary_type == summary_type,
            )
            .first()
        )

    def get_story_summary(self) -> str:
        """Get story summary, regenerating if needed.

        Returns:
            Story summary text (may be empty if no milestones yet)
        """
        summary = self._get_summary(SummaryType.STORY)
        last_milestone = self.milestone_manager.get_last_milestone()

        # Check if we need to regenerate
        needs_regen = False
        if summary is None:
            needs_regen = last_milestone is not None
        elif last_milestone and summary.milestone_id != last_milestone.id:
            needs_regen = True

        if needs_regen:
            # Regenerate synchronously would block, return existing or empty
            # Actual regeneration happens via regenerate_story_on_milestone
            return summary.summary_text if summary else ""

        return summary.summary_text if summary else ""

    def get_recent_summary(self) -> str:
        """Get recent summary (last milestone → last night).

        Returns:
            Recent summary text (may be empty if too early)
        """
        summary = self._get_summary(SummaryType.RECENT)
        current_day = self._get_current_day()

        # Check if we need to regenerate (new day)
        if summary is None:
            return ""
        elif summary.covers_through_day < current_day - 1:
            # Summary is stale, but regeneration is async
            # Return existing for now
            pass

        return summary.summary_text if summary else ""

    def get_turns_since_night(self, current_day: int | None = None) -> str:
        """Get full raw text of turns since last night.

        Args:
            current_day: Current game day (defaults to querying TimeState)

        Returns:
            Formatted string of turns since last night
        """
        if current_day is None:
            current_day = self._get_current_day()

        # Get turns that happened on the current day
        # This assumes turns have game_day_at_turn populated
        turns = (
            self.db.query(Turn)
            .filter(
                Turn.session_id == self.session_id,
                Turn.game_day_at_turn == current_day,
            )
            .order_by(Turn.turn_number.asc())
            .all()
        )

        if not turns:
            # Fallback: get last N turns if no day-specific turns
            turns = (
                self.db.query(Turn)
                .filter(Turn.session_id == self.session_id)
                .order_by(Turn.turn_number.desc())
                .limit(10)
                .all()
            )
            turns = list(reversed(turns))

        return self._format_turns_raw(turns)

    def _format_turns_raw(self, turns: list[Turn]) -> str:
        """Format turns as raw text.

        Args:
            turns: List of Turn objects

        Returns:
            Formatted string with full turn text
        """
        if not turns:
            return ""

        lines = []
        for turn in turns:
            lines.append(f"**Turn {turn.turn_number}**")
            lines.append(f"Player: {turn.player_input}")
            lines.append(f"GM: {turn.gm_response}")
            lines.append("")

        return "\n".join(lines)

    def _format_turns_brief(self, turns: list[Turn]) -> str:
        """Format turns as brief summaries for LLM input.

        Args:
            turns: List of Turn objects

        Returns:
            Formatted string with abbreviated turn info
        """
        if not turns:
            return "No turns recorded."

        lines = []
        for turn in turns:
            # Truncate for summary input
            player = turn.player_input[:100]
            if len(turn.player_input) > 100:
                player += "..."

            gm = turn.gm_response[:200]
            if len(turn.gm_response) > 200:
                gm += "..."

            lines.append(f"Turn {turn.turn_number}: Player: {player}")
            lines.append(f"  GM: {gm}")

        return "\n".join(lines)

    async def regenerate_story_on_milestone(self, milestone: Milestone) -> ContextSummary:
        """Regenerate story summary when a milestone is reached.

        Args:
            milestone: The milestone that triggered regeneration

        Returns:
            Updated ContextSummary
        """
        # Get all milestones
        milestones = self.milestone_manager.get_all_milestones()
        milestones_text = "\n".join(
            f"- {m.milestone_type.value}: {m.description} (Turn {m.turn_number}, Day {m.game_day})"
            for m in milestones
        )

        # Get turns since last milestone (or all if first)
        all_turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.session_id)
            .order_by(Turn.turn_number.asc())
            .all()
        )
        turn_summaries = self._format_turns_brief(all_turns)

        # Build prompt
        prompt = STORY_SUMMARY_PROMPT.format(
            milestones=milestones_text or "No milestones yet.",
            from_turn=1,
            to_turn=milestone.turn_number,
            turn_summaries=turn_summaries,
        )

        # Generate summary
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await self.llm_provider.complete(
            messages=messages,
            system_prompt=STORY_SUMMARY_SYSTEM,
            temperature=0.5,
            max_tokens=800,
        )

        summary_text = response.content if hasattr(response, "content") else str(response)

        # Save or update summary
        summary = self._get_summary(SummaryType.STORY)
        current_day = self._get_current_day()

        if summary:
            summary.summary_text = summary_text
            summary.generated_at_turn = self.current_turn
            summary.generated_at_day = current_day
            summary.covers_through_turn = milestone.turn_number
            summary.covers_through_day = milestone.game_day
            summary.milestone_id = milestone.id
            summary.token_count = len(summary_text) // 4  # Rough estimate
        else:
            summary = ContextSummary(
                session_id=self.session_id,
                summary_type=SummaryType.STORY,
                summary_text=summary_text,
                generated_at_turn=self.current_turn,
                generated_at_day=current_day,
                covers_through_turn=milestone.turn_number,
                covers_through_day=milestone.game_day,
                milestone_id=milestone.id,
                token_count=len(summary_text) // 4,
            )
            self.db.add(summary)

        self.db.flush()
        return summary

    async def regenerate_recent_on_new_day(self, current_day: int) -> ContextSummary | None:
        """Regenerate recent summary at the start of a new day.

        Args:
            current_day: The new day number

        Returns:
            Updated ContextSummary or None if not enough content
        """
        last_milestone = self.milestone_manager.get_last_milestone()
        if not last_milestone:
            return None

        # Get turns from milestone to yesterday (exclusive of today)
        yesterday = current_day - 1
        turns = (
            self.db.query(Turn)
            .filter(
                Turn.session_id == self.session_id,
                Turn.turn_number > last_milestone.turn_number,
                Turn.game_day_at_turn < current_day,
            )
            .order_by(Turn.turn_number.asc())
            .all()
        )

        if not turns:
            return None

        turn_summaries = self._format_turns_brief(turns)

        # Build prompt
        prompt = RECENT_SUMMARY_PROMPT.format(
            milestone_description=last_milestone.description,
            milestone_turn=last_milestone.turn_number,
            milestone_day=last_milestone.game_day,
            from_turn=last_milestone.turn_number + 1,
            to_turn=turns[-1].turn_number if turns else last_milestone.turn_number,
            turn_summaries=turn_summaries,
        )

        # Generate summary
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await self.llm_provider.complete(
            messages=messages,
            system_prompt=RECENT_SUMMARY_SYSTEM,
            temperature=0.5,
            max_tokens=600,
        )

        summary_text = response.content if hasattr(response, "content") else str(response)

        # Save or update summary
        summary = self._get_summary(SummaryType.RECENT)

        if summary:
            summary.summary_text = summary_text
            summary.generated_at_turn = self.current_turn
            summary.generated_at_day = current_day
            summary.covers_through_turn = turns[-1].turn_number if turns else last_milestone.turn_number
            summary.covers_through_day = yesterday
            summary.milestone_id = last_milestone.id
            summary.token_count = len(summary_text) // 4
        else:
            summary = ContextSummary(
                session_id=self.session_id,
                summary_type=SummaryType.RECENT,
                summary_text=summary_text,
                generated_at_turn=self.current_turn,
                generated_at_day=current_day,
                covers_through_turn=turns[-1].turn_number if turns else last_milestone.turn_number,
                covers_through_day=yesterday,
                milestone_id=last_milestone.id,
                token_count=len(summary_text) // 4,
            )
            self.db.add(summary)

        self.db.flush()
        return summary

    def is_new_day(self) -> bool:
        """Check if the current day is different from the last recent summary.

        Returns:
            True if recent summary needs regeneration due to day change
        """
        summary = self._get_summary(SummaryType.RECENT)
        if summary is None:
            return True

        current_day = self._get_current_day()
        return summary.generated_at_day < current_day

    def needs_story_regeneration(self) -> tuple[bool, Milestone | None]:
        """Check if story summary needs regeneration.

        Returns:
            Tuple of (needs_regen, triggering_milestone)
        """
        summary = self._get_summary(SummaryType.STORY)
        last_milestone = self.milestone_manager.get_last_milestone()

        if last_milestone is None:
            return False, None

        if summary is None:
            return True, last_milestone

        if summary.milestone_id != last_milestone.id:
            return True, last_milestone

        return False, None
