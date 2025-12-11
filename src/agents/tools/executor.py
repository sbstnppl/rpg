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
from src.database.models.enums import DiscoveryMethod
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
