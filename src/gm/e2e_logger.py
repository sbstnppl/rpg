"""E2E Test Logger for GM Pipeline.

Creates a single combined markdown log file per test run containing:
- Session metadata
- Each turn's context, response, tools, and assessment
- Summary of all results
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TurnLog:
    """Log data for a single turn."""

    turn_number: int
    timestamp: datetime
    player_input: str
    description: str

    # LLM interaction
    context_sent: str
    raw_response: str
    narrative: str

    # Tool calls
    tool_calls: list[dict[str, Any]]

    # DB changes
    db_before: dict[str, Any]
    db_after: dict[str, Any]
    db_changes: list[str]

    # Assessment
    passed: bool
    assessment_details: dict[str, Any]
    issues: list[str]

    # Timing
    time_passed_minutes: int | None
    duration_seconds: float


@dataclass
class ScenarioLog:
    """Log data for a complete scenario."""

    scenario_name: str
    scenario_description: str
    session_id: int
    player_id: int
    starting_location: str
    start_time: datetime
    turns: list[TurnLog] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for t in self.turns if t.passed)

    @property
    def total_count(self) -> int:
        return len(self.turns)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total_count if self.total_count > 0 else 0.0


class GME2ELogger:
    """Single-file markdown logger for E2E tests."""

    def __init__(self, log_dir: Path | str = "logs/gm_e2e"):
        """Initialize the logger.

        Args:
            log_dir: Directory to write log files to.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log: ScenarioLog | None = None
        self._log_path: Path | None = None

    def start_scenario(
        self,
        scenario_name: str,
        scenario_description: str,
        session_id: int,
        player_id: int,
        starting_location: str,
    ) -> Path:
        """Start logging a new scenario.

        Args:
            scenario_name: Name of the test scenario.
            scenario_description: Description of what the scenario tests.
            session_id: Fresh session ID created for this test.
            player_id: Player entity ID.
            starting_location: Player's starting location key.

        Returns:
            Path to the log file.
        """
        timestamp = datetime.now()
        self.current_log = ScenarioLog(
            scenario_name=scenario_name,
            scenario_description=scenario_description,
            session_id=session_id,
            player_id=player_id,
            starting_location=starting_location,
            start_time=timestamp,
        )

        # Create log file path
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        safe_name = scenario_name.lower().replace(" ", "_")
        self._log_path = self.log_dir / f"run_{timestamp_str}_{safe_name}.md"

        # Write header immediately
        self._write_header()

        return self._log_path

    def log_turn(self, turn: TurnLog) -> None:
        """Log a completed turn.

        Args:
            turn: Turn log data.
        """
        if self.current_log is None:
            raise RuntimeError("No scenario started. Call start_scenario first.")

        self.current_log.turns.append(turn)
        self._append_turn(turn)

    def finish_scenario(self) -> ScenarioLog:
        """Finish the scenario and write summary.

        Returns:
            The complete scenario log.
        """
        if self.current_log is None:
            raise RuntimeError("No scenario started.")

        self._write_summary()

        result = self.current_log
        self.current_log = None
        return result

    def _write_header(self) -> None:
        """Write the log file header."""
        if self._log_path is None or self.current_log is None:
            return

        log = self.current_log
        lines = [
            f"# GM E2E Test Run - {log.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Session Info",
            f"- **Scenario**: {log.scenario_name}",
            f"- **Description**: {log.scenario_description}",
            f"- **Session ID**: {log.session_id} (created fresh)",
            f"- **Player ID**: {log.player_id}",
            f"- **Starting Location**: {log.starting_location}",
            "",
            "---",
            "",
        ]

        self._log_path.write_text("\n".join(lines), encoding="utf-8")

    def _append_turn(self, turn: TurnLog) -> None:
        """Append a turn to the log file."""
        if self._log_path is None:
            return

        status = "PASS" if turn.passed else "FAIL"
        lines = [
            f"## Turn {turn.turn_number}: \"{turn.player_input}\"",
            "",
            f"*{turn.description}*",
            "",
            f"**Status**: {status}",
            f"**Time Passed**: {turn.time_passed_minutes} minutes",
            f"**Duration**: {turn.duration_seconds:.2f}s",
            "",
        ]

        # LLM Context (truncated for readability)
        lines.append("### LLM Context (truncated)")
        lines.append("```")
        context_preview = turn.context_sent[:2000]
        if len(turn.context_sent) > 2000:
            context_preview += f"\n\n... (truncated, {len(turn.context_sent)} chars total)"
        lines.append(context_preview)
        lines.append("```")
        lines.append("")

        # Response
        lines.append("### GM Response")
        lines.append("```")
        lines.append(turn.narrative or "(empty response)")
        lines.append("```")
        lines.append("")

        # Tool Calls
        if turn.tool_calls:
            lines.append("### Tool Calls")
            for tc in turn.tool_calls:
                tool_name = tc.get("tool", "unknown")
                args = tc.get("arguments", {})
                result = tc.get("result", {})

                lines.append(f"#### `{tool_name}`")
                lines.append("**Arguments:**")
                lines.append("```json")
                lines.append(json.dumps(args, indent=2, default=str))
                lines.append("```")
                lines.append("**Result:**")
                lines.append("```json")
                lines.append(json.dumps(result, indent=2, default=str))
                lines.append("```")
                lines.append("")
        else:
            lines.append("### Tool Calls")
            lines.append("*No tools called*")
            lines.append("")

        # DB Changes
        if turn.db_changes:
            lines.append("### DB Changes")
            for change in turn.db_changes:
                lines.append(f"- {change}")
            lines.append("")
        else:
            lines.append("### DB Changes")
            lines.append("*No changes detected*")
            lines.append("")

        # Assessment
        lines.append("### Assessment")
        details = turn.assessment_details
        for category, info in details.items():
            if isinstance(info, dict):
                passed = info.get("passed", True)
                icon = "+" if passed else "-"
                lines.append(f"- [{icon}] **{category}**: {info.get('message', 'OK')}")
            else:
                lines.append(f"- **{category}**: {info}")

        if turn.issues:
            lines.append("")
            lines.append("**Issues:**")
            for issue in turn.issues:
                lines.append(f"- {issue}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Append to file
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _write_summary(self) -> None:
        """Write the summary section."""
        if self._log_path is None or self.current_log is None:
            return

        log = self.current_log
        lines = [
            "## Summary",
            "",
            f"- **Pass Rate**: {log.passed_count}/{log.total_count} ({log.pass_rate:.1%})",
            "",
        ]

        # List all turns with status
        lines.append("### Turn Results")
        for turn in log.turns:
            icon = "+" if turn.passed else "-"
            lines.append(f"- [{icon}] Turn {turn.turn_number}: {turn.player_input}")

        # Collect all issues
        all_issues = []
        for turn in log.turns:
            for issue in turn.issues:
                all_issues.append(f"Turn {turn.turn_number}: {issue}")

        if all_issues:
            lines.append("")
            lines.append("### Issues Found")
            for issue in all_issues:
                lines.append(f"- {issue}")

        lines.append("")

        # Append to file
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines))


