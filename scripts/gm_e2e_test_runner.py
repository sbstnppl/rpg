#!/usr/bin/env python3
"""GM Pipeline E2E Test Runner.

Creates fresh sessions and runs flowing gameplay scenarios with comprehensive logging.

Usage:
    python scripts/gm_e2e_test_runner.py                     # Run all scenarios
    python scripts/gm_e2e_test_runner.py --scenario dialog   # Run specific scenario
    python scripts/gm_e2e_test_runner.py --quick             # Run quick test subset
"""

import asyncio
import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, ".")

from src.database.connection import get_db_session
from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.database.models.world import TimeState, Fact
from src.database.models.character_state import CharacterNeeds
from src.database.models.items import Item
from src.database.models.relationships import Relationship
from src.database.models.tasks import Quest, Task, Appointment
from src.gm.graph import build_gm_graph
from src.gm.e2e_logger import GME2ELogger, TurnLog, compute_db_changes
from src.gm.e2e_assessor import GME2EAssessor
from scripts.gm_e2e_scenarios import (
    ALL_SCENARIOS,
    QUICK_TEST_SCENARIOS,
    TestScenario,
    TestAction,
)


@dataclass
class ScenarioResult:
    """Result of running a complete scenario."""

    scenario_name: str
    session_id: int
    passed_count: int
    total_count: int
    log_path: Path

    @property
    def passed(self) -> bool:
        return self.passed_count == self.total_count

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total_count if self.total_count > 0 else 0.0


