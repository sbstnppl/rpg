"""Economy models for market prices, trade routes, and economic events."""

from enum import Enum

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin


class SupplyLevel(str, Enum):
    """Supply level affecting prices."""

    SCARCE = "scarce"  # 2.0x price
    LOW = "low"  # 1.3x price
    NORMAL = "normal"  # 1.0x price
    ABUNDANT = "abundant"  # 0.8x price
    OVERSUPPLY = "oversupply"  # 0.5x price


class DemandLevel(str, Enum):
    """Demand level affecting prices."""

    NONE = "none"  # 0.5x price
    LOW = "low"  # 0.8x price
    NORMAL = "normal"  # 1.0x price
    HIGH = "high"  # 1.3x price
    DESPERATE = "desperate"  # 2.0x price


class RouteStatus(str, Enum):
    """Trade route operational status."""

    ACTIVE = "active"
    DISRUPTED = "disrupted"  # Partial disruption, higher costs
    BLOCKED = "blocked"  # Temporarily impassable
    DESTROYED = "destroyed"  # Permanently damaged


class MarketPrice(Base, TimestampMixin):
    """Tracks item category prices at specific market locations.

    Prices are calculated using supply/demand modifiers rather than
    storing absolute values. This allows dynamic price calculation
    based on current market conditions.
    """

    __tablename__ = "market_prices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Market identity
    location_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Location key where this market exists",
    )
    item_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Item category: weapons, armor, food, luxury, tools, materials, etc.",
    )

    # Price modifiers
    base_price_modifier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Location-specific base price modifier (e.g., 1.2 for expensive city)",
    )
    supply_level: Mapped[str] = mapped_column(
        String(20),
        default=SupplyLevel.NORMAL.value,
        nullable=False,
        comment="Current supply level",
    )
    demand_level: Mapped[str] = mapped_column(
        String(20),
        default=DemandLevel.NORMAL.value,
        nullable=False,
        comment="Current demand level",
    )

    # Tracking
    last_updated_turn: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Turn when prices were last recalculated",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint(
            "session_id", "location_key", "item_category",
            name="uq_market_location_category"
        ),
    )

    def __repr__(self) -> str:
        return f"<MarketPrice {self.location_key}:{self.item_category}>"


class TradeRoute(Base, TimestampMixin):
    """Connections between market locations for goods transport.

    Trade routes affect availability and prices. Disrupted routes
    increase costs while blocked routes may cause shortages.
    """

    __tablename__ = "trade_routes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Route identity
    route_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique route identifier",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable route name",
    )

    # Endpoints
    origin_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Starting location key",
    )
    destination_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Ending location key",
    )

    # Goods traded
    goods_traded: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Item categories traded on this route",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=RouteStatus.ACTIVE.value,
        nullable=False,
    )
    disruption_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why route is disrupted/blocked",
    )

    # Route properties
    travel_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Normal travel time in days",
    )
    danger_level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Danger level 0-100 (affects merchant willingness)",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "route_key", name="uq_trade_route_key"),
    )

    def __repr__(self) -> str:
        return f"<TradeRoute {self.route_key}: {self.origin_key} -> {self.destination_key}>"


class EconomicEvent(Base, TimestampMixin):
    """Events that affect market prices and trade.

    Economic events modify prices across affected locations and
    categories. Events can be temporary (duration_turns) or
    permanent (duration_turns=None).
    """

    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event identity
    event_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique event identifier",
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Event type: famine, war, festival, plague, discovery, etc.",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable event description",
    )

    # Scope
    affected_locations: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Location keys affected by this event",
    )
    affected_categories: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="Item categories affected (empty = all categories)",
    )

    # Effects
    price_modifier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Price multiplier (0.5 = half, 2.0 = double)",
    )
    supply_effect: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Supply change: 'increase', 'decrease', or null",
    )

    # Timing
    start_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Turn when event started",
    )
    duration_turns: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration in turns (null = permanent)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "event_key", name="uq_economic_event_key"),
    )

    def __repr__(self) -> str:
        status = "active" if self.is_active else "ended"
        return f"<EconomicEvent {self.event_key} ({self.event_type}) [{status}]>"
