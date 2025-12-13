"""Context compiler for assembling GM prompt context."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.database.models.character_state import CharacterNeeds
from src.database.models.entities import Entity, EntityAttribute, EntitySkill, NPCExtension
from src.database.models.enums import EntityType, GoalStatus
from src.database.models.goals import NPCGoal
from src.dice.checks import get_proficiency_tier_name
from src.database.models.injuries import BodyInjury
from src.database.models.navigation import ZoneDiscovery
from src.database.models.relationships import Relationship
from src.database.models.session import GameSession, Turn
from src.database.models.world import Fact, Location, TimeState, WorldEvent
from src.managers.base import BaseManager
from src.managers.discovery_manager import DiscoveryManager
from src.managers.entity_manager import EntityManager
from src.managers.goal_manager import GoalManager
from src.managers.injuries import InjuryManager
from src.managers.item_manager import ItemManager
from src.managers.map_manager import MapManager
from src.managers.needs import NeedsManager
from src.managers.relationship_manager import RelationshipManager
from src.managers.zone_manager import ZoneManager


@dataclass
class SceneContext:
    """Compiled scene context for GM."""

    turn_context: str  # Turn number and recent history
    time_context: str
    location_context: str
    player_context: str
    npcs_context: str
    tasks_context: str
    recent_events_context: str
    secrets_context: str  # GM-only info
    navigation_context: str = ""  # Current zone and navigation info
    entity_registry_context: str = ""  # Entity keys for manifest references

    def to_prompt(self, include_secrets: bool = True) -> str:
        """Format as prompt string for GM."""
        sections = [
            self.turn_context,
            self.time_context,
            self.location_context,
            self.player_context,
            self.npcs_context,
        ]

        if self.navigation_context:
            sections.append(self.navigation_context)

        if self.tasks_context:
            sections.append(self.tasks_context)

        if self.recent_events_context:
            sections.append(self.recent_events_context)

        if self.entity_registry_context:
            sections.append(self.entity_registry_context)

        if include_secrets and self.secrets_context:
            sections.append(self.secrets_context)

        return "\n\n".join(sections)


class ContextCompiler(BaseManager):
    """Compiles game state into context strings for GM prompts."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        needs_manager: NeedsManager | None = None,
        injury_manager: InjuryManager | None = None,
        relationship_manager: RelationshipManager | None = None,
        item_manager: ItemManager | None = None,
        zone_manager: ZoneManager | None = None,
        discovery_manager: DiscoveryManager | None = None,
        goal_manager: GoalManager | None = None,
    ) -> None:
        """Initialize with optional manager references.

        If managers aren't provided, they'll be created on demand.
        """
        super().__init__(db, game_session)
        self._needs_manager = needs_manager
        self._injury_manager = injury_manager
        self._relationship_manager = relationship_manager
        self._item_manager = item_manager
        self._zone_manager = zone_manager
        self._discovery_manager = discovery_manager
        self._goal_manager = goal_manager

    @property
    def needs_manager(self) -> NeedsManager:
        if self._needs_manager is None:
            self._needs_manager = NeedsManager(self.db, self.game_session)
        return self._needs_manager

    @property
    def injury_manager(self) -> InjuryManager:
        if self._injury_manager is None:
            self._injury_manager = InjuryManager(self.db, self.game_session)
        return self._injury_manager

    @property
    def relationship_manager(self) -> RelationshipManager:
        if self._relationship_manager is None:
            self._relationship_manager = RelationshipManager(self.db, self.game_session)
        return self._relationship_manager

    @property
    def item_manager(self) -> ItemManager:
        if self._item_manager is None:
            self._item_manager = ItemManager(self.db, self.game_session)
        return self._item_manager

    @property
    def zone_manager(self) -> ZoneManager:
        if self._zone_manager is None:
            self._zone_manager = ZoneManager(self.db, self.game_session)
        return self._zone_manager

    @property
    def discovery_manager(self) -> DiscoveryManager:
        if self._discovery_manager is None:
            self._discovery_manager = DiscoveryManager(self.db, self.game_session)
        return self._discovery_manager

    @property
    def goal_manager(self) -> GoalManager:
        if self._goal_manager is None:
            self._goal_manager = GoalManager(self.db, self.game_session)
        return self._goal_manager

    def compile_scene(
        self,
        player_id: int,
        location_key: str,
        turn_number: int = 1,
        include_secrets: bool = True,
        current_zone_key: str | None = None,
    ) -> SceneContext:
        """Compile full scene context for GM.

        Args:
            player_id: Player entity ID
            location_key: Current location key
            turn_number: Current turn number (1 = first turn)
            include_secrets: Whether to include GM-only secrets
            current_zone_key: Current terrain zone key (if using zone navigation)

        Returns:
            SceneContext with all compiled sections
        """
        return SceneContext(
            turn_context=self._get_turn_context(turn_number),
            time_context=self._get_time_context(),
            location_context=self._get_location_context(location_key),
            player_context=self._get_player_context(player_id),
            npcs_context=self._get_npcs_context(location_key, player_id),
            tasks_context=self._get_tasks_context(player_id),
            recent_events_context=self._get_recent_events(limit=5),
            secrets_context=self._get_secrets_context(location_key) if include_secrets else "",
            navigation_context=self._get_navigation_context(current_zone_key),
            entity_registry_context=self._get_entity_registry_context(location_key, player_id),
        )

    def _get_turn_context(self, turn_number: int, history_limit: int = 3) -> str:
        """Get turn number and recent conversation history.

        Args:
            turn_number: Current turn number (1 = first turn).
            history_limit: Number of recent turns to include.

        Returns:
            Formatted turn context string.
        """
        lines = [f"## Turn {turn_number}"]

        if turn_number == 1:
            lines.append("This is the FIRST TURN. Introduce the player character.")
        else:
            lines.append("This is a CONTINUATION. Do NOT re-introduce the character.")

            # Get recent turns for context
            recent_turns = (
                self.db.query(Turn)
                .filter(Turn.session_id == self.session_id)
                .order_by(Turn.turn_number.desc())
                .limit(history_limit)
                .all()
            )

            if recent_turns:
                lines.append("\n### Recent History")
                # Reverse to show oldest first
                reversed_turns = list(reversed(recent_turns))
                for i, turn in enumerate(reversed_turns):
                    # More context for recent turns, less for older ones
                    is_most_recent = (i == len(reversed_turns) - 1)

                    # Player input usually short, but allow more space
                    player_input = turn.player_input[:200]
                    if len(turn.player_input) > 200:
                        player_input += "..."

                    # Most recent turn gets full context, older turns abbreviated
                    max_gm_len = 1000 if is_most_recent else 400
                    gm_summary = turn.gm_response[:max_gm_len]
                    if len(turn.gm_response) > max_gm_len:
                        gm_summary += "..."

                    lines.append(f"\n**Turn {turn.turn_number}**")
                    lines.append(f"Player: {player_input}")
                    lines.append(f"GM: {gm_summary}")

        return "\n".join(lines)

    def _get_time_context(self) -> str:
        """Get current time/date/weather context."""
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

        if not time_state:
            return "## Current Scene\n- Time: Unknown"

        lines = ["## Current Scene"]
        lines.append(
            f"- Time: Day {time_state.current_day}, {time_state.current_time} "
            f"({time_state.day_of_week})"
        )

        if time_state.weather:
            lines.append(f"- Weather: {time_state.weather}")
        if time_state.temperature:
            lines.append(f"- Temperature: {time_state.temperature}")
        if time_state.season:
            lines.append(f"- Season: {time_state.season}")

        return "\n".join(lines)

    def _get_location_context(self, location_key: str) -> str:
        """Get location description context."""
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        if not location:
            return f"- Location: {location_key}"

        lines = [f"- Location: {location.display_name}"]

        if location.description:
            lines.append(f"- Description: {location.description[:200]}...")
        if location.atmosphere:
            lines.append(f"- Atmosphere: {location.atmosphere}")

        return "\n".join(lines)

    def _get_player_context(self, player_id: int) -> str:
        """Get player character context including needs, injuries, equipment, and abilities."""
        player = (
            self.db.query(Entity)
            .filter(Entity.id == player_id)
            .first()
        )

        if not player:
            return "## Player Character\n- Not found"

        lines = ["## Player Character"]
        lines.append(f"- Name: {player.display_name}")
        lines.append(f"- Entity Key: {player.entity_key}")

        # Appearance (includes age if set)
        if player.appearance:
            appearance_desc = self._format_appearance(player.appearance)
            if appearance_desc:
                lines.append(f"- Appearance: {appearance_desc}")

        # Equipment/clothing
        equipment_desc = self._get_equipment_description(player_id)
        if equipment_desc:
            lines.append(f"- Wearing: {equipment_desc}")

        # Condition (needs + injuries)
        condition = self._get_condition_summary(player_id)
        if condition:
            lines.append(f"- Condition: {condition}")

        # Attributes
        attributes = self._get_player_attributes(player_id)
        if attributes:
            lines.append(f"- Attributes: {attributes}")

        # Skills
        skills = self._get_player_skills(player_id)
        if skills:
            lines.append(f"- Skills: {skills}")

        return "\n".join(lines)

    def _get_player_attributes(self, player_id: int) -> str:
        """Get player's attribute scores for skill check context.

        Args:
            player_id: Player entity ID.

        Returns:
            Formatted attribute string (e.g., "STR 14, DEX 12, INT 16").
        """
        attributes = (
            self.db.query(EntityAttribute)
            .filter(EntityAttribute.entity_id == player_id)
            .order_by(EntityAttribute.attribute_key)
            .all()
        )

        if not attributes:
            return ""

        # Format as abbreviated key/value pairs
        attr_strings = []
        for attr in attributes:
            # Use first 3 letters uppercase as abbreviation
            abbrev = attr.attribute_key[:3].upper()
            attr_strings.append(f"{abbrev} {attr.value}")

        return ", ".join(attr_strings)

    def _get_player_skills(self, player_id: int) -> str:
        """Get player's notable skills for skill check context.

        Args:
            player_id: Player entity ID.

        Returns:
            Formatted skills string (e.g., "swimming (Expert), lockpicking (Apprentice)").
        """
        skills = (
            self.db.query(EntitySkill)
            .filter(EntitySkill.entity_id == player_id)
            .order_by(EntitySkill.proficiency_level.desc())
            .limit(10)  # Show top 10 skills by proficiency
            .all()
        )

        if not skills:
            return ""

        skill_strings = []
        for skill in skills:
            tier = get_proficiency_tier_name(skill.proficiency_level)
            # Only show skills above Novice level to avoid clutter
            if skill.proficiency_level >= 20:
                skill_strings.append(f"{skill.skill_key} ({tier})")

        if not skill_strings:
            return ""

        return ", ".join(skill_strings)

    def _get_equipment_description(self, entity_id: int) -> str:
        """Get human-readable description of visible equipment/clothing.

        Args:
            entity_id: Entity to describe.

        Returns:
            Comma-separated list of visible equipment.
        """
        visible_items = self.item_manager.get_visible_equipment(entity_id)
        if not visible_items:
            return ""

        # Group by slot for natural description
        descriptions = []
        for item in visible_items:
            descriptions.append(item.display_name.lower())

        return ", ".join(descriptions)

    def _get_npcs_context(self, location_key: str, player_id: int) -> str:
        """Get context for all NPCs at the current location.

        Uses EntityManager to filter NPCs by their current_location field
        from NPCExtension. Falls back to all active NPCs if no location
        is specified or no NPCs found at location.
        """
        entity_manager = EntityManager(self.db, self.game_session)

        # First try to get NPCs at the specific location
        npcs = []
        if location_key:
            npcs = entity_manager.get_npcs_in_scene(location_key)

        # Fallback: if no location or no NPCs found, get companions
        # (companions should always show regardless of location tracking)
        companions = entity_manager.get_companions()
        companion_ids = {c.id for c in companions}

        # Combine: NPCs at location + companions not already included
        all_npcs = list(npcs)
        for companion in companions:
            if companion.id not in {n.id for n in all_npcs}:
                all_npcs.append(companion)

        # Limit total to avoid overwhelming context
        all_npcs = all_npcs[:10]

        if not all_npcs:
            return "## NPCs Present\nNone present"

        lines = ["## NPCs Present"]

        for npc in all_npcs:
            npc_lines = self._format_npc_context(npc, player_id)
            lines.extend(npc_lines)

        return "\n".join(lines)

    def _format_npc_context(self, npc: Entity, player_id: int) -> list[str]:
        """Format context for a single NPC including motivations and goals."""
        lines = [f"\n### {npc.display_name} ({npc.entity_key})"]

        # WHY HERE - Location reason based on goals or schedule
        location_reason = self._get_npc_location_reason(npc)
        if location_reason:
            lines.append(f"- **Location reason:** {location_reason}")

        # Appearance
        if npc.appearance:
            appearance = self._format_appearance(npc.appearance)
            if appearance:
                lines.append(f"- Appearance: {appearance}")

        # Current activity (from NPC extension or schedule)
        if npc.npc_extension:
            if npc.npc_extension.current_activity:
                lines.append(f"- Activity: {npc.npc_extension.current_activity}")
            if npc.npc_extension.current_mood:
                lines.append(f"- Mood: {npc.npc_extension.current_mood}")

        # Active goals
        active_goals = self._get_npc_active_goals(npc.id)
        if active_goals:
            lines.append("- **Active Goals:**")
            for goal_info in active_goals[:3]:  # Limit to top 3
                lines.append(f"  - {goal_info}")

        # Condition (visible needs/injuries)
        condition = self._get_condition_summary(npc.id, visible_only=True)
        if condition:
            lines.append(f"- Condition: {condition}")

        # Urgent needs (for behavioral prediction)
        urgent_needs = self._get_urgent_needs(npc.id)
        if urgent_needs:
            lines.append(f"- **Urgent needs:** {urgent_needs}")

        # Attitude toward player
        attitude = self.relationship_manager.get_attitude(npc.id, player_id)
        if attitude["knows"]:
            lines.append("- Attitude toward you:")
            lines.append(f"  - Trust: {attitude['trust']}/100")
            lines.append(f"  - Liking: {attitude['effective_liking']}/100")
            lines.append(f"  - Respect: {attitude['respect']}/100")
            if attitude["romantic_interest"] > 0:
                lines.append(f"  - Romantic Interest: {attitude['romantic_interest']}/100")
            if attitude["fear"] > 20:
                lines.append(f"  - Fear: {attitude['fear']}/100")

            # Disposition description
            disposition = self.relationship_manager.get_attitude_description(npc.id, player_id)
            lines.append(f"  - Disposition: {disposition}")

        # Visible personality traits
        if npc.npc_extension and npc.npc_extension.personality_traits:
            visible_traits = self._get_visible_personality_traits(npc.npc_extension.personality_traits)
            if visible_traits:
                lines.append(f"- Personality: {visible_traits}")

        return lines

    def _get_visible_personality_traits(self, traits: dict) -> str:
        """Get personality traits that would be observable."""
        # Some traits are observable, others are hidden
        observable = {
            "shy": "reserved",
            "outgoing": "outgoing",
            "prideful": "proud",
            "humble": "humble",
            "romantic": "flirtatious",
            "suspicious": "wary",
            "trusting": "open",
            "fearless": "bold",
            "anxious": "nervous",
        }

        visible = []
        for trait, is_active in traits.items():
            if is_active and trait in observable:
                visible.append(observable[trait])

        return ", ".join(visible) if visible else ""

    def _get_condition_summary(
        self, entity_id: int, visible_only: bool = False
    ) -> str:
        """Get human-readable condition summary (needs + injuries).

        Args:
            entity_id: Entity to summarize
            visible_only: If True, only include visually obvious conditions

        Returns:
            Condition description string
        """
        parts = []

        # Needs summary
        needs_summary = self._get_needs_description(entity_id, visible_only)
        if needs_summary:
            parts.append(needs_summary)

        # Injuries summary
        injuries_summary = self._get_injury_description(entity_id, visible_only)
        if injuries_summary:
            parts.append(injuries_summary)

        return "; ".join(parts) if parts else ""

    def _get_needs_description(self, entity_id: int, visible_only: bool = False) -> str:
        """Get human-readable needs description."""
        needs = self.needs_manager.get_needs(entity_id)
        if not needs:
            return ""

        descriptions = []

        # Visible conditions (someone else could observe)
        # All needs: 0 = bad, 100 = good
        if needs.energy < 20:
            descriptions.append("exhausted")
        elif needs.energy < 40:
            descriptions.append("tired")

        if needs.hunger < 15:
            descriptions.append("starving")
        elif needs.hunger < 30:
            descriptions.append("hungry")

        if needs.hygiene < 20:
            descriptions.append("filthy")
        elif needs.hygiene < 40:
            descriptions.append("disheveled")

        if needs.wellness < 40:
            descriptions.append("in obvious pain")
        elif needs.wellness < 60:
            descriptions.append("uncomfortable")

        # Less visible (only for player/self)
        if not visible_only:
            if needs.morale < 20:
                descriptions.append("depressed")
            elif needs.morale < 40:
                descriptions.append("low spirits")

            if needs.social_connection < 20:
                descriptions.append("lonely")

            if needs.intimacy < 20:
                descriptions.append("restless")

        return ", ".join(descriptions)

    def _get_injury_description(self, entity_id: int, visible_only: bool = False) -> str:
        """Get human-readable injury description."""
        injuries = self.injury_manager.get_injuries(entity_id, active_only=True)
        if not injuries:
            return ""

        # Map injuries to descriptions
        descriptions = []
        for injury in injuries:
            desc = self._injury_to_description(injury, visible_only)
            if desc:
                descriptions.append(desc)

        # Limit to 3 most severe
        return ", ".join(descriptions[:3])

    def _injury_to_description(self, injury: BodyInjury, visible_only: bool) -> str:
        """Convert injury to human-readable description."""
        from src.database.models.enums import BodyPart, InjurySeverity, InjuryType

        # Visible injuries (observable by others)
        visible_body_parts = {
            BodyPart.HEAD, BodyPart.LEFT_ARM, BodyPart.RIGHT_ARM,
            BodyPart.LEFT_HAND, BodyPart.RIGHT_HAND, BodyPart.LEFT_LEG,
            BodyPart.RIGHT_LEG, BodyPart.LEFT_FOOT, BodyPart.RIGHT_FOOT,
        }

        visible_injury_types = {
            InjuryType.CUT, InjuryType.LACERATION, InjuryType.BURN,
            InjuryType.BRUISE, InjuryType.FRACTURE, InjuryType.DISLOCATION,
        }

        if visible_only:
            if injury.body_part not in visible_body_parts:
                return ""
            if injury.injury_type not in visible_injury_types:
                return ""

        # Build description
        part_name = injury.body_part.value.replace("_", " ")

        if injury.injury_type == InjuryType.FRACTURE:
            if injury.body_part in (BodyPart.LEFT_LEG, BodyPart.RIGHT_LEG):
                return "limping heavily"
            elif injury.body_part in (BodyPart.LEFT_ARM, BodyPart.RIGHT_ARM):
                return f"arm in a sling"
            else:
                return f"broken {part_name}"
        elif injury.injury_type == InjuryType.SPRAIN:
            if injury.body_part in (BodyPart.LEFT_LEG, BodyPart.RIGHT_LEG):
                return "limping"
            else:
                return f"favoring {part_name}"
        elif injury.injury_type == InjuryType.CUT:
            if injury.severity == InjurySeverity.MINOR:
                return f"small cut on {part_name}"
            else:
                return f"bandaged {part_name}"
        elif injury.injury_type == InjuryType.BURN:
            return f"burn marks on {part_name}"
        elif injury.injury_type == InjuryType.BRUISE:
            return f"bruised {part_name}"
        elif injury.injury_type == InjuryType.CONCUSSION:
            return "dazed, moving carefully"

        # Generic fallback
        if injury.severity in (InjurySeverity.SEVERE, InjurySeverity.CRITICAL):
            return f"seriously injured {part_name}"
        return f"injured {part_name}"

    def _format_appearance(self, appearance: dict) -> str:
        """Format appearance dict into readable string."""
        parts = []

        if appearance.get("age"):
            age = appearance["age"]
            if isinstance(age, int):
                parts.append(f"{age} years old")
            else:
                parts.append(str(age))
        if appearance.get("height"):
            parts.append(appearance["height"])
        if appearance.get("build"):
            parts.append(appearance["build"])
        if appearance.get("hair"):
            parts.append(f"{appearance['hair']} hair")
        if appearance.get("eyes"):
            parts.append(f"{appearance['eyes']} eyes")
        if appearance.get("distinguishing"):
            parts.append(appearance["distinguishing"])

        return ", ".join(parts)

    def _get_tasks_context(self, player_id: int) -> str:
        """Get active tasks, quests, and appointments context.

        Queries TaskManager for active tasks, upcoming appointments, and quests.
        """
        from src.managers.task_manager import TaskManager
        from src.managers.time_manager import TimeManager

        time_manager = TimeManager(self.db, self.game_session)
        task_manager = TaskManager(self.db, self.game_session, time_manager=time_manager)

        lines = []

        # Active tasks
        try:
            active_tasks = task_manager.get_active_tasks()
            if active_tasks:
                lines.append("## Active Tasks")
                for task in active_tasks[:5]:  # Limit to 5 most important
                    priority_str = f" [{task.priority.value}]" if task.priority else ""
                    lines.append(f"- {task.description}{priority_str}")
                    if task.deadline_day:
                        lines.append(f"  Deadline: Day {task.deadline_day}")
        except Exception:
            pass  # TaskManager may not have all methods

        # Upcoming appointments
        try:
            current_day, current_time = time_manager.get_current_time()
            appointments = task_manager.get_appointments_for_day(current_day)
            # Filter to upcoming (not yet passed)
            upcoming = [a for a in appointments if a.game_time and a.game_time >= current_time]
            if upcoming:
                if lines:
                    lines.append("")
                lines.append("## Today's Appointments")
                for appt in upcoming[:3]:
                    time_str = f" at {appt.game_time}" if appt.game_time else ""
                    loc_str = f" ({appt.location_name})" if appt.location_name else ""
                    lines.append(f"- {appt.description}{time_str}{loc_str}")
        except Exception:
            pass  # TimeManager may not have time state initialized

        # Active quests
        try:
            active_quests = task_manager.get_active_quests()
            if active_quests:
                if lines:
                    lines.append("")
                lines.append("## Active Quests")
                for quest in active_quests[:3]:
                    lines.append(f"- **{quest.title}**: {quest.description[:100]}...")
                    # Get current stage
                    current_stage = task_manager.get_current_quest_stage(quest.id)
                    if current_stage:
                        lines.append(f"  Current objective: {current_stage.description}")
        except Exception:
            pass

        return "\n".join(lines) if lines else ""

    def _get_recent_events(self, limit: int = 5) -> str:
        """Get recent world events for context."""
        events = (
            self.db.query(WorldEvent)
            .filter(
                WorldEvent.session_id == self.session_id,
                WorldEvent.is_processed == True,
            )
            .order_by(WorldEvent.game_day.desc(), WorldEvent.id.desc())
            .limit(limit)
            .all()
        )

        if not events:
            return ""

        lines = ["## Recent Events"]
        for event in events:
            time_str = f"Day {event.game_day}"
            if event.game_time:
                time_str += f" {event.game_time}"
            lines.append(f"- [{time_str}] {event.summary}")

        return "\n".join(lines)

    def _get_secrets_context(self, location_key: str) -> str:
        """Get GM-only secrets for this scene."""
        # Get secret facts about entities at this location
        secrets = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_secret == True,
            )
            .limit(10)
            .all()
        )

        if not secrets:
            return ""

        lines = ["## GM Secrets (hidden from player)"]
        for fact in secrets:
            lines.append(f"- {fact.subject_key}: {fact.predicate} = {fact.value}")

        # Get foreshadowing hints that should be planted
        foreshadowing = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.is_foreshadowing == True,
                Fact.times_mentioned < 3,  # Not yet fully planted
            )
            .limit(3)
            .all()
        )

        if foreshadowing:
            lines.append("\n### Foreshadowing to Plant")
            for hint in foreshadowing:
                lines.append(
                    f"- {hint.foreshadow_target or hint.value} "
                    f"(mentioned {hint.times_mentioned}/3 times)"
                )

        return "\n".join(lines)

    def get_quick_context(self, player_id: int, location_key: str) -> str:
        """Get minimal context for quick updates.

        Useful for EntityExtractor or brief checks.
        """
        time_state = (
            self.db.query(TimeState)
            .filter(TimeState.session_id == self.session_id)
            .first()
        )

        player = (
            self.db.query(Entity)
            .filter(Entity.id == player_id)
            .first()
        )

        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )

        parts = []
        if time_state:
            parts.append(f"Day {time_state.current_day}, {time_state.current_time}")
        if location:
            parts.append(f"at {location.display_name}")
        if player:
            condition = self._get_condition_summary(player_id)
            if condition:
                parts.append(f"({condition})")

        return " ".join(parts)

    def _get_navigation_context(self, current_zone_key: str | None) -> str:
        """Get navigation context including current zone and accessible areas.

        Args:
            current_zone_key: Current terrain zone key, or None if not in a zone.

        Returns:
            Formatted navigation context string.
        """
        if current_zone_key is None:
            return ""

        zone = self.zone_manager.get_zone(current_zone_key)
        if zone is None:
            return ""

        lines = ["## Navigation"]

        # Current zone info
        terrain_name = zone.terrain_type.value if zone.terrain_type else "unknown"
        lines.append(f"### Current Zone: {zone.display_name}")
        lines.append(f"- Terrain: {terrain_name}")

        if zone.description:
            lines.append(f"- {zone.description[:150]}...")

        # Hazard warning for current zone
        if zone.requires_skill:
            dc_text = f" (DC {zone.skill_difficulty})" if zone.skill_difficulty else ""
            lines.append(f"- Requires: {zone.requires_skill} skill{dc_text}")

        # Get adjacent zones with directions
        adjacent_data = self.zone_manager.get_adjacent_zones_with_directions(current_zone_key)

        # Filter to only discovered zones
        discovered_adjacent = []
        for item in adjacent_data:
            adj_zone = item["zone"]
            direction = item["direction"]
            if self.discovery_manager.is_zone_discovered(adj_zone.zone_key):
                discovered_adjacent.append((adj_zone, direction))

        if discovered_adjacent:
            lines.append("\n### Known Adjacent Areas")
            for adj_zone, direction in discovered_adjacent:
                dir_str = f"({direction}) " if direction else ""
                terrain = adj_zone.terrain_type.value if adj_zone.terrain_type else ""

                # Add hazard indicator
                hazard = ""
                if adj_zone.requires_skill:
                    hazard = f" [requires {adj_zone.requires_skill}]"

                lines.append(f"- {dir_str}{adj_zone.display_name} ({terrain}){hazard}")

        # Get discovered locations in current zone
        discovered_locations = self.discovery_manager.get_known_locations(
            zone_key=current_zone_key
        )

        if discovered_locations:
            lines.append("\n### Known Locations Here")
            for loc in discovered_locations[:5]:  # Limit to 5
                lines.append(f"- {loc.display_name}")

        # Add maps in possession
        maps_context = self._get_maps_context()
        if maps_context:
            lines.append("")
            lines.append(maps_context)

        return "\n".join(lines)

    def _get_maps_context(self) -> str:
        """Get context for maps in player's possession.

        Returns a summary of maps the player has, which can be used
        to discover new locations.
        """
        # Get player entity
        player = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.PLAYER,
            )
            .first()
        )

        if not player:
            return ""

        map_manager = MapManager(self.db, self.game_session)

        # Get all items owned by player
        player_items = self.item_manager.get_inventory(player.id)

        maps_info = []
        for item in player_items:
            map_data = map_manager.get_map_item(item.item_key)
            if map_data:
                map_type = map_data.get("map_type", "unknown")
                is_complete = map_data.get("is_complete", True)
                quality = "complete" if is_complete else "partial/damaged"
                maps_info.append(f"- {item.display_name} ({map_type}, {quality})")

        if not maps_info:
            return ""

        lines = ["### Available Maps"]
        lines.extend(maps_info[:5])  # Limit to 5 maps
        lines.append("(Use `view_map` tool when player examines a map)")

        return "\n".join(lines)

    # =========================================================================
    # NPC Motivation & Goal Context Methods
    # =========================================================================

    def _get_npc_location_reason(self, npc: Entity) -> str:
        """Get WHY an NPC is at their current location.

        Checks goals first, then falls back to schedule/job.

        Args:
            npc: NPC entity.

        Returns:
            Human-readable reason for NPC's presence.
        """
        # Check for goal-driven presence
        active_goals = self.goal_manager.get_active_goals(entity_id=npc.id)
        for goal in active_goals:
            if goal.priority.value in ("urgent", "high"):
                goal_type = goal.goal_type.value
                return f"Goal pursuit - {goal.description} ({goal_type})"

        # Fall back to schedule/job
        if npc.npc_extension:
            if npc.npc_extension.job:
                return f"Scheduled - works as {npc.npc_extension.job}"
            if npc.npc_extension.current_activity:
                return f"Scheduled - {npc.npc_extension.current_activity}"

        return "Scheduled - routine activity"

    def _get_npc_active_goals(self, entity_id: int) -> list[str]:
        """Get formatted list of NPC's active goals.

        Args:
            entity_id: NPC entity ID.

        Returns:
            List of goal description strings.
        """
        goals = self.goal_manager.get_active_goals(entity_id=entity_id)
        if not goals:
            return []

        result = []
        for goal in goals[:5]:  # Limit to 5 goals
            priority_str = f"[{goal.priority.value}]" if goal.priority else ""
            goal_type = goal.goal_type.value if goal.goal_type else "unknown"
            motivation_str = ""
            if goal.motivation:
                motivation_str = f" (motivated by: {', '.join(goal.motivation[:2])})"

            result.append(f"{priority_str} {goal.description} ({goal_type}){motivation_str}")

        return result

    def _get_urgent_needs(self, entity_id: int) -> str:
        """Get urgent needs for behavioral prediction.

        Args:
            entity_id: Entity ID.

        Returns:
            Comma-separated list of urgent needs.
        """
        urgency = self.needs_manager.get_npc_urgency(entity_id)
        need_name, urgency_level = urgency

        if urgency_level < 60:
            return ""

        # Get all needs above threshold
        needs = self.needs_manager.get_needs(entity_id)
        if not needs:
            return ""

        urgent = []
        # All needs: 0 = bad, 100 = good. Urgency = 100 - value
        if needs.hunger < 40:
            urgent.append(f"hunger ({100 - needs.hunger}%)")
        if needs.thirst < 40:
            urgent.append(f"thirst ({100 - needs.thirst}%)")
        if needs.energy < 30:
            urgent.append(f"fatigue ({100 - needs.energy}%)")
        if needs.social_connection < 30:
            urgent.append(f"loneliness ({100 - needs.social_connection}%)")
        if needs.intimacy < 25:
            urgent.append(f"intimacy ({100 - needs.intimacy}%)")

        return ", ".join(urgent)

    def _get_entity_registry_context(self, location_key: str, player_id: int) -> str:
        """Get entity registry for manifest references.

        Provides entity keys that the GM should use when referencing
        entities in structured output.

        Args:
            location_key: Current location key.
            player_id: Player entity ID.

        Returns:
            Formatted entity registry string.
        """
        lines = ["## Entity Registry (use these keys in manifest)"]

        # Player
        player = self.db.query(Entity).filter(Entity.id == player_id).first()
        if player:
            lines.append(f"\n### Player")
            lines.append(f"- {player.entity_key}: \"{player.display_name}\"")

        # NPCs at location
        npcs = (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                Entity.is_alive == True,
                Entity.is_active == True,
            )
            .limit(10)
            .all()
        )

        if npcs:
            lines.append(f"\n### NPCs at Location")
            for npc in npcs:
                goal_hint = ""
                active_goals = self.goal_manager.get_active_goals(entity_id=npc.id)
                if active_goals:
                    top_goal = active_goals[0]
                    goal_hint = f" (HERE FOR: {top_goal.description})"
                lines.append(f"- {npc.entity_key}: \"{npc.display_name}\"{goal_hint}")

        # Player inventory (visible items)
        visible_items = self.item_manager.get_visible_equipment(player_id)
        if visible_items:
            lines.append(f"\n### Player Visible Items")
            for item in visible_items[:5]:
                lines.append(f"- {item.item_key}: \"{item.display_name}\"")

        # Location items
        location_items = self.item_manager.get_items_at_location(location_key)
        if location_items:
            lines.append(f"\n### Items at Location")
            for item in location_items[:5]:
                lines.append(f"- {item.item_key}: \"{item.display_name}\"")

        return "\n".join(lines)
