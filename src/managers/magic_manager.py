"""MagicManager for spell casting, mana management, and magic profiles."""

from dataclasses import dataclass, field

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.database.models.magic import (
    CastingTime,
    EntityMagicProfile,
    MagicTradition,
    SpellCastRecord,
    SpellDefinition,
    SpellSchool,
)
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class SpellInfo:
    """Information about a spell and whether it can be cast.

    Attributes:
        spell_key: The spell's unique key.
        name: Display name of the spell.
        school: School of magic.
        level: Spell level (0 = cantrip).
        cost: Mana cost to cast.
        can_cast: Whether the entity can currently cast this spell.
        reason_if_not: Reason why the spell cannot be cast, if applicable.
    """

    spell_key: str
    name: str
    school: str
    level: int
    cost: int
    can_cast: bool
    reason_if_not: str | None = None


@dataclass
class CastResult:
    """Result of attempting to cast a spell.

    Attributes:
        success: Whether the spell was successfully cast.
        mana_spent: Amount of mana consumed.
        effect_description: Description of the spell's effect.
        targets_affected: List of entity keys that were affected.
    """

    success: bool
    mana_spent: int
    effect_description: str
    targets_affected: list[str] = field(default_factory=list)


class MagicManager(BaseManager):
    """Manager for magic system.

    Handles:
    - Spell definition management
    - Entity magic profiles (mana, known spells)
    - Spell learning and preparation
    - Mana management
    - Spell casting validation and execution
    - Cast history tracking
    """

    # Mana cost per level when upcasting
    UPCAST_MANA_PER_LEVEL = 2

    # --- Magic Profile Management ---

    def get_or_create_magic_profile(self, entity_id: int) -> EntityMagicProfile:
        """Get or create a magic profile for an entity.

        Args:
            entity_id: The entity's ID.

        Returns:
            The entity's magic profile.
        """
        profile = self.get_magic_profile(entity_id)
        if profile:
            return profile

        profile = EntityMagicProfile(
            session_id=self.session_id,
            entity_id=entity_id,
            max_mana=0,
            current_mana=0,
            mana_regen_per_rest=0,
            known_spells=[],
        )
        self.db.add(profile)
        self.db.flush()
        return profile

    def get_magic_profile(self, entity_id: int) -> EntityMagicProfile | None:
        """Get an entity's magic profile.

        Args:
            entity_id: The entity's ID.

        Returns:
            EntityMagicProfile if found, None otherwise.
        """
        return (
            self.db.query(EntityMagicProfile)
            .filter(
                and_(
                    EntityMagicProfile.session_id == self.session_id,
                    EntityMagicProfile.entity_id == entity_id,
                )
            )
            .first()
        )

    def set_magic_profile(
        self,
        entity_id: int,
        tradition: MagicTradition | None = None,
        max_mana: int | None = None,
        current_mana: int | None = None,
        mana_regen_per_rest: int | None = None,
    ) -> EntityMagicProfile:
        """Set or update an entity's magic profile.

        Args:
            entity_id: The entity's ID.
            tradition: Magic tradition (arcane, divine, etc.).
            max_mana: Maximum mana pool.
            current_mana: Current mana available.
            mana_regen_per_rest: Mana restored per long rest.

        Returns:
            The updated magic profile.
        """
        profile = self.get_or_create_magic_profile(entity_id)

        if tradition is not None:
            profile.tradition = tradition.value if isinstance(tradition, MagicTradition) else tradition
        if max_mana is not None:
            profile.max_mana = max_mana
        if current_mana is not None:
            profile.current_mana = current_mana
        if mana_regen_per_rest is not None:
            profile.mana_regen_per_rest = mana_regen_per_rest

        self.db.flush()
        return profile

    # --- Spell Definition Management ---

    def create_spell(
        self,
        spell_key: str,
        display_name: str,
        tradition: MagicTradition,
        school: SpellSchool,
        level: int,
        base_cost: int,
        casting_time: CastingTime,
        range_description: str,
        duration: str,
        components: list[str],
        description: str,
        effects: dict,
        material_component: str | None = None,
        scaling: dict | None = None,
    ) -> SpellDefinition:
        """Create a new spell definition.

        Args:
            spell_key: Unique spell identifier.
            display_name: Human-readable spell name.
            tradition: Magic tradition.
            school: School of magic.
            level: Spell level (0 = cantrip).
            base_cost: Base mana cost.
            casting_time: How long to cast.
            range_description: Spell range description.
            duration: How long spell lasts.
            components: Required components.
            description: Full spell description.
            effects: Structured spell effects.
            material_component: Material component if required.
            scaling: How spell scales when upcast.

        Returns:
            The created SpellDefinition.
        """
        spell = SpellDefinition(
            session_id=self.session_id,
            spell_key=spell_key,
            display_name=display_name,
            tradition=tradition.value if isinstance(tradition, MagicTradition) else tradition,
            school=school.value if isinstance(school, SpellSchool) else school,
            level=level,
            base_cost=base_cost,
            casting_time=casting_time.value if isinstance(casting_time, CastingTime) else casting_time,
            range_description=range_description,
            duration=duration,
            components=components,
            material_component=material_component,
            description=description,
            effects=effects,
            scaling=scaling,
        )
        self.db.add(spell)
        self.db.flush()
        return spell

    def get_spell(self, spell_key: str) -> SpellDefinition | None:
        """Get a spell definition by key.

        Args:
            spell_key: The spell's unique key.

        Returns:
            SpellDefinition if found, None otherwise.
        """
        return (
            self.db.query(SpellDefinition)
            .filter(
                and_(
                    SpellDefinition.session_id == self.session_id,
                    SpellDefinition.spell_key == spell_key,
                )
            )
            .first()
        )

    def get_spells_by_tradition(self, tradition: MagicTradition) -> list[SpellDefinition]:
        """Get all spells of a specific tradition.

        Args:
            tradition: The magic tradition.

        Returns:
            List of matching SpellDefinitions.
        """
        return (
            self.db.query(SpellDefinition)
            .filter(
                and_(
                    SpellDefinition.session_id == self.session_id,
                    SpellDefinition.tradition == tradition.value,
                )
            )
            .all()
        )

    def get_spells_by_school(self, school: SpellSchool) -> list[SpellDefinition]:
        """Get all spells of a specific school.

        Args:
            school: The spell school.

        Returns:
            List of matching SpellDefinitions.
        """
        return (
            self.db.query(SpellDefinition)
            .filter(
                and_(
                    SpellDefinition.session_id == self.session_id,
                    SpellDefinition.school == school.value,
                )
            )
            .all()
        )

    def get_spells_by_level(self, level: int) -> list[SpellDefinition]:
        """Get all spells of a specific level.

        Args:
            level: The spell level (0 = cantrip).

        Returns:
            List of matching SpellDefinitions.
        """
        return (
            self.db.query(SpellDefinition)
            .filter(
                and_(
                    SpellDefinition.session_id == self.session_id,
                    SpellDefinition.level == level,
                )
            )
            .all()
        )

    # --- Spell Learning and Preparation ---

    def learn_spell(self, entity_id: int, spell_key: str) -> bool:
        """Add a spell to an entity's known spells.

        Args:
            entity_id: The entity's ID.
            spell_key: The spell to learn.

        Returns:
            True if spell was learned, False if already known or spell doesn't exist.
        """
        spell = self.get_spell(spell_key)
        if not spell:
            return False

        profile = self.get_or_create_magic_profile(entity_id)

        if spell_key in profile.known_spells:
            return False

        profile.known_spells = profile.known_spells + [spell_key]
        flag_modified(profile, "known_spells")
        self.db.flush()
        return True

    def forget_spell(self, entity_id: int, spell_key: str) -> bool:
        """Remove a spell from an entity's known spells.

        Args:
            entity_id: The entity's ID.
            spell_key: The spell to forget.

        Returns:
            True if spell was forgotten, False if not known.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile or spell_key not in profile.known_spells:
            return False

        profile.known_spells = [s for s in profile.known_spells if s != spell_key]
        flag_modified(profile, "known_spells")

        # Also remove from prepared if applicable
        if profile.prepared_spells and spell_key in profile.prepared_spells:
            profile.prepared_spells = [s for s in profile.prepared_spells if s != spell_key]
            if not profile.prepared_spells:
                profile.prepared_spells = None
            flag_modified(profile, "prepared_spells")

        self.db.flush()
        return True

    def prepare_spell(self, entity_id: int, spell_key: str) -> bool:
        """Prepare a known spell for casting.

        Args:
            entity_id: The entity's ID.
            spell_key: The spell to prepare.

        Returns:
            True if spell was prepared, False if not known or already prepared.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile or spell_key not in profile.known_spells:
            return False

        if profile.prepared_spells is None:
            profile.prepared_spells = []

        if spell_key in profile.prepared_spells:
            return False

        profile.prepared_spells = profile.prepared_spells + [spell_key]
        flag_modified(profile, "prepared_spells")
        self.db.flush()
        return True

    def unprepare_spell(self, entity_id: int, spell_key: str) -> bool:
        """Unprepare a spell.

        Args:
            entity_id: The entity's ID.
            spell_key: The spell to unprepare.

        Returns:
            True if spell was unprepared, False if not prepared.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile or not profile.prepared_spells or spell_key not in profile.prepared_spells:
            return False

        profile.prepared_spells = [s for s in profile.prepared_spells if s != spell_key]
        flag_modified(profile, "prepared_spells")
        self.db.flush()
        return True

    # --- Mana Management ---

    def spend_mana(self, entity_id: int, amount: int) -> bool:
        """Spend mana from an entity's pool.

        Args:
            entity_id: The entity's ID.
            amount: Amount of mana to spend.

        Returns:
            True if mana was spent, False if insufficient.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile or profile.current_mana < amount:
            return False

        profile.current_mana -= amount
        self.db.flush()
        return True

    def restore_mana(self, entity_id: int, amount: int) -> int:
        """Restore mana to an entity's pool.

        Args:
            entity_id: The entity's ID.
            amount: Amount of mana to restore.

        Returns:
            Actual amount of mana restored (capped at max).
        """
        profile = self.get_magic_profile(entity_id)
        if not profile:
            return 0

        actual_restore = min(amount, profile.max_mana - profile.current_mana)
        profile.current_mana += actual_restore
        self.db.flush()
        return actual_restore

    def regenerate_mana(self, entity_id: int, rest_type: str = "long") -> int:
        """Regenerate mana based on rest type.

        Args:
            entity_id: The entity's ID.
            rest_type: "long" for full regen, "short" for half.

        Returns:
            Amount of mana restored.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile:
            return 0

        regen_amount = profile.mana_regen_per_rest
        if rest_type == "short":
            regen_amount = regen_amount // 2

        return self.restore_mana(entity_id, regen_amount)

    # --- Casting Validation ---

    def can_cast_spell(
        self, entity_id: int, spell_key: str, upcast_level: int | None = None
    ) -> tuple[bool, str | None]:
        """Check if an entity can cast a spell.

        Args:
            entity_id: The entity's ID.
            spell_key: The spell to cast.
            upcast_level: Level to cast at (if higher than base).

        Returns:
            Tuple of (can_cast, reason_if_not).
        """
        profile = self.get_magic_profile(entity_id)
        if not profile:
            return False, "No magic profile"

        spell = self.get_spell(spell_key)
        if not spell:
            return False, "Spell does not exist"

        if spell_key not in profile.known_spells:
            return False, "Spell not known"

        # Check preparation (only if prepared_spells is initialized)
        if profile.prepared_spells is not None and spell_key not in profile.prepared_spells:
            # Cantrips don't need preparation
            if spell.level > 0:
                return False, "Spell not prepared"

        # Calculate mana cost
        mana_cost = spell.base_cost
        if upcast_level and upcast_level > spell.level:
            mana_cost += (upcast_level - spell.level) * self.UPCAST_MANA_PER_LEVEL

        # Cantrips are free
        if spell.level == 0:
            mana_cost = 0

        if profile.current_mana < mana_cost:
            return False, f"Insufficient mana (need {mana_cost}, have {profile.current_mana})"

        return True, None

    # --- Spell Casting ---

    def cast_spell(
        self,
        caster_id: int,
        spell_key: str,
        target_keys: list[str],
        upcast_level: int | None = None,
    ) -> CastResult:
        """Cast a spell.

        Args:
            caster_id: The caster's entity ID.
            spell_key: The spell to cast.
            target_keys: Entity keys of targets.
            upcast_level: Level to cast at (if higher than base).

        Returns:
            CastResult with outcome details.
        """
        can_cast, reason = self.can_cast_spell(caster_id, spell_key, upcast_level)
        if not can_cast:
            return CastResult(
                success=False,
                mana_spent=0,
                effect_description=f"Failed to cast: {reason}",
                targets_affected=[],
            )

        spell = self.get_spell(spell_key)

        # Calculate mana cost
        mana_cost = spell.base_cost
        if upcast_level and upcast_level > spell.level:
            mana_cost += (upcast_level - spell.level) * self.UPCAST_MANA_PER_LEVEL

        # Cantrips are free
        if spell.level == 0:
            mana_cost = 0

        # Spend mana
        if mana_cost > 0:
            self.spend_mana(caster_id, mana_cost)

        # Record the cast
        cast_record = SpellCastRecord(
            session_id=self.session_id,
            caster_entity_id=caster_id,
            spell_key=spell_key,
            turn_cast=self.current_turn,
            target_entity_keys=target_keys,
            mana_spent=mana_cost,
            success=True,
            outcome_description=f"Cast {spell.display_name}",
        )
        self.db.add(cast_record)
        self.db.flush()

        return CastResult(
            success=True,
            mana_spent=mana_cost,
            effect_description=f"Cast {spell.display_name}",
            targets_affected=target_keys,
        )

    # --- Spell Info and History ---

    def get_known_spells(self, entity_id: int) -> list[SpellInfo]:
        """Get list of known spells with cast availability info.

        Args:
            entity_id: The entity's ID.

        Returns:
            List of SpellInfo for each known spell.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile:
            return []

        result = []
        for spell_key in profile.known_spells:
            spell = self.get_spell(spell_key)
            if not spell:
                continue

            can_cast, reason = self.can_cast_spell(entity_id, spell_key)

            result.append(
                SpellInfo(
                    spell_key=spell_key,
                    name=spell.display_name,
                    school=spell.school,
                    level=spell.level,
                    cost=spell.base_cost,
                    can_cast=can_cast,
                    reason_if_not=reason,
                )
            )

        return result

    def get_spell_cast_history(
        self, entity_id: int, limit: int = 10
    ) -> list[SpellCastRecord]:
        """Get spell cast history for an entity.

        Args:
            entity_id: The entity's ID.
            limit: Maximum number of records to return.

        Returns:
            List of SpellCastRecords, most recent first.
        """
        return (
            self.db.query(SpellCastRecord)
            .filter(
                and_(
                    SpellCastRecord.session_id == self.session_id,
                    SpellCastRecord.caster_entity_id == entity_id,
                )
            )
            .order_by(SpellCastRecord.turn_cast.desc())
            .limit(limit)
            .all()
        )

    # --- Context Generation ---

    def get_magic_context(self, entity_id: int) -> str:
        """Generate magic context for GM prompts.

        Args:
            entity_id: The entity's ID.

        Returns:
            Formatted string describing magic status.
        """
        profile = self.get_magic_profile(entity_id)
        if not profile:
            return ""

        lines = ["## Magic Status", ""]

        # Tradition and mana
        if profile.tradition:
            lines.append(f"**Tradition:** {profile.tradition.title()}")
        lines.append(f"**Mana:** {profile.current_mana}/{profile.max_mana}")
        lines.append("")

        # Known spells
        if profile.known_spells:
            lines.append("**Known Spells:**")
            for spell_key in profile.known_spells:
                spell = self.get_spell(spell_key)
                if spell:
                    prepared = ""
                    if profile.prepared_spells and spell_key in profile.prepared_spells:
                        prepared = " (prepared)"
                    level_str = "cantrip" if spell.level == 0 else f"level {spell.level}"
                    lines.append(f"- {spell.display_name} ({level_str}, {spell.base_cost} mana){prepared}")

        return "\n".join(lines)
