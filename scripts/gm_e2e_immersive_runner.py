#!/usr/bin/env python3
"""Immersive GM Pipeline E2E Test Runner.

Uses LLM-powered test player agent (Ollama qwen3:32b) to simulate
real gameplay with natural player decisions based on GM responses.

Usage:
    python scripts/gm_e2e_immersive_runner.py                    # Run all scenarios
    python scripts/gm_e2e_immersive_runner.py --quick            # Run quick test subset
    python scripts/gm_e2e_immersive_runner.py --priority 1       # Run priority 1 only
    python scripts/gm_e2e_immersive_runner.py --category hunger  # Run hunger scenarios
"""

import asyncio
import argparse
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, ".")

from src.database.connection import get_db_session
from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.world import TimeState, Fact, Location
from src.database.models.character_state import CharacterNeeds
from src.database.models.items import Item
from src.database.models.relationships import Relationship
from src.gm.graph import build_gm_graph
from src.gm.e2e_logger import GME2ELogger, TurnLog, compute_db_changes
from src.gm.e2e_assessor import GME2EAssessor, TurnAssessment
from scripts.gm_e2e_player_agent import TestPlayerAgent, PlayerDecision
from scripts.gm_e2e_scenarios import (
    ALL_IMMERSIVE_SCENARIOS,
    PRIORITY_1_SCENARIOS,
    QUICK_TEST_SCENARIOS,
    ImmersiveScenario,
    SuccessCriterion,
    FocusArea,
    ActionExpectations,
)


class ErrorType(str, Enum):
    """Types of fundamental errors that trigger test halt."""

    CHARACTER_BREAK = "CHARACTER_BREAK"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    GM_EXCEPTION = "GM_EXCEPTION"
    DB_ERROR = "DB_ERROR"
    PLAYER_AGENT_ERROR = "PLAYER_AGENT_ERROR"
    CONSECUTIVE_FAILURES = "CONSECUTIVE_FAILURES"


@dataclass
class TurnResult:
    """Result of a single turn."""

    turn_number: int
    player_input: str
    gm_response: str
    time_passed: int | None
    tool_calls: list[dict[str, Any]]
    db_changes: list[str]
    passed: bool
    issues: list[str]
    duration_seconds: float


@dataclass
class ScenarioResult:
    """Result of running a complete immersive scenario."""

    scenario_name: str
    session_id: int
    turns: list[TurnResult]
    success_criteria_met: list[str]
    success_criteria_failed: list[str]
    fundamental_error: ErrorType | None = None
    error_details: str | None = None
    log_path: Path | None = None

    @property
    def passed(self) -> bool:
        """Scenario passed if no fundamental errors and all criteria met."""
        return (
            self.fundamental_error is None
            and len(self.success_criteria_failed) == 0
        )

    @property
    def turn_pass_rate(self) -> float:
        """Percentage of turns that passed."""
        if not self.turns:
            return 0.0
        return sum(1 for t in self.turns if t.passed) / len(self.turns)


@dataclass
class ErrorTracker:
    """Tracks consecutive errors to detect fundamental failures."""

    max_consecutive: int = 3
    error_counts: dict[ErrorType, int] = field(default_factory=dict)
    last_error_type: ErrorType | None = None
    consecutive_same_type: int = 0

    def record_error(self, error_type: ErrorType) -> bool:
        """Record an error and return True if fundamental failure detected."""
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        if error_type == self.last_error_type:
            self.consecutive_same_type += 1
        else:
            self.consecutive_same_type = 1
            self.last_error_type = error_type

        return self.consecutive_same_type >= self.max_consecutive

    def reset(self) -> None:
        """Reset error tracking."""
        self.error_counts = {}
        self.last_error_type = None
        self.consecutive_same_type = 0


