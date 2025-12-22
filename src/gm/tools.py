"""Tools for the Simplified GM Pipeline.

Provides tool functions for skill checks, combat, and entity creation.
These tools are called by the GM LLM during generation.
"""

import random
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.database.models.entities import Entity, EntityAttribute, EntitySkill
from src.database.models.enums import EntityType
from src.database.models.items import Item
from src.database.models.session import GameSession
from src.dice.checks import (
    make_skill_check,
    proficiency_to_modifier,
    calculate_ability_modifier,
)
from src.dice.types import AdvantageType
from src.gm.schemas import (
    SkillCheckResult as GMSkillCheckResult,
    AttackResult,
    DamageResult,
    CreateEntityResult,
    EntityType as GMEntityType,
)
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager


class GMTools:
    """Tool provider for the GM LLM.

    Handles skill checks, combat rolls, and entity creation.
    Supports both auto mode (immediate results) and manual mode
    (returns pending for player roll animation).
    """

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player_id: int,
        roll_mode: str = "auto",
    ) -> None:
        """Initialize tools.

        Args:
            db: Database session.
            game_session: Current game session.
            player_id: Player entity ID.
            roll_mode: "auto" for background rolls, "manual" for player animation.
        """
        self.db = db
        self.game_session = game_session
        self.session_id = game_session.id
        self.player_id = player_id
        self.roll_mode = roll_mode

        self._entity_manager: EntityManager | None = None
        self._item_manager: ItemManager | None = None

    @property
    def entity_manager(self) -> EntityManager:
        if self._entity_manager is None:
            self._entity_manager = EntityManager(self.db, self.game_session)
        return self._entity_manager

    @property
    def item_manager(self) -> ItemManager:
        if self._item_manager is None:
            self._item_manager = ItemManager(self.db, self.game_session)
        return self._item_manager

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Claude API.

        Returns:
            List of tool definitions in Claude's format.
        """
        return [
            {
                "name": "skill_check",
                "description": (
                    "Roll a skill check when outcome is uncertain. "
                    "Returns success/failure with roll details."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": "Skill being checked (e.g., stealth, perception, lockpick)",
                        },
                        "dc": {
                            "type": "integer",
                            "description": "Difficulty Class (10=easy, 15=medium, 20=hard, 25=very hard)",
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional context for the check",
                        },
                    },
                    "required": ["skill", "dc"],
                },
            },
            {
                "name": "attack_roll",
                "description": (
                    "Make an attack against a target. "
                    "Returns hit/miss and damage if hit."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Entity key of the target",
                        },
                        "weapon": {
                            "type": "string",
                            "description": "Weapon item key (or 'unarmed')",
                        },
                        "attacker": {
                            "type": "string",
                            "description": "Entity key of attacker (default: player)",
                        },
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "damage_entity",
                "description": (
                    "Apply damage to an entity after a hit. "
                    "Returns remaining HP and status."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Entity key of the target",
                        },
                        "amount": {
                            "type": "integer",
                            "description": "Damage amount to apply",
                        },
                        "damage_type": {
                            "type": "string",
                            "description": "Type of damage (physical, fire, cold, poison)",
                        },
                    },
                    "required": ["target", "amount"],
                },
            },
            {
                "name": "create_entity",
                "description": (
                    "Create a new NPC, item, or location. "
                    "Use this to introduce new things that don't exist yet."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["npc", "item", "location"],
                            "description": "Type of entity to create",
                        },
                        "name": {
                            "type": "string",
                            "description": "Display name for the entity",
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description",
                        },
                        "gender": {
                            "type": "string",
                            "description": "For NPCs: male, female, or other",
                        },
                        "occupation": {
                            "type": "string",
                            "description": "For NPCs: their job/role",
                        },
                        "item_type": {
                            "type": "string",
                            "description": "For items: weapon, armor, clothing, tool, misc",
                        },
                        "category": {
                            "type": "string",
                            "description": "For locations: interior, exterior, underground",
                        },
                        "parent_location": {
                            "type": "string",
                            "description": "For locations: parent location key",
                        },
                    },
                    "required": ["entity_type", "name", "description"],
                },
            },
            {
                "name": "record_fact",
                "description": (
                    "Record a fact about the world using Subject-Predicate-Value pattern. "
                    "Use this when inventing or revealing lore, especially during OOC responses. "
                    "Examples: 'widow_brennan has_occupation herbalist', 'village was_founded 200_years_ago'."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject_type": {
                            "type": "string",
                            "enum": ["entity", "location", "world", "item", "group"],
                            "description": "Type of thing the fact is about",
                        },
                        "subject_key": {
                            "type": "string",
                            "description": "Key of the subject (e.g., npc_marcus, village_eldoria)",
                        },
                        "predicate": {
                            "type": "string",
                            "description": "What aspect this describes (e.g., has_occupation, was_born_in, knows_secret)",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value of the fact",
                        },
                        "is_secret": {
                            "type": "boolean",
                            "description": "Whether this is GM-only knowledge (hidden from player)",
                        },
                    },
                    "required": ["subject_type", "subject_key", "predicate", "value"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Tool result as a dictionary.
        """
        if tool_name == "skill_check":
            return self.skill_check(**tool_input).model_dump()
        elif tool_name == "attack_roll":
            return self.attack_roll(**tool_input).model_dump()
        elif tool_name == "damage_entity":
            return self.damage_entity(**tool_input).model_dump()
        elif tool_name == "create_entity":
            return self.create_entity(**tool_input).model_dump()
        elif tool_name == "record_fact":
            return self.record_fact(**tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def skill_check(
        self,
        skill: str,
        dc: int,
        context: str = "",
    ) -> GMSkillCheckResult:
        """Execute a skill check.

        Args:
            skill: The skill being checked.
            dc: Difficulty Class.
            context: Optional context for the check.

        Returns:
            SkillCheckResult with roll details.
        """
        # Get player's skill modifier
        skill_modifier = self._get_skill_modifier(self.player_id, skill)
        attribute_modifier = self._get_related_attribute_modifier(self.player_id, skill)

        # Manual mode: return pending for player to roll
        if self.roll_mode == "manual":
            return GMSkillCheckResult(
                pending=True,
                skill=skill,
                dc=dc,
                modifier=skill_modifier + attribute_modifier,
            )

        # Auto mode: roll immediately using the dice system
        result = make_skill_check(
            dc=dc,
            attribute_modifier=attribute_modifier,
            skill_modifier=skill_modifier,
            advantage_type=AdvantageType.NORMAL,
        )

        # Extract roll value (2d10 system)
        if result.roll_result:
            roll = result.roll_result.total - (skill_modifier + attribute_modifier)
        else:
            roll = 11  # Auto-success average

        return GMSkillCheckResult(
            pending=False,
            skill=skill,
            dc=dc,
            modifier=skill_modifier + attribute_modifier,
            roll=roll,
            total=result.roll_result.total if result.roll_result else roll + skill_modifier + attribute_modifier,
            success=result.success,
            critical_success=result.is_critical_success,
            critical_failure=result.is_critical_failure,
        )

    def attack_roll(
        self,
        target: str,
        weapon: str = "unarmed",
        attacker: str | None = None,
    ) -> AttackResult:
        """Make an attack roll.

        Args:
            target: Entity key of the target.
            weapon: Weapon item key or "unarmed".
            attacker: Attacker entity key (default: player).

        Returns:
            AttackResult with hit/miss and damage.
        """
        # Get attacker
        if attacker is None or attacker == "player":
            attacker_entity = self.db.query(Entity).filter(Entity.id == self.player_id).first()
            attacker_key = attacker_entity.entity_key if attacker_entity else "player"
        else:
            attacker_entity = self.entity_manager.get_entity(attacker)
            attacker_key = attacker

        # Get target
        target_entity = self.entity_manager.get_entity(target)
        if not target_entity:
            return AttackResult(
                target=target,
                weapon=weapon,
                attacker=attacker_key,
                roll=0,
                hits=False,
            )

        # Calculate attack bonus
        attack_bonus = self._get_attack_bonus(attacker_entity, weapon)

        # Get target AC (from attributes or default)
        target_ac = self._get_armor_class(target_entity)

        # Manual mode: return pending
        if self.roll_mode == "manual":
            return AttackResult(
                pending=True,
                attacker=attacker_key,
                target=target,
                weapon=weapon,
                attack_bonus=attack_bonus,
                target_ac=target_ac,
            )

        # Auto mode: roll attack
        # Use 2d10 for attack (to be consistent with skill checks)
        roll = random.randint(1, 10) + random.randint(1, 10)
        total = roll + attack_bonus
        hits = total >= target_ac
        critical = roll == 20  # Double 10s

        # Calculate damage if hit
        damage = 0
        if hits:
            damage = self._roll_weapon_damage(weapon, critical)

        return AttackResult(
            pending=False,
            attacker=attacker_key,
            target=target,
            weapon=weapon,
            attack_bonus=attack_bonus,
            target_ac=target_ac,
            roll=roll,
            hits=hits,
            critical=critical,
            damage=damage,
        )

    def damage_entity(
        self,
        target: str,
        amount: int,
        damage_type: str = "physical",
    ) -> DamageResult:
        """Apply damage to an entity.

        Args:
            target: Entity key of the target.
            amount: Damage amount.
            damage_type: Type of damage.

        Returns:
            DamageResult with remaining HP.
        """
        target_entity = self.entity_manager.get_entity(target)
        if not target_entity:
            return DamageResult(
                target=target,
                damage_taken=0,
                remaining_hp=0,
                unconscious=False,
                dead=False,
            )

        # Get current HP (from attributes or default)
        current_hp = self._get_entity_hp(target_entity)
        new_hp = max(0, current_hp - amount)

        # Update HP in database
        self._set_entity_hp(target_entity, new_hp)

        return DamageResult(
            target=target,
            damage_taken=amount,
            remaining_hp=new_hp,
            unconscious=new_hp == 0,
            dead=new_hp <= -10,  # Using negative HP death threshold
        )

    def create_entity(
        self,
        entity_type: str,
        name: str,
        description: str,
        gender: str | None = None,
        occupation: str | None = None,
        item_type: str | None = None,
        category: str | None = None,
        parent_location: str | None = None,
    ) -> CreateEntityResult:
        """Create a new entity.

        Args:
            entity_type: Type of entity (npc, item, location).
            name: Display name.
            description: Detailed description.
            gender: For NPCs.
            occupation: For NPCs.
            item_type: For items.
            category: For locations.
            parent_location: For locations.

        Returns:
            CreateEntityResult with the new entity key.
        """
        # Generate a unique key
        base_key = name.lower().replace(" ", "_").replace("'", "")
        entity_key = f"{base_key}_{random.randint(100, 999)}"

        try:
            if entity_type == "npc":
                entity = self.entity_manager.create_npc(
                    entity_key=entity_key,
                    display_name=name,
                    gender=gender or "unknown",
                    occupation=occupation,
                )
                # Add description as a note or in extension
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.NPC,
                    display_name=name,
                    success=True,
                )

            elif entity_type == "item":
                item = self.item_manager.create_item(
                    item_key=entity_key,
                    display_name=name,
                    description=description,
                    item_type=item_type or "misc",
                )
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.ITEM,
                    display_name=name,
                    success=True,
                )

            elif entity_type == "location":
                from src.managers.location_manager import LocationManager
                location_manager = LocationManager(self.db, self.game_session)
                location = location_manager.create_location(
                    location_key=entity_key,
                    display_name=name,
                    description=description,
                    parent_key=parent_location,
                    category=category or "interior",
                )
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.LOCATION,
                    display_name=name,
                    success=True,
                )

            else:
                return CreateEntityResult(
                    entity_key=entity_key,
                    entity_type=GMEntityType.ITEM,  # Default
                    display_name=name,
                    success=False,
                    error=f"Unknown entity type: {entity_type}",
                )

        except Exception as e:
            return CreateEntityResult(
                entity_key=entity_key,
                entity_type=GMEntityType.NPC,
                display_name=name,
                success=False,
                error=str(e),
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_skill_modifier(self, entity_id: int, skill: str) -> int:
        """Get skill modifier for an entity."""
        skill_record = (
            self.db.query(EntitySkill)
            .filter(
                EntitySkill.entity_id == entity_id,
                EntitySkill.skill_key == skill.lower(),
            )
            .first()
        )

        if skill_record:
            return proficiency_to_modifier(skill_record.proficiency_level)

        return 0  # No proficiency

    def _get_related_attribute_modifier(self, entity_id: int, skill: str) -> int:
        """Get the attribute modifier related to a skill.

        Maps skills to their governing attributes.
        """
        # Skill to attribute mapping
        skill_attributes = {
            "stealth": "dexterity",
            "perception": "wisdom",
            "lockpick": "dexterity",
            "persuasion": "charisma",
            "intimidation": "charisma",
            "athletics": "strength",
            "acrobatics": "dexterity",
            "survival": "wisdom",
            "medicine": "wisdom",
            "investigation": "intelligence",
            "deception": "charisma",
        }

        attribute_key = skill_attributes.get(skill.lower(), "dexterity")

        attribute = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == attribute_key,
            )
            .first()
        )

        if attribute:
            return calculate_ability_modifier(attribute.value)

        return 0  # Default modifier

    def _get_attack_bonus(self, entity: Entity | None, weapon: str) -> int:
        """Calculate attack bonus for an entity with a weapon."""
        if not entity:
            return 0

        # Get strength or dexterity modifier based on weapon
        # For now, use strength for melee, dexterity for ranged
        # TODO: Check weapon properties

        strength_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "strength",
            )
            .first()
        )

        modifier = 0
        if strength_attr:
            modifier = calculate_ability_modifier(strength_attr.value)

        # Add proficiency bonus (simplified: +2 for most characters)
        return modifier + 2

    def _get_armor_class(self, entity: Entity) -> int:
        """Calculate armor class for an entity."""
        # Base AC is 10
        ac = 10

        # Add dexterity modifier
        dex_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "dexterity",
            )
            .first()
        )

        if dex_attr:
            ac += calculate_ability_modifier(dex_attr.value)

        # TODO: Add armor bonuses from equipped items

        return ac

    def _roll_weapon_damage(self, weapon: str, critical: bool = False) -> int:
        """Roll damage for a weapon."""
        # Default unarmed damage: 1d4
        if weapon == "unarmed":
            damage = random.randint(1, 4)
        else:
            # TODO: Look up weapon damage from item
            # Default weapon damage: 1d8
            damage = random.randint(1, 8)

        if critical:
            damage *= 2

        return damage

    def _get_entity_hp(self, entity: Entity) -> int:
        """Get current HP for an entity."""
        # Check for HP attribute
        hp_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "hp",
            )
            .first()
        )

        if hp_attr:
            return hp_attr.value

        # Default HP based on entity type
        if entity.entity_type == EntityType.NPC:
            return 10  # Default NPC HP
        return 20  # Default player HP

    def _set_entity_hp(self, entity: Entity, hp: int) -> None:
        """Set HP for an entity."""
        hp_attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity.id,
                EntityAttribute.attribute_key == "hp",
            )
            .first()
        )

        if hp_attr:
            hp_attr.value = hp
        else:
            # Create HP attribute
            new_attr = EntityAttribute(
                entity_id=entity.id,
                attribute_key="hp",
                value=hp,
            )
            self.db.add(new_attr)

        self.db.commit()

    def record_fact(
        self,
        subject_type: str,
        subject_key: str,
        predicate: str,
        value: str,
        is_secret: bool = False,
    ) -> dict[str, Any]:
        """Record a fact about the world using SPV pattern.

        Args:
            subject_type: Type of subject (entity, location, world, item, group).
            subject_key: Key of the subject.
            predicate: What aspect this describes.
            value: The value of the fact.
            is_secret: Whether this is GM-only knowledge.

        Returns:
            Result dict with success status.
        """
        from src.database.models.world import Fact
        from src.database.models.enums import FactCategory

        # Check for existing fact with same subject and predicate
        existing = (
            self.db.query(Fact)
            .filter(
                Fact.session_id == self.session_id,
                Fact.subject_key == subject_key,
                Fact.predicate == predicate,
            )
            .first()
        )

        if existing:
            # Update existing fact
            existing.value = value
            existing.is_secret = is_secret
            self.db.flush()
            return {
                "success": True,
                "updated": True,
                "message": f"Updated: {subject_key}.{predicate} = {value}",
            }

        # Create new fact
        fact = Fact(
            session_id=self.session_id,
            subject_type=subject_type,
            subject_key=subject_key,
            predicate=predicate,
            value=value,
            category=FactCategory.PERSONAL,
            is_secret=is_secret,
            confidence=80,
        )
        self.db.add(fact)
        self.db.flush()

        return {
            "success": True,
            "created": True,
            "message": f"Recorded: {subject_key}.{predicate} = {value}",
        }
