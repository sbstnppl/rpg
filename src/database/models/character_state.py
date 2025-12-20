"""Character state models (needs)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession


class CharacterNeeds(Base, TimestampMixin):
    """Tracks character physiological and psychological needs."""

    __tablename__ = "character_needs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # === TIER 1: Survival (always tracked) ===
    hunger: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="0=starving, 50=satisfied, 100=stuffed. Optimal: 30-70",
    )
    thirst: Mapped[int] = mapped_column(
        default=80,
        nullable=False,
        comment="0=dehydrated, 50=satisfied, 100=well-hydrated. Optimal: 40-80",
    )
    stamina: Mapped[int] = mapped_column(
        default=80,
        nullable=False,
        comment="0=collapsed, 50=fatigued, 100=fresh. Physical capacity.",
    )
    sleep_pressure: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="0=well-rested, 50=tired, 100=desperately sleepy. Homeostatic sleep debt.",
    )

    # === TIER 2: Comfort (normal mode) ===
    hygiene: Mapped[int] = mapped_column(
        default=80,
        nullable=False,
        comment="0=filthy, 100=spotless",
    )
    comfort: Mapped[int] = mapped_column(
        default=70,
        nullable=False,
        comment="0=miserable conditions, 100=luxurious (environmental)",
    )
    wellness: Mapped[int] = mapped_column(
        default=100,
        nullable=False,
        comment="0=agony (from injuries), 100=pain-free",
    )

    # === TIER 3: Psychological (realism mode) ===
    social_connection: Mapped[int] = mapped_column(
        default=60,
        nullable=False,
        comment="0=isolated/lonely, 100=socially fulfilled",
    )
    morale: Mapped[int] = mapped_column(
        default=70,
        nullable=False,
        comment="0=depressed, 50=neutral, 100=elated",
    )
    sense_of_purpose: Mapped[int] = mapped_column(
        default=50,
        nullable=False,
        comment="0=aimless, 100=driven by clear goals",
    )
    intimacy: Mapped[int] = mapped_column(
        default=70,
        nullable=False,
        comment="0=desperate, 100=content. Intimacy fulfillment level.",
    )

    # === CRAVING MODIFIERS (temporary psychological urgency) ===
    # Cravings intensify when encountering relevant stimuli (seeing food, etc.)
    # Formula: effective_need = max(0, need_value - craving_value)
    hunger_craving: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Temporary hunger urgency boost from stimuli (0-100)",
    )
    thirst_craving: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Temporary thirst urgency boost from stimuli (0-100)",
    )
    # Note: No stamina_craving or sleep_pressure_craving - these are physical states
    # that don't have psychological "craving" modifiers like hunger/thirst do
    social_craving: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Temporary social urgency boost from stimuli (0-100)",
    )
    intimacy_craving: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Temporary intimacy urgency boost from stimuli (0-100)",
    )

    # Timestamps for decay calculation and deduplication
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    last_meal_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_drink_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_sleep_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_bath_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_social_turn: Mapped[int | None] = mapped_column(nullable=True)
    last_intimate_turn: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        return (
            f"<CharacterNeeds entity={self.entity_id} "
            f"H:{self.hunger} T:{self.thirst} S:{self.stamina} SP:{self.sleep_pressure} M:{self.morale}>"
        )

    def get_effective_need(self, need_name: str) -> int:
        """Get effective need value accounting for craving modifier.

        The effective need is the perceived urgency, which may be higher
        than the actual physiological state due to cravings triggered by stimuli.

        Note: stamina and sleep_pressure don't have craving modifiers since
        they represent physical states rather than psychological urges.

        Args:
            need_name: Name of the need (hunger, thirst, stamina, sleep_pressure,
                       social_connection, intimacy)

        Returns:
            Effective need value (0-100), where lower = more urgent
        """
        need_value = getattr(self, need_name, 0)

        # Map need names to their craving fields
        # Note: stamina and sleep_pressure don't have cravings
        craving_map = {
            "hunger": "hunger_craving",
            "thirst": "thirst_craving",
            "social_connection": "social_craving",
            "intimacy": "intimacy_craving",
        }

        craving_field = craving_map.get(need_name)
        if craving_field:
            craving_value = getattr(self, craving_field, 0)
            return max(0, need_value - craving_value)

        return need_value


class NeedsCommunicationLog(Base, TimestampMixin):
    """Tracks when character needs were last communicated to the player.

    This enables signal-based needs narration:
    - Alert GM when need state CHANGES (crossed threshold)
    - Remind GM of ongoing issues after X hours without mention
    - Prevent repetitive "your stomach growls" every turn
    """

    __tablename__ = "needs_communication_log"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "entity_id", "need_name",
            name="uq_needs_comm_session_entity_need"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    need_name: Mapped[str] = mapped_column(
        nullable=False,
        comment="Need being tracked (hunger, stamina, sleep_pressure, hygiene, etc.)",
    )

    # When was this need last communicated to the player?
    communicated_turn: Mapped[int] = mapped_column(
        nullable=False,
        comment="Turn number when this need was last narrated",
    )
    communicated_game_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="In-game datetime when this need was last narrated",
    )

    # What was the state when communicated?
    communicated_value: Mapped[int] = mapped_column(
        nullable=False,
        comment="Need value (0-100) at time of communication",
    )
    communicated_state: Mapped[str] = mapped_column(
        nullable=False,
        comment="State label (hungry, starving, well-fed, etc.) when communicated",
    )

    # Relationships
    entity: Mapped["Entity"] = relationship(foreign_keys=[entity_id])

    def __repr__(self) -> str:
        return (
            f"<NeedsCommunicationLog entity={self.entity_id} "
            f"need={self.need_name} state={self.communicated_state} turn={self.communicated_turn}>"
        )
