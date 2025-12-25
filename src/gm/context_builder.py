"""Context builder for the Simplified GM Pipeline.

Wraps the existing ContextCompiler manager and formats output
for the new GM prompt template.
"""

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, EntityAttribute, EntitySkill
from src.database.models.enums import EntityType
from src.database.models.items import Item
from src.database.models.session import GameSession, Turn
from src.database.models.world import Location, TimeState, Fact
from src.managers.base import BaseManager
from src.managers.context_compiler import ContextCompiler
from src.managers.item_manager import ItemManager
from src.managers.location_manager import LocationManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.storage_observation_manager import StorageObservationManager
from src.managers.summary_manager import SummaryManager
from src.gm.prompts import GM_USER_TEMPLATE


class GMContextBuilder(BaseManager):
    """Builds rich context for the GM LLM.

    Uses the existing ContextCompiler for most data gathering,
    then formats it according to the new GM prompt template.
    """

    def __init__(self, db: Session, game_session: GameSession) -> None:
        super().__init__(db, game_session)
        self._context_compiler: ContextCompiler | None = None
        self._item_manager: ItemManager | None = None
        self._location_manager: LocationManager | None = None
        self._needs_manager: NeedsManager | None = None
        self._relationship_manager: RelationshipManager | None = None
        self._storage_observation_manager: StorageObservationManager | None = None
        self._summary_manager: SummaryManager | None = None

    @property
    def context_compiler(self) -> ContextCompiler:
        if self._context_compiler is None:
            self._context_compiler = ContextCompiler(self.db, self.game_session)
        return self._context_compiler

    @property
    def item_manager(self) -> ItemManager:
        if self._item_manager is None:
            self._item_manager = ItemManager(self.db, self.game_session)
        return self._item_manager

    @property
    def location_manager(self) -> LocationManager:
        if self._location_manager is None:
            self._location_manager = LocationManager(self.db, self.game_session)
        return self._location_manager

    @property
    def needs_manager(self) -> NeedsManager:
        if self._needs_manager is None:
            self._needs_manager = NeedsManager(self.db, self.game_session)
        return self._needs_manager

    @property
    def relationship_manager(self) -> RelationshipManager:
        if self._relationship_manager is None:
            self._relationship_manager = RelationshipManager(self.db, self.game_session)
        return self._relationship_manager

    @property
    def storage_observation_manager(self) -> StorageObservationManager:
        if self._storage_observation_manager is None:
            self._storage_observation_manager = StorageObservationManager(
                self.db, self.game_session
            )
        return self._storage_observation_manager

    @property
    def summary_manager(self) -> SummaryManager:
        if self._summary_manager is None:
            self._summary_manager = SummaryManager(self.db, self.game_session)
        return self._summary_manager

    def build(
        self,
        player_id: int,
        location_key: str,
        player_input: str,
        turn_number: int = 1,
        is_ooc_hint: bool = False,
    ) -> str:
        """Build the full context prompt for the GM LLM.

        Args:
            player_id: Player entity ID.
            location_key: Current location key.
            player_input: The player's input/action.
            turn_number: Current turn number.
            is_ooc_hint: Whether explicit OOC prefix was detected.

        Returns:
            Formatted prompt string.
        """
        # Get player entity
        player = self.db.query(Entity).filter(Entity.id == player_id).first()
        if not player:
            return f"Error: Player not found (ID: {player_id})"

        return GM_USER_TEMPLATE.format(
            player_name=player.display_name,
            background=self._get_background(player),
            needs_summary=self._get_needs_summary(player_id),
            inventory=self._get_inventory(player_id),
            equipped=self._get_equipped(player_id),
            location_name=self._get_location_name(location_key),
            location_description=self._get_location_description(location_key),
            npcs_present=self._get_npcs_present(location_key, player_id),
            items_present=self._get_items_present(location_key),
            exits=self._get_exits(location_key),
            storage_context=self._get_storage_context(player_id, location_key),
            relationships=self._get_relationships(player_id),
            known_facts=self._get_known_facts(),
            familiarity=self._get_familiarity_context(player_id, location_key),
            story_summary=self._get_story_summary(),
            recent_summary=self._get_recent_summary(),
            recent_turns=self._get_recent_turns(turn_number),
            system_hints=self._get_system_hints(player_id),
            constraints=self._get_constraints(player_id, location_key),
            ooc_hint=self._get_ooc_hint(is_ooc_hint, player_input),
            player_input=player_input,
        )

    def _get_background(self, player: Entity) -> str:
        """Get player's background story."""
        parts = []

        if player.occupation:
            years = f" ({player.occupation_years} years)" if player.occupation_years else ""
            parts.append(f"Occupation: {player.occupation}{years}")

        if player.appearance:
            appearance_parts = []
            if player.appearance.get("age"):
                appearance_parts.append(f"{player.appearance['age']} years old")
            if player.appearance.get("build"):
                appearance_parts.append(player.appearance["build"])
            if appearance_parts:
                parts.append(", ".join(appearance_parts))

        # TODO: Get background from character creation/facts
        return "\n".join(parts) if parts else "No specific background established."

    def _get_needs_summary(self, player_id: int) -> str:
        """Get player's current needs state."""
        needs = self.needs_manager.get_needs(player_id)
        if not needs:
            return "Needs: Unknown"

        lines = []

        # Format each need with a descriptor
        def describe(value: int, low: str, mid: str, high: str) -> str:
            if value < 30:
                return f"{low} ({value}/100)"
            elif value < 70:
                return f"{mid} ({value}/100)"
            else:
                return f"{high} ({value}/100)"

        # Sleep pressure is inverted (0=rested, 100=exhausted)
        if needs.sleep_pressure > 70:
            lines.append(f"- Fatigue: Exhausted ({needs.sleep_pressure}/100)")
        elif needs.sleep_pressure > 40:
            lines.append(f"- Fatigue: Tired ({needs.sleep_pressure}/100)")
        else:
            lines.append(f"- Fatigue: Rested ({needs.sleep_pressure}/100)")

        lines.append(f"- Hunger: {describe(needs.hunger, 'Starving', 'Peckish', 'Well-fed')}")
        lines.append(f"- Thirst: {describe(needs.thirst, 'Parched', 'Thirsty', 'Hydrated')}")
        lines.append(f"- Stamina: {describe(needs.stamina, 'Exhausted', 'Winded', 'Fresh')}")
        lines.append(f"- Wellness: {describe(needs.wellness, 'Unwell', 'Okay', 'Healthy')}")
        lines.append(f"- Hygiene: {describe(needs.hygiene, 'Filthy', 'Unkempt', 'Clean')}")

        return "\n".join(lines)

    def _get_inventory(self, player_id: int) -> str:
        """Get player's inventory items."""
        items = self.item_manager.get_inventory(player_id)
        if not items:
            return "Empty"

        item_strs = []
        for item in items[:20]:  # Limit to 20 items
            item_strs.append(f"- {item.item_key}: {item.display_name}")

        return "\n".join(item_strs)

    def _get_equipped(self, player_id: int) -> str:
        """Get player's equipped items."""
        items = self.item_manager.get_equipped_items(player_id)
        if not items:
            return "Nothing equipped"

        item_strs = []
        for item in items:
            slot = item.body_slot or "unknown"
            item_strs.append(f"- [{slot}] {item.item_key}: {item.display_name}")

        return "\n".join(item_strs)

    def _get_location_name(self, location_key: str) -> str:
        """Get location display name."""
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )
        return location.display_name if location else location_key

    def _get_location_description(self, location_key: str) -> str:
        """Get location description."""
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if not location:
            return "No description available."

        parts = []
        if location.description:
            parts.append(location.description)
        if location.atmosphere:
            parts.append(f"Atmosphere: {location.atmosphere}")

        return "\n".join(parts) if parts else "No description available."

    def _get_npcs_present(self, location_key: str, player_id: int) -> str:
        """Get NPCs at the current location."""
        from src.managers.entity_manager import EntityManager

        entity_manager = EntityManager(self.db, self.game_session)
        npcs = entity_manager.get_npcs_in_scene(location_key)

        if not npcs:
            return "None"

        lines = []
        for npc in npcs[:10]:  # Limit to 10 NPCs
            npc_line = f"- {npc.entity_key}: {npc.display_name}"

            # Add occupation if known
            if npc.occupation:
                npc_line += f" ({npc.occupation})"

            # Add mood if available
            if npc.npc_extension and npc.npc_extension.current_mood:
                npc_line += f" - {npc.npc_extension.current_mood}"

            # Add attitude toward player
            attitude = self.relationship_manager.get_attitude(npc.id, player_id)
            if attitude["knows"]:
                disposition = self.relationship_manager.get_attitude_description(npc.id, player_id)
                npc_line += f" [{disposition}]"

            lines.append(npc_line)

        return "\n".join(lines)

    def _get_items_present(self, location_key: str) -> str:
        """Get items at the current location."""
        items = self.item_manager.get_items_at_location(location_key)

        if not items:
            return "None visible"

        lines = []
        for item in items[:15]:  # Limit to 15 items
            lines.append(f"- {item.item_key}: {item.display_name}")

        return "\n".join(lines)

    def _get_exits(self, location_key: str) -> str:
        """Get available exits from current location.

        Uses location_manager.get_accessible_locations() for consistency.
        """
        try:
            accessible = self.location_manager.get_accessible_locations(location_key)
            if not accessible:
                return "None apparent"

            lines = []
            for loc in accessible:
                lines.append(f"- {loc.display_name} [{loc.location_key}]")
            return "\n".join(lines)
        except Exception:
            return "None apparent"

    def _get_storage_context(self, player_id: int, location_key: str) -> str:
        """Get storage containers at location with first-time/revisit status.

        This helps the GM know whether to freely invent contents (first time)
        or reference established contents (revisit).

        Args:
            player_id: Player entity ID.
            location_key: Current location key.

        Returns:
            Storage context string with [FIRST TIME] or [REVISIT] tags.
        """
        from src.database.models.items import StorageLocation

        # Get the Location entity to get its ID
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if not location:
            return "No storage containers"

        # Get storages with observation status
        storages_with_status = (
            self.storage_observation_manager.get_storages_at_location_with_status(
                observer_id=player_id,
                location_id=location.id,
            )
        )

        if not storages_with_status:
            return "No storage containers"

        lines = []
        for storage_info in storages_with_status:
            storage_key = storage_info["storage_key"]
            first_time = storage_info["first_time"]
            original_contents = storage_info["original_contents"]

            if first_time:
                lines.append(f"- {storage_key}: **[FIRST TIME]** - freely invent reasonable contents")
            else:
                if original_contents:
                    contents_str = ", ".join(original_contents[:5])
                    if len(original_contents) > 5:
                        contents_str += f" (+{len(original_contents) - 5} more)"
                    lines.append(f"- {storage_key}: **[REVISIT]** - established contents: {contents_str}")
                else:
                    lines.append(f"- {storage_key}: **[REVISIT]** - was empty when first observed")

        return "\n".join(lines) if lines else "No storage containers"

    def _get_relationships(self, player_id: int) -> str:
        """Get player's relationships with known NPCs."""
        try:
            # Get relationships where NPCs have attitudes toward the player
            relationships = self.relationship_manager.get_relationships_for_entity(
                player_id, direction="to"
            )

            if not relationships:
                return "No established relationships"

            lines = []
            for rel in relationships[:10]:  # Limit to 10
                # Get the NPC (from_entity has the attitude toward player)
                npc = self.db.query(Entity).filter(Entity.id == rel.from_entity_id).first()

                if npc and rel.knows:
                    # Get attitude description
                    disposition = self.relationship_manager.get_attitude_description(
                        rel.from_entity_id, player_id
                    )
                    trust = rel.trust or 50
                    liking = rel.liking or 50
                    lines.append(f"- {npc.display_name}: {disposition} (trust: {trust}, liking: {liking})")

            return "\n".join(lines) if lines else "No established relationships"
        except Exception:
            return "No established relationships"

    def _get_known_facts(self) -> str:
        """Get non-secret facts the player knows."""
        facts = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_secret == False,
            )
            .limit(20)
            .all()
        )

        if not facts:
            return "No specific facts established"

        lines = []
        for fact in facts:
            lines.append(f"- {fact.subject_key}: {fact.predicate} = {fact.value}")

        return "\n".join(lines)

    def _get_familiarity_context(self, player_id: int, location_key: str) -> str:
        """Determine what the character is familiar with at current location.

        Returns context that helps the LLM decide OOC vs IC for knowledge questions.
        Questions about familiar things should be answered OOC (player asking about
        character knowledge, not character asking in-world).

        Args:
            player_id: The player entity ID.
            location_key: Current location key.

        Returns:
            Familiarity context string for the prompt.
        """
        lines = []
        player = self.db.query(Entity).filter(Entity.id == player_id).first()
        if not player:
            return "**Unfamiliar with current location** - character doesn't know details"

        # 1. Check if this is player's home (via lives_at fact)
        lives_at = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == player.entity_key,
                Fact.predicate == "lives_at",
            )
            .first()
        )

        if lives_at and location_key.startswith(lives_at.value):
            lines.append(
                f"- **This is {player.display_name}'s home** - "
                "knows all routines, locations, items"
            )

        # 2. Check player-owned items at location
        try:
            location_items = self.item_manager.get_items_at_location(location_key)
            owned_items = [i for i in location_items if i.owner_id == player_id]
            if owned_items:
                item_names = ", ".join(i.display_name for i in owned_items[:5])
                lines.append(f"- Owns items here: {item_names}")
        except Exception:
            pass  # Item lookup failed, skip this check

        # 3. Check facts about this location
        location_facts = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == location_key,
                Fact.is_secret == False,
            )
            .all()
        )
        if location_facts:
            lines.append(f"- Has {len(location_facts)} known facts about this location")

        # Format output
        if lines:
            lines.insert(0, "**Familiar with current location:**")
            lines.append(
                "\n→ Questions about familiar things = OOC "
                "(player asking, not character)"
            )
        else:
            lines.append(
                "**Unfamiliar with current location** - character doesn't know details"
            )

        return "\n".join(lines)

    def _get_story_summary(self) -> str:
        """Get story summary from start to last milestone."""
        return self.summary_manager.get_story_summary() or "Story just beginning"

    def _get_recent_summary(self) -> str:
        """Get recent events summary."""
        return self.summary_manager.get_recent_summary() or "No recent events"

    def _get_recent_turns(self, turn_number: int, limit: int = 10) -> str:
        """Get the last N turns' text."""
        if turn_number <= 1:
            return "This is the first turn - introduce the scene."

        turns = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.session_id)
            .order_by(Turn.turn_number.desc())
            .limit(limit)
            .all()
        )

        if not turns:
            return "No previous turns"

        lines = []
        for turn in reversed(turns):  # Show oldest first
            lines.append(f"**Turn {turn.turn_number}**")
            lines.append(f"Player: {turn.player_input[:200]}")
            lines.append(f"GM: {turn.gm_response[:500]}")
            lines.append("")

        return "\n".join(lines)

    def _get_system_hints(self, player_id: int) -> str:
        """Get system hints for the GM (needs alerts, time for events, etc.)."""
        hints = []

        # Check for urgent needs
        needs = self.needs_manager.get_needs(player_id)
        if needs:
            if needs.hunger < 20:
                hints.append("- Player is STARVING - hunger effects should be noticeable")
            if needs.thirst < 20:
                hints.append("- Player is PARCHED - thirst effects should be noticeable")
            if needs.sleep_pressure > 80:
                hints.append("- Player is EXHAUSTED - drowsiness should be affecting them")
            if needs.hygiene < 20:
                hints.append("- Player is FILTHY - NPCs may react to smell/appearance")

        # Get time of day for mood hints
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )
        if time_state:
            time_str = time_state.current_time or "12:00"
            hour = int(time_str.split(":")[0])
            if hour < 6:
                hints.append("- It's before dawn - most people are asleep")
            elif hour >= 22:
                hints.append("- It's late night - most people are retiring")
            elif hour >= 18:
                hints.append("- It's evening - people are winding down")

        return "\n".join(hints) if hints else "No special hints"

    def _get_constraints(self, player_id: int, location_key: str) -> str:
        """Get constraints on what's possible."""
        constraints = []

        # Check what player is holding
        equipped = self.item_manager.get_equipped_items(player_id)
        main_hand = None
        off_hand = None
        for item in equipped:
            if item.body_slot == "main_hand":
                main_hand = item
            elif item.body_slot == "off_hand":
                off_hand = item

        if main_hand and off_hand:
            constraints.append("- Both hands are full - must drop or store something to pick up items")
        elif main_hand or off_hand:
            constraints.append("- One hand is occupied")
        else:
            constraints.append("- Both hands are free")

        # Check stamina for physical actions
        needs = self.needs_manager.get_needs(player_id)
        if needs and needs.stamina < 20:
            constraints.append("- Too exhausted for strenuous physical actions")

        return "\n".join(constraints) if constraints else "No special constraints"

    def _get_ooc_hint(self, is_explicit_ooc: bool, player_input: str) -> str:
        """Generate OOC detection hint for the GM.

        Args:
            is_explicit_ooc: Whether explicit OOC prefix was detected.
            player_input: The player's input.

        Returns:
            OOC hint string for the prompt.
        """
        if is_explicit_ooc:
            return (
                "[EXPLICIT OOC REQUEST] - Player used 'ooc:' prefix. "
                "Respond as GM directly to player, not in narrative. "
                "Start your response with [OOC]."
            )

        # Check for implicit OOC signals
        implicit_signals = [
            # Character knowledge questions
            "what does my character know",
            "what do i know about",
            "tell me about my",
            "what's my backstory",
            "what happened to me",
            "where is my bathroom",
            "where's my",
            # Routine/habit questions (character would know their own habits)
            "where do i usually",
            "how do i usually",
            "what's my usual",
            "what do i normally",
            "when do i usually",
            "where do i sleep",
            "where do i wash",
            "where do i eat",
        ]
        input_lower = player_input.lower()

        for signal in implicit_signals:
            if signal in input_lower:
                return (
                    "[POSSIBLE OOC] - This might be an OOC question about the character's own knowledge. "
                    "If the player is asking about things their CHARACTER already knows, "
                    "respond OOC with [OOC] prefix. If it's an in-world action, respond IC."
                )

        return "No explicit OOC signals detected - respond in-character with narrative unless context suggests OOC."

    def get_all_entity_keys(self, player_id: int, location_key: str) -> set[str]:
        """Get all known entity keys for validation.

        Returns:
            Set of entity keys that exist in the current context.
        """
        keys = set()

        # Player
        player = self.db.query(Entity).filter(Entity.id == player_id).first()
        if player:
            keys.add(player.entity_key)

        # NPCs at location
        from src.managers.entity_manager import EntityManager
        entity_manager = EntityManager(self.db, self.game_session)
        npcs = entity_manager.get_npcs_in_scene(location_key)
        for npc in npcs:
            keys.add(npc.entity_key)

        # Player inventory and equipped
        for item in self.item_manager.get_inventory(player_id):
            keys.add(item.item_key)
        for item in self.item_manager.get_equipped_items(player_id):
            keys.add(item.item_key)

        # Items at location
        for item in self.item_manager.get_items_at_location(location_key):
            keys.add(item.item_key)

        # Location itself
        keys.add(location_key)

        return keys
