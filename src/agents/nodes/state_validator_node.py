"""State validator node for the System-Authority architecture.

This node runs after execute_actions to ensure data integrity
and auto-fix common issues before narration.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.validators.state_integrity_validator import StateIntegrityValidator

logger = logging.getLogger(__name__)


async def state_validator_node(state: GameState) -> dict[str, Any]:
    """Validate game state integrity after action execution.

    Runs integrity checks and auto-fixes issues like:
    - NPCs without locations
    - Items without ownership
    - Orphaned relationships

    Args:
        state: Current game state after execute_actions.

    Returns:
        Partial state update with validation_report.
    """
    db: Session = state.get("_db")  # type: ignore
    game_session: GameSession = state.get("_game_session")  # type: ignore

    if db is None or game_session is None:
        return {
            "validation_report": None,
            "errors": ["Missing database session or game session in state"],
        }

    # Skip validation if no actions were executed (optimization for performance)
    turn_result = state.get("turn_result", {})
    executions = turn_result.get("executions", []) if turn_result else []

    # Only run full validation if state changes occurred
    has_state_changes = any(
        ex.get("state_changes", []) for ex in executions
    )

    if not has_state_changes:
        # Fast path: no state changes, skip expensive validation
        return {
            "validation_report": {
                "violations": [],
                "fixes_applied": 0,
                "errors_remaining": 0,
                "summary": "Skipped (no state changes)",
            },
        }

    # Run validation with auto-fix enabled
    validator = StateIntegrityValidator(db, game_session, auto_fix=True)
    report = validator.validate_and_fix()

    # Log results
    if report.has_violations:
        logger.info(f"State integrity: {report.summary()}")
        for violation in report.violations:
            log_level = logging.WARNING if violation.severity == "warning" else logging.ERROR
            fix_msg = f" [FIXED: {violation.fix_action}]" if violation.fixed else ""
            logger.log(
                log_level,
                f"  {violation.category}/{violation.target_type}: {violation.message}{fix_msg}"
            )

    # Convert report to dict for state serialization
    violations_list = []
    for v in report.violations:
        violations_list.append({
            "category": v.category,
            "severity": v.severity,
            "message": v.message,
            "target_type": v.target_type,
            "target_id": v.target_id,
            "fixed": v.fixed,
            "fix_action": v.fix_action,
        })

    return {
        "validation_report": {
            "violations": violations_list,
            "fixes_applied": report.fixes_applied,
            "errors_remaining": report.errors_remaining,
            "summary": report.summary(),
        },
    }