class ImmersiveTestRunner:
    """LLM-driven E2E test runner with natural gameplay."""

    def __init__(
        self,
        log_dir: Path | None = None,
        player_model: str = "qwen3:32b",
        ollama_url: str = "http://localhost:11434",
        verbose: bool = False,
        per_scenario_logs: bool = False,
    ):
        """Initialize the immersive test runner.

        Args:
            log_dir: Custom log directory. Defaults to logs/gm_e2e.
            player_model: Ollama model for test player.
            ollama_url: Ollama server URL.
            verbose: Show detailed pipeline progress.
            per_scenario_logs: Create separate log file per scenario.
        """
        self.log_dir = log_dir or Path("logs/gm_e2e")
        self.error_dump_path = self.log_dir / "gm_e2e_error.md"
        self.logger = GME2ELogger(self.log_dir, per_scenario_logs=per_scenario_logs)
        self.player_agent = TestPlayerAgent(
            model=player_model,
            ollama_url=ollama_url,
        )
        self.error_tracker = ErrorTracker()
        self.verbose = verbose

        # Assessment infrastructure
        self.assessor = GME2EAssessor()
        self.previous_responses: list[str] = []

        # Create observability hook if verbose mode
        if verbose:
            from src.observability.console_observer import RichConsoleObserver
            self.observer = RichConsoleObserver(show_tool_details=True, show_tokens=True)
        else:
            self.observer = None

    async def run_scenario(
        self, scenario: ImmersiveScenario
    ) -> ScenarioResult:
        """Run an immersive scenario with LLM-driven player.

        Args:
            scenario: The immersive scenario to run.

        Returns:
            Result of the scenario run.
        """
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario.name}")
        print(f"Goal: {scenario.goal}")
        print(f"{'='*60}")

        # Reset state
        self.player_agent.reset()
        self.error_tracker.reset()
        self.previous_responses = []

        # Create fresh session
        try:
            session_id, player_id, location = await self._create_fresh_session()
        except Exception as e:
            return ScenarioResult(
                scenario_name=scenario.name,
                session_id=-1,
                turns=[],
                success_criteria_met=[],
                success_criteria_failed=["Session creation failed"],
                fundamental_error=ErrorType.DB_ERROR,
                error_details=str(e),
            )

        print(f"Created session {session_id} at {location}")

        # Start logging
        log_path = self.logger.start_scenario(
            scenario_name=scenario.name,
            scenario_description=f"Goal: {scenario.goal}",
            session_id=session_id,
            player_id=player_id,
            starting_location=location,
        )

        turns: list[TurnResult] = []
        db_snapshots: list[dict] = []
        fundamental_error: ErrorType | None = None
        error_details: str | None = None

        with get_db_session() as db:
            graph = build_gm_graph()
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
            player = db.query(Entity).filter(Entity.id == player_id).first()

            # Initial action based on scenario type
            # OOC scenarios should start with the OOC query directly (no time should pass)
            if FocusArea.OOC in scenario.focus_areas:
                goal_lower = scenario.goal.lower()
                if "time" in goal_lower:
                    current_action = "[OOC] What time is it?"
                elif "inventory" in goal_lower or "carrying" in goal_lower:
                    current_action = "[OOC] What am I carrying?"
                elif "needs" in goal_lower or "status" in goal_lower:
                    current_action = "[OOC] What are my character's needs?"
                elif "location" in goal_lower or "where" in goal_lower:
                    current_action = "[OOC] Where am I?"
                else:
                    current_action = "[OOC] Help me"
            else:
                # Normal scenarios start with "look around" to establish scene
                current_action = "I look around"
            current_location = location

            for turn_num in range(1, scenario.max_turns + 1):
                if self.verbose:
                    # Verbose mode: newline before turn, observer will print details
                    print(f"\n  Turn {turn_num}: \"{current_action[:50]}...\"")
                else:
                    print(f"  Turn {turn_num}: \"{current_action[:50]}...\" ", end="", flush=True)

                # Capture DB state before
                db_before = self._snapshot_db(db, session_id, player_id)

                # Run the turn
                start_time = time.time()
                try:
                    result = await self._run_turn(
                        db=db,
                        graph=graph,
                        game_session=game_session,
                        player=player,
                        player_input=current_action,
                        turn_number=turn_num,
                        location=current_location,
                    )
                except Exception as e:
                    error_details = f"GM Exception: {e}\n{traceback.format_exc()}"
                    if self.error_tracker.record_error(ErrorType.GM_EXCEPTION):
                        fundamental_error = ErrorType.GM_EXCEPTION
                        print("FATAL - GM Exception")
                        break
                    print(f"ERROR: {e}")
                    continue

                duration = time.time() - start_time

                # Capture DB state after
                db.flush()
                db_after = self._snapshot_db(db, session_id, player_id)
                db_snapshots.append(db_after)

                # Extract response details
                gm_response = result.get("gm_response", "")
                gm_response_obj = result.get("_gm_response_obj")
                time_passed = gm_response_obj.time_passed_minutes if gm_response_obj else None
                tool_calls = self._extract_tool_calls(gm_response_obj)
                db_changes = compute_db_changes(db_before, db_after)

                # Check for empty response
                if not gm_response or len(gm_response) < 20:
                    if self.error_tracker.record_error(ErrorType.EMPTY_RESPONSE):
                        fundamental_error = ErrorType.EMPTY_RESPONSE
                        error_details = "GM returned empty or too-short response 3 times"
                        print("FATAL - Empty response")
                        break

                # Check for character breaks
                if self._has_character_break(gm_response):
                    if self.error_tracker.record_error(ErrorType.CHARACTER_BREAK):
                        fundamental_error = ErrorType.CHARACTER_BREAK
                        error_details = f"Character break detected 3 times. Last: {gm_response[:200]}"
                        print("FATAL - Character break")
                        break

                # Assess turn quality using full assessor
                # OOC scenarios have shorter responses (e.g., "It is 9:00 AM.")
                is_ooc_scenario = FocusArea.OOC in scenario.focus_areas
                expectations = ActionExpectations(
                    min_chars=20 if is_ooc_scenario else 50,
                    max_chars=2000,
                    min_time=0,
                    max_time=60,
                )
                # Expected entities from the test session setup
                # Skip entity grounding for OOC scenarios (meta-game queries don't describe scene)
                expected_entities = None if is_ooc_scenario else ["marcus", "farmer", "farmhouse", "bread", "water"]

                assessment = self.assessor.assess_turn(
                    narrative=gm_response,
                    time_passed=time_passed,
                    tool_calls=tool_calls,
                    errors=result.get("errors", []),
                    db_changes=db_changes,
                    expectations=expectations,
                    previous_responses=self.previous_responses,
                    expected_entities=expected_entities,
                )
                self.previous_responses.append(gm_response)

                passed = assessment.overall_passed
                issues = assessment.all_issues

                # Create turn result
                turn_result = TurnResult(
                    turn_number=turn_num,
                    player_input=current_action,
                    gm_response=gm_response,
                    time_passed=time_passed,
                    tool_calls=tool_calls,
                    db_changes=db_changes,
                    passed=passed,
                    issues=issues,
                    duration_seconds=duration,
                )
                turns.append(turn_result)

                # Log the turn
                self._log_turn(turn_result, db_before, db_after, result.get("_context_sent", ""))

                # Print result
                status = "PASS" if passed else "FAIL"
                if self.verbose:
                    # Verbose mode: print on new line after observer output
                    print(f"  -> {status} ({len(gm_response)} chars, {time_passed} min, {duration:.1f}s)")
                else:
                    print(f"{status} ({len(gm_response)} chars, {time_passed} min)")

                if issues:
                    for issue in issues[:2]:  # Show first 2 issues
                        print(f"    ! {issue}")

                # Update location if changed
                if result.get("location_changed"):
                    current_location = result.get("new_location", current_location)

                # Check if scenario goal achieved
                if turn_num >= scenario.min_turns:
                    criteria_results = self._check_success_criteria(
                        scenario, turns, db_snapshots
                    )
                    if all(criteria_results.values()):
                        print(f"  -> Goal achieved at turn {turn_num}!")
                        break

                # Get next action from player agent
                try:
                    player_state = self._build_player_state(db, player_id, current_location)
                    decision = await self.player_agent.decide_action(
                        goal=scenario.goal,
                        gm_response=gm_response,
                        player_state=player_state,
                    )
                    current_action = decision.action

                    if decision.is_done:
                        print(f"  -> Player agent believes goal is complete")
                        break

                except Exception as e:
                    error_details = f"Player agent error: {e}"
                    if self.error_tracker.record_error(ErrorType.PLAYER_AGENT_ERROR):
                        fundamental_error = ErrorType.PLAYER_AGENT_ERROR
                        print("FATAL - Player agent error")
                        break
                    # Fallback action
                    current_action = "I look around"

            db.commit()

        # Finish logging
        self.logger.finish_scenario()

        # Evaluate success criteria
        criteria_results = self._check_success_criteria(scenario, turns, db_snapshots)
        success_met = [c for c, v in criteria_results.items() if v]
        success_failed = [c for c, v in criteria_results.items() if not v]

        result = ScenarioResult(
            scenario_name=scenario.name,
            session_id=session_id,
            turns=turns,
            success_criteria_met=success_met,
            success_criteria_failed=success_failed,
            fundamental_error=fundamental_error,
            error_details=error_details,
            log_path=log_path,
        )

        # Generate error dump if fundamental error
        if fundamental_error:
            self._generate_error_dump(result, scenario, turns, db_snapshots)

        return result

    def _has_character_break(self, text: str) -> bool:
        """Check if the text contains character break patterns."""
        import re

        patterns = [
            r"\bmy name is\b",
            r"\bi'?m an? (?:ai|llm|assistant)\b",
            r"\bfeel free to ask\b",
            r"\bhow can i help\b",
            r"\bthe player\b",
        ]
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _check_success_criteria(
        self,
        scenario: ImmersiveScenario,
        turns: list[TurnResult],
        db_snapshots: list[dict],
    ) -> dict[str, bool]:
        """Evaluate success criteria against scenario results."""
        results = {}

        for criterion in scenario.success_criteria:
            key = criterion.description
            results[key] = self._evaluate_criterion(criterion, turns, db_snapshots)

        return results

    def _evaluate_criterion(
        self,
        criterion: SuccessCriterion,
        turns: list[TurnResult],
        db_snapshots: list[dict],
    ) -> bool:
        """Evaluate a single success criterion."""
        if criterion.check_type == "narrative_quality":
            # Check that at least one turn has good narrative
            return any(len(t.gm_response) >= criterion.params.get("min_chars", 50) for t in turns)

        elif criterion.check_type == "narrative_contains":
            # Check that narrative contains expected patterns
            patterns = criterion.params.get("patterns", [])
            for turn in turns:
                text_lower = turn.gm_response.lower()
                for pattern in patterns:
                    if pattern.lower() in text_lower:
                        return True
            return False

        elif criterion.check_type == "tool_called":
            # Check that expected tool was called
            expected_tool = criterion.params.get("tool")
            for turn in turns:
                for tc in turn.tool_calls:
                    if tc.get("tool") == expected_tool:
                        return True
            return False

        elif criterion.check_type == "time_passed":
            # Check time passed is within range
            min_time = criterion.params.get("min", 0)
            max_time = criterion.params.get("max", 999)
            total_time = sum(t.time_passed or 0 for t in turns)
            return min_time <= total_time <= max_time

        elif criterion.check_type == "need_change":
            # Check that a need changed appropriately
            if len(db_snapshots) < 2:
                return False
            need = criterion.params.get("need")
            direction = criterion.params.get("direction")
            min_delta = criterion.params.get("min_delta", 0)

            first = db_snapshots[0].get("needs", {})
            last = db_snapshots[-1].get("needs", {})

            if need not in first or need not in last:
                return False

            delta = last[need] - first[need]
            if direction == "decrease":
                return delta <= -min_delta
            elif direction == "increase":
                return delta >= min_delta
            return False

        elif criterion.check_type == "db_change":
            # Check for specific DB change
            field = criterion.params.get("field", "")
            expected = criterion.params.get("expected", "")

            for turn in turns:
                for change in turn.db_changes:
                    change_lower = change.lower()
                    # Special handling for item holder changes
                    # Format: "Item X moved: holder None -> 285"
                    if field == "holder_id":
                        if expected == "player" and "moved: holder" in change_lower:
                            # Check if holder changed to a numeric ID (player)
                            if "-> none" not in change_lower and "-> null" not in change_lower:
                                return True
                        elif expected == "null" and "-> none" in change_lower:
                            return True
                    else:
                        # Generic field=expected check
                        expected_change = f"{field}={expected}"
                        if expected_change.lower() in change_lower:
                            return True
            return False

        return True  # Unknown criterion type - pass by default

    def _generate_error_dump(
        self,
        result: ScenarioResult,
        scenario: ImmersiveScenario,
        turns: list[TurnResult],
        db_snapshots: list[dict],
    ) -> None:
        """Generate diagnostic dump file for fundamental errors."""
        self.error_dump_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# E2E Test Error Report",
            "",
            "## Error Summary",
            f"- **Type**: {result.fundamental_error.value if result.fundamental_error else 'Unknown'}",
            f"- **Scenario**: {scenario.name}",
            f"- **Goal**: {scenario.goal}",
            f"- **Turn**: {len(turns)} of {scenario.max_turns}",
            f"- **Timestamp**: {datetime.now().isoformat()}",
            "",
            "## Error Details",
            "```",
            result.error_details or "No details available",
            "```",
            "",
            "## Last 5 Turns",
        ]

        for turn in turns[-5:]:
            lines.extend([
                f"### Turn {turn.turn_number}",
                f"**Player**: {turn.player_input}",
                f"**GM** ({len(turn.gm_response)} chars, {turn.time_passed} min):",
                f"> {turn.gm_response[:300]}...",
                "",
            ])

        lines.extend([
            "## DB State Snapshot",
            "```json",
        ])
        if db_snapshots:
            import json
            lines.append(json.dumps(db_snapshots[-1], indent=2, default=str))
        lines.append("```")

        lines.extend([
            "",
            "## Tool Calls (Last Turn)",
        ])
        if turns:
            for tc in turns[-1].tool_calls:
                lines.append(f"- {tc.get('tool')}: {tc.get('arguments')}")

        lines.extend([
            "",
            "## Suggested Investigation",
            f"- Check src/gm/gm_node.py for {result.fundamental_error.value if result.fundamental_error else 'errors'}",
            "- Review src/gm/prompts.py system prompt",
            "- Check logs in logs/gm_e2e/ for full details",
            "",
            "## Resume Testing",
            "```bash",
            "# Start Claude Code and tackle this issue:",
            "cc",
            f"> /tackle {self.error_dump_path}",
            "```",
        ])

        self.error_dump_path.write_text("\n".join(lines))
        print(f"\nError dump written to: {self.error_dump_path}")

    def _build_player_state(
        self, db, player_id: int, location: str
    ) -> dict[str, Any]:
        """Build player state for the player agent."""
        needs_record = db.query(CharacterNeeds).filter(
            CharacterNeeds.entity_id == player_id
        ).first()

        needs = {}
        if needs_record:
            needs = {
                "hunger": needs_record.hunger,
                "thirst": needs_record.thirst,
                "stamina": needs_record.stamina,
            }

        # Get inventory
        items = db.query(Item).filter(Item.holder_id == player_id).all()
        inventory = [i.display_name for i in items]

        return {
            "location": location,
            "needs": needs,
            "inventory": inventory,
        }

    def _log_turn(
        self,
        turn: TurnResult,
        db_before: dict,
        db_after: dict,
        context_sent: str,
    ) -> None:
        """Log a turn to the logger."""
        turn_log = TurnLog(
            turn_number=turn.turn_number,
            timestamp=datetime.now(),
            player_input=turn.player_input,
            description=f"LLM-generated action",
            context_sent=context_sent,
            raw_response=turn.gm_response,
            narrative=turn.gm_response,
            tool_calls=turn.tool_calls,
            db_before=db_before,
            db_after=db_after,
            db_changes=turn.db_changes,
            passed=turn.passed,
            assessment_details={"issues": turn.issues},
            issues=turn.issues,
            time_passed_minutes=turn.time_passed,
            duration_seconds=turn.duration_seconds,
        )
        self.logger.log_turn(turn_log)

    async def _create_fresh_session(self) -> tuple[int, int, str]:
        """Create a fresh test session."""
        from src.cli.commands.character import (
            _create_character_records,
            _create_starting_equipment,
            _create_character_preferences,
        )
        from src.cli.commands.game import _create_auto_character_state
        from src.schemas.settings import get_setting_schema
        from src.database.models.entities import NPCExtension
        from src.database.models.items import Item, StorageLocation
        from src.database.models.enums import ItemType, StorageLocationType

        with get_db_session() as db:
            # Create game session
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            game_session = GameSession(
                session_name=f"E2E Immersive {timestamp}",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="anthropic",
                gm_model="claude-sonnet-4-20250514",
            )
            db.add(game_session)
            db.flush()

            # Create time state
            time_state = TimeState(
                session_id=game_session.id,
                current_day=1,
                current_time="09:00",
                day_of_week="Monday",
                season="Spring",
                weather="Clear",
            )
            db.add(time_state)

            # Create test character
            creation_state = _create_auto_character_state()
            schema = get_setting_schema("fantasy")

            entity = _create_character_records(
                db=db,
                game_session=game_session,
                name=creation_state.name,
                attributes=creation_state.attributes,
                background=creation_state.background or "",
                creation_state=creation_state,
                potential_stats=None,
                occupation=None,
                occupation_years=None,
            )

            _create_starting_equipment(db, game_session, entity, schema)
            _create_character_preferences(db, game_session, entity)

            # Create test location
            location_key = "test_farmhouse"

            # Create the Location record (required for GM context)
            location = Location(
                session_id=game_session.id,
                location_key=location_key,
                display_name="Farmhouse",
                description=(
                    "A modest farmhouse with rough-hewn wooden walls and a thatched roof. "
                    "The interior is simple but well-kept, with a stone fireplace dominating "
                    "one wall. A rough-hewn table sits at the center of the room, and sunlight "
                    "filters through a small, dusty window above the sink. The scent of hay "
                    "and woodsmoke hangs in the air."
                ),
                category="building",
                atmosphere="Warm and rustic, with the crackle of a small fire",
            )
            db.add(location)

            storage = StorageLocation(
                session_id=game_session.id,
                location_key=location_key,
                location_type=StorageLocationType.PLACE,
            )
            db.add(storage)
            db.flush()

            # Create NPC
            npc = Entity(
                session_id=game_session.id,
                entity_key="farmer_marcus",
                entity_type=EntityType.NPC,
                display_name="Marcus",
            )
            db.add(npc)
            db.flush()

            npc_ext = NPCExtension(
                entity_id=npc.id,
                current_location=location_key,
                current_activity="standing by the fireplace",
            )
            db.add(npc_ext)

            # Create items
            items_data = [
                ("bread_001", "Bread", "A fresh loaf of bread.", ItemType.CONSUMABLE),
                ("water_jug_001", "Water Jug", "A jug of clean water.", ItemType.CONSUMABLE),
            ]

            for key, name, desc, item_type in items_data:
                item = Item(
                    session_id=game_session.id,
                    item_key=key,
                    display_name=name,
                    description=desc,
                    item_type=item_type,
                    storage_location_id=storage.id,
                )
                db.add(item)

            # Set player location
            if entity.npc_extension:
                entity.npc_extension.current_location = location_key
            else:
                player_ext = NPCExtension(
                    entity_id=entity.id,
                    current_location=location_key,
                )
                db.add(player_ext)

            db.commit()
            return game_session.id, entity.id, location_key

    async def _run_turn(
        self,
        db,
        graph,
        game_session: GameSession,
        player: Entity,
        player_input: str,
        turn_number: int,
        location: str,
    ) -> dict[str, Any]:
        """Run a single turn through the GM pipeline."""
        # Reset observer state for new turn if verbose
        if self.observer:
            self.observer.reset()

        state = {
            "session_id": game_session.id,
            "player_id": player.id,
            "player_location": location,
            "player_input": player_input,
            "turn_number": turn_number,
            "_db": db,
            "_game_session": game_session,
            "_observability_hook": self.observer,  # Pass observer through state
            "roll_mode": "auto",
            "_gm_response_obj": None,
            "gm_response": "",
            "new_location": None,
            "location_changed": False,
            "errors": [],
            "skill_checks": [],
        }

        result = await graph.ainvoke(state)
        return result

    def _snapshot_db(self, db, session_id: int, player_id: int) -> dict[str, Any]:
        """Capture relevant DB state for comparison."""
        items = db.query(Item).filter(Item.session_id == session_id).all()
        items_data = [
            {
                "entity_key": i.item_key,
                "display_name": i.display_name,
                "holder_id": i.holder_id,
                "storage_location_id": i.storage_location_id,
            }
            for i in items
        ]

        npcs = (
            db.query(Entity)
            .filter(Entity.session_id == session_id, Entity.entity_type == EntityType.NPC)
            .all()
        )
        npcs_data = [
            {
                "entity_key": n.entity_key,
                "display_name": n.display_name,
                "current_location": n.npc_extension.current_location if n.npc_extension else None,
            }
            for n in npcs
        ]

        rels = db.query(Relationship).filter(Relationship.session_id == session_id).all()
        rels_data = [
            {
                "from_key": r.from_entity.entity_key if r.from_entity else None,
                "to_key": r.to_entity.entity_key if r.to_entity else None,
                "trust": r.trust,
                "liking": r.liking,
                "respect": r.respect,
            }
            for r in rels
        ]

        facts = db.query(Fact).filter(Fact.session_id == session_id).all()
        facts_data = [
            {"subject_key": f.subject_key, "predicate": f.predicate, "value": f.value}
            for f in facts
        ]

        needs_record = db.query(CharacterNeeds).filter(CharacterNeeds.entity_id == player_id).first()
        needs_data = {}
        if needs_record:
            needs_data = {
                "hunger": needs_record.hunger,
                "thirst": needs_record.thirst,
                "stamina": needs_record.stamina,
                "sleep_pressure": needs_record.sleep_pressure,
                "hygiene": needs_record.hygiene,
                "comfort": needs_record.comfort,
            }

        time_state = db.query(TimeState).filter(TimeState.session_id == session_id).first()
        time_data = {}
        if time_state:
            time_data = {
                "current_day": time_state.current_day,
                "current_time": time_state.current_time,
            }

        return {
            "items": items_data,
            "npcs": npcs_data,
            "relationships": rels_data,
            "facts": facts_data,
            "needs": needs_data,
            "time": time_data,
        }

    def _extract_tool_calls(self, gm_response_obj) -> list[dict[str, Any]]:
        """Extract tool calls from GM response object."""
        if gm_response_obj is None:
            return []

        tool_results = getattr(gm_response_obj, "tool_results", [])
        return [
            {
                "tool": tr.get("tool", "unknown"),
                "arguments": tr.get("arguments", {}),
                "result": tr.get("result", {}),
            }
            for tr in tool_results
        ]

    async def run_all(
        self,
        scenarios: list[ImmersiveScenario] | None = None,
        stop_on_fundamental_error: bool = True,
    ) -> list[ScenarioResult]:
        """Run all scenarios.

        Args:
            scenarios: Scenarios to run. Defaults to ALL_IMMERSIVE_SCENARIOS.
            stop_on_fundamental_error: Stop testing on fundamental error.

        Returns:
            List of scenario results.
        """
        scenarios = scenarios or ALL_IMMERSIVE_SCENARIOS

        results = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)

            if result.fundamental_error and stop_on_fundamental_error:
                print(f"\n*** STOPPING: Fundamental error detected ***")
                print(f"Error: {result.fundamental_error.value}")
                print(f"See: {self.error_dump_path}")
                break

        # Print summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: list[ScenarioResult]) -> None:
        """Print final summary of test run."""
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)

        total_passed = sum(1 for r in results if r.passed)
        total_scenarios = len(results)
        total_turns = sum(len(r.turns) for r in results)
        passed_turns = sum(sum(1 for t in r.turns if t.passed) for r in results)

        print(f"Scenarios: {total_passed}/{total_scenarios} passed")
        print(f"Turns: {passed_turns}/{total_turns} passed ({passed_turns/total_turns*100:.1f}%)" if total_turns else "")
        print()

        for r in results:
            icon = "[+]" if r.passed else "[-]"
            status = "PASS" if r.passed else "FAIL"
            if r.fundamental_error:
                status = f"FATAL ({r.fundamental_error.value})"
            print(f"{icon} {r.scenario_name}: {status}")
            if r.success_criteria_failed:
                for c in r.success_criteria_failed[:2]:
                    print(f"    ! {c}")

        print(f"\nLogs in: {self.log_dir}")
        if any(r.fundamental_error for r in results):
            print(f"Error dump: {self.error_dump_path}")


