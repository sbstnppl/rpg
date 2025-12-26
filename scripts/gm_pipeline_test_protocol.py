#!/usr/bin/env python3
"""GM Pipeline E2E Test Protocol.

A comprehensive test script for validating the GM pipeline functionality.
Runs through all test scenarios and generates a detailed report.

Usage:
    python scripts/gm_pipeline_test_protocol.py [--session SESSION_ID]
"""

import asyncio
import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Add project root to path
sys.path.insert(0, ".")

from src.database.connection import get_db_session
from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.world import TimeState
from src.database.models.character_state import CharacterNeeds
from src.gm.graph import build_gm_graph


@dataclass
class TestResult:
    """Result of a single test."""
    category: str
    action: str
    passed: bool
    response_length: int
    time_passed: int | None
    errors: list[str]
    skill_checks: list[dict]
    state_changes: list[dict]
    notes: str = ""


@dataclass
class TestReport:
    """Complete test report."""
    session_id: int
    session_name: str
    timestamp: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total_count if self.total_count > 0 else 0


# Test scenarios organized by category
TEST_SCENARIOS = {
    "Observation": [
        ("look around", {"min_chars": 100, "max_time": 5}),
        ("examine the area", {"min_chars": 50, "max_time": 5}),
        ("search the room", {"min_chars": 50, "max_time": 10}),
    ],
    "Dialog": [
        ("Good morning!", {"min_chars": 30, "max_time": 2}),
        ("How are you?", {"min_chars": 30, "max_time": 2}),
        ("Tell me about yourself", {"min_chars": 50, "max_time": 5}),
    ],
    "Movement - Local": [
        ("go outside", {"min_chars": 50, "max_time": 5}),
        ("walk to the table", {"min_chars": 30, "max_time": 3}),
        ("step back", {"min_chars": 30, "max_time": 2}),
    ],
    "Movement - Travel": [
        ("walk to the village", {"min_chars": 50, "min_time": 5, "max_time": 60}),
        ("travel to the market", {"min_chars": 50, "min_time": 10, "max_time": 120}),
    ],
    "Items - Take": [
        ("take the pitchfork", {"min_chars": 30, "max_time": 2}),
        ("pick up the basket", {"min_chars": 30, "max_time": 2}),
    ],
    "Items - Drop": [
        ("drop the pitchfork", {"min_chars": 30, "max_time": 2}),
        ("put down the basket", {"min_chars": 30, "max_time": 2}),
    ],
    "Needs - Hunger": [
        ("eat some bread", {"min_chars": 30, "max_time": 15}),
        ("have some food", {"min_chars": 30, "max_time": 15}),
    ],
    "Needs - Thirst": [
        ("drink water", {"min_chars": 30, "max_time": 5}),
        ("take a sip from the mug", {"min_chars": 30, "max_time": 5}),
    ],
    "Needs - Rest": [
        ("rest for a bit", {"min_chars": 30, "min_time": 5, "max_time": 30}),
        ("catch my breath", {"min_chars": 30, "max_time": 10}),
    ],
    "Skills - Stealth": [
        ("sneak past quietly", {"min_chars": 30, "expects_skill_check": True}),
        ("hide in the shadows", {"min_chars": 30, "expects_skill_check": True}),
    ],
    "Skills - Perception": [
        ("listen carefully for danger", {"min_chars": 30, "expects_skill_check": True}),
        ("search for hidden items", {"min_chars": 30, "expects_skill_check": True}),
    ],
    "Skills - Social": [
        ("persuade her to help me", {"min_chars": 30, "expects_skill_check": True}),
        ("try to charm the stranger", {"min_chars": 30, "expects_skill_check": True}),
    ],
    "OOC": [
        ("ooc: what time is it?", {"min_chars": 10, "max_time": 0}),
        ("ooc: what skills do I have?", {"min_chars": 10, "max_time": 0}),
    ],
}


async def run_turn(
    db,
    game_session: GameSession,
    player: Entity,
    player_input: str,
    location: str = "brennan_farm",
) -> dict[str, Any]:
    """Run a single turn through the GM pipeline."""
    graph = build_gm_graph()

    state = {
        "session_id": game_session.id,
        "player_id": player.id,
        "player_location": location,
        "player_input": player_input,
        "turn_number": game_session.total_turns + 1,
        "_db": db,
        "_game_session": game_session,
        "roll_mode": "auto",
        "_gm_response_obj": None,
        "gm_response": "",
        "new_location": None,
        "location_changed": False,
        "errors": [],
        "skill_checks": [],
    }

    try:
        result = await graph.ainvoke(state)
    except Exception as e:
        return {
            "response": "",
            "time_passed": None,
            "errors": [str(e)],
            "skill_checks": [],
            "state_changes": [],
            "location_changed": False,
            "new_location": None,
        }

    gm_obj = result.get("_gm_response_obj")
    time_passed = gm_obj.time_passed_minutes if gm_obj else None
    state_changes = gm_obj.state_changes if gm_obj else []

    return {
        "response": result.get("gm_response", ""),
        "time_passed": time_passed,
        "errors": result.get("errors", []),
        "skill_checks": result.get("skill_checks", []),
        "state_changes": [sc.model_dump() for sc in state_changes] if state_changes else [],
        "location_changed": result.get("location_changed", False),
        "new_location": result.get("new_location"),
    }


