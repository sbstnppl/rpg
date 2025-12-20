"""Manager for tracking needs communication to prevent repetitive narration."""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds, NeedsCommunicationLog
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Hours (in-game time) before reminding about an ongoing negative state
REMINDER_INTERVAL_HOURS = 2

# Need state definitions: (threshold, label, is_negative)
# Most needs: 0 = bad, 100 = good (threshold = "below this")
# Exception: sleep_pressure: 0 = good, 100 = bad (threshold = "above this")
NEED_STATE_THRESHOLDS: dict[str, list[tuple[int, str, bool]]] = {
    "stamina": [
        (20, "physically exhausted", True),
        (40, "winded", True),
        (80, "fresh", False),
    ],
    # Note: sleep_pressure thresholds are inverted (higher = worse)
    # The get_need_state method handles this inversion
    "sleep_pressure": [
        (80, "desperately sleepy", True),  # Above 80 = desperately sleepy
        (60, "tired", True),  # Above 60 = tired
        (20, "well-rested", False),  # Below 20 = well-rested
    ],
    "hunger": [
        (15, "starving", True),
        (30, "hungry", True),
        (85, "well-fed", False),
    ],
    "thirst": [
        (20, "dehydrated", True),
        (40, "thirsty", True),
        (80, "well-hydrated", False),
    ],
    "hygiene": [
        (20, "filthy", True),
        (40, "disheveled", True),
        (80, "clean", False),
    ],
    "wellness": [
        (40, "in pain", True),
        (60, "uncomfortable", True),
        (90, "healthy", False),
    ],
    "comfort": [
        (30, "uncomfortable", True),
        (80, "comfortable", False),
    ],
    "morale": [
        (20, "depressed", True),
        (40, "low spirits", True),
        (80, "in good spirits", False),
    ],
    "social_connection": [
        (20, "lonely", True),
        (80, "socially fulfilled", False),
    ],
    "intimacy": [
        (20, "restless", True),
        (80, "content", False),
    ],
    "sense_of_purpose": [
        (20, "aimless", True),
        (80, "driven", False),
    ],
}


@dataclass
class NeedAlert:
    """A need state change that should be narrated."""

    need_name: str
    current_state: str
    current_value: int
    previous_state: str | None
    alert_type: Literal["state_change", "reminder", "status"]
    hours_since_mentioned: float | None = None
    is_improvement: bool = False