async def main():
    parser = argparse.ArgumentParser(description="Immersive GM Pipeline E2E Test Runner")
    parser.add_argument("--quick", "-q", action="store_true", help="Run quick test subset")
    parser.add_argument("--priority", "-p", type=int, help="Run only scenarios with this priority")
    parser.add_argument("--category", "-c", help="Run only scenarios in this category")
    parser.add_argument("--model", default="qwen3:32b", help="Ollama model for player agent")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    parser.add_argument("--log-dir", type=Path, help="Custom log directory")
    parser.add_argument("--no-stop", action="store_true", help="Don't stop on fundamental errors")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed pipeline progress (phases, LLM calls, tools)")
    parser.add_argument("--per-scenario-logs", action="store_true",
                        help="Create separate log file per scenario instead of single live.log")
    args = parser.parse_args()

    runner = ImmersiveTestRunner(
        log_dir=args.log_dir,
        player_model=args.model,
        ollama_url=args.ollama_url,
        verbose=args.verbose,
        per_scenario_logs=args.per_scenario_logs,
    )

    # Determine which scenarios to run
    if args.quick:
        scenarios = QUICK_TEST_SCENARIOS
    elif args.priority:
        scenarios = [s for s in ALL_IMMERSIVE_SCENARIOS if s.priority == args.priority]
    elif args.category:
        category = args.category.upper()
        try:
            focus = FocusArea(args.category.lower())
            scenarios = [s for s in ALL_IMMERSIVE_SCENARIOS if focus in s.focus_areas]
        except ValueError:
            print(f"Unknown category: {args.category}")
            print("Available: " + ", ".join(f.value for f in FocusArea))
            sys.exit(1)
    else:
        scenarios = ALL_IMMERSIVE_SCENARIOS

    print(f"Running {len(scenarios)} immersive scenario(s)...")
    print(f"Player agent model: {args.model}")
    if args.verbose:
        print(f"Verbose mode: ON (showing pipeline details)")
    log_file = runner.log_dir / ("live.log" if not args.per_scenario_logs else "[per-scenario]")
    print(f"Log file: {log_file}")
    print()

    results = await runner.run_all(
        scenarios=scenarios,
        stop_on_fundamental_error=not args.no_stop,
    )

    # Exit with appropriate code
    all_passed = all(r.passed for r in results)
    has_fatal = any(r.fundamental_error for r in results)
    sys.exit(2 if has_fatal else (0 if all_passed else 1))


if __name__ == "__main__":
    asyncio.run(main())