def evaluate_result(
    result: dict[str, Any],
    expectations: dict[str, Any],
) -> tuple[bool, str]:
    """Evaluate if a test result meets expectations."""
    notes = []
    passed = True

    # Check response length
    min_chars = expectations.get("min_chars", 30)
    if len(result["response"]) < min_chars:
        passed = False
        notes.append(f"Response too short: {len(result['response'])} < {min_chars}")

    # Check for errors
    if result["errors"]:
        passed = False
        notes.append(f"Errors: {result['errors']}")

    # Check time bounds
    time_passed = result["time_passed"]
    if time_passed is not None:
        min_time = expectations.get("min_time", 0)
        max_time = expectations.get("max_time", 999)

        if time_passed < min_time:
            notes.append(f"Time too short: {time_passed} < {min_time}")
        if time_passed > max_time:
            notes.append(f"Time too long: {time_passed} > {max_time}")
    elif expectations.get("max_time", 999) > 0:
        notes.append("No time tracking")

    # Check skill check expectation
    if expectations.get("expects_skill_check", False):
        if not result["skill_checks"]:
            notes.append("Expected skill check but none triggered")
        else:
            check = result["skill_checks"][0]
            notes.append(f"Skill: {check.get('skill')} DC {check.get('dc')} -> {'Pass' if check.get('success') else 'Fail'}")

    return passed, "; ".join(notes) if notes else "OK"


async def run_test_protocol(session_id: int | None = None) -> TestReport:
    """Run the complete test protocol."""

    with get_db_session() as db:
        # Get session
        if session_id:
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
        else:
            game_session = db.query(GameSession).order_by(GameSession.id.desc()).first()

        if not game_session:
            raise ValueError("No game session found")

        # Get player
        player = db.query(Entity).filter(
            Entity.session_id == game_session.id,
            Entity.entity_type == EntityType.PLAYER
        ).first()

        if not player:
            raise ValueError("No player entity found in session")

        # Get player location from NPC extension or default
        location = "brennan_farm"
        if player.npc_extension and player.npc_extension.current_location:
            location = player.npc_extension.current_location

        # Create report
        report = TestReport(
            session_id=game_session.id,
            session_name=game_session.session_name,
            timestamp=datetime.now().isoformat(),
        )

        print(f"\n{'='*60}")
        print(f"GM Pipeline Test Protocol")
        print(f"Session: {game_session.session_name} (ID: {game_session.id})")
        print(f"Player: {player.display_name}")
        print(f"Location: {location}")
        print(f"{'='*60}\n")

        # Run tests by category
        for category, tests in TEST_SCENARIOS.items():
            print(f"\n--- {category} ---")

            for action, expectations in tests:
                print(f"  Testing: '{action}'... ", end="", flush=True)

                result = await run_turn(db, game_session, player, action, location)
                passed, notes = evaluate_result(result, expectations)

                test_result = TestResult(
                    category=category,
                    action=action,
                    passed=passed,
                    response_length=len(result["response"]),
                    time_passed=result["time_passed"],
                    errors=result["errors"],
                    skill_checks=result["skill_checks"],
                    state_changes=result["state_changes"],
                    notes=notes,
                )
                report.results.append(test_result)

                status = "PASS" if passed else "FAIL"
                print(f"{status} ({len(result['response'])} chars, {result['time_passed']} min)")
                if notes and notes != "OK":
                    print(f"    Notes: {notes}")

        # Don't commit changes - this is just testing
        db.rollback()

    return report


def print_report(report: TestReport) -> None:
    """Print a formatted test report."""
    print(f"\n{'='*60}")
    print("TEST REPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Session: {report.session_name} (ID: {report.session_id})")
    print(f"Timestamp: {report.timestamp}")
    print(f"Pass Rate: {report.passed_count}/{report.total_count} ({report.pass_rate:.1%})")
    print()

    # Group by category
    categories: dict[str, list[TestResult]] = {}
    for result in report.results:
        if result.category not in categories:
            categories[result.category] = []
        categories[result.category].append(result)

    # Print by category
    for category, results in categories.items():
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        status = "✅" if passed == total else "⚠️" if passed > 0 else "❌"
        print(f"{status} {category}: {passed}/{total}")

        for r in results:
            icon = "✓" if r.passed else "✗"
            print(f"    {icon} {r.action}")
            if not r.passed and r.notes:
                print(f"      → {r.notes}")

    # List all failures
    failures = [r for r in report.results if not r.passed]
    if failures:
        print(f"\n{'='*60}")
        print("FAILURES")
        print(f"{'='*60}")
        for f in failures:
            print(f"\n[{f.category}] {f.action}")
            print(f"  Response: {f.response_length} chars")
            print(f"  Time: {f.time_passed} min")
            if f.errors:
                print(f"  Errors: {f.errors}")
            print(f"  Notes: {f.notes}")

    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")

    if report.pass_rate < 0.5:
        print("• Critical: Less than 50% pass rate. Check tool definitions and error handling.")

    # Check for common issues
    empty_responses = sum(1 for r in report.results if r.response_length == 0)
    if empty_responses > 0:
        print(f"• {empty_responses} tests returned empty responses. Check tool execution errors.")

    no_time = sum(1 for r in report.results if r.time_passed is None)
    if no_time > 0:
        print(f"• {no_time} tests had no time tracking. Check _estimate_time_passed logic.")

    no_skill_checks = sum(1 for r in report.results
                         if "Skills" in r.category and not r.skill_checks)
    if no_skill_checks > 0:
        print(f"• {no_skill_checks} skill tests didn't trigger checks. Check tool invocation.")


async def main():
    parser = argparse.ArgumentParser(description="GM Pipeline E2E Test Protocol")
    parser.add_argument("--session", "-s", type=int, help="Session ID to test")
    args = parser.parse_args()

    try:
        report = await run_test_protocol(args.session)
        print_report(report)

        # Exit with error code if any tests failed
        sys.exit(0 if report.pass_rate == 1.0 else 1)

    except Exception as e:
        print(f"\nError running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
