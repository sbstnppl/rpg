"""Tests for EconomyManager."""

import pytest

from src.database.models.economy import (
    DemandLevel,
    EconomicEvent,
    MarketPrice,
    RouteStatus,
    SupplyLevel,
    TradeRoute,
)
from src.managers.economy_manager import (
    EconomyManager,
    MarketSummary,
    PriceInfo,
)


class TestMarketPriceCreation:
    """Tests for market price setup."""

    def test_set_market_price_basic(self, db_session, game_session):
        """Test setting a basic market price."""
        manager = EconomyManager(db_session, game_session)

        market = manager.set_market_price(
            location_key="market_square",
            item_category="weapons",
        )

        assert market.location_key == "market_square"
        assert market.item_category == "weapons"
        assert market.supply_level == SupplyLevel.NORMAL.value
        assert market.demand_level == DemandLevel.NORMAL.value
        assert market.base_price_modifier == 1.0

    def test_set_market_price_with_modifiers(self, db_session, game_session):
        """Test setting market price with custom modifiers."""
        manager = EconomyManager(db_session, game_session)

        market = manager.set_market_price(
            location_key="luxury_district",
            item_category="jewelry",
            base_price_modifier=1.5,
            supply_level=SupplyLevel.SCARCE,
            demand_level=DemandLevel.HIGH,
        )

        assert market.base_price_modifier == 1.5
        assert market.supply_level == SupplyLevel.SCARCE.value
        assert market.demand_level == DemandLevel.HIGH.value

    def test_get_market_price(self, db_session, game_session):
        """Test retrieving a market price."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("town_market", "food")

        market = manager.get_market_price("town_market", "food")
        assert market is not None
        assert market.item_category == "food"

    def test_get_market_price_not_found(self, db_session, game_session):
        """Test retrieving non-existent market price."""
        manager = EconomyManager(db_session, game_session)
        market = manager.get_market_price("nonexistent", "nothing")
        assert market is None


class TestPriceCalculation:
    """Tests for price calculation with modifiers."""

    def test_calculate_price_normal(self, db_session, game_session):
        """Test price calculation with normal supply/demand."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("market", "weapons")

        price_info = manager.calculate_price("market", "weapons", base_price=100)

        assert price_info.base_price == 100
        assert price_info.current_price == 100  # 1.0 * 1.0 * 1.0 = 1.0

    def test_calculate_price_scarce_supply(self, db_session, game_session):
        """Test price increase with scarce supply."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price(
            "market", "weapons",
            supply_level=SupplyLevel.SCARCE
        )

        price_info = manager.calculate_price("market", "weapons", base_price=100)
        assert price_info.current_price == 200  # 2.0x for scarce

    def test_calculate_price_high_demand(self, db_session, game_session):
        """Test price increase with high demand."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price(
            "market", "food",
            demand_level=DemandLevel.HIGH
        )

        price_info = manager.calculate_price("market", "food", base_price=100)
        assert price_info.current_price == 130  # 1.3x for high demand

    def test_calculate_price_combined_modifiers(self, db_session, game_session):
        """Test price with multiple modifiers."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price(
            "market", "weapons",
            base_price_modifier=1.2,  # Expensive location
            supply_level=SupplyLevel.LOW,  # 1.3x
            demand_level=DemandLevel.HIGH,  # 1.3x
        )

        price_info = manager.calculate_price("market", "weapons", base_price=100)
        # 100 * 1.2 * 1.3 * 1.3 = 202.8 -> 203
        assert price_info.current_price == 203

    def test_calculate_price_oversupply_low_demand(self, db_session, game_session):
        """Test price decrease with oversupply and low demand."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price(
            "market", "grain",
            supply_level=SupplyLevel.OVERSUPPLY,  # 0.5x
            demand_level=DemandLevel.LOW,  # 0.8x
        )

        price_info = manager.calculate_price("market", "grain", base_price=100)
        assert price_info.current_price == 40  # 0.5 * 0.8 = 0.4

    def test_calculate_price_no_market(self, db_session, game_session):
        """Test price calculation with no market data returns base price."""
        manager = EconomyManager(db_session, game_session)

        price_info = manager.calculate_price("unknown", "weapons", base_price=100)
        assert price_info.current_price == 100
        assert "no market data" in price_info.modifiers[0].lower()