def compute_db_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Compute human-readable DB changes between snapshots.

    Args:
        before: DB state before the turn.
        after: DB state after the turn.

    Returns:
        List of change descriptions.
    """
    changes = []

    # Check items
    before_items = {i["entity_key"]: i for i in before.get("items", [])}
    after_items = {i["entity_key"]: i for i in after.get("items", [])}

    for key in after_items:
        if key not in before_items:
            item = after_items[key]
            changes.append(f"Created item: {item.get('display_name', key)}")
        elif before_items[key] != after_items[key]:
            before_holder = before_items[key].get("holder_id")
            after_holder = after_items[key].get("holder_id")
            if before_holder != after_holder:
                changes.append(f"Item {key} moved: holder {before_holder} -> {after_holder}")

    # Check NPCs
    before_npcs = {n["entity_key"]: n for n in before.get("npcs", [])}
    after_npcs = {n["entity_key"]: n for n in after.get("npcs", [])}

    for key in after_npcs:
        if key not in before_npcs:
            npc = after_npcs[key]
            changes.append(f"Created NPC: {npc.get('display_name', key)}")

    # Check relationships
    before_rels = {(r["from_key"], r["to_key"]): r for r in before.get("relationships", [])}
    after_rels = {(r["from_key"], r["to_key"]): r for r in after.get("relationships", [])}

    for key in after_rels:
        if key not in before_rels:
            changes.append(f"New relationship: {key[0]} -> {key[1]}")
        elif before_rels[key] != after_rels[key]:
            before_r = before_rels[key]
            after_r = after_rels[key]
            for dim in ["trust", "liking", "respect"]:
                if before_r.get(dim) != after_r.get(dim):
                    changes.append(
                        f"Relationship {key[0]}->{key[1]} {dim}: "
                        f"{before_r.get(dim)} -> {after_r.get(dim)}"
                    )

    # Check facts
    before_facts = set(
        (f["subject_key"], f["predicate"], f["value"]) for f in before.get("facts", [])
    )
    after_facts = set(
        (f["subject_key"], f["predicate"], f["value"]) for f in after.get("facts", [])
    )

    for fact in after_facts - before_facts:
        changes.append(f"New fact: {fact[0]}.{fact[1]} = {fact[2]}")

    # Check needs
    before_needs = before.get("needs", {})
    after_needs = after.get("needs", {})

    for need_name in ["hunger", "thirst", "stamina", "sleep_pressure", "hygiene", "comfort"]:
        before_val = before_needs.get(need_name)
        after_val = after_needs.get(need_name)
        if before_val is not None and after_val is not None:
            diff = after_val - before_val
            if abs(diff) >= 5:  # Only report significant changes
                direction = "increased" if diff > 0 else "decreased"
                changes.append(f"Need {need_name} {direction}: {before_val} -> {after_val}")

    # Check time
    before_time = before.get("time", {})
    after_time = after.get("time", {})

    if before_time.get("current_time") != after_time.get("current_time"):
        changes.append(
            f"Time advanced: {before_time.get('current_time')} -> {after_time.get('current_time')}"
        )

    if before_time.get("current_day") != after_time.get("current_day"):
        changes.append(
            f"Day changed: {before_time.get('current_day')} -> {after_time.get('current_day')}"
        )

    return changes
