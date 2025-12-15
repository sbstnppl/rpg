"""GM Tool Executor for processing LLM tool calls.

Executes tools and returns structured results for the LLM to incorporate
into its narrative.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.agents.schemas.npc_state import (
    NPCConstraints,
    PlayerSummary,
    SceneContext,
    VisibleItem,
)
from src.database.models.entities import Entity, EntityAttribute, EntitySkill
from src.database.models.enums import DiscoveryMethod, ItemType, StorageLocationType
from src.database.models.items import Item, StorageLocation
from src.database.models.session import GameSession
from src.dice.checks import (
    calculate_ability_modifier,
    get_difficulty_description,
    get_proficiency_tier_name,
    make_skill_check,
    proficiency_to_modifier,
)
from src.dice.combat import make_attack_roll, roll_damage
from src.dice.skills import get_attribute_for_skill
from src.dice.types import AdvantageType
from src.managers.discovery_manager import DiscoveryManager
from src.managers.item_manager import ItemManager
from src.managers.pathfinding_manager import PathfindingManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.zone_manager import ZoneManager


class GMToolExecutor:
    """Executes GM tools and returns structured results."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        current_zone_key: str | None = None,
        scene_context: SceneContext | None = None,
    ):
        """Initialize executor with database context.

        Args:
            db: Database session.
            game_session: Current game session.
            current_zone_key: Player's current zone key (for navigation tools).
            scene_context: Current scene context for NPC tools.
        """
        self.db = db
        self.game_session = game_session
        self.current_zone_key = current_zone_key
        self.scene_context = scene_context
        self.relationship_manager = RelationshipManager(db, game_session)
        self._zone_manager: ZoneManager | None = None
        self._pathfinding_manager: PathfindingManager | None = None
        self._discovery_manager: DiscoveryManager | None = None
        self._npc_generator = None
        self._item_generator = None

        # State updates to propagate to game_master_node
        # These replace the STATE block parsing approach
        self.pending_state_updates: dict[str, Any] = {}

    @property
    def zone_manager(self) -> ZoneManager:
        if self._zone_manager is None:
            self._zone_manager = ZoneManager(self.db, self.game_session)
        return self._zone_manager

    @property
    def pathfinding_manager(self) -> PathfindingManager:
        if self._pathfinding_manager is None:
            self._pathfinding_manager = PathfindingManager(self.db, self.game_session)
        return self._pathfinding_manager

    @property
    def discovery_manager(self) -> DiscoveryManager:
        if self._discovery_manager is None:
            self._discovery_manager = DiscoveryManager(self.db, self.game_session)
        return self._discovery_manager

    @property
    def npc_generator(self):
        """Lazy-load NPC generator to avoid import cycles."""
        if self._npc_generator is None:
            from src.services.emergent_npc_generator import EmergentNPCGenerator
            self._npc_generator = EmergentNPCGenerator(self.db, self.game_session)
        return self._npc_generator

    @property
    def item_generator(self):
        """Lazy-load item generator to avoid import cycles."""
        if self._item_generator is None:
            from src.services.emergent_item_generator import EmergentItemGenerator
            self._item_generator = EmergentItemGenerator(self.db, self.game_session)
        return self._item_generator

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return structured result.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments from LLM.

        Returns:
            Structured result dict for LLM to use.

        Raises:
            ValueError: If tool_name is unknown.
        """
        handlers = {
            "skill_check": self._execute_skill_check,
            "attack_roll": self._execute_attack_roll,
            "roll_damage": self._execute_roll_damage,
            "get_npc_attitude": self._execute_get_npc_attitude,
            "update_npc_attitude": self._execute_update_npc_attitude,
            "satisfy_need": self._execute_satisfy_need,
            "apply_stimulus": self._execute_apply_stimulus,
            "mark_need_communicated": self._execute_mark_need_communicated,
            "check_route": self._execute_check_route,
            "start_travel": self._execute_start_travel,
            "move_to_zone": self._execute_move_to_zone,
            "check_terrain": self._execute_check_terrain,
            "discover_zone": self._execute_discover_zone,
            "discover_location": self._execute_discover_location,
            "view_map": self._execute_view_map,
            # NPC creation/query tools
            "create_npc": self._execute_create_npc,
            "query_npc": self._execute_query_npc,
            # Item creation tools
            "create_item": self._execute_create_item,
            # Item acquisition tools
            "acquire_item": self._execute_acquire_item,
            "drop_item": self._execute_drop_item,
            # World spawning tools
            "spawn_storage": self._execute_spawn_storage,
            "spawn_item": self._execute_spawn_item,
            # State management tools (replace STATE block)
            "advance_time": self._execute_advance_time,
            "entity_move": self._execute_entity_move,
            "start_combat": self._execute_start_combat,
            "end_combat": self._execute_end_combat,
            # Quest management tools
            "assign_quest": self._execute_assign_quest,
            "update_quest": self._execute_update_quest,
            "complete_quest": self._execute_complete_quest,
            # World fact tools
            "record_fact": self._execute_record_fact,
            # NPC scene management tools
            "introduce_npc": self._execute_introduce_npc,
            "npc_leaves": self._execute_npc_leaves,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        return handler(arguments)

    def _execute_skill_check(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a skill check with proficiency and attribute lookup.

        Uses 2d10 bell curve system with auto-success for routine tasks.
        See docs/game-mechanics.md for full mechanics documentation.

        Args:
            args: Tool arguments with entity_key, dc, skill_name, description,
                  attribute_key (optional), advantage.

        Returns:
            Result with success, roll, margin, modifiers, outcome_tier, and description.
        """
        entity_key = args["entity_key"]
        dc = args["dc"]
        skill_name = args["skill_name"]
        check_description = args.get("description", f"{skill_name.title()} check")
        attribute_key_override = args.get("attribute_key")
        advantage_str = args.get("advantage", "normal")

        # Get entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"error": f"Entity '{entity_key}' not found"}

        # Determine which attribute governs this skill
        attribute_key = attribute_key_override or get_attribute_for_skill(skill_name)

        # Look up skill proficiency
        skill_record = (
            self.db.query(EntitySkill)
            .filter(
                EntitySkill.entity_id == entity.id,
                EntitySkill.skill_key == skill_name.lower().replace(" ", "_"),
            )
            .first()
        )
        proficiency_level = skill_record.proficiency_level if skill_record else 0
        skill_modifier = proficiency_to_modifier(proficiency_level)
        skill_tier = get_proficiency_tier_name(proficiency_level)

        # Look up attribute score
        attr_record = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == attribute_key.lower(),
            )
            .first()
        )
        attribute_score = attr_record.value if attr_record else 10
        attribute_modifier = calculate_ability_modifier(attribute_score)

        # Get difficulty assessment from character's perspective
        difficulty_assessment = get_difficulty_description(
            dc=dc,
            skill_modifier=skill_modifier,
            attribute_modifier=attribute_modifier,
        )

        # Parse advantage type
        advantage_type = self._parse_advantage(advantage_str)

        # Make the roll (uses 2d10 system with auto-success)
        result = make_skill_check(
            dc=dc,
            attribute_modifier=attribute_modifier,
            skill_modifier=skill_modifier,
            advantage_type=advantage_type,
        )

        # Build outcome description based on outcome tier
        if result.is_auto_success:
            outcome = "Auto-Success"
        elif result.is_critical_success:
            outcome = "Critical Success!"
        elif result.is_critical_failure:
            outcome = "Critical Failure!"
        else:
            # Use outcome tier for nuanced description
            tier_outcomes = {
                "exceptional": "Exceptional Success!",
                "clear_success": "Clear Success",
                "narrow_success": "Narrow Success",
                "bare_success": "Bare Success",
                "partial_failure": "Partial Failure",
                "clear_failure": "Clear Failure",
                "catastrophic": "Catastrophic Failure!",
            }
            outcome = tier_outcomes.get(result.outcome_tier.value, "Success" if result.success else "Failure")

        total_modifier = attribute_modifier + skill_modifier
        modifier_str = f"+{total_modifier}" if total_modifier >= 0 else str(total_modifier)

        # Build roll summary based on whether dice were rolled
        if result.is_auto_success:
            roll_summary = f"Auto-success (DC {dc} ≤ {10 + total_modifier})"
            roll_total = None
            dice_rolls = None
        else:
            roll_result = result.roll_result
            dice_rolls = list(roll_result.individual_rolls)
            roll_total = roll_result.total
            # Format: "Roll: (5+8) +5 = 18 vs DC 15"
            dice_str = "+".join(str(d) for d in dice_rolls)
            roll_summary = f"Roll: ({dice_str}) {modifier_str} = {roll_total} vs DC {dc}"

        return {
            "entity_key": entity_key,
            "skill_name": skill_name,
            "description": check_description,
            "dc": dc,
            "success": result.success,
            "roll": roll_total,
            "dice_rolls": dice_rolls,  # 2d10 individual dice (or None for auto-success)
            "margin": result.margin,
            "is_critical_success": result.is_critical_success,
            "is_critical_failure": result.is_critical_failure,
            "is_auto_success": result.is_auto_success,
            "outcome": outcome,
            "outcome_tier": result.outcome_tier.value,
            # Modifier breakdown
            "attribute_key": attribute_key,
            "attribute_score": attribute_score,
            "attribute_modifier": attribute_modifier,
            "proficiency_level": proficiency_level,
            "skill_modifier": skill_modifier,
            "skill_tier": skill_tier,
            "total_modifier": total_modifier,
            "modifier_string": modifier_str,
            # Assessment (for player-facing display)
            "difficulty_assessment": difficulty_assessment,
            "roll_summary": roll_summary,
        }

    def _execute_attack_roll(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute an attack roll.

        Args:
            args: Tool arguments with target_ac, attack_bonus, advantage.

        Returns:
            Result with hit, roll, and critical status.
        """
        target_ac = args["target_ac"]
        attack_bonus = args.get("attack_bonus", 0)
        advantage_str = args.get("advantage", "normal")

        advantage_type = self._parse_advantage(advantage_str)

        result = make_attack_roll(
            target_ac=target_ac,
            attack_bonus=attack_bonus,
            advantage_type=advantage_type,
        )

        return {
            "hit": result.hit,
            "roll": result.roll_result.total,
            "natural_roll": result.roll_result.individual_rolls[0],
            "is_critical_hit": result.is_critical_hit,
            "is_critical_miss": result.is_critical_miss,
            "target_ac": target_ac,
        }

    def _execute_roll_damage(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a damage roll.

        Args:
            args: Tool arguments with damage_dice, damage_type, bonus, is_critical.

        Returns:
            Result with total, dice breakdown, and damage type.
        """
        damage_dice = args["damage_dice"]
        damage_type = args.get("damage_type", "untyped")
        bonus = args.get("bonus", 0)
        is_critical = args.get("is_critical", False)

        result = roll_damage(
            damage_dice=damage_dice,
            damage_type=damage_type,
            bonus=bonus,
            is_critical=is_critical,
        )

        return {
            "total": result.roll_result.total,
            "dice_rolls": list(result.roll_result.individual_rolls),
            "damage_type": result.damage_type,
            "is_critical": result.is_critical,
        }

    def _execute_get_npc_attitude(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get NPC attitude toward another entity.

        Args:
            args: Tool arguments with from_entity, to_entity (entity keys).

        Returns:
            Attitude dimensions or error.
        """
        from_key = args["from_entity"]
        to_key = args["to_entity"]

        # Look up entities by key
        from_entity = self._get_entity_by_key(from_key)
        to_entity = self._get_entity_by_key(to_key)

        if from_entity is None:
            return {"error": f"Entity '{from_key}' not found"}
        if to_entity is None:
            return {"error": f"Entity '{to_key}' not found"}

        attitude = self.relationship_manager.get_attitude(from_entity.id, to_entity.id)

        return {
            "from_entity": from_key,
            "to_entity": to_key,
            "trust": attitude["trust"],
            "liking": attitude["liking"],
            "respect": attitude["respect"],
            "romantic_interest": attitude["romantic_interest"],
            "familiarity": attitude["familiarity"],
            "fear": attitude["fear"],
            "knows": attitude["knows"],
        }

    def _execute_update_npc_attitude(self, args: dict[str, Any]) -> dict[str, Any]:
        """Update NPC attitude toward another entity.

        Args:
            args: Tool arguments with from_entity, to_entity, dimension, delta, reason.

        Returns:
            New value and delta applied.
        """
        from_key = args["from_entity"]
        to_key = args["to_entity"]
        dimension = args["dimension"]
        delta = args["delta"]
        reason = args["reason"]

        # Look up entities by key
        from_entity = self._get_entity_by_key(from_key)
        to_entity = self._get_entity_by_key(to_key)

        if from_entity is None:
            return {"error": f"Entity '{from_key}' not found"}
        if to_entity is None:
            return {"error": f"Entity '{to_key}' not found"}

        # Get old value for delta calculation
        old_attitude = self.relationship_manager.get_attitude(from_entity.id, to_entity.id)
        old_value = old_attitude.get(dimension, 50)

        # Update attitude
        self.relationship_manager.update_attitude(
            from_id=from_entity.id,
            to_id=to_entity.id,
            dimension=dimension,
            delta=delta,
            reason=reason,
        )

        # Get new value
        new_attitude = self.relationship_manager.get_attitude(from_entity.id, to_entity.id)
        new_value = new_attitude.get(dimension, 50)

        return {
            "from_entity": from_key,
            "to_entity": to_key,
            "dimension": dimension,
            "old_value": old_value,
            "new_value": new_value,
            "delta": new_value - old_value,
            "reason": reason,
        }

    def _get_entity_by_key(self, entity_key: str) -> Entity | None:
        """Look up an entity by its entity_key.

        Args:
            entity_key: The entity's unique key.

        Returns:
            Entity or None if not found.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

    def _parse_advantage(self, advantage_str: str) -> AdvantageType:
        """Parse advantage string to enum.

        Args:
            advantage_str: One of "normal", "advantage", "disadvantage".

        Returns:
            AdvantageType enum value.
        """
        mapping = {
            "normal": AdvantageType.NORMAL,
            "advantage": AdvantageType.ADVANTAGE,
            "disadvantage": AdvantageType.DISADVANTAGE,
        }
        return mapping.get(advantage_str, AdvantageType.NORMAL)

    def _execute_satisfy_need(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute need satisfaction with preference modifiers.

        Args:
            args: Tool arguments with entity_key, need_name, action_type, quality, base_amount.

        Returns:
            Result with amount satisfied, modifiers applied, new value.
        """
        from src.database.models.character_preferences import CharacterPreferences
        from src.managers.needs import (
            NeedsManager,
            estimate_base_satisfaction,
            get_preference_multiplier,
        )

        entity_key = args["entity_key"]
        need_name = args["need_name"]
        action_type = args["action_type"]
        quality = args.get("quality", "basic")
        base_amount = args.get("base_amount")

        # Get entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"error": f"Entity '{entity_key}' not found"}

        # Initialize needs manager
        needs_mgr = NeedsManager(self.db, self.game_session)

        # If base_amount not provided, estimate from action_type
        if base_amount is None:
            base_amount = estimate_base_satisfaction(need_name, action_type, quality)

        # Get character preferences for preference multiplier
        prefs = (
            self.db.query(CharacterPreferences)
            .filter(
                CharacterPreferences.entity_id == entity.id,
                CharacterPreferences.session_id == self.game_session.id,
            )
            .first()
        )

        # Get satisfaction multiplier from NeedModifier (system-level)
        satisfaction_mult = needs_mgr.get_satisfaction_multiplier(entity.id, need_name)

        # Get preference-based multiplier (context-specific)
        pref_mult = get_preference_multiplier(prefs, need_name, action_type, quality)

        # Calculate final amount (preference multiplier applied here, satisfaction_mult applied in satisfy_need)
        # Note: satisfy_need already applies satisfaction_mult, so we only apply pref_mult here
        adjusted_amount = int(base_amount * pref_mult)

        # Get old value
        old_needs = needs_mgr.get_needs(entity.id)
        old_value = getattr(old_needs, need_name) if old_needs else 50

        # Apply satisfaction (satisfy_need will apply satisfaction_mult internally)
        new_needs = needs_mgr.satisfy_need(
            entity.id,
            need_name,
            adjusted_amount,
            turn=self.game_session.total_turns,
        )
        new_value = getattr(new_needs, need_name)

        return {
            "entity_key": entity_key,
            "need_name": need_name,
            "action_type": action_type,
            "quality": quality,
            "base_amount": base_amount,
            "preference_multiplier": round(pref_mult, 2),
            "satisfaction_multiplier": round(satisfaction_mult, 2),
            "final_amount": int(adjusted_amount * satisfaction_mult),
            "old_value": old_value,
            "new_value": new_value,
            "delta": new_value - old_value,
        }

    def _execute_apply_stimulus(self, args: dict[str, Any]) -> dict[str, Any]:
        """Apply a stimulus effect to character needs (craving boost).

        Args:
            args: Tool arguments with entity_key, stimulus_type, stimulus_description,
                  intensity, memory_emotion.

        Returns:
            Result with need affected, craving boost applied, and effects.
        """
        from src.managers.needs import NeedsManager

        entity_key = args["entity_key"]
        stimulus_type = args["stimulus_type"]
        stimulus_description = args["stimulus_description"]
        intensity = args.get("intensity", "moderate")
        memory_emotion = args.get("memory_emotion")

        # Get entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"error": f"Entity '{entity_key}' not found"}

        # Map intensity to relevance factor
        intensity_map = {
            "mild": 0.3,
            "moderate": 0.6,
            "strong": 0.9,
        }
        relevance = intensity_map.get(intensity, 0.6)

        # Map stimulus type to need
        stimulus_to_need = {
            "food_sight": "hunger",
            "drink_sight": "thirst",
            "rest_opportunity": "energy",
            "social_atmosphere": "social_connection",
            "intimacy_trigger": "intimacy",
            "memory_trigger": None,  # Affects morale, not a specific need
        }

        need_affected = stimulus_to_need.get(stimulus_type)
        needs_mgr = NeedsManager(self.db, self.game_session)

        result: dict[str, Any] = {
            "entity_key": entity_key,
            "stimulus_type": stimulus_type,
            "stimulus_description": stimulus_description,
            "intensity": intensity,
        }

        if need_affected:
            # Apply craving boost to the need
            craving_boost = needs_mgr.apply_craving(entity.id, need_affected, relevance)
            result["need_affected"] = need_affected
            result["craving_boost"] = craving_boost
            result["message"] = (
                f"Applied {intensity} {stimulus_type} stimulus. "
                f"{need_affected} craving boosted by {craving_boost}."
            )
        elif stimulus_type == "memory_trigger":
            # Memory triggers affect morale directly
            # Negative emotions reduce morale, positive ones boost it
            needs = needs_mgr.get_needs(entity.id)
            if needs:
                negative_emotions = ["grief", "fear", "anger", "shame", "guilt", "sadness"]
                positive_emotions = ["joy", "pride", "love", "nostalgia", "hope"]

                morale_change = 0
                if memory_emotion:
                    emotion_lower = memory_emotion.lower()
                    if any(neg in emotion_lower for neg in negative_emotions):
                        morale_change = -int(relevance * 15)  # Up to -15 morale
                    elif any(pos in emotion_lower for pos in positive_emotions):
                        morale_change = int(relevance * 10)  # Up to +10 morale

                if morale_change != 0:
                    old_morale = needs.morale
                    needs.morale = max(0, min(100, needs.morale + morale_change))
                    self.db.flush()

                    result["memory_emotion"] = memory_emotion
                    result["morale_change"] = morale_change
                    result["old_morale"] = old_morale
                    result["new_morale"] = needs.morale
                    result["message"] = (
                        f"Memory trigger ({memory_emotion}) affected morale: "
                        f"{old_morale} → {needs.morale}."
                    )
                else:
                    result["message"] = f"Memory trigger noted but had no mechanical effect."
        else:
            result["message"] = f"Unknown stimulus type: {stimulus_type}"

        return result

    def _execute_mark_need_communicated(self, args: dict[str, Any]) -> dict[str, Any]:
        """Mark that a need was communicated to the player in the narration.

        This prevents repetitive mentions of the same need state. The system will
        avoid alerting the GM about this need until the state changes or significant
        time passes.

        Args:
            args: Tool arguments with entity_key and need_name.

        Returns:
            Confirmation of the communication record.
        """
        from src.database.models.world import TimeState
        from src.managers.needs import NeedsManager
        from src.managers.needs_communication_manager import NeedsCommunicationManager

        entity_key = args["entity_key"]
        need_name = args["need_name"]

        # Get entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"error": f"Entity '{entity_key}' not found"}

        # Get current needs to record the state
        needs_mgr = NeedsManager(self.db, self.game_session)
        needs = needs_mgr.get_needs(entity.id)
        if needs is None:
            return {"error": f"No needs record for entity '{entity_key}'"}

        # Get current need value
        need_value = getattr(needs, need_name, None)
        if need_value is None:
            return {"error": f"Unknown need: {need_name}"}

        # Get game time
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.game_session.id)
            .first()
        )

        # Construct game datetime
        if time_state:
            from datetime import datetime
            hour, minute = 8, 0
            if time_state.current_time:
                parts = time_state.current_time.split(":")
                if len(parts) >= 2:
                    hour = int(parts[0])
                    minute = int(parts[1])
            game_time = datetime(2000, 1, time_state.current_day, hour, minute)
        else:
            from datetime import datetime
            game_time = datetime(2000, 1, 1, 8, 0)

        # Get state label
        comm_mgr = NeedsCommunicationManager(self.db, self.game_session)
        state_label, _ = comm_mgr.get_state_label(need_name, need_value)

        # Record the communication
        comm_mgr.record_communication(
            entity_id=entity.id,
            need_name=need_name,
            value=need_value,
            state_label=state_label,
            game_time=game_time,
            turn=self.game_session.total_turns,
        )

        return {
            "entity_key": entity_key,
            "need_name": need_name,
            "recorded_value": need_value,
            "recorded_state": state_label,
            "turn": self.game_session.total_turns,
            "message": f"Recorded communication of {need_name} ({state_label}) for {entity_key}.",
        }

    # =========================================================================
    # Navigation Tool Handlers
    # =========================================================================

    def _execute_check_route(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check the optimal route and travel time between zones.

        Args:
            args: Tool arguments with from_zone, to_zone, transport_mode.

        Returns:
            Route info including path, travel time, and hazards.
        """
        from_zone = args.get("from_zone") or self.current_zone_key
        to_zone = args["to_zone"]
        transport_mode = args.get("transport_mode", "walking")

        if from_zone is None:
            return {"error": "No starting zone specified and current zone unknown"}

        # Check destination is known
        if not self.discovery_manager.is_zone_discovered(to_zone):
            return {"error": f"Destination '{to_zone}' is unknown - it must be discovered first"}

        result = self.pathfinding_manager.find_optimal_path(
            from_zone_key=from_zone,
            to_zone_key=to_zone,
            transport_mode_key=transport_mode,
        )

        if not result["found"]:
            return {
                "error": f"No route found to '{to_zone}' via {transport_mode}",
                "reason": result.get("reason", "Destination may be inaccessible"),
            }

        # Get route summary with hazards
        summary = self.pathfinding_manager.get_route_summary(result["path"], transport_mode)

        return {
            "from_zone": from_zone,
            "to_zone": to_zone,
            "transport_mode": transport_mode,
            "total_travel_minutes": result["total_cost"],
            "zones_traversed": len(result["path"]),
            "path": [z.display_name for z in result["path"]],
            "hazards": summary.get("hazards", []),
            "skill_checks_required": summary.get("skill_checks", []),
        }

    def _execute_start_travel(self, args: dict[str, Any]) -> dict[str, Any]:
        """Start a journey to a destination zone.

        Args:
            args: Tool arguments with to_zone, transport_mode, prefer_roads.

        Returns:
            Journey initiation result.
        """
        from src.managers.travel_manager import TravelManager

        to_zone = args["to_zone"]
        transport_mode = args.get("transport_mode", "walking")
        prefer_roads = args.get("prefer_roads", False)

        if self.current_zone_key is None:
            return {"error": "Current zone unknown - cannot start journey"}

        # Check destination is known
        if not self.discovery_manager.is_zone_discovered(to_zone):
            return {"error": f"Destination '{to_zone}' is unknown - it must be discovered first"}

        travel_mgr = TravelManager(self.db, self.game_session)

        result = travel_mgr.start_journey(
            from_zone_key=self.current_zone_key,
            to_zone_key=to_zone,
            transport_mode=transport_mode,
            prefer_roads=prefer_roads,
        )

        if not result["success"]:
            return {"error": result.get("reason", "Failed to start journey")}

        journey = result["journey"]
        return {
            "started": True,
            "destination": to_zone,
            "transport_mode": transport_mode,
            "estimated_minutes": journey.estimated_total_minutes,
            "zones_to_traverse": len(journey.path),
            "current_zone": journey.current_zone_key,
            "message": f"Journey to {to_zone} started. Estimated travel time: {journey.estimated_total_minutes} minutes.",
        }

    def _execute_move_to_zone(self, args: dict[str, Any]) -> dict[str, Any]:
        """Move to an adjacent zone immediately.

        Args:
            args: Tool arguments with zone_key, transport_mode.

        Returns:
            Movement result.
        """
        zone_key = args["zone_key"]
        transport_mode = args.get("transport_mode", "walking")

        if self.current_zone_key is None:
            return {"error": "Current zone unknown - cannot move"}

        # Check zone is adjacent
        adjacent_data = self.zone_manager.get_adjacent_zones_with_directions(self.current_zone_key)
        adjacent_keys = [item["zone"].zone_key for item in adjacent_data]

        if zone_key not in adjacent_keys:
            return {
                "error": f"'{zone_key}' is not adjacent to current zone",
                "adjacent_zones": adjacent_keys,
            }

        # Check accessibility
        accessibility = self.zone_manager.check_accessibility(zone_key, transport_mode)

        if not accessibility["can_enter"]:
            return {
                "error": f"Cannot enter '{zone_key}' via {transport_mode}",
                "reason": accessibility.get("reason", "Terrain is impassable"),
                "required_skill": accessibility.get("requires_skill"),
            }

        # Auto-discover surroundings on arrival
        discovery_result = self.discovery_manager.auto_discover_surroundings(zone_key)

        zone = self.zone_manager.get_zone(zone_key)
        travel_cost = self.zone_manager.get_terrain_cost(zone_key, transport_mode)

        return {
            "moved": True,
            "new_zone": zone_key,
            "zone_name": zone.display_name if zone else zone_key,
            "terrain": zone.terrain_type.value if zone and zone.terrain_type else "unknown",
            "travel_minutes": travel_cost,
            "new_discoveries": {
                "zones": discovery_result.get("adjacent_zones_discovered", []),
                "locations": discovery_result.get("locations_discovered", []),
            },
        }

    def _execute_check_terrain(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check terrain accessibility and requirements.

        Args:
            args: Tool arguments with zone_key, transport_mode.

        Returns:
            Terrain accessibility info.
        """
        zone_key = args["zone_key"]
        transport_mode = args.get("transport_mode", "walking")

        zone = self.zone_manager.get_zone(zone_key)
        if zone is None:
            return {"error": f"Zone '{zone_key}' not found"}

        accessibility = self.zone_manager.check_accessibility(zone_key, transport_mode)

        return {
            "zone_key": zone_key,
            "zone_name": zone.display_name,
            "terrain_type": zone.terrain_type.value if zone.terrain_type else "unknown",
            "transport_mode": transport_mode,
            "can_enter": accessibility["can_enter"],
            "reason": accessibility.get("reason"),
            "requires_skill": accessibility.get("requires_skill"),
            "skill_difficulty": accessibility.get("skill_difficulty"),
            "failure_consequence": zone.failure_consequence,
            "travel_cost": accessibility.get("travel_cost"),
        }

    def _execute_discover_zone(self, args: dict[str, Any]) -> dict[str, Any]:
        """Mark a zone as discovered.

        Args:
            args: Tool arguments with zone_key, discovery_method, source_entity.

        Returns:
            Discovery result.
        """
        zone_key = args["zone_key"]
        method_str = args["discovery_method"]
        source_entity = args.get("source_entity")

        # Map string to enum
        method_map = {
            "told_by_npc": DiscoveryMethod.TOLD_BY_NPC,
            "map_viewed": DiscoveryMethod.MAP_VIEWED,
            "visible_from": DiscoveryMethod.VISIBLE_FROM,
            "visited": DiscoveryMethod.VISITED,
        }
        method = method_map.get(method_str, DiscoveryMethod.VISITED)

        result = self.discovery_manager.discover_zone(
            zone_key=zone_key,
            method=method,
            source_entity_key=source_entity,
        )

        if not result["success"]:
            return {"error": result.get("reason", f"Failed to discover zone '{zone_key}'")}

        zone = result.get("zone")
        return {
            "discovered": result["newly_discovered"],
            "zone_key": zone_key,
            "zone_name": zone.display_name if zone else zone_key,
            "method": method_str,
            "already_known": not result["newly_discovered"],
        }

    def _execute_discover_location(self, args: dict[str, Any]) -> dict[str, Any]:
        """Mark a location as discovered.

        Args:
            args: Tool arguments with location_key, discovery_method, source_entity.

        Returns:
            Discovery result.
        """
        location_key = args["location_key"]
        method_str = args["discovery_method"]
        source_entity = args.get("source_entity")

        # Map string to enum
        method_map = {
            "told_by_npc": DiscoveryMethod.TOLD_BY_NPC,
            "map_viewed": DiscoveryMethod.MAP_VIEWED,
            "visible_from": DiscoveryMethod.VISIBLE_FROM,
            "visited": DiscoveryMethod.VISITED,
        }
        method = method_map.get(method_str, DiscoveryMethod.VISITED)

        result = self.discovery_manager.discover_location(
            location_key=location_key,
            method=method,
            source_entity_key=source_entity,
        )

        if not result["success"]:
            return {"error": result.get("reason", f"Failed to discover location '{location_key}'")}

        location = result.get("location")
        return {
            "discovered": result["newly_discovered"],
            "location_key": location_key,
            "location_name": location.display_name if location else location_key,
            "method": method_str,
            "already_known": not result["newly_discovered"],
        }

    def _execute_view_map(self, args: dict[str, Any]) -> dict[str, Any]:
        """View a map item and discover its contents.

        Args:
            args: Tool arguments with item_key, viewer_entity_key.

        Returns:
            Result with zones and locations discovered.
        """
        from src.managers.map_manager import MapManager

        item_key = args["item_key"]
        viewer_entity_key = args.get("viewer_entity_key", "player")

        # Verify viewer entity exists
        viewer = self._get_entity_by_key(viewer_entity_key)
        if viewer is None:
            return {"error": f"Viewer entity '{viewer_entity_key}' not found"}

        # Use discovery manager's view_map method
        result = self.discovery_manager.view_map(item_key)

        if not result["success"]:
            return {
                "error": result.get("reason", f"Failed to view map '{item_key}'"),
                "success": False,
            }

        # Get map details for richer response
        map_manager = MapManager(self.db, self.game_session)
        map_info = map_manager.get_map_item(item_key)

        return {
            "success": True,
            "item_key": item_key,
            "viewer": viewer_entity_key,
            "map_type": result.get("map_type", "unknown"),
            "zones_discovered": result["zones_discovered"],
            "locations_discovered": result["locations_discovered"],
            "total_zones_discovered": len(result["zones_discovered"]),
            "total_locations_discovered": len(result["locations_discovered"]),
            "is_complete": map_info.get("is_complete", True) if map_info else True,
            "message": (
                f"Discovered {len(result['zones_discovered'])} zones and "
                f"{len(result['locations_discovered'])} locations from the map."
                if result["zones_discovered"] or result["locations_discovered"]
                else "No new areas discovered (already known or map is empty)."
            ),
        }

    # =========================================================================
    # NPC Creation/Query Tool Handlers
    # =========================================================================

    def _execute_create_npc(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a new NPC with emergent traits.

        Args:
            args: Tool arguments with role, location_key, and optional constraints.

        Returns:
            Full NPC state including appearance, personality, and environmental reactions.
        """
        role = args["role"]
        location_key = args["location_key"]

        # Build constraints from optional arguments
        constraints = None
        constraint_args = {
            "name": args.get("constraint_name"),
            "gender": args.get("constraint_gender"),
            "age_range": args.get("constraint_age_range"),
            "occupation": args.get("constraint_occupation"),
            "personality": args.get("constraint_personality"),
            "hostile_to_player": args.get("constraint_hostile"),
            "friendly_to_player": args.get("constraint_friendly"),
            "attracted_to_player": args.get("constraint_attracted"),
        }

        # Only create constraints if any were provided
        if any(v is not None for v in constraint_args.values()):
            constraints = NPCConstraints(**{k: v for k, v in constraint_args.items() if v is not None})

        # Ensure we have a scene context
        scene_context = self.scene_context
        if scene_context is None:
            # Create minimal scene context if not provided
            scene_context = SceneContext(
                location_key=location_key,
                location_description="Unknown location",
                entities_present=["player"],
            )

        try:
            # Create the NPC
            npc_state = self.npc_generator.create_npc(
                role=role,
                location_key=location_key,
                scene_context=scene_context,
                constraints=constraints,
            )

            # Convert to dict for LLM
            return {
                "success": True,
                "entity_key": npc_state.entity_key,
                "display_name": npc_state.display_name,
                # Appearance for description
                "appearance": {
                    "age": npc_state.appearance.age,
                    "age_description": npc_state.appearance.age_description,
                    "gender": npc_state.appearance.gender,
                    "height_description": npc_state.appearance.height_description,
                    "build": npc_state.appearance.build,
                    "hair": npc_state.appearance.hair,
                    "eyes": npc_state.appearance.eyes,
                    "skin": npc_state.appearance.skin,
                    "notable_features": npc_state.appearance.notable_features,
                    "clothing": npc_state.appearance.clothing,
                    "voice": npc_state.appearance.voice,
                },
                # Background
                "background": {
                    "occupation": npc_state.background.occupation,
                    "occupation_years": npc_state.background.occupation_years,
                    "background_summary": npc_state.background.background_summary,
                },
                # Personality (what GM needs to know)
                "personality": {
                    "traits": npc_state.personality.traits,
                    "values": npc_state.personality.values,
                    "flaws": npc_state.personality.flaws,
                    "quirks": npc_state.personality.quirks,
                    "speech_pattern": npc_state.personality.speech_pattern,
                },
                # Current state
                "current_state": {
                    "mood": npc_state.current_state.mood,
                    "activity": npc_state.current_state.current_activity,
                    "location": npc_state.current_state.current_location,
                },
                # Needs (urgency levels, higher = more urgent)
                "current_needs": {
                    "hunger": npc_state.current_needs.hunger,
                    "thirst": npc_state.current_needs.thirst,
                    "fatigue": npc_state.current_needs.fatigue,
                    "social": npc_state.current_needs.social,
                },
                # Environmental reactions (IMPORTANT for GM)
                "environmental_reactions": [
                    {
                        "notices": r.notices,
                        "reaction_type": r.reaction_type,
                        "need_triggered": r.need_triggered,
                        "intensity": r.intensity,
                        "attraction_score": {
                            "physical": r.attraction_score.physical,
                            "personality": r.attraction_score.personality,
                            "overall": r.attraction_score.overall,
                        } if r.attraction_score else None,
                        "internal_thought": r.internal_thought,
                        "likely_behavior": r.likely_behavior,
                    }
                    for r in npc_state.environmental_reactions
                ],
                # Goals
                "immediate_goals": [
                    {"goal": g.goal, "priority": g.priority}
                    for g in npc_state.immediate_goals
                ],
                # Behavioral guidance for GM
                "behavioral_prediction": npc_state.behavioral_prediction,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create NPC: {str(e)}",
            }

    def _execute_query_npc(self, args: dict[str, Any]) -> dict[str, Any]:
        """Query an existing NPC's current state and reactions.

        Args:
            args: Tool arguments with entity_key.

        Returns:
            Updated NPC reactions and behavioral prediction.
        """
        entity_key = args["entity_key"]

        # Ensure we have a scene context
        scene_context = self.scene_context
        if scene_context is None:
            # Try to build from current zone
            scene_context = SceneContext(
                location_key=self.current_zone_key or "unknown",
                location_description="Unknown location",
                entities_present=["player"],
            )

        try:
            reactions = self.npc_generator.query_npc_reactions(
                entity_key=entity_key,
                scene_context=scene_context,
            )

            if reactions is None:
                return {
                    "success": False,
                    "error": f"NPC '{entity_key}' not found",
                }

            return {
                "success": True,
                "entity_key": reactions.entity_key,
                "current_mood": reactions.current_mood,
                "current_needs": {
                    "hunger": reactions.current_needs.hunger,
                    "thirst": reactions.current_needs.thirst,
                    "fatigue": reactions.current_needs.fatigue,
                    "social": reactions.current_needs.social,
                },
                "environmental_reactions": [
                    {
                        "notices": r.notices,
                        "reaction_type": r.reaction_type,
                        "need_triggered": r.need_triggered,
                        "intensity": r.intensity,
                        "attraction_score": {
                            "physical": r.attraction_score.physical,
                            "personality": r.attraction_score.personality,
                            "overall": r.attraction_score.overall,
                        } if r.attraction_score else None,
                        "internal_thought": r.internal_thought,
                        "likely_behavior": r.likely_behavior,
                    }
                    for r in reactions.environmental_reactions
                ],
                "behavioral_prediction": reactions.behavioral_prediction,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to query NPC: {str(e)}",
            }

    # =========================================================================
    # Item Creation Tool Handlers
    # =========================================================================

    def _execute_create_item(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a new item with emergent properties.

        Args:
            args: Tool arguments with item_type, context, location_key, and optional constraints.

        Returns:
            Full item state including quality, condition, value, and narrative hooks.
        """
        from src.services.emergent_item_generator import ItemConstraints

        item_type = args["item_type"]
        context = args["context"]
        location_key = args["location_key"]

        # Get owner entity ID if specified
        owner_entity_id = None
        owner_entity_key = args.get("owner_entity_key")
        if owner_entity_key:
            owner_entity = self._get_entity_by_key(owner_entity_key)
            if owner_entity:
                owner_entity_id = owner_entity.id
            else:
                return {
                    "success": False,
                    "error": f"Owner entity '{owner_entity_key}' not found",
                }

        # Build constraints from optional arguments
        constraints = None
        constraint_args = {
            "name": args.get("constraint_name"),
            "quality": args.get("constraint_quality"),
            "condition": args.get("constraint_condition"),
            "has_history": args.get("constraint_has_history"),
        }

        # Only create constraints if any were provided
        if any(v is not None for v in constraint_args.values()):
            constraints = ItemConstraints(**{k: v for k, v in constraint_args.items() if v is not None})

        try:
            item_state = self.item_generator.create_item(
                item_type=item_type,
                context=context,
                location_key=location_key,
                owner_entity_id=owner_entity_id,
                constraints=constraints,
            )

            return {
                "success": True,
                "item_key": item_state.item_key,
                "display_name": item_state.display_name,
                "item_type": item_state.item_type,
                "description": item_state.description,
                # Physical properties
                "quality": item_state.quality,
                "condition": item_state.condition,
                # Value info
                "estimated_value": item_state.estimated_value,
                "value_description": item_state.value_description,
                # History (may be None)
                "age_description": item_state.age_description,
                "provenance": item_state.provenance,
                # Special properties
                "properties": item_state.properties,
                # Need triggers (for NPCs noticing this item)
                "need_triggers": item_state.need_triggers,
                # Narrative hooks
                "narrative_hooks": item_state.narrative_hooks,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create item: {str(e)}",
            }

    # =========================================================================
    # Item Acquisition Tool Handlers
    # =========================================================================

    def _execute_acquire_item(self, args: dict[str, Any]) -> dict[str, Any]:
        """Acquire item with slot/weight validation.

        Args:
            args: Tool arguments with entity_key, display_name, item_type,
                  optional slot, item_size, description, weight, quantity.

        Returns:
            Result with success status, item details, or failure reason.
        """
        from src.database.models.enums import ItemType

        entity_key = args["entity_key"]
        display_name = args["display_name"]
        item_type_str = args["item_type"]
        item_key = args.get("item_key")
        slot = args.get("slot")
        item_size = args.get("item_size", "small")
        description = args.get("description")
        weight = args.get("weight", 0)
        quantity = args.get("quantity", 1)

        # Get entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"success": False, "error": f"Entity '{entity_key}' not found"}

        # Initialize item manager
        item_mgr = ItemManager(self.db, self.game_session)

        # If slot not specified, auto-find one
        if slot is None:
            slot = item_mgr.find_available_slot(entity.id, item_type_str, item_size)
            if slot is None:
                # Get inventory summary for context
                summary = item_mgr.get_inventory_summary(entity.id)
                return {
                    "success": False,
                    "reason": "No available slot - inventory full",
                    "occupied_slots": summary["occupied_slots"],
                    "suggestion": "Put something down first or find a container",
                }

        # Check slot availability (if specific slot requested)
        if not item_mgr.check_slot_available(entity.id, slot):
            occupied_by = item_mgr.get_item_in_slot(entity.id, slot)
            return {
                "success": False,
                "reason": f"Slot '{slot}' is occupied",
                "occupied_by": occupied_by.display_name if occupied_by else "unknown item",
                "suggestion": f"Drop the {occupied_by.display_name if occupied_by else 'item'} first",
            }

        # Check weight capacity
        total_weight = weight * quantity
        if total_weight > 0 and not item_mgr.can_carry_weight(entity.id, total_weight):
            current = item_mgr.get_total_carried_weight(entity.id)
            return {
                "success": False,
                "reason": "Too heavy - exceeds carrying capacity",
                "current_weight": current,
                "item_weight": total_weight,
                "max_weight": 50.0,
                "suggestion": "Drop something heavy first",
            }

        # Generate item key if not provided
        if not item_key:
            # Create key from display name
            import re
            base_key = re.sub(r'[^a-z0-9]+', '_', display_name.lower()).strip('_')
            item_key = f"{entity_key}_{base_key}"

        # Check if item already exists
        existing_item = item_mgr.get_item(item_key)
        if existing_item:
            # Transfer existing item to entity
            existing_item.holder_id = entity.id
            existing_item.owner_id = entity.id
            existing_item.body_slot = slot
            self.db.flush()
            return {
                "success": True,
                "item_key": existing_item.item_key,
                "display_name": existing_item.display_name,
                "assigned_slot": slot,
                "was_existing": True,
                "message": f"{entity.display_name} now has {existing_item.display_name} in {slot}",
            }

        # Map string item_type to enum
        try:
            item_type = ItemType(item_type_str)
        except ValueError:
            item_type = ItemType.MISC

        # Create new item
        try:
            item = item_mgr.create_item(
                item_key=item_key,
                display_name=display_name,
                item_type=item_type,
                owner_id=entity.id,
                holder_id=entity.id,
                description=description,
                weight=weight if weight > 0 else None,
                quantity=quantity,
                is_stackable=quantity > 1,
            )

            # Assign to slot
            item.body_slot = slot
            self.db.flush()

            return {
                "success": True,
                "item_key": item.item_key,
                "display_name": item.display_name,
                "assigned_slot": slot,
                "was_existing": False,
                "message": f"{entity.display_name} acquired {item.display_name} in {slot}",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create item: {str(e)}",
            }

    def _execute_drop_item(self, args: dict[str, Any]) -> dict[str, Any]:
        """Drop or transfer an item.

        Args:
            args: Tool arguments with entity_key, item_key, optional transfer_to.

        Returns:
            Result with success status or error.
        """
        entity_key = args["entity_key"]
        item_key = args["item_key"]
        transfer_to = args.get("transfer_to")

        # Get entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"success": False, "error": f"Entity '{entity_key}' not found"}

        # Initialize item manager
        item_mgr = ItemManager(self.db, self.game_session)

        # Get the item
        item = item_mgr.get_item(item_key)
        if item is None:
            return {"success": False, "error": f"Item '{item_key}' not found"}

        # Verify entity has the item
        if item.holder_id != entity.id:
            return {
                "success": False,
                "error": f"{entity.display_name} is not holding {item.display_name}",
            }

        if transfer_to:
            # Transfer to another entity
            target = self._get_entity_by_key(transfer_to)
            if target is None:
                return {"success": False, "error": f"Target entity '{transfer_to}' not found"}

            # Check if target can receive it
            target_slot = item_mgr.find_available_slot(
                target.id, item.item_type.value if item.item_type else "misc"
            )
            if target_slot is None:
                return {
                    "success": False,
                    "reason": f"{target.display_name} cannot carry more items",
                    "suggestion": "They need to free up a slot first",
                }

            item.holder_id = target.id
            item.body_slot = target_slot
            self.db.flush()

            return {
                "success": True,
                "item_key": item.item_key,
                "display_name": item.display_name,
                "from_entity": entity_key,
                "to_entity": transfer_to,
                "new_slot": target_slot,
                "message": f"{entity.display_name} gave {item.display_name} to {target.display_name}",
            }
        else:
            # Drop on ground
            item.holder_id = None
            item.body_slot = None
            self.db.flush()

            return {
                "success": True,
                "item_key": item.item_key,
                "display_name": item.display_name,
                "from_entity": entity_key,
                "dropped": True,
                "message": f"{entity.display_name} dropped {item.display_name}",
            }

    # =========================================================================
    # World Spawning Tool Handlers
    # =========================================================================

    def _execute_spawn_storage(self, args: dict[str, Any]) -> dict[str, Any]:
        """Spawn a storage surface at the current location.

        Creates furniture like tables, shelves, chests that can hold items.

        Args:
            args: Tool arguments with container_type, optional description, storage_key.

        Returns:
            Result with storage_key and success status.
        """
        from src.managers.location_manager import LocationManager

        container_type = args["container_type"]
        description = args.get("description")
        storage_key = args.get("storage_key")
        is_fixed = args.get("is_fixed", True)
        capacity = args.get("capacity", 20)

        # Get current player location
        if self.current_zone_key is None:
            return {"success": False, "error": "Current location unknown"}

        # Get or create Location record
        location_mgr = LocationManager(self.db, self.game_session)
        location = location_mgr.get_location(self.current_zone_key)

        if location is None:
            # Create a basic location record if it doesn't exist
            from src.database.models.world import Location
            location = Location(
                session_id=self.game_session.id,
                location_key=self.current_zone_key,
                display_name=self.current_zone_key.replace("_", " ").title(),
                description=description or f"A location with a {container_type}",
            )
            self.db.add(location)
            self.db.flush()

        # Generate storage key if not provided
        if not storage_key:
            # Count existing storage of this type at location
            existing_count = (
                self.db.query(StorageLocation)
                .filter(
                    StorageLocation.session_id == self.game_session.id,
                    StorageLocation.world_location_id == location.id,
                    StorageLocation.container_type == container_type,
                )
                .count()
            )
            storage_key = f"{self.current_zone_key}_{container_type}_{existing_count + 1}"

        # Check if storage with this key already exists
        existing = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.game_session.id,
                StorageLocation.location_key == storage_key,
            )
            .first()
        )
        if existing:
            return {
                "success": False,
                "error": f"Storage '{storage_key}' already exists at this location",
                "existing_key": existing.location_key,
            }

        # Create storage location
        item_mgr = ItemManager(self.db, self.game_session)
        storage = item_mgr.create_storage(
            location_key=storage_key,
            location_type=StorageLocationType.PLACE,
            container_type=container_type,
            world_location_id=location.id,
            is_fixed=is_fixed,
            capacity=capacity,
        )

        return {
            "success": True,
            "storage_key": storage.location_key,
            "container_type": container_type,
            "location": self.current_zone_key,
            "description": description,
            "message": f"Created {container_type} at {location.display_name}",
        }

    def _execute_spawn_item(self, args: dict[str, Any]) -> dict[str, Any]:
        """Spawn an item at the current location.

        Creates an interactable item that appears in /nearby.

        Args:
            args: Tool arguments with display_name, description, item_type, surface.

        Returns:
            Result with item_key and success status.
        """
        from src.managers.location_manager import LocationManager

        display_name = args["display_name"]
        description = args["description"]
        item_type_str = args["item_type"]
        surface = args.get("surface", "floor")
        item_key = args.get("item_key")
        quantity = args.get("quantity", 1)
        weight = args.get("weight", 0.5)

        # Get current player location
        if self.current_zone_key is None:
            return {"success": False, "error": "Current location unknown"}

        # Get location
        location_mgr = LocationManager(self.db, self.game_session)
        location = location_mgr.get_location(self.current_zone_key)

        if location is None:
            return {
                "success": False,
                "error": f"Location '{self.current_zone_key}' not found. Use entity_move to establish location first.",
            }

        # Find storage location for the specified surface
        storage = (
            self.db.query(StorageLocation)
            .filter(
                StorageLocation.session_id == self.game_session.id,
                StorageLocation.world_location_id == location.id,
                StorageLocation.container_type == surface,
            )
            .first()
        )

        if storage is None:
            # Check if any storage exists at all
            any_storage = (
                self.db.query(StorageLocation)
                .filter(
                    StorageLocation.session_id == self.game_session.id,
                    StorageLocation.world_location_id == location.id,
                )
                .all()
            )
            available = [s.container_type for s in any_storage] if any_storage else []

            return {
                "success": False,
                "error": f"No '{surface}' storage exists at this location. Use spawn_storage first.",
                "available_surfaces": available,
                "suggestion": f"Call spawn_storage(container_type='{surface}') first",
            }

        # Generate item key if not provided
        if not item_key:
            # Create slug from display name
            slug = display_name.lower().replace(" ", "_").replace("'", "")[:30]
            # Count existing items with similar prefix
            existing_count = (
                self.db.query(Item)
                .filter(
                    Item.session_id == self.game_session.id,
                    Item.item_key.like(f"{slug}%"),
                )
                .count()
            )
            item_key = f"{slug}_{existing_count + 1}" if existing_count > 0 else slug

        # Check if item with this key already exists
        existing = (
            self.db.query(Item)
            .filter(
                Item.session_id == self.game_session.id,
                Item.item_key == item_key,
            )
            .first()
        )
        if existing:
            return {
                "success": False,
                "error": f"Item '{item_key}' already exists",
                "existing_name": existing.display_name,
            }

        # Map item type string to enum
        try:
            item_type = ItemType(item_type_str.upper())
        except ValueError:
            item_type = ItemType.MISC

        # Create the item
        item = Item(
            session_id=self.game_session.id,
            item_key=item_key,
            display_name=display_name,
            item_type=item_type,
            storage_location_id=storage.id,
            owner_location_id=location.id,  # Owned by the location
            weight=weight,
            quantity=quantity,
            properties={"description": description},
        )
        self.db.add(item)
        self.db.flush()

        return {
            "success": True,
            "item_key": item.item_key,
            "display_name": display_name,
            "surface": surface,
            "location": self.current_zone_key,
            "message": f"Spawned {display_name} on {surface}",
        }

    # =========================================================================
    # State Management Tool Handlers (replace STATE block parsing)
    # =========================================================================

    def _execute_advance_time(self, args: dict[str, Any]) -> dict[str, Any]:
        """Advance game time and update TimeState.

        Sets pending_state_updates["time_advance_minutes"] for propagation
        to game_master_node result.

        Args:
            args: Tool arguments with minutes, optional reason.

        Returns:
            Result with minutes_advanced and new time info.
        """
        from src.database.models.world import TimeState

        minutes = args["minutes"]
        reason = args.get("reason", "")

        # Clamp to reasonable range
        minutes = max(1, min(480, minutes))

        # Update pending state (will be merged into node result)
        self.pending_state_updates["time_advance_minutes"] = minutes

        # Also update TimeState in database
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.game_session.id)
            .first()
        )

        result: dict[str, Any] = {
            "success": True,
            "minutes_advanced": minutes,
            "reason": reason,
        }

        if time_state:
            old_time = time_state.current_time
            old_day = time_state.current_day

            # Parse and advance time
            try:
                hours, mins = map(int, time_state.current_time.split(":"))
                total_mins = hours * 60 + mins + minutes

                # Handle day rollover
                days_passed = total_mins // (24 * 60)
                remaining_mins = total_mins % (24 * 60)
                new_hours = remaining_mins // 60
                new_mins = remaining_mins % 60

                time_state.current_time = f"{new_hours:02d}:{new_mins:02d}"
                time_state.current_day += days_passed

                self.db.flush()

                result["old_time"] = old_time
                result["new_time"] = time_state.current_time
                result["old_day"] = old_day
                result["new_day"] = time_state.current_day
                result["days_passed"] = days_passed
            except (ValueError, AttributeError):
                result["warning"] = "Could not parse current time state"

        return result

    def _execute_entity_move(self, args: dict[str, Any]) -> dict[str, Any]:
        """Move an entity (player or NPC) to a new location.

        For player: Sets pending_state_updates for location tracking.
        For NPCs: Updates their current_location in NPCExtension.

        Args:
            args: Tool arguments with entity_key, location_key, create_if_missing.

        Returns:
            Result with success status and location info.
        """
        from src.database.models.entities import NPCExtension
        from src.database.models.world import Location

        entity_key = args["entity_key"]
        location_key = args["location_key"]
        create_if_missing = args.get("create_if_missing", True)

        # Get the entity
        entity = self._get_entity_by_key(entity_key)
        if entity is None:
            return {"success": False, "error": f"Entity '{entity_key}' not found"}

        # Check if location exists
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.game_session.id,
                Location.location_key == location_key,
            )
            .first()
        )

        if location is None and create_if_missing:
            # Create a minimal location record
            # Generate display name from key
            display_name = location_key.replace("_", " ").title()
            location = Location(
                session_id=self.game_session.id,
                location_key=location_key,
                display_name=display_name,
                description=f"A place called {display_name}.",
            )
            self.db.add(location)
            self.db.flush()

        if location is None:
            return {
                "success": False,
                "error": f"Location '{location_key}' not found and create_if_missing=False",
            }

        # Handle based on entity type
        if entity_key == "player":
            # Player movement: update graph state tracking
            self.pending_state_updates["location_changed"] = True
            self.pending_state_updates["player_location"] = location_key
            self.pending_state_updates["previous_location"] = self.current_zone_key
        else:
            # NPC movement: update their NPCExtension
            npc_ext = (
                self.db.query(NPCExtension)
                .filter(NPCExtension.entity_id == entity.id)
                .first()
            )
            if npc_ext:
                npc_ext.current_location = location_key
                self.db.flush()

        return {
            "success": True,
            "entity_key": entity_key,
            "entity_name": entity.display_name,
            "new_location": location_key,
            "location_name": location.display_name,
            "was_created": location is not None and create_if_missing,
        }

    def _execute_start_combat(self, args: dict[str, Any]) -> dict[str, Any]:
        """Initiate a combat encounter.

        Sets pending_state_updates for combat state tracking.

        Args:
            args: Tool arguments with enemy_keys, surprise, reason.

        Returns:
            Result with combat initialization info.
        """
        enemy_keys = args.get("enemy_keys", [])
        surprise = args.get("surprise", "none")
        reason = args.get("reason", "Combat initiated")

        # Validate enemies exist
        enemies = []
        missing = []
        for key in enemy_keys:
            entity = self._get_entity_by_key(key)
            if entity:
                enemies.append({
                    "entity_key": key,
                    "display_name": entity.display_name,
                })
            else:
                missing.append(key)

        if missing:
            return {
                "success": False,
                "error": f"Some enemies not found: {missing}",
                "found_enemies": enemies,
            }

        # Update pending state
        self.pending_state_updates["combat_active"] = True
        self.pending_state_updates["combat_state"] = {
            "enemies": enemies,
            "surprise": surprise,
            "reason": reason,
            "round": 1,
        }

        return {
            "success": True,
            "combat_started": True,
            "enemies": enemies,
            "surprise": surprise,
            "reason": reason,
            "message": f"Combat initiated: {reason}",
        }

    def _execute_end_combat(self, args: dict[str, Any]) -> dict[str, Any]:
        """End the current combat encounter.

        Clears combat state in pending_state_updates.

        Args:
            args: Tool arguments with outcome, optional summary.

        Returns:
            Result with combat resolution info.
        """
        outcome = args["outcome"]
        summary = args.get("summary", "")

        # Update pending state
        self.pending_state_updates["combat_active"] = False
        self.pending_state_updates["combat_state"] = None

        return {
            "success": True,
            "combat_ended": True,
            "outcome": outcome,
            "summary": summary,
            "message": f"Combat ended: {outcome}",
        }

    # === Quest Management Tools ===

    def _execute_assign_quest(self, args: dict[str, Any]) -> dict[str, Any]:
        """Assign a new quest to the player.

        Args:
            args: Tool arguments with quest_key, title, description, etc.

        Returns:
            Result with quest creation info.
        """
        from src.database.models.tasks import Quest
        from src.database.models.enums import QuestStatus

        quest_key = args["quest_key"]
        title = args["title"]
        description = args["description"]
        giver_key = args.get("giver_entity_key")
        rewards_text = args.get("rewards")

        # Check if quest already exists
        existing = (
            self.db.query(Quest)
            .filter(
                Quest.session_id == self.game_session.id,
                Quest.quest_key == quest_key,
            )
            .first()
        )
        if existing:
            return {
                "success": False,
                "reason": f"Quest '{quest_key}' already exists",
                "message": f"Quest already active: {existing.name}",
            }

        # Get quest giver entity if specified
        giver_entity_id = None
        if giver_key:
            giver = (
                self.db.query(Entity)
                .filter(
                    Entity.session_id == self.game_session.id,
                    Entity.entity_key == giver_key,
                )
                .first()
            )
            if giver:
                giver_entity_id = giver.id

        # Create quest record
        quest = Quest(
            session_id=self.game_session.id,
            quest_key=quest_key,
            name=title,
            description=description,
            status=QuestStatus.ACTIVE,
            current_stage=0,
            giver_entity_id=giver_entity_id,
            rewards={"description": rewards_text} if rewards_text else None,
            started_turn=self.game_session.total_turns,
        )
        self.db.add(quest)
        self.db.flush()

        return {
            "success": True,
            "quest_key": quest_key,
            "title": title,
            "message": f"Quest assigned: {title}",
        }

    def _execute_update_quest(self, args: dict[str, Any]) -> dict[str, Any]:
        """Update progress on an existing quest.

        Args:
            args: Tool arguments with quest_key, new_stage, notes, etc.

        Returns:
            Result with update info.
        """
        from src.database.models.tasks import Quest, QuestStage

        quest_key = args["quest_key"]
        new_stage = args.get("new_stage")
        stage_name = args.get("stage_name")
        stage_description = args.get("stage_description")
        notes = args.get("notes")

        # Find quest
        quest = (
            self.db.query(Quest)
            .filter(
                Quest.session_id == self.game_session.id,
                Quest.quest_key == quest_key,
            )
            .first()
        )
        if not quest:
            return {
                "success": False,
                "reason": f"Quest '{quest_key}' not found",
                "message": f"No active quest with key: {quest_key}",
            }

        # Update stage if provided
        if new_stage is not None:
            # Mark current stage as completed
            if quest.stages:
                current_stage_obj = next(
                    (s for s in quest.stages if s.stage_order == quest.current_stage),
                    None,
                )
                if current_stage_obj:
                    current_stage_obj.is_completed = True
                    current_stage_obj.completed_turn = self.game_session.total_turns

            quest.current_stage = new_stage

            # Create new stage record if details provided
            if stage_name and stage_description:
                new_stage_obj = QuestStage(
                    quest_id=quest.id,
                    stage_order=new_stage,
                    name=stage_name,
                    description=stage_description,
                    objective=stage_description,
                )
                self.db.add(new_stage_obj)

        self.db.flush()

        return {
            "success": True,
            "quest_key": quest_key,
            "current_stage": quest.current_stage,
            "notes": notes,
            "message": f"Quest '{quest.name}' updated to stage {quest.current_stage}",
        }

    def _execute_complete_quest(self, args: dict[str, Any]) -> dict[str, Any]:
        """Mark a quest as completed or failed.

        Args:
            args: Tool arguments with quest_key, outcome.

        Returns:
            Result with completion info.
        """
        from src.database.models.tasks import Quest
        from src.database.models.enums import QuestStatus

        quest_key = args["quest_key"]
        outcome = args["outcome"]
        outcome_notes = args.get("outcome_notes", "")

        # Find quest
        quest = (
            self.db.query(Quest)
            .filter(
                Quest.session_id == self.game_session.id,
                Quest.quest_key == quest_key,
            )
            .first()
        )
        if not quest:
            return {
                "success": False,
                "reason": f"Quest '{quest_key}' not found",
                "message": f"No active quest with key: {quest_key}",
            }

        # Update status
        quest.status = QuestStatus.COMPLETED if outcome == "completed" else QuestStatus.FAILED
        quest.completed_turn = self.game_session.total_turns
        self.db.flush()

        return {
            "success": True,
            "quest_key": quest_key,
            "outcome": outcome,
            "rewards": quest.rewards,
            "message": f"Quest '{quest.name}' {outcome}!",
        }

    # === World Fact Tools ===

    def _execute_record_fact(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record a fact about the world.

        Args:
            args: Tool arguments with subject_type, subject_key, predicate, value, etc.

        Returns:
            Result with fact creation info.
        """
        from src.database.models.world import Fact
        from src.database.models.enums import FactCategory

        subject_type = args["subject_type"]
        subject_key = args["subject_key"]
        predicate = args["predicate"]
        value = args["value"]
        is_secret = args.get("is_secret", False)
        confidence = args.get("confidence", 80)

        # Check for existing fact with same subject+predicate
        existing = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.game_session.id,
                Fact.subject_type == subject_type,
                Fact.subject_key == subject_key,
                Fact.predicate == predicate,
            )
            .first()
        )

        if existing:
            # Update existing fact
            existing.value = value
            existing.is_secret = is_secret
            existing.confidence = confidence
            self.db.flush()
            return {
                "success": True,
                "updated": True,
                "fact_id": existing.id,
                "message": f"Updated fact: {subject_key} {predicate} = {value}",
            }

        # Create new fact
        fact = Fact(
            session_id=self.game_session.id,
            subject_type=subject_type,
            subject_key=subject_key,
            predicate=predicate,
            value=value,
            category=FactCategory.PERSONAL,  # Default category
            is_secret=is_secret,
            confidence=confidence,
            source_turn=self.game_session.total_turns,
        )
        self.db.add(fact)
        self.db.flush()

        return {
            "success": True,
            "created": True,
            "fact_id": fact.id,
            "message": f"Recorded fact: {subject_key} {predicate} = {value}",
        }

    # === NPC Scene Management Tools ===

    def _execute_introduce_npc(self, args: dict[str, Any]) -> dict[str, Any]:
        """Introduce an NPC into the scene.

        Args:
            args: Tool arguments with entity_key, display_name, description, etc.

        Returns:
            Result with NPC creation/update info.
        """
        from src.database.models.entities import NPCExtension
        from src.database.models.enums import EntityType
        from src.database.models.relationships import Relationship

        entity_key = args["entity_key"]
        display_name = args["display_name"]
        description = args["description"]
        location_key = args["location_key"]
        occupation = args.get("occupation")
        initial_attitude = args.get("initial_attitude", "neutral")

        # Check if NPC already exists
        existing = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

        if existing:
            # Update location for existing NPC
            npc_ext = (
                self.db.query(NPCExtension)
                .filter(NPCExtension.entity_id == existing.id)
                .first()
            )
            if npc_ext:
                npc_ext.current_location = location_key
            self.db.flush()

            return {
                "success": True,
                "created": False,
                "entity_key": entity_key,
                "message": f"{display_name} enters the scene.",
            }

        # Create new NPC entity
        npc = Entity(
            session_id=self.game_session.id,
            entity_key=entity_key,
            display_name=display_name,
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
            appearance={"description": description},  # Store description in appearance
        )
        self.db.add(npc)
        self.db.flush()

        # Create NPC extension with location
        npc_ext = NPCExtension(
            entity_id=npc.id,
            current_location=location_key,
            job=occupation,  # NPCExtension uses 'job' not 'occupation'
        )
        self.db.add(npc_ext)

        # Create initial relationship with player if attitude specified
        player = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_type == EntityType.PLAYER,
            )
            .first()
        )
        if player:
            # Map attitude to numeric values
            attitude_map = {
                "hostile": 10,
                "unfriendly": 30,
                "neutral": 50,
                "friendly": 70,
                "warm": 85,
            }
            initial_value = attitude_map.get(initial_attitude, 50)

            relationship = Relationship(
                session_id=self.game_session.id,
                from_entity_id=npc.id,
                to_entity_id=player.id,
                trust=initial_value,
                liking=initial_value,
                familiarity=10,  # Just met
            )
            self.db.add(relationship)

        self.db.flush()

        return {
            "success": True,
            "created": True,
            "entity_key": entity_key,
            "entity_id": npc.id,
            "message": f"{display_name} appears in the scene.",
        }

    def _execute_npc_leaves(self, args: dict[str, Any]) -> dict[str, Any]:
        """Have an NPC leave the current scene.

        Args:
            args: Tool arguments with entity_key, destination, reason.

        Returns:
            Result with departure info.
        """
        from src.database.models.entities import NPCExtension

        entity_key = args["entity_key"]
        destination = args.get("destination")
        reason = args.get("reason", "")

        # Find NPC
        npc = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == entity_key,
            )
            .first()
        )
        if not npc:
            return {
                "success": False,
                "reason": f"NPC '{entity_key}' not found",
                "message": f"Unknown NPC: {entity_key}",
            }

        # Update location
        npc_ext = (
            self.db.query(NPCExtension)
            .filter(NPCExtension.entity_id == npc.id)
            .first()
        )
        if npc_ext and destination:
            npc_ext.current_location = destination
            self.db.flush()

        return {
            "success": True,
            "entity_key": entity_key,
            "destination": destination,
            "reason": reason,
            "message": f"{npc.display_name} leaves the scene.",
        }