class GME2ETestRunner:
    """Main E2E test runner for GM Pipeline."""

    def __init__(self, log_dir: Path | None = None):
        """Initialize the test runner.

        Args:
            log_dir: Custom log directory. Defaults to logs/gm_e2e.
        """
        self.log_dir = log_dir or Path("logs/gm_e2e")
        self.logger = GME2ELogger(self.log_dir)
        self.assessor = GME2EAssessor()

    async def run_scenario(self, scenario: TestScenario) -> ScenarioResult:
        """Run a complete test scenario.

        Args:
            scenario: The scenario to run.

        Returns:
            Result of the scenario run.
        """
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        print(f"{'='*60}")

        # Create fresh session
        session_id, player_id, location = await self._create_fresh_session()
        print(f"Created fresh session {session_id} at {location}")

        # Start logging
        log_path = self.logger.start_scenario(
            scenario_name=scenario.name,
            scenario_description=scenario.description,
            session_id=session_id,
            player_id=player_id,
            starting_location=location,
        )
        print(f"Logging to: {log_path}")
        print()

        passed_count = 0
        current_location = location

        with get_db_session() as db:
            graph = build_gm_graph()

            # Get the session and player for this DB session
            game_session = db.query(GameSession).filter(GameSession.id == session_id).first()
            player = db.query(Entity).filter(Entity.id == player_id).first()

            # Track previous responses for duplicate detection
            previous_responses: list[str] = []

            for i, action in enumerate(scenario.actions, 1):
                print(f"  Turn {i}: \"{action.input}\"... ", end="", flush=True)

                # Capture DB state before
                db_before = self._snapshot_db(db, session_id, player_id)

                # Run the turn
                start_time = time.time()
                result = await self._run_turn(
                    db=db,
                    graph=graph,
                    game_session=game_session,
                    player=player,
                    player_input=action.input,
                    turn_number=i,
                    location=current_location,
                )
                duration = time.time() - start_time

                # Capture DB state after
                db.flush()  # Ensure changes are visible
                db_after = self._snapshot_db(db, session_id, player_id)

                # Compute DB changes
                db_changes = compute_db_changes(db_before, db_after)

                # Get response details
                gm_response_obj = result.get("_gm_response_obj")
                narrative = result.get("gm_response", "")
                time_passed = gm_response_obj.time_passed_minutes if gm_response_obj else None
                tool_calls = self._extract_tool_calls(gm_response_obj)
                errors = result.get("errors", [])

                # Get context that was sent
                context_sent = result.get("_context_sent", "(context not captured)")

                # Assess the turn
                assessment = self.assessor.assess_turn(
                    narrative=narrative,
                    time_passed=time_passed,
                    tool_calls=tool_calls,
                    errors=errors,
                    db_changes=db_changes,
                    expectations=action.expectations,
                    previous_responses=previous_responses,
                )

                # Track this response for duplicate detection in next turn
                previous_responses.append(narrative)

                # Log the turn
                turn_log = TurnLog(
                    turn_number=i,
                    timestamp=datetime.now(),
                    player_input=action.input,
                    description=action.description,
                    context_sent=context_sent,
                    raw_response=narrative,
                    narrative=narrative,
                    tool_calls=tool_calls,
                    db_before=db_before,
                    db_after=db_after,
                    db_changes=db_changes,
                    passed=assessment.overall_passed,
                    assessment_details=assessment.to_dict(),
                    issues=assessment.all_issues,
                    time_passed_minutes=time_passed,
                    duration_seconds=duration,
                )
                self.logger.log_turn(turn_log)

                # Print result
                status = "PASS" if assessment.overall_passed else "FAIL"
                print(f"{status} ({len(narrative)} chars, {time_passed} min)")

                if assessment.all_issues:
                    for issue in assessment.all_issues:
                        print(f"    ! {issue}")

                if assessment.overall_passed:
                    passed_count += 1

                # Update location if changed
                if result.get("location_changed"):
                    current_location = result.get("new_location", current_location)

            # Commit all changes
            db.commit()

        # Finish logging
        self.logger.finish_scenario()

        return ScenarioResult(
            scenario_name=scenario.name,
            session_id=session_id,
            passed_count=passed_count,
            total_count=len(scenario.actions),
            log_path=log_path,
        )

    async def _create_fresh_session(self) -> tuple[int, int, str]:
        """Create a fresh test session.

        Returns:
            Tuple of (session_id, player_id, starting_location).
        """
        from src.cli.commands.character import (
            _create_character_records,
            _create_starting_equipment,
            _create_character_preferences,
        )
        from src.cli.commands.game import _create_auto_character_state
        from src.schemas.settings import get_setting_schema

        with get_db_session() as db:
            # Create game session
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            game_session = GameSession(
                session_name=f"E2E Test {timestamp}",
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

            # Create starting equipment
            _create_starting_equipment(
                db=db,
                game_session=game_session,
                entity=entity,
                schema=schema,
            )

            # Create character preferences
            _create_character_preferences(db, game_session, entity)

            # Create a simple starting location for testing
            starting_location = self._create_test_location(db, game_session, entity)

            db.commit()

            return game_session.id, entity.id, starting_location

    def _create_test_location(self, db, game_session: GameSession, player: Entity) -> str:
        """Create a simple test location with some NPCs and items.

        Args:
            db: Database session.
            game_session: The game session.
            player: The player entity.

        Returns:
            Location key.
        """
        from src.database.models.entities import Entity, NPCExtension
        from src.database.models.items import Item, StorageLocation
        from src.database.models.enums import ItemType, StorageLocationType

        location_key = "test_farmhouse"

        # Create a storage location for the farmhouse (place type)
        storage = StorageLocation(
            session_id=game_session.id,
            location_key=location_key,
            location_type=StorageLocationType.PLACE,
        )
        db.add(storage)
        db.flush()

        # Create an NPC at the location
        npc = Entity(
            session_id=game_session.id,
            entity_key="farmer_marcus",
            entity_type=EntityType.NPC,
            display_name="Marcus",
        )
        db.add(npc)
        db.flush()

        # Create NPC extension with location
        npc_ext = NPCExtension(
            entity_id=npc.id,
            current_location=location_key,
            current_activity="standing by the fireplace",
        )
        db.add(npc_ext)

        # Create some items at the storage location
        items_data = [
            ("pitchfork_001", "Pitchfork", "A well-used farming tool.", ItemType.TOOL),
            ("bread_001", "Bread", "A fresh loaf of bread.", ItemType.CONSUMABLE),
            ("water_jug_001", "Water Jug", "A ceramic jug filled with clean water.", ItemType.CONSUMABLE),
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

        # Set player location via NPC extension
        if player.npc_extension:
            player.npc_extension.current_location = location_key
        else:
            player_ext = NPCExtension(
                entity_id=player.id,
                current_location=location_key,
            )
            db.add(player_ext)

        return location_key

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
        """Run a single turn through the GM pipeline.

        Args:
            db: Database session.
            graph: Compiled GM graph.
            game_session: The game session.
            player: Player entity.
            player_input: Player's input text.
            turn_number: Current turn number.
            location: Current player location.

        Returns:
            Result dictionary from the graph.
        """
        state = {
            "session_id": game_session.id,
            "player_id": player.id,
            "player_location": location,
            "player_input": player_input,
            "turn_number": turn_number,
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
            return result
        except Exception as e:
            return {
                "gm_response": "",
                "_gm_response_obj": None,
                "errors": [str(e)],
                "skill_checks": [],
                "location_changed": False,
                "new_location": None,
                "_context_sent": "(error before context built)",
            }

    def _snapshot_db(self, db, session_id: int, player_id: int) -> dict[str, Any]:
        """Capture relevant DB state for comparison.

        Args:
            db: Database session.
            session_id: Game session ID.
            player_id: Player entity ID.

        Returns:
            Dictionary with DB state snapshots.
        """
        # Items
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

        # NPCs
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

        # Relationships
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

        # Facts
        facts = db.query(Fact).filter(Fact.session_id == session_id).all()
        facts_data = [
            {
                "subject_key": f.subject_key,
                "predicate": f.predicate,
                "value": f.value,
            }
            for f in facts
        ]

        # Needs
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

        # Time
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
        """Extract tool calls from GM response object.

        Args:
            gm_response_obj: GMResponse object or None.

        Returns:
            List of tool call dictionaries.
        """
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
        scenarios: list[TestScenario] | None = None,
    ) -> list[ScenarioResult]:
        """Run all scenarios.

        Args:
            scenarios: Scenarios to run. Defaults to ALL_SCENARIOS.

        Returns:
            List of scenario results.
        """
        scenarios = scenarios or ALL_SCENARIOS

        results = []
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)

        # Print final summary
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)

        total_passed = sum(r.passed_count for r in results)
        total_tests = sum(r.total_count for r in results)
        overall_rate = total_passed / total_tests if total_tests > 0 else 0

        print(f"Overall: {total_passed}/{total_tests} ({overall_rate:.1%})")
        print()

        for r in results:
            icon = "[+]" if r.passed else "[-]"
            print(f"{icon} {r.scenario_name}: {r.passed_count}/{r.total_count}")
            print(f"    Log: {r.log_path}")

        print()
        print(f"All logs in: {self.log_dir}")

        return results


async def main():
    parser = argparse.ArgumentParser(description="GM Pipeline E2E Test Runner")
    parser.add_argument(
        "--scenario",
        "-s",
        help="Run specific scenario by name (partial match)",
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Run quick test subset only",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Custom log directory",
    )
    args = parser.parse_args()

    runner = GME2ETestRunner(log_dir=args.log_dir)

    # Determine which scenarios to run
    if args.quick:
        scenarios = QUICK_TEST_SCENARIOS
    elif args.scenario:
        scenarios = [
            s for s in ALL_SCENARIOS if args.scenario.lower() in s.name.lower()
        ]
        if not scenarios:
            print(f"No scenario matching '{args.scenario}' found.")
            print("Available scenarios:")
            for s in ALL_SCENARIOS:
                print(f"  - {s.name}")
            sys.exit(1)
    else:
        scenarios = ALL_SCENARIOS

    print(f"Running {len(scenarios)} scenario(s)...")

    results = await runner.run_all(scenarios)

    # Exit with appropriate code
    all_passed = all(r.passed for r in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
