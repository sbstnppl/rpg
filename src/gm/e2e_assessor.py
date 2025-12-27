"""E2E Test Assessor for GM Pipeline.

Evaluates turn results against expectations:
- Narrative quality (length, format, content, no duplicates)
- Tool usage (expected/forbidden tools)
- Database changes (expected state updates)
- Time tracking (within expected range)
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from scripts.gm_e2e_scenarios import ActionExpectations


@dataclass
class AssessmentResult:
    """Result of a single assessment category."""

    passed: bool
    message: str
    issues: list[str] = field(default_factory=list)


@dataclass
class TurnAssessment:
    """Complete assessment of a turn."""

    overall_passed: bool
    narrative: AssessmentResult
    tool_usage: AssessmentResult
    db_changes: AssessmentResult
    time_tracking: AssessmentResult
    grounding: AssessmentResult | None = None  # Entity grounding check

    @property
    def all_issues(self) -> list[str]:
        """Collect all issues from all categories."""
        issues = []
        issues.extend(self.narrative.issues)
        issues.extend(self.tool_usage.issues)
        issues.extend(self.db_changes.issues)
        issues.extend(self.time_tracking.issues)
        if self.grounding:
            issues.extend(self.grounding.issues)
        return issues

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        result = {
            "narrative": {
                "passed": self.narrative.passed,
                "message": self.narrative.message,
            },
            "tool_usage": {
                "passed": self.tool_usage.passed,
                "message": self.tool_usage.message,
            },
            "db_changes": {
                "passed": self.db_changes.passed,
                "message": self.db_changes.message,
            },
            "time_tracking": {
                "passed": self.time_tracking.passed,
                "message": self.time_tracking.message,
            },
        }
        if self.grounding:
            result["grounding"] = {
                "passed": self.grounding.passed,
                "message": self.grounding.message,
            }
        return result


class GME2EAssessor:
    """Assess GM turn results against expectations."""

    def assess_turn(
        self,
        narrative: str,
        time_passed: int | None,
        tool_calls: list[dict[str, Any]],
        errors: list[str],
        db_changes: list[str],
        expectations: ActionExpectations,
        previous_responses: list[str] | None = None,
        expected_entities: list[str] | None = None,
        skip_duplicate_check: bool = False,
    ) -> TurnAssessment:
        """Assess a complete turn.

        Args:
            narrative: GM narrative response.
            time_passed: Minutes of game time passed.
            tool_calls: List of tool calls made.
            errors: Any errors that occurred.
            db_changes: List of DB change descriptions.
            expectations: Expected outcomes for this action.
            previous_responses: List of previous turn responses (for duplicate detection).
            expected_entities: List of entity names that should appear in narrative.
            skip_duplicate_check: If True, don't flag duplicate responses as failures.
                                  Useful for OOC queries where identical answers are expected.

        Returns:
            Complete turn assessment.
        """
        narrative_result = self._assess_narrative(
            narrative, errors, expectations, previous_responses or [],
            skip_duplicate_check=skip_duplicate_check
        )
        tool_result = self._assess_tools(tool_calls, expectations)
        db_result = self._assess_db_changes(db_changes, expectations)
        time_result = self._assess_time(time_passed, expectations)
        grounding_result = self._assess_grounding(narrative, expected_entities)

        results = [
            narrative_result.passed,
            tool_result.passed,
            db_result.passed,
            time_result.passed,
        ]
        # Only include grounding if expected_entities was provided
        if expected_entities:
            results.append(grounding_result.passed)

        overall = all(results)

        return TurnAssessment(
            overall_passed=overall,
            narrative=narrative_result,
            tool_usage=tool_result,
            db_changes=db_result,
            time_tracking=time_result,
            grounding=grounding_result if expected_entities else None,
        )

    def _text_similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings.

        Args:
            a: First string.
            b: Second string.

        Returns:
            Similarity ratio (0.0 to 1.0).
        """
        if not a or not b:
            return 0.0
        # Normalize
        a_norm = a.strip().lower()
        b_norm = b.strip().lower()
        # Exact match
        if a_norm == b_norm:
            return 1.0
        # Use difflib for similarity
        return SequenceMatcher(None, a_norm, b_norm).ratio()

    def _assess_narrative(
        self,
        narrative: str,
        errors: list[str],
        expectations: ActionExpectations,
        previous_responses: list[str],
        skip_duplicate_check: bool = False,
    ) -> AssessmentResult:
        """Assess narrative quality.

        Checks:
        - Response length meets minimum
        - No errors occurred
        - No raw data structures
        - Second-person narration
        - No markdown formatting
        - Not a duplicate of previous responses (unless skip_duplicate_check is True)
        """
        issues = []

        # Check for errors
        if errors:
            issues.append(f"Errors occurred: {errors}")

        # Check for duplicate responses (skip for OOC scenarios where same answer is expected)
        if not skip_duplicate_check:
            for i, prev in enumerate(previous_responses):
                similarity = self._text_similarity(narrative, prev)
                if similarity > 0.95:  # 95% similar = duplicate
                    issues.append(f"Response is duplicate of turn {i + 1} ({similarity:.0%} similar)")
                    break

        # Check length
        if len(narrative) < expectations.min_chars:
            issues.append(
                f"Response too short: {len(narrative)} < {expectations.min_chars} chars"
            )

        if expectations.max_chars and len(narrative) > expectations.max_chars:
            issues.append(
                f"Response too long: {len(narrative)} > {expectations.max_chars} chars"
            )

        # Check for raw data structures
        bad_patterns = ["GMResponse", "StateChange", "ToolResult", "```"]
        for pattern in bad_patterns:
            if pattern in narrative:
                issues.append(f"Raw data structure in output: '{pattern}'")

        # Check for third-person narration
        if "the player" in narrative.lower():
            issues.append("Third-person narration detected ('the player')")

        # Check for markdown formatting (shouldn't be in clean narrative)
        if "**" in narrative:
            issues.append("Markdown bold formatting in narrative")

        if "##" in narrative:
            issues.append("Markdown headers in narrative")

        passed = len(issues) == 0
        if passed:
            message = f"OK ({len(narrative)} chars)"
        else:
            message = f"FAIL ({len(issues)} issues)"

        return AssessmentResult(passed=passed, message=message, issues=issues)

    def _assess_tools(
        self,
        tool_calls: list[dict[str, Any]],
        expectations: ActionExpectations,
    ) -> AssessmentResult:
        """Assess tool usage.

        Checks:
        - Expected tools were called
        - Forbidden tools were not called
        - Tool calls did not return errors
        """
        issues = []
        actual_tools = [tc.get("tool", "") for tc in tool_calls]

        # Check expected tools
        if expectations.expected_tools:
            for tool in expectations.expected_tools:
                if tool not in actual_tools:
                    issues.append(f"Expected tool not called: {tool}")

        # Check forbidden tools
        if expectations.forbidden_tools:
            for tool in expectations.forbidden_tools:
                if tool in actual_tools:
                    issues.append(f"Forbidden tool was called: {tool}")

        # Check for tool errors
        for tc in tool_calls:
            result = tc.get("result", {})
            if isinstance(result, dict) and "error" in result:
                tool_name = tc.get("tool", "unknown")
                issues.append(f"Tool '{tool_name}' error: {result['error']}")

        passed = len(issues) == 0
        if passed:
            if actual_tools:
                message = f"OK (called: {', '.join(actual_tools)})"
            else:
                message = "OK (no tools called)"
        else:
            message = f"FAIL ({len(issues)} issues)"

        return AssessmentResult(passed=passed, message=message, issues=issues)

    def _assess_db_changes(
        self,
        db_changes: list[str],
        expectations: ActionExpectations,
    ) -> AssessmentResult:
        """Assess database changes.

        Checks:
        - Expected changes occurred
        """
        issues = []

        if expectations.expected_db_changes:
            for expected in expectations.expected_db_changes:
                # Check if any actual change matches the expected pattern
                found = any(expected.lower() in change.lower() for change in db_changes)
                if not found:
                    issues.append(f"Expected DB change not found: {expected}")

        passed = len(issues) == 0
        if passed:
            if db_changes:
                message = f"OK ({len(db_changes)} changes)"
            else:
                message = "OK (no changes)"
        else:
            message = f"FAIL ({len(issues)} issues)"

        return AssessmentResult(passed=passed, message=message, issues=issues)

    def _assess_time(
        self,
        time_passed: int | None,
        expectations: ActionExpectations,
    ) -> AssessmentResult:
        """Assess time tracking.

        Checks:
        - Time passed is within expected range
        """
        issues = []

        if time_passed is None:
            if expectations.max_time > 0:
                issues.append("No time tracking (time_passed is None)")
            time_str = "None"
        else:
            time_str = f"{time_passed} min"

            if time_passed < expectations.min_time:
                issues.append(
                    f"Time too short: {time_passed} < {expectations.min_time} min"
                )

            if time_passed > expectations.max_time:
                issues.append(
                    f"Time too long: {time_passed} > {expectations.max_time} min"
                )

        passed = len(issues) == 0
        if passed:
            message = f"OK ({time_str})"
        else:
            message = f"FAIL ({time_str})"

        return AssessmentResult(passed=passed, message=message, issues=issues)

    def _assess_grounding(
        self,
        narrative: str,
        expected_entities: list[str] | None,
    ) -> AssessmentResult:
        """Assess entity grounding in narrative.

        Checks that narrative mentions at least one expected scene entity,
        helping detect when the GM hallucinates content not in the scene.

        Args:
            narrative: GM narrative response.
            expected_entities: List of entity names/terms that should appear.

        Returns:
            Assessment result for grounding check.
        """
        issues = []

        if expected_entities:
            narrative_lower = narrative.lower()
            mentioned = [e for e in expected_entities if e.lower() in narrative_lower]

            if not mentioned:
                # Truncate list for readability
                display_entities = expected_entities[:5]
                if len(expected_entities) > 5:
                    display_entities.append("...")
                issues.append(
                    f"No scene entities mentioned (expected: {display_entities})"
                )

        passed = len(issues) == 0
        if passed:
            message = "OK (grounded)"
        else:
            message = "FAIL (ungrounded)"

        return AssessmentResult(passed=passed, message=message, issues=issues)
