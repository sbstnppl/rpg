"""OOC (Out-of-Character) Handler.

Handles out-of-character queries with game state information.
Uses a hybrid approach:
- Known queries (exits, time, etc.) get instant responses from game state
- Unknown queries go to LLM for GM-style answers
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.llm.message_types import Message
from src.managers.location_manager import LocationManager

if TYPE_CHECKING:
    from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class OOCQueryType(Enum):
    """Type of OOC query detected."""

    EXITS = "exits"
    TIME = "time"
    INVENTORY = "inventory"
    LOCATION = "location"
    NPCS = "npcs"
    STATS = "stats"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class OOCContext:
    """Context for OOC query handling.

    Contains all the information needed to answer OOC queries.
    """

    db: Session
    game_session: GameSession
    location_key: str
    # Optional fields for richer context
    player_entity_key: str | None = None
    game_time: str | None = None


# Keywords for query classification
# Each key maps to a list of phrases that indicate that query type
QUERY_KEYWORDS: dict[OOCQueryType, list[str]] = {
    OOCQueryType.EXITS: [
        "exit",
        "exits",
        "where can i go",
        "directions",
        "leave",
        "way out",
    ],
    OOCQueryType.TIME: [
        "time",
        "what time",
        "hour",
        "day",
        "date",
    ],
    OOCQueryType.INVENTORY: [
        "inventory",
        "items",
        "what do i have",
        "carrying",
        "my stuff",
    ],
    OOCQueryType.LOCATION: [
        "where am i",
        "location",
        "this place",
        "current location",
    ],
    OOCQueryType.NPCS: [
        "who is here",
        "who's here",
        "npcs",
        "people",
        "anyone here",
    ],
    OOCQueryType.STATS: [
        "stats",
        "attributes",
        "health",
        "status",
        "my stats",
    ],
    OOCQueryType.HELP: [
        "help",
        "commands",
        "what can i ask",
        "ooc commands",
    ],
}


class OOCHandler:
    """Handles out-of-character queries with game state information.

    Uses keyword matching for known queries (fast path) and falls back
    to LLM for unknown queries (GM-style answers).
    """

    def _classify_query(self, query: str) -> OOCQueryType:
        """Classify an OOC query by type.

        Args:
            query: The raw OOC query text.

        Returns:
            The classified query type.
        """
        # Strip OOC prefix if present
        clean = query.lower().strip()
        if clean.startswith("ooc:"):
            clean = clean[4:].strip()
        elif clean.startswith("ooc "):
            clean = clean[4:].strip()

        # Check each query type's keywords
        for query_type, keywords in QUERY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in clean:
                    return query_type

        return OOCQueryType.UNKNOWN

    def handle_query(self, query: str, context: OOCContext) -> str:
        """Handle an OOC query synchronously.

        Routes to appropriate handler based on query classification.
        For unknown queries, returns a generic message (use handle_query_async
        for LLM fallback).

        Args:
            query: The OOC query text.
            context: The OOC context with game state access.

        Returns:
            Response string prefixed with [OOC].
        """
        query_type = self._classify_query(query)

        handler_map = {
            OOCQueryType.EXITS: self._handle_exits,
            OOCQueryType.TIME: self._handle_time,
            OOCQueryType.INVENTORY: self._handle_inventory,
            OOCQueryType.LOCATION: self._handle_location,
            OOCQueryType.NPCS: self._handle_npcs,
            OOCQueryType.STATS: self._handle_stats,
            OOCQueryType.HELP: self._handle_help,
        }

        handler = handler_map.get(query_type)
        if handler:
            return handler(context)

        # Unknown query - return generic message in sync mode
        return "[OOC] I'm not sure how to answer that. Try asking about exits, time, inventory, location, npcs, stats, or type 'help' for options."

    async def handle_query_async(
        self,
        query: str,
        context: OOCContext,
        llm_provider: "LLMProvider | None" = None,
    ) -> str:
        """Handle an OOC query with LLM fallback for unknown queries.

        Args:
            query: The OOC query text.
            context: The OOC context with game state access.
            llm_provider: Optional LLM provider for unknown queries.

        Returns:
            Response string prefixed with [OOC].
        """
        query_type = self._classify_query(query)

        # Fast path for known queries
        handler_map = {
            OOCQueryType.EXITS: self._handle_exits,
            OOCQueryType.TIME: self._handle_time,
            OOCQueryType.INVENTORY: self._handle_inventory,
            OOCQueryType.LOCATION: self._handle_location,
            OOCQueryType.NPCS: self._handle_npcs,
            OOCQueryType.STATS: self._handle_stats,
            OOCQueryType.HELP: self._handle_help,
        }

        handler = handler_map.get(query_type)
        if handler:
            return handler(context)

        # Unknown query - fall back to LLM
        return await self._handle_unknown(query, context, llm_provider)

    def _handle_exits(self, context: OOCContext) -> str:
        """Return available exits from current location.

        Args:
            context: The OOC context.

        Returns:
            Formatted list of exits or 'no exits' message.
        """
        location_manager = LocationManager(context.db, context.game_session)
        accessible = location_manager.get_accessible_locations(context.location_key)

        if not accessible:
            return "[OOC] There are no obvious exits from here."

        lines = ["[OOC] Available exits:"]
        for loc in accessible:
            lines.append(f"  - {loc.display_name}")

        return "\n".join(lines)

    def _handle_time(self, context: OOCContext) -> str:
        """Return current in-game time.

        Args:
            context: The OOC context.

        Returns:
            Current time information.
        """
        if context.game_time:
            return f"[OOC] The current time is {context.game_time}."

        # TODO: Query TimeState from database when available in context
        return "[OOC] Time information not available."

    def _handle_inventory(self, context: OOCContext) -> str:
        """Return player inventory.

        Args:
            context: The OOC context.

        Returns:
            Inventory information.
        """
        # TODO: Implement when inventory handler is needed
        return "[OOC] Inventory query not yet implemented."

    def _handle_location(self, context: OOCContext) -> str:
        """Return current location description.

        Args:
            context: The OOC context.

        Returns:
            Location description.
        """
        location_manager = LocationManager(context.db, context.game_session)
        location = location_manager.get_location(context.location_key)

        if not location:
            return "[OOC] Unable to determine your location."

        return f"[OOC] You are at {location.display_name}."

    def _handle_npcs(self, context: OOCContext) -> str:
        """Return NPCs at current location.

        Args:
            context: The OOC context.

        Returns:
            List of NPCs present.
        """
        # TODO: Implement when NPC query is needed
        return "[OOC] NPC query not yet implemented."

    def _handle_stats(self, context: OOCContext) -> str:
        """Return player stats.

        Args:
            context: The OOC context.

        Returns:
            Player statistics.
        """
        # TODO: Implement when stats query is needed
        return "[OOC] Stats query not yet implemented."

    def _handle_help(self, context: OOCContext) -> str:
        """Return list of available OOC commands.

        Args:
            context: The OOC context.

        Returns:
            Help message listing available commands.
        """
        return """[OOC] Available OOC commands:
  - exits / where can I go - List available exits
  - time - Current in-game time
  - inventory / what do I have - Your inventory
  - where am I - Current location
  - who is here - NPCs at this location
  - stats / health - Your character status
  - help - Show this message

