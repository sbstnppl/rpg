"""EconomyManager for market prices, trade routes, and economic events."""

from dataclasses import dataclass, field

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.database.models.economy import (
    DemandLevel,
    EconomicEvent,
    MarketPrice,
    RouteStatus,
    SupplyLevel,
    TradeRoute,
)
from src.database.models.session import GameSession
from src.managers.base import BaseManager


# Price modifiers by supply level
SUPPLY_MODIFIERS = {
    SupplyLevel.SCARCE.value: 2.0,
    SupplyLevel.LOW.value: 1.3,
    SupplyLevel.NORMAL.value: 1.0,
    SupplyLevel.ABUNDANT.value: 0.8,
    SupplyLevel.OVERSUPPLY.value: 0.5,
}

# Price modifiers by demand level
DEMAND_MODIFIERS = {
    DemandLevel.NONE.value: 0.5,
    DemandLevel.LOW.value: 0.8,
    DemandLevel.NORMAL.value: 1.0,
    DemandLevel.HIGH.value: 1.3,
    DemandLevel.DESPERATE.value: 2.0,
}


@dataclass
class PriceInfo:
    """Information about a calculated price.

    Attributes:
        item_category: The item category being priced.
        base_price: The base price before modifiers.
        current_price: The final calculated price.
        supply_level: Current supply level.
        demand_level: Current demand level.
        modifiers: List of price modifier descriptions.
    """

    item_category: str
    base_price: int
    current_price: int
    supply_level: str
    demand_level: str
    modifiers: list[str] = field(default_factory=list)


@dataclass
class MarketSummary:
    """Summary of market conditions at a location.

    Attributes:
        location_key: The market location.
        categories: Item categories available at this market.
        connected_routes: Trade routes connected to this location.
        active_events: Economic events affecting this location.
        route_statuses: Status of each connected route.
    """

    location_key: str
    categories: list[str]
    connected_routes: list[str]
    active_events: list[str]
    route_statuses: dict[str, str] = field(default_factory=dict)