class TestTradeRoutes:
    """Tests for trade route management."""

    def test_create_trade_route(self, db_session, game_session):
        """Test creating a trade route."""
        manager = EconomyManager(db_session, game_session)

        route = manager.create_trade_route(
            route_key="north_road",
            display_name="Northern Trade Road",
            origin_key="capital",
            destination_key="northern_town",
            goods_traded=["weapons", "armor", "luxury"],
            travel_days=3,
        )

        assert route.route_key == "north_road"
        assert route.origin_key == "capital"
        assert route.destination_key == "northern_town"
        assert route.status == RouteStatus.ACTIVE.value
        assert "weapons" in route.goods_traded

    def test_get_trade_route(self, db_session, game_session):
        """Test retrieving a trade route."""
        manager = EconomyManager(db_session, game_session)
        manager.create_trade_route(
            "river_route", "River Route", "port_city", "inland_city",
            goods_traded=["food"]
        )

        route = manager.get_trade_route("river_route")
        assert route is not None
        assert route.display_name == "River Route"

    def test_disrupt_trade_route(self, db_session, game_session):
        """Test disrupting a trade route."""
        manager = EconomyManager(db_session, game_session)
        manager.create_trade_route(
            "mountain_pass", "Mountain Pass", "east_city", "west_city",
            goods_traded=["metals"]
        )

        manager.disrupt_trade_route("mountain_pass", "Bandit activity")

        route = manager.get_trade_route("mountain_pass")
        assert route.status == RouteStatus.DISRUPTED.value
        assert "Bandit" in route.disruption_reason

    def test_block_trade_route(self, db_session, game_session):
        """Test blocking a trade route."""
        manager = EconomyManager(db_session, game_session)
        manager.create_trade_route(
            "bridge_road", "Bridge Road", "town_a", "town_b",
            goods_traded=["food"]
        )

        manager.block_trade_route("bridge_road", "Bridge collapsed")

        route = manager.get_trade_route("bridge_road")
        assert route.status == RouteStatus.BLOCKED.value

    def test_restore_trade_route(self, db_session, game_session):
        """Test restoring a disrupted trade route."""
        manager = EconomyManager(db_session, game_session)
        manager.create_trade_route(
            "coast_route", "Coastal Route", "port_a", "port_b",
            goods_traded=["fish"]
        )
        manager.disrupt_trade_route("coast_route", "Storms")

        manager.restore_trade_route("coast_route")

        route = manager.get_trade_route("coast_route")
        assert route.status == RouteStatus.ACTIVE.value
        assert route.disruption_reason is None

    def test_get_routes_for_location(self, db_session, game_session):
        """Test getting all routes connected to a location."""
        manager = EconomyManager(db_session, game_session)
        manager.create_trade_route("route_1", "Route 1", "hub", "town_a", ["food"])
        manager.create_trade_route("route_2", "Route 2", "hub", "town_b", ["weapons"])
        manager.create_trade_route("route_3", "Route 3", "town_a", "hub", ["tools"])

        routes = manager.get_routes_for_location("hub")
        assert len(routes) == 3  # All routes touch hub


class TestEconomicEvents:
    """Tests for economic event management."""

    def test_create_economic_event(self, db_session, game_session):
        """Test creating an economic event."""
        manager = EconomyManager(db_session, game_session)

        event = manager.create_economic_event(
            event_key="harvest_festival",
            event_type="festival",
            description="Annual harvest celebration brings traders",
            affected_locations=["town_square", "market_district"],
            affected_categories=["food", "alcohol"],
            price_modifier=0.8,  # 20% off
        )

        assert event.event_key == "harvest_festival"
        assert event.event_type == "festival"
        assert event.price_modifier == 0.8
        assert event.is_active is True

    def test_create_event_with_duration(self, db_session, game_session):
        """Test creating a temporary economic event."""
        manager = EconomyManager(db_session, game_session)

        event = manager.create_economic_event(
            event_key="war_shortage",
            event_type="war",
            description="War drives up weapon prices",
            affected_locations=["capital"],
            affected_categories=["weapons", "armor"],
            price_modifier=1.5,
            duration_turns=20,
        )

        assert event.duration_turns == 20

    def test_get_active_events(self, db_session, game_session):
        """Test getting active events."""
        manager = EconomyManager(db_session, game_session)
        manager.create_economic_event(
            "event_1", "famine", "Crops failed", ["town"], ["food"], 2.0
        )
        manager.create_economic_event(
            "event_2", "festival", "Celebration", ["city"], ["alcohol"], 0.9
        )

        events = manager.get_active_events()
        assert len(events) == 2

    def test_end_economic_event(self, db_session, game_session):
        """Test ending an economic event."""
        manager = EconomyManager(db_session, game_session)
        manager.create_economic_event(
            "plague", "plague", "Disease outbreak", ["town"], ["medicine"], 3.0
        )

        manager.end_event("plague")

        event = manager.get_event("plague")
        assert event.is_active is False

    def test_get_events_affecting_location(self, db_session, game_session):
        """Test getting events affecting a specific location."""
        manager = EconomyManager(db_session, game_session)
        manager.create_economic_event(
            "e1", "war", "War", ["capital", "border"], ["weapons"], 1.5
        )
        manager.create_economic_event(
            "e2", "festival", "Festival", ["capital"], ["food"], 0.9
        )
        manager.create_economic_event(
            "e3", "famine", "Famine", ["village"], ["food"], 2.0
        )

        events = manager.get_events_for_location("capital")
        assert len(events) == 2  # e1 and e2 affect capital


