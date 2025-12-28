#!/usr/bin/env python3
"""Interactive Gameplay Monitor.

Play the game while observing all LLM calls, tool executions, and state changes.
Designed for debugging and understanding the GM pipeline.

Usage:
    python scripts/gameplay_monitor.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, ".")

from src.database.connection import get_db_session
from src.database.models.session import GameSession
from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType, ItemType
from src.database.models.world import TimeState, Location
from src.database.models.items import Item, StorageLocation
from src.database.models.enums import StorageLocationType
from src.database.models.character_state import CharacterNeeds
from src.gm.graph import build_gm_graph


class GameplayMonitor:
    """Interactive gameplay monitor for debugging GM pipeline."""

    def __init__(self):
        self.session_id: int | None = None
        self.player_id: int | None = None
        self.location: str = ""
        self.turn_number: int = 0
        self.issues: list[dict] = []
        self.milestones: list[str] = []

    async def create_session(self) -> tuple[int, int, str]:
        """Create a new game session with test data."""
        from src.cli.commands.character import (
            _create_character_records,
            _create_starting_equipment,
            _create_character_preferences,
        )
        from src.cli.commands.game import _create_auto_character_state
        from src.schemas.settings import get_setting_schema

        with get_db_session() as db:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            game_session = GameSession(
                session_name=f"Monitor Session {timestamp}",
                setting="fantasy",
                status="active",
                total_turns=0,
                llm_provider="ollama",
                gm_model="qwen3:32b",
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

            # Create player character
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
            location_key = "village_tavern"
            location = Location(
                session_id=game_session.id,
                location_key=location_key,
                display_name="The Rusty Tankard",
                description=(
                    "A cozy village tavern with low wooden beams and a crackling fireplace. "
                    "The air smells of ale and roasted meat. Several worn tables fill the room, "
                    "and a long bar stretches along one wall. Patrons murmur in conversation."
                ),
                category="building",
                atmosphere="Warm and welcoming, with the buzz of quiet conversation",
            )
            db.add(location)

            storage = StorageLocation(
                session_id=game_session.id,
                location_key=location_key,
                location_type=StorageLocationType.PLACE,
            )
            db.add(storage)
            db.flush()

            # Create NPCs
            barkeep = Entity(
                session_id=game_session.id,
                entity_key="barkeep_elara",
                entity_type=EntityType.NPC,
                display_name="Elara",
            )
            db.add(barkeep)
            db.flush()

            barkeep_ext = NPCExtension(
                entity_id=barkeep.id,
                current_location=location_key,
                current_activity="polishing a mug behind the bar",
            )
            db.add(barkeep_ext)

            traveler = Entity(
                session_id=game_session.id,
                entity_key="traveler_hooded",
                entity_type=EntityType.NPC,
                display_name="Hooded Traveler",
            )
            db.add(traveler)
            db.flush()

            traveler_ext = NPCExtension(
                entity_id=traveler.id,
                current_location=location_key,
                current_activity="sitting in a dark corner, nursing a drink",
            )
            db.add(traveler_ext)

            # Create items
            items_data = [
                ("ale_mug_001", "Mug of Ale", "A frothy mug of ale.", ItemType.CONSUMABLE),
                ("bread_loaf_001", "Bread Loaf", "A fresh loaf of bread.", ItemType.CONSUMABLE),
                ("coin_pouch_001", "Coin Pouch", "A leather pouch with coins.", ItemType.MISC),
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

    async def run_turn(self, player_input: str) -> dict[str, Any]:
        """Run a single turn and capture all details."""
        from src.observability.console_observer import RichConsoleObserver

        self.turn_number += 1

        with get_db_session() as db:
            graph = build_gm_graph()
            game_session = db.query(GameSession).filter(GameSession.id == self.session_id).first()
            player = db.query(Entity).filter(Entity.id == self.player_id).first()

            # Create observer for detailed output
            observer = RichConsoleObserver(show_tool_details=True, show_tokens=True)

            state = {
                "session_id": game_session.id,
                "player_id": player.id,
                "player_location": self.location,
                "player_input": player_input,
                "turn_number": self.turn_number,
                "_db": db,
                "_game_session": game_session,
                "_observability_hook": observer,
                "roll_mode": "auto",
                "_gm_response_obj": None,
                "gm_response": "",
                "new_location": None,
                "location_changed": False,
                "errors": [],
                "skill_checks": [],
            }

            print(f"\n{'='*60}")
            print(f"TURN {self.turn_number}: {player_input}")
            print(f"{'='*60}")

            result = await graph.ainvoke(state)

            # Extract details
            gm_response = result.get("gm_response", "")
            gm_response_obj = result.get("_gm_response_obj")

            # Get tool calls
            tool_results = []
            if gm_response_obj and hasattr(gm_response_obj, "tool_results"):
                tool_results = gm_response_obj.tool_results

            # Get time passed
            time_passed = gm_response_obj.time_passed_minutes if gm_response_obj else None

            # Print results
            print(f"\n--- NARRATIVE ---")
            print(gm_response)

            print(f"\n--- TOOL CALLS ({len(tool_results)}) ---")
            for tr in tool_results:
                tool_name = tr.get("tool", "?")
                args = tr.get("arguments", {})
                res = tr.get("result", {})
                success = res.get("success", True) if isinstance(res, dict) else True
                status = "OK" if success else "FAIL"
                print(f"  [{status}] {tool_name}: {args}")
                if not success:
                    print(f"       Error: {res}")

            print(f"\n--- TIME ---")
            print(f"  Time passed: {time_passed} minutes")

            # Query DB for changes
            needs = db.query(CharacterNeeds).filter(CharacterNeeds.entity_id == self.player_id).first()
            time_state = db.query(TimeState).filter(TimeState.session_id == self.session_id).first()

            print(f"\n--- STATE ---")
            print(f"  Game time: Day {time_state.current_day}, {time_state.current_time}")
            if needs:
                print(f"  Hunger: {needs.hunger}, Thirst: {needs.thirst}, Stamina: {needs.stamina}")

            # Update location if changed
            if result.get("location_changed"):
                self.location = result.get("new_location", self.location)
                print(f"  Location changed to: {self.location}")

            db.commit()

            return {
                "narrative": gm_response,
                "tool_calls": tool_results,
                "time_passed": time_passed,
                "errors": result.get("errors", []),
            }

    def record_issue(self, title: str, expected: str, actual: str, severity: str = "medium"):
        """Record an issue found during testing."""
        issue = {
            "number": len(self.issues) + 1,
            "turn": self.turn_number,
            "title": title,
            "expected": expected,
            "actual": actual,
            "severity": severity,
        }
        self.issues.append(issue)
        print(f"\n!!! ISSUE #{issue['number']}: {title}")

    def record_milestone(self, name: str):
        """Record a milestone achieved."""
        self.milestones.append(name)
        print(f"\n*** MILESTONE: {name} ***")

    def print_summary(self):
        """Print session summary."""
        print(f"\n{'='*60}")
        print("SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"Turns played: {self.turn_number}")
        print(f"Milestones: {len(self.milestones)}")
        for m in self.milestones:
            print(f"  - {m}")
        print(f"Issues found: {len(self.issues)}")
        for i in self.issues:
            print(f"  - [{i['severity']}] #{i['number']}: {i['title']}")


async def main():
    """Run the gameplay monitor."""
    monitor = GameplayMonitor()

    print("Creating game session...")
    session_id, player_id, location = await monitor.create_session()
    monitor.session_id = session_id
    monitor.player_id = player_id
    monitor.location = location

    print(f"\nSession created: {session_id}")
    print(f"Player ID: {player_id}")
    print(f"Location: {location}")
    print("\nReady to play! Type your actions or 'quit' to exit.")
    print("Commands: /issue, /milestone, /summary, quit")

    # Predefined actions for automated testing
    actions = [
        "I look around the tavern",
        "I walk up to the bar and greet the barkeep",
        "Hello there! What's your name?",
        "I'd like some ale please",
        "I pick up the mug of ale",
        "I take a drink from the ale",
        "Who's that hooded figure in the corner?",
        "I approach the hooded traveler",
        "Greetings, stranger. What brings you here?",
        "[OOC] What time is it?",
        "I'm feeling tired. I think I'll rest for a bit.",
        "[OOC] What are my current needs?",
        "I examine the coin pouch on the table",
        "I try to pick the lock on the back door",
        "I wave goodbye to Elara and head outside",
    ]

    turn_count = 0
    for action in actions:
        turn_count += 1
        print(f"\n>>> [{turn_count}/{len(actions)}] Playing: {action}")

        try:
            result = await monitor.run_turn(action)

            # Check for milestones
            if turn_count == 1 and len(result["narrative"]) > 50:
                monitor.record_milestone("Scene Introduction")
            elif "greet" in action.lower() or "hello" in action.lower():
                if len(result.get("tool_calls", [])) > 0 or len(result["narrative"]) > 100:
                    monitor.record_milestone("Dialog Exchange")
            elif "pick up" in action.lower() or "take" in action.lower():
                monitor.record_milestone("Item Interaction")
            elif "lock" in action.lower():
                if any(tc.get("tool") == "skill_check" for tc in result.get("tool_calls", [])):
                    monitor.record_milestone("Skill Check")
            elif "rest" in action.lower() or "drink" in action.lower():
                if result.get("time_passed", 0) > 5:
                    monitor.record_milestone("Time Passage")

            # Check for issues
            if not result["narrative"] or len(result["narrative"]) < 30:
                monitor.record_issue(
                    "Short/empty response",
                    "Response >= 30 chars",
                    f"Got {len(result['narrative'])} chars",
                    "critical"
                )

            if result.get("errors"):
                for err in result["errors"]:
                    monitor.record_issue(
                        "Pipeline error",
                        "No errors",
                        str(err),
                        "critical"
                    )

        except Exception as e:
            monitor.record_issue(
                "Exception during turn",
                "No exceptions",
                str(e),
                "critical"
            )
            import traceback
            traceback.print_exc()

        # Stop conditions
        if len(monitor.milestones) >= 5:
            print("\n*** 5 milestones reached! ***")
            break
        if len(monitor.issues) >= 5:
            print("\n*** 5 issues found - stopping for discussion ***")
            break

    monitor.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