class NeedsCommunicationManager(BaseManager):
    """Manages tracking of when needs were communicated to prevent repetition.

    This enables signal-based needs narration:
    - Alert GM when need state CHANGES (crossed threshold)
    - Remind GM of ongoing issues after X hours without mention
    - Prevent repetitive "your stomach growls" every turn
    """

    def get_state_label(self, need_name: str, value: int) -> tuple[str, bool]:
        """Get the state label and negativity for a need value.

        Args:
            need_name: Name of the need (hunger, stamina, sleep_pressure, etc.)
            value: Current need value (0-100)

        Returns:
            Tuple of (state_label, is_negative)
            e.g., ("hungry", True) or ("well-fed", False)
        """
        thresholds = NEED_STATE_THRESHOLDS.get(need_name, [])

        # sleep_pressure is inverted: higher value = worse state
        is_inverted = need_name == "sleep_pressure"

        # Check thresholds in order
        for threshold, label, is_negative in thresholds:
            if is_inverted:
                # For sleep_pressure: high value is bad, low is good
                if is_negative and value > threshold:
                    return label, True
                elif not is_negative and value < threshold:
                    return label, False
            else:
                # Normal needs: low value is bad, high is good
                if is_negative and value < threshold:
                    return label, True
                elif not is_negative and value > threshold:
                    return label, False

        # Default neutral state
        return "normal", False

    def get_communication_log(self, entity_id: int) -> dict[str, NeedsCommunicationLog]:
        """Get all communication log entries for an entity.

        Args:
            entity_id: Entity to get logs for

        Returns:
            Dict mapping need_name to NeedsCommunicationLog
        """
        logs = (
            self.db.query(NeedsCommunicationLog)
            .filter(
                NeedsCommunicationLog.session_id == self.session_id,
                NeedsCommunicationLog.entity_id == entity_id,
            )
            .all()
        )
        return {log.need_name: log for log in logs}

    def record_communication(
        self,
        entity_id: int,
        need_name: str,
        value: int,
        state_label: str,
        game_time: datetime,
        turn: int,
    ) -> NeedsCommunicationLog:
        """Record that a need was communicated to the player.

        Args:
            entity_id: Entity whose need was communicated
            need_name: Name of the need (hunger, stamina, sleep_pressure, etc.)
            value: Current need value at time of communication
            state_label: State label (hungry, tired, etc.)
            game_time: In-game datetime when communicated
            turn: Turn number when communicated

        Returns:
            The created or updated NeedsCommunicationLog
        """
        # Check if entry exists (upsert pattern)
        existing = (
            self.db.query(NeedsCommunicationLog)
            .filter(
                NeedsCommunicationLog.session_id == self.session_id,
                NeedsCommunicationLog.entity_id == entity_id,
                NeedsCommunicationLog.need_name == need_name,
            )
            .first()
        )

        if existing:
            existing.communicated_turn = turn
            existing.communicated_game_time = game_time
            existing.communicated_value = value
            existing.communicated_state = state_label
            self.db.flush()
            return existing

        log = NeedsCommunicationLog(
            session_id=self.session_id,
            entity_id=entity_id,
            need_name=need_name,
            communicated_turn=turn,
            communicated_game_time=game_time,
            communicated_value=value,
            communicated_state=state_label,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def get_needs_alerts(
        self,
        entity_id: int,
        needs: CharacterNeeds,
        current_game_time: datetime,
        current_turn: int,
        reminder_hours: float = REMINDER_INTERVAL_HOURS,
    ) -> list[NeedAlert]:
        """Generate needs alerts based on state changes and time elapsed.

        Args:
            entity_id: Entity to check
            needs: Current CharacterNeeds object
            current_game_time: Current in-game datetime
            current_turn: Current turn number
            reminder_hours: Hours before reminder for ongoing issues

        Returns:
            List of NeedAlert objects sorted by priority (alerts first, then reminders)
        """
        comm_log = self.get_communication_log(entity_id)
        alerts: list[NeedAlert] = []

        # Check all trackable needs
        need_values = {
            "stamina": needs.stamina,
            "sleep_pressure": needs.sleep_pressure,
            "hunger": needs.hunger,
            "thirst": needs.thirst,
            "hygiene": needs.hygiene,
            "wellness": needs.wellness,
            "comfort": needs.comfort,
            "morale": needs.morale,
            "social_connection": needs.social_connection,
            "intimacy": needs.intimacy,
            "sense_of_purpose": needs.sense_of_purpose,
        }

        for need_name, value in need_values.items():
            current_state, is_negative = self.get_state_label(need_name, value)
            last_comm = comm_log.get(need_name)

            if last_comm:
                # Case 1: State changed (crossed threshold) - ALERT
                if current_state != last_comm.communicated_state:
                    is_improvement = value > last_comm.communicated_value
                    alerts.append(
                        NeedAlert(
                            need_name=need_name,
                            current_state=current_state,
                            current_value=value,
                            previous_state=last_comm.communicated_state,
                            alert_type="state_change",
                            is_improvement=is_improvement,
                        )
                    )
                # Case 2: Bad state, not mentioned in X hours - REMINDER
                elif is_negative:
                    hours_since = (
                        current_game_time - last_comm.communicated_game_time
                    ).total_seconds() / 3600
                    if hours_since >= reminder_hours:
                        alerts.append(
                            NeedAlert(
                                need_name=need_name,
                                current_state=current_state,
                                current_value=value,
                                previous_state=last_comm.communicated_state,
                                alert_type="reminder",
                                hours_since_mentioned=hours_since,
                            )
                        )
                # Case 3: Everything else - just status (only include negative or notable)
                elif is_negative or current_state != "normal":
                    alerts.append(
                        NeedAlert(
                            need_name=need_name,
                            current_state=current_state,
                            current_value=value,
                            previous_state=last_comm.communicated_state,
                            alert_type="status",
                        )
                    )
            else:
                # Never communicated before
                if is_negative:
                    # Negative state never mentioned - treat as alert
                    alerts.append(
                        NeedAlert(
                            need_name=need_name,
                            current_state=current_state,
                            current_value=value,
                            previous_state=None,
                            alert_type="state_change",
                        )
                    )
                elif current_state != "normal":
                    # Positive state - just status
                    alerts.append(
                        NeedAlert(
                            need_name=need_name,
                            current_state=current_state,
                            current_value=value,
                            previous_state=None,
                            alert_type="status",
                        )
                    )

        # Sort: alerts first, then reminders, then status
        priority = {"state_change": 0, "reminder": 1, "status": 2}
        alerts.sort(key=lambda a: (priority[a.alert_type], a.need_name))

        return alerts

    def format_alerts_for_gm(
        self,
        alerts: list[NeedAlert],
        entity_name: str = "Player",
    ) -> str:
        """Format needs alerts for GM context.

        Args:
            alerts: List of NeedAlert objects
            entity_name: Name of the entity (for display)

        Returns:
            Formatted string for GM context
        """
        state_changes = [a for a in alerts if a.alert_type == "state_change"]
        reminders = [a for a in alerts if a.alert_type == "reminder"]
        status = [a for a in alerts if a.alert_type == "status"]

        lines = []

        if state_changes:
            lines.append("## Needs Alerts (narrate these!)")
            for alert in state_changes:
                if alert.is_improvement:
                    lines.append(
                        f"- {alert.need_name} improved to '{alert.current_state}' ({alert.current_value})"
                    )
                else:
                    lines.append(
                        f"- {alert.need_name} dropped to '{alert.current_state}' ({alert.current_value})"
                    )

        if reminders:
            lines.append("## Needs Reminders (consider mentioning)")
            for alert in reminders:
                hours = int(alert.hours_since_mentioned or 0)
                lines.append(
                    f"- {alert.need_name}: still {alert.current_state} ({alert.current_value}), "
                    f"{hours}h since mentioned"
                )

        if status:
            lines.append("## Needs Status (reference only)")
            for alert in status:
                lines.append(f"- {alert.need_name}: {alert.current_state} ({alert.current_value})")

        return "\n".join(lines) if lines else ""