class EconomyManager(BaseManager):
    """Manager for economic systems.

    Handles:
    - Market price setup and calculation
    - Trade route management
    - Economic event tracking
    - Price modifiers from supply/demand and events
    """

    # --- Market Price Management ---

    def set_market_price(
        self,
        location_key: str,
        item_category: str,
        base_price_modifier: float = 1.0,
        supply_level: SupplyLevel = SupplyLevel.NORMAL,
        demand_level: DemandLevel = DemandLevel.NORMAL,
    ) -> MarketPrice:
        """Set or update market price data for a location/category.

        Args:
            location_key: The market location key.
            item_category: The item category.
            base_price_modifier: Location-specific price modifier.
            supply_level: Current supply level.
            demand_level: Current demand level.

        Returns:
            The created or updated MarketPrice record.
        """
        existing = self.get_market_price(location_key, item_category)

        if existing:
            existing.base_price_modifier = base_price_modifier
            existing.supply_level = supply_level.value
            existing.demand_level = demand_level.value
            existing.last_updated_turn = self.current_turn
            self.db.flush()
            return existing

        market = MarketPrice(
            session_id=self.session_id,
            location_key=location_key,
            item_category=item_category,
            base_price_modifier=base_price_modifier,
            supply_level=supply_level.value,
            demand_level=demand_level.value,
            last_updated_turn=self.current_turn,
        )
        self.db.add(market)
        self.db.flush()
        return market

    def get_market_price(
        self, location_key: str, item_category: str
    ) -> MarketPrice | None:
        """Get market price data for a location/category.

        Args:
            location_key: The market location key.
            item_category: The item category.

        Returns:
            MarketPrice if found, None otherwise.
        """
        return (
            self.db.query(MarketPrice)
            .filter(
                and_(
                    MarketPrice.session_id == self.session_id,
                    MarketPrice.location_key == location_key,
                    MarketPrice.item_category == item_category,
                )
            )
            .first()
        )

    def get_market_prices_for_location(self, location_key: str) -> list[MarketPrice]:
        """Get all market prices at a location.

        Args:
            location_key: The market location key.

        Returns:
            List of MarketPrice records.
        """
        return (
            self.db.query(MarketPrice)
            .filter(
                and_(
                    MarketPrice.session_id == self.session_id,
                    MarketPrice.location_key == location_key,
                )
            )
            .all()
        )

    def calculate_price(
        self, location_key: str, item_category: str, base_price: int
    ) -> PriceInfo:
        """Calculate the current price for an item category at a location.

        Applies supply/demand modifiers and active economic events.

        Args:
            location_key: The market location key.
            item_category: The item category.
            base_price: The base price of the item.

        Returns:
            PriceInfo with calculated price and modifier breakdown.
        """
        modifiers = []
        multiplier = 1.0

        market = self.get_market_price(location_key, item_category)

        if not market:
            return PriceInfo(
                item_category=item_category,
                base_price=base_price,
                current_price=base_price,
                supply_level=SupplyLevel.NORMAL.value,
                demand_level=DemandLevel.NORMAL.value,
                modifiers=["No market data - using base price"],
            )

        # Apply base price modifier
        if market.base_price_modifier != 1.0:
            multiplier *= market.base_price_modifier
            modifiers.append(f"Location: x{market.base_price_modifier}")

        # Apply supply modifier
        supply_mod = SUPPLY_MODIFIERS.get(market.supply_level, 1.0)
        if supply_mod != 1.0:
            multiplier *= supply_mod
            modifiers.append(f"Supply ({market.supply_level}): x{supply_mod}")

        # Apply demand modifier
        demand_mod = DEMAND_MODIFIERS.get(market.demand_level, 1.0)
        if demand_mod != 1.0:
            multiplier *= demand_mod
            modifiers.append(f"Demand ({market.demand_level}): x{demand_mod}")

        # Apply event modifiers
        events = self.get_events_for_location(location_key)
        for event in events:
            # Check if event affects this category
            if event.affected_categories and item_category not in event.affected_categories:
                continue
            if event.price_modifier != 1.0:
                multiplier *= event.price_modifier
                modifiers.append(f"Event ({event.event_type}): x{event.price_modifier}")

        final_price = round(base_price * multiplier)

        return PriceInfo(
            item_category=item_category,
            base_price=base_price,
            current_price=final_price,
            supply_level=market.supply_level,
            demand_level=market.demand_level,
            modifiers=modifiers if modifiers else ["Standard price"],
        )

    # --- Trade Route Management ---

    def create_trade_route(
        self,
        route_key: str,
        display_name: str,
        origin_key: str,
        destination_key: str,
        goods_traded: list[str],
        travel_days: int = 1,
        danger_level: int = 0,
    ) -> TradeRoute:
        """Create a new trade route.

        Args:
            route_key: Unique route identifier.
            display_name: Human-readable route name.
            origin_key: Starting location key.
            destination_key: Ending location key.
            goods_traded: Item categories traded on this route.
            travel_days: Travel time in days.
            danger_level: Danger level 0-100.

        Returns:
            The created TradeRoute.
        """
        route = TradeRoute(
            session_id=self.session_id,
            route_key=route_key,
            display_name=display_name,
            origin_key=origin_key,
            destination_key=destination_key,
            goods_traded=goods_traded,
            travel_days=travel_days,
            danger_level=danger_level,
            status=RouteStatus.ACTIVE.value,
        )
        self.db.add(route)
        self.db.flush()
        return route

    def get_trade_route(self, route_key: str) -> TradeRoute | None:
        """Get a trade route by key.

        Args:
            route_key: The route's unique key.

        Returns:
            TradeRoute if found, None otherwise.
        """
        return (
            self.db.query(TradeRoute)
            .filter(
                and_(
                    TradeRoute.session_id == self.session_id,
                    TradeRoute.route_key == route_key,
                )
            )
            .first()
        )

    def get_routes_for_location(self, location_key: str) -> list[TradeRoute]:
        """Get all trade routes connected to a location.

        Args:
            location_key: The location key.

        Returns:
            List of TradeRoutes (as origin or destination).
        """
        return (
            self.db.query(TradeRoute)
            .filter(
                and_(
                    TradeRoute.session_id == self.session_id,
                    (
                        (TradeRoute.origin_key == location_key)
                        | (TradeRoute.destination_key == location_key)
                    ),
                )
            )
            .all()
        )

    def disrupt_trade_route(self, route_key: str, reason: str) -> None:
        """Disrupt a trade route (partial disruption).

        Args:
            route_key: The route to disrupt.
            reason: Reason for disruption.
        """
        route = self.get_trade_route(route_key)
        if route:
            route.status = RouteStatus.DISRUPTED.value
            route.disruption_reason = reason
            self.db.flush()

    def block_trade_route(self, route_key: str, reason: str) -> None:
        """Block a trade route (complete blockage).

        Args:
            route_key: The route to block.
            reason: Reason for blockage.
        """
        route = self.get_trade_route(route_key)
        if route:
            route.status = RouteStatus.BLOCKED.value
            route.disruption_reason = reason
            self.db.flush()

    def restore_trade_route(self, route_key: str) -> None:
        """Restore a disrupted or blocked trade route.

        Args:
            route_key: The route to restore.
        """
        route = self.get_trade_route(route_key)
        if route:
            route.status = RouteStatus.ACTIVE.value
            route.disruption_reason = None
            self.db.flush()

    # --- Economic Event Management ---

    def create_economic_event(
        self,
        event_key: str,
        event_type: str,
        description: str,
        affected_locations: list[str],
        affected_categories: list[str],
        price_modifier: float,
        supply_effect: str | None = None,
        duration_turns: int | None = None,
    ) -> EconomicEvent:
        """Create a new economic event.

        Args:
            event_key: Unique event identifier.
            event_type: Event type (famine, war, festival, etc.).
            description: Human-readable description.
            affected_locations: Location keys affected.
            affected_categories: Item categories affected.
            price_modifier: Price multiplier.
            supply_effect: Supply change ('increase', 'decrease', or None).
            duration_turns: Duration in turns (None = permanent).

        Returns:
            The created EconomicEvent.
        """
        event = EconomicEvent(
            session_id=self.session_id,
            event_key=event_key,
            event_type=event_type,
            description=description,
            affected_locations=affected_locations,
            affected_categories=affected_categories,
            price_modifier=price_modifier,
            supply_effect=supply_effect,
            start_turn=self.current_turn,
            duration_turns=duration_turns,
            is_active=True,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_event(self, event_key: str) -> EconomicEvent | None:
        """Get an economic event by key.

        Args:
            event_key: The event's unique key.

        Returns:
            EconomicEvent if found, None otherwise.
        """
        return (
            self.db.query(EconomicEvent)
            .filter(
                and_(
                    EconomicEvent.session_id == self.session_id,
                    EconomicEvent.event_key == event_key,
                )
            )
            .first()
        )

    def get_active_events(self) -> list[EconomicEvent]:
        """Get all active economic events.

        Returns:
            List of active EconomicEvents.
        """
        return (
            self.db.query(EconomicEvent)
            .filter(
                and_(
                    EconomicEvent.session_id == self.session_id,
                    EconomicEvent.is_active == True,  # noqa: E712
                )
            )
            .all()
        )

    def get_events_for_location(self, location_key: str) -> list[EconomicEvent]:
        """Get active events affecting a specific location.

        Args:
            location_key: The location key.

        Returns:
            List of active EconomicEvents affecting this location.
        """
        events = self.get_active_events()
        return [e for e in events if location_key in e.affected_locations]

    def end_event(self, event_key: str) -> None:
        """End an active economic event.

        Args:
            event_key: The event to end.
        """
        event = self.get_event(event_key)
        if event:
            event.is_active = False
            self.db.flush()

    # --- Market Summary ---

    def get_market_summary(self, location_key: str) -> MarketSummary:
        """Get a summary of market conditions at a location.

        Args:
            location_key: The market location key.

        Returns:
            MarketSummary with all relevant market data.
        """
        markets = self.get_market_prices_for_location(location_key)
        routes = self.get_routes_for_location(location_key)
        events = self.get_events_for_location(location_key)

        return MarketSummary(
            location_key=location_key,
            categories=[m.item_category for m in markets],
            connected_routes=[r.route_key for r in routes],
            active_events=[e.event_key for e in events],
            route_statuses={r.route_key: r.status for r in routes},
        )

    # --- Context Generation ---

    def get_economy_context(self, location_key: str) -> str:
        """Generate economy context for GM prompts.

        Args:
            location_key: The market location key.

        Returns:
            Formatted string describing market conditions.
        """
        markets = self.get_market_prices_for_location(location_key)
        events = self.get_events_for_location(location_key)
        routes = self.get_routes_for_location(location_key)

        if not markets and not events:
            return ""

        lines = [f"## Market Conditions at {location_key}", ""]

        # Supply/Demand overview
        if markets:
            lines.append("**Available Goods:**")
            for market in markets:
                supply_desc = self._describe_supply(market.supply_level)
                demand_desc = self._describe_demand(market.demand_level)
                lines.append(f"- {market.item_category}: {supply_desc}, {demand_desc}")
            lines.append("")

        # Active events
        if events:
            lines.append("**Current Economic Conditions:**")
            for event in events:
                effect = "prices higher" if event.price_modifier > 1 else "prices lower"
                lines.append(f"- {event.event_type.title()}: {event.description} ({effect})")
            lines.append("")

        # Trade routes
        disrupted = [r for r in routes if r.status != RouteStatus.ACTIVE.value]
        if disrupted:
            lines.append("**Trade Route Issues:**")
            for route in disrupted:
                lines.append(f"- {route.display_name}: {route.status} - {route.disruption_reason}")

        return "\n".join(lines)

    def _describe_supply(self, supply_level: str) -> str:
        """Get human-readable supply description."""
        descriptions = {
            SupplyLevel.SCARCE.value: "very scarce supply",
            SupplyLevel.LOW.value: "low supply",
            SupplyLevel.NORMAL.value: "normal supply",
            SupplyLevel.ABUNDANT.value: "plentiful supply",
            SupplyLevel.OVERSUPPLY.value: "oversupply (surplus)",
        }
        return descriptions.get(supply_level, "unknown supply")

    def _describe_demand(self, demand_level: str) -> str:
        """Get human-readable demand description."""
        descriptions = {
            DemandLevel.NONE.value: "no demand",
            DemandLevel.LOW.value: "low demand",
            DemandLevel.NORMAL.value: "normal demand",
            DemandLevel.HIGH.value: "high demand",
            DemandLevel.DESPERATE.value: "desperate demand",
        }
        return descriptions.get(demand_level, "unknown demand")