For other questions, just ask and I'll do my best to answer as your GM."""

    async def _handle_unknown(
        self,
        query: str,
        context: OOCContext,
        llm_provider: "LLMProvider | None",
    ) -> str:
        """Handle unknown queries via LLM fallback.

        Args:
            query: The original query.
            context: The OOC context.
            llm_provider: LLM provider for generating responses.

        Returns:
            GM-style answer from LLM or generic response if no provider.
        """
        if llm_provider is None:
            return "[OOC] I don't have enough information to answer that question. Try asking about exits, time, inventory, location, npcs, or stats."

        # Build context for LLM
        location_manager = LocationManager(context.db, context.game_session)
        location = location_manager.get_location(context.location_key)
        location_name = location.display_name if location else "Unknown Location"

        prompt = f"""You are a tabletop RPG game master answering an out-of-character question.

Current scene context:
- Location: {location_name}

Player's OOC question: {query}

Answer helpfully and concisely as a GM would. Stay factual about game state.
Prefix your response with [OOC]."""

        try:
            llm_response = await llm_provider.complete(
                messages=[Message.user(prompt)],
                max_tokens=256,
                temperature=0.7,
            )
            response_text = llm_response.content or ""
            # Ensure [OOC] prefix
            if not response_text.strip().startswith("[OOC]"):
                response_text = f"[OOC] {response_text}"
            return response_text
        except Exception as e:
            logger.warning(f"LLM fallback failed for OOC query: {e}")
            return "[OOC] I'm unable to answer that question right now."