class TestPriceWithEvents:
    """Tests for price calculation including economic events."""

    def test_price_with_event_modifier(self, db_session, game_session):
        """Test price calculation with active event."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("market", "food")
        manager.create_economic_event(
            "famine", "famine", "Food shortage",
            affected_locations=["market"],
            affected_categories=["food"],
            price_modifier=2.0,
        )

        price_info = manager.calculate_price("market", "food", base_price=100)
        assert price_info.current_price == 200  # 2.0x from event

    def test_price_with_multiple_events(self, db_session, game_session):
        """Test price with multiple affecting events."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("market", "weapons")
        manager.create_economic_event(
            "war", "war", "War demand",
            affected_locations=["market"],
            affected_categories=["weapons"],
            price_modifier=1.5,
        )
        manager.create_economic_event(
            "shortage", "shortage", "Supply shortage",
            affected_locations=["market"],
            affected_categories=["weapons"],
            price_modifier=1.3,
        )

        price_info = manager.calculate_price("market", "weapons", base_price=100)
        # 100 * 1.5 * 1.3 = 195
        assert price_info.current_price == 195

    def test_price_event_category_mismatch(self, db_session, game_session):
        """Test that events only affect matching categories."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("market", "armor")
        manager.create_economic_event(
            "food_crisis", "famine", "Food shortage",
            affected_locations=["market"],
            affected_categories=["food"],  # Not armor
            price_modifier=2.0,
        )

        price_info = manager.calculate_price("market", "armor", base_price=100)
        assert price_info.current_price == 100  # Not affected

    def test_price_event_location_mismatch(self, db_session, game_session):
        """Test that events only affect matching locations."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("town_market", "food")
        manager.create_economic_event(
            "city_famine", "famine", "City food shortage",
            affected_locations=["city_market"],  # Not town_market
            affected_categories=["food"],
            price_modifier=2.0,
        )

        price_info = manager.calculate_price("town_market", "food", base_price=100)
        assert price_info.current_price == 100  # Not affected


class TestMarketSummary:
    """Tests for market summary generation."""

    def test_get_market_summary(self, db_session, game_session):
        """Test getting a market summary."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("main_market", "food")
        manager.set_market_price("main_market", "weapons")
        manager.create_trade_route(
            "supply_route", "Supply Route", "main_market", "farm",
            goods_traded=["food"]
        )

        summary = manager.get_market_summary("main_market")

        assert isinstance(summary, MarketSummary)
        assert summary.location_key == "main_market"
        assert len(summary.categories) == 2
        assert "food" in summary.categories
        assert len(summary.connected_routes) >= 1

    def test_market_summary_includes_events(self, db_session, game_session):
        """Test that summary includes active events."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("city_market", "luxury")
        manager.create_economic_event(
            "festival", "festival", "City festival",
            affected_locations=["city_market"],
            affected_categories=["luxury"],
            price_modifier=0.9,
        )

        summary = manager.get_market_summary("city_market")
        assert len(summary.active_events) == 1


class TestEconomyContext:
    """Tests for GM context generation."""

    def test_economy_context_basic(self, db_session, game_session):
        """Test basic economy context generation."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("town", "food", supply_level=SupplyLevel.ABUNDANT)
        manager.set_market_price("town", "weapons", supply_level=SupplyLevel.SCARCE)

        context = manager.get_economy_context("town")

        assert "food" in context.lower()
        assert "weapons" in context.lower()
        assert "abundant" in context.lower() or "plentiful" in context.lower()
        assert "scarce" in context.lower()

    def test_economy_context_with_events(self, db_session, game_session):
        """Test economy context includes events."""
        manager = EconomyManager(db_session, game_session)
        manager.set_market_price("market", "grain")
        manager.create_economic_event(
            "drought", "drought", "Severe drought affecting crops",
            affected_locations=["market"],
            affected_categories=["grain"],
            price_modifier=2.5,
        )

        context = manager.get_economy_context("market")
        assert "drought" in context.lower()


class TestSessionIsolation:
    """Tests for session isolation."""

    def test_markets_isolated_by_session(self, db_session, game_session, game_session_2):
        """Test that markets are isolated between sessions."""
        manager1 = EconomyManager(db_session, game_session)
        manager2 = EconomyManager(db_session, game_session_2)

        manager1.set_market_price("shared_market", "food", supply_level=SupplyLevel.SCARCE)
        manager2.set_market_price("shared_market", "food", supply_level=SupplyLevel.ABUNDANT)

        market1 = manager1.get_market_price("shared_market", "food")
        market2 = manager2.get_market_price("shared_market", "food")

        assert market1.supply_level == SupplyLevel.SCARCE.value
        assert market2.supply_level == SupplyLevel.ABUNDANT.value

    def test_events_isolated_by_session(self, db_session, game_session, game_session_2):
        """Test that events are isolated between sessions."""
        manager1 = EconomyManager(db_session, game_session)
        manager2 = EconomyManager(db_session, game_session_2)

        manager1.create_economic_event(
            "war", "war", "War", ["city"], ["weapons"], 2.0
        )

        events1 = manager1.get_active_events()
        events2 = manager2.get_active_events()

        assert len(events1) == 1
        assert len(events2) == 0
