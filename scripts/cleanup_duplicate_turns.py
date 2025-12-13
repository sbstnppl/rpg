#!/usr/bin/env python3
"""Cleanup script to remove duplicate turn records.

This script identifies turns with the same session_id and turn_number,
keeps the one with the most complete data, and deletes the duplicates.

Usage:
    python scripts/cleanup_duplicate_turns.py [--dry-run]
"""

import argparse
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Get database URL from environment or .env file."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url

    # Try to load from .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    return line.strip().split("=", 1)[1]

    raise ValueError("DATABASE_URL not found in environment or .env file")


def find_duplicates(session) -> list[dict]:
    """Find all duplicate turns (same session_id and turn_number)."""
    result = session.execute(text("""
        SELECT session_id, turn_number, COUNT(*) as cnt
        FROM turns
        GROUP BY session_id, turn_number
        HAVING COUNT(*) > 1
        ORDER BY session_id, turn_number
    """))
    return [{"session_id": row[0], "turn_number": row[1], "count": row[2]} for row in result]


def get_turns_for_duplicate(session, session_id: int, turn_number: int) -> list[dict]:
    """Get all turn records for a duplicate set."""
    result = session.execute(text("""
        SELECT id, session_id, turn_number, player_input, gm_response,
               location_at_turn, entities_extracted, created_at
        FROM turns
        WHERE session_id = :sid AND turn_number = :tnum
        ORDER BY id
    """), {"sid": session_id, "tnum": turn_number})

    turns = []
    for row in result:
        turns.append({
            "id": row[0],
            "session_id": row[1],
            "turn_number": row[2],
            "player_input": row[3],
            "gm_response": row[4],
            "location_at_turn": row[5],
            "entities_extracted": row[6],
            "created_at": row[7],
        })
    return turns


def score_turn(turn: dict) -> int:
    """Score a turn by how complete its data is. Higher = more complete."""
    score = 0
    if turn["player_input"]:
        score += len(turn["player_input"])
    if turn["gm_response"]:
        score += len(turn["gm_response"]) * 2  # Weight response higher
    if turn["location_at_turn"]:
        score += 10
    if turn["entities_extracted"]:
        score += 20
    return score


def cleanup_duplicates(session, dry_run: bool = True) -> dict:
    """Remove duplicate turns, keeping the most complete one.

    Returns:
        Dict with stats about the cleanup.
    """
    duplicates = find_duplicates(session)

    stats = {
        "duplicate_sets": len(duplicates),
        "turns_deleted": 0,
        "turns_kept": 0,
        "details": [],
    }

    for dup in duplicates:
        turns = get_turns_for_duplicate(session, dup["session_id"], dup["turn_number"])

        # Score each turn and pick the best one
        scored = [(score_turn(t), t) for t in turns]
        scored.sort(key=lambda x: x[0], reverse=True)

        keep = scored[0][1]
        delete = [t[1] for t in scored[1:]]

        detail = {
            "session_id": dup["session_id"],
            "turn_number": dup["turn_number"],
            "kept_id": keep["id"],
            "deleted_ids": [t["id"] for t in delete],
        }
        stats["details"].append(detail)
        stats["turns_kept"] += 1
        stats["turns_deleted"] += len(delete)

        if not dry_run:
            for t in delete:
                session.execute(text("DELETE FROM turns WHERE id = :id"), {"id": t["id"]})

    if not dry_run:
        session.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Cleanup duplicate turn records")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without actually deleting (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the duplicates",
    )
    args = parser.parse_args()

    dry_run = not args.execute

    try:
        db_url = get_database_url()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 60)
        if dry_run:
            print("DRY RUN - No changes will be made")
        else:
            print("EXECUTING - Duplicates will be deleted!")
        print("=" * 60)
        print()

        stats = cleanup_duplicates(session, dry_run=dry_run)

        print(f"Duplicate sets found: {stats['duplicate_sets']}")
        print(f"Turns to keep: {stats['turns_kept']}")
        print(f"Turns to delete: {stats['turns_deleted']}")
        print()

        if stats["details"]:
            print("Details:")
            for detail in stats["details"]:
                print(f"  Session {detail['session_id']}, Turn {detail['turn_number']}:")
                print(f"    Keep ID: {detail['kept_id']}")
                print(f"    Delete IDs: {detail['deleted_ids']}")

        print()
        if dry_run:
            print("Run with --execute to actually delete duplicates")
        else:
            print("Cleanup complete!")

    finally:
        session.close()


if __name__ == "__main__":
    main()
