"""Tests for MagicManager."""

import pytest
from sqlalchemy.orm import Session

from src.database.models.magic import (
    CastingTime,
    EntityMagicProfile,
    MagicTradition,
    SpellCastRecord,
    SpellDefinition,
    SpellSchool,
)
from src.database.models.session import GameSession
from src.database.models.entities import Entity
from src.database.models.enums import EntityType
from src.managers.magic_manager import (
    CastResult,
    MagicManager,
    SpellInfo,
)


@pytest.fixture
def magic_manager(db_session: Session, game_session: GameSession) -> MagicManager:
    """Create a MagicManager fixture."""
    return MagicManager(db=db_session, game_session=game_session)


@pytest.fixture
def wizard_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a wizard entity fixture."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="wizard_merlin",
        display_name="Merlin the Wizard",
        entity_type=EntityType.NPC,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def target_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a target entity fixture."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="goblin_enemy",
        display_name="Goblin",
        entity_type=EntityType.MONSTER,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def fireball_spell(db_session: Session, game_session: GameSession) -> SpellDefinition:
    """Create a fireball spell definition."""
    spell = SpellDefinition(
        session_id=game_session.id,
        spell_key="fireball",
        display_name="Fireball",
        tradition=MagicTradition.ARCANE.value,
        school=SpellSchool.EVOCATION.value,
        level=3,
        base_cost=5,
        casting_time=CastingTime.ACTION.value,
        range_description="150 feet",
        duration="instantaneous",
        components=["verbal", "somatic", "material"],
        material_component="a tiny ball of bat guano and sulfur",
        description="A bright streak flashes from your pointing finger.",
        effects={
            "damage": {
                "dice": "8d6",
                "type": "fire",
                "save": "dexterity",
                "half_on_save": True,
            }
        },
        scaling={"additional_dice_per_level": "1d6"},
    )
    db_session.add(spell)
    db_session.flush()
    return spell


@pytest.fixture
def heal_spell(db_session: Session, game_session: GameSession) -> SpellDefinition:
    """Create a healing spell definition."""
    spell = SpellDefinition(
        session_id=game_session.id,
        spell_key="cure_wounds",
        display_name="Cure Wounds",
        tradition=MagicTradition.DIVINE.value,
        school=SpellSchool.EVOCATION.value,
        level=1,
        base_cost=2,
        casting_time=CastingTime.ACTION.value,
        range_description="touch",
        duration="instantaneous",
        components=["verbal", "somatic"],
        material_component=None,
        description="A creature you touch regains hit points.",
        effects={"healing": {"dice": "1d8", "bonus": 3}},
        scaling={"additional_dice_per_level": "1d8"},
    )
    db_session.add(spell)
    db_session.flush()
    return spell


@pytest.fixture
def cantrip_spell(db_session: Session, game_session: GameSession) -> SpellDefinition:
    """Create a cantrip (level 0) spell definition."""
    spell = SpellDefinition(
        session_id=game_session.id,
        spell_key="fire_bolt",
        display_name="Fire Bolt",
        tradition=MagicTradition.ARCANE.value,
        school=SpellSchool.EVOCATION.value,
        level=0,
        base_cost=0,  # Cantrips are free
        casting_time=CastingTime.ACTION.value,
        range_description="120 feet",
        duration="instantaneous",
        components=["verbal", "somatic"],
        material_component=None,
        description="You hurl a mote of fire at a creature.",
        effects={"damage": {"dice": "1d10", "type": "fire"}},
        scaling=None,
    )
    db_session.add(spell)
    db_session.flush()
    return spell


# --- Magic Profile Tests ---


class TestMagicProfile:
    """Tests for magic profile management."""

    def test_get_or_create_magic_profile_creates_new(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test creating a new magic profile."""
        profile = magic_manager.get_or_create_magic_profile(wizard_entity.id)

        assert profile is not None
        assert profile.entity_id == wizard_entity.id
        assert profile.max_mana == 0
        assert profile.current_mana == 0
        assert profile.known_spells == []

    def test_get_or_create_magic_profile_returns_existing(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test getting existing magic profile."""
        # Create a profile manually
        existing = EntityMagicProfile(
            session_id=game_session.id,
            entity_id=wizard_entity.id,
            tradition=MagicTradition.ARCANE.value,
            max_mana=20,
            current_mana=15,
            mana_regen_per_rest=10,
            known_spells=["fireball"],
        )
        db_session.add(existing)
        db_session.flush()

        # Should return the existing profile
        profile = magic_manager.get_or_create_magic_profile(wizard_entity.id)

        assert profile.id == existing.id
        assert profile.max_mana == 20
        assert profile.current_mana == 15

    def test_set_magic_profile(self, magic_manager: MagicManager, wizard_entity: Entity):
        """Test setting magic profile properties."""
        profile = magic_manager.set_magic_profile(
            entity_id=wizard_entity.id,
            tradition=MagicTradition.ARCANE,
            max_mana=30,
            current_mana=30,
            mana_regen_per_rest=15,
        )

        assert profile.tradition == MagicTradition.ARCANE.value
        assert profile.max_mana == 30
        assert profile.current_mana == 30
        assert profile.mana_regen_per_rest == 15

    def test_get_magic_profile(self, magic_manager: MagicManager, wizard_entity: Entity):
        """Test getting magic profile by entity ID."""
        # Create profile first
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id,
            max_mana=25,
        )

        profile = magic_manager.get_magic_profile(wizard_entity.id)

        assert profile is not None
        assert profile.max_mana == 25

    def test_get_magic_profile_not_found(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test getting non-existent magic profile."""
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile is None


# --- Spell Definition Tests ---


class TestSpellDefinitions:
    """Tests for spell definition management."""

    def test_create_spell(self, magic_manager: MagicManager):
        """Test creating a spell definition."""
        spell = magic_manager.create_spell(
            spell_key="magic_missile",
            display_name="Magic Missile",
            tradition=MagicTradition.ARCANE,
            school=SpellSchool.EVOCATION,
            level=1,
            base_cost=2,
            casting_time=CastingTime.ACTION,
            range_description="120 feet",
            duration="instantaneous",
            components=["verbal", "somatic"],
            description="You create three glowing darts of magical force.",
            effects={"damage": {"dice": "1d4+1", "type": "force", "auto_hit": True}},
        )

        assert spell.spell_key == "magic_missile"
        assert spell.level == 1
        assert spell.tradition == MagicTradition.ARCANE.value

    def test_get_spell(
        self, magic_manager: MagicManager, fireball_spell: SpellDefinition
    ):
        """Test getting a spell by key."""
        spell = magic_manager.get_spell("fireball")

        assert spell is not None
        assert spell.display_name == "Fireball"
        assert spell.level == 3

    def test_get_spell_not_found(self, magic_manager: MagicManager):
        """Test getting non-existent spell."""
        spell = magic_manager.get_spell("nonexistent_spell")
        assert spell is None

    def test_get_spells_by_tradition(
        self,
        magic_manager: MagicManager,
        fireball_spell: SpellDefinition,
        heal_spell: SpellDefinition,
    ):
        """Test getting spells by tradition."""
        arcane_spells = magic_manager.get_spells_by_tradition(MagicTradition.ARCANE)
        divine_spells = magic_manager.get_spells_by_tradition(MagicTradition.DIVINE)

        assert len(arcane_spells) == 1
        assert arcane_spells[0].spell_key == "fireball"
        assert len(divine_spells) == 1
        assert divine_spells[0].spell_key == "cure_wounds"

    def test_get_spells_by_school(
        self, magic_manager: MagicManager, fireball_spell: SpellDefinition
    ):
        """Test getting spells by school."""
        evocation_spells = magic_manager.get_spells_by_school(SpellSchool.EVOCATION)
        illusion_spells = magic_manager.get_spells_by_school(SpellSchool.ILLUSION)

        assert len(evocation_spells) == 1
        assert evocation_spells[0].spell_key == "fireball"
        assert len(illusion_spells) == 0

    def test_get_spells_by_level(
        self,
        magic_manager: MagicManager,
        fireball_spell: SpellDefinition,
        heal_spell: SpellDefinition,
        cantrip_spell: SpellDefinition,
    ):
        """Test getting spells by level."""
        cantrips = magic_manager.get_spells_by_level(0)
        level_1 = magic_manager.get_spells_by_level(1)
        level_3 = magic_manager.get_spells_by_level(3)

        assert len(cantrips) == 1
        assert cantrips[0].spell_key == "fire_bolt"
        assert len(level_1) == 1
        assert len(level_3) == 1


# --- Learning and Preparation Tests ---


class TestSpellLearning:
    """Tests for spell learning and preparation."""

    def test_learn_spell(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test learning a spell."""
        # Create magic profile
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)

        result = magic_manager.learn_spell(wizard_entity.id, "fireball")

        assert result is True
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert "fireball" in profile.known_spells

    def test_learn_spell_already_known(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test learning an already known spell."""
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)
        magic_manager.learn_spell(wizard_entity.id, "fireball")

        # Try to learn again
        result = magic_manager.learn_spell(wizard_entity.id, "fireball")

        assert result is False

    def test_learn_spell_nonexistent(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test learning a non-existent spell."""
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)

        result = magic_manager.learn_spell(wizard_entity.id, "nonexistent")

        assert result is False

    def test_prepare_spell(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test preparing a known spell."""
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)
        magic_manager.learn_spell(wizard_entity.id, "fireball")

        result = magic_manager.prepare_spell(wizard_entity.id, "fireball")

        assert result is True
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert "fireball" in profile.prepared_spells

    def test_prepare_spell_not_known(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test preparing an unknown spell fails."""
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)

        result = magic_manager.prepare_spell(wizard_entity.id, "fireball")

        assert result is False

    def test_unprepare_spell(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test unpreparing a spell."""
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        result = magic_manager.unprepare_spell(wizard_entity.id, "fireball")

        assert result is True
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert "fireball" not in profile.prepared_spells

    def test_forget_spell(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test forgetting a spell removes it from known and prepared."""
        magic_manager.set_magic_profile(entity_id=wizard_entity.id, max_mana=20)
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        result = magic_manager.forget_spell(wizard_entity.id, "fireball")

        assert result is True
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert "fireball" not in profile.known_spells
        assert profile.prepared_spells is None or "fireball" not in profile.prepared_spells


# --- Mana Management Tests ---


class TestManaManagement:
    """Tests for mana pool management."""

    def test_spend_mana(self, magic_manager: MagicManager, wizard_entity: Entity):
        """Test spending mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=20
        )

        result = magic_manager.spend_mana(wizard_entity.id, 5)

        assert result is True
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 15

    def test_spend_mana_insufficient(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test spending mana with insufficient amount."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=3
        )

        result = magic_manager.spend_mana(wizard_entity.id, 5)

        assert result is False
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 3  # Unchanged

    def test_restore_mana(self, magic_manager: MagicManager, wizard_entity: Entity):
        """Test restoring mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=10
        )

        restored = magic_manager.restore_mana(wizard_entity.id, 5)

        assert restored == 5
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 15

    def test_restore_mana_caps_at_max(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test restoring mana doesn't exceed maximum."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=18
        )

        restored = magic_manager.restore_mana(wizard_entity.id, 10)

        assert restored == 2  # Only 2 could be restored
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 20

    def test_regenerate_mana_long_rest(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test mana regeneration on long rest."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id,
            max_mana=30,
            current_mana=5,
            mana_regen_per_rest=15,
        )

        restored = magic_manager.regenerate_mana(wizard_entity.id, rest_type="long")

        assert restored == 15
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 20

    def test_regenerate_mana_short_rest(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test mana regeneration on short rest (half of long rest)."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id,
            max_mana=30,
            current_mana=10,
            mana_regen_per_rest=20,
        )

        restored = magic_manager.regenerate_mana(wizard_entity.id, rest_type="short")

        assert restored == 10  # Half of long rest regen
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 20


# --- Casting Validation Tests ---


class TestCastingValidation:
    """Tests for spell casting validation."""

    def test_can_cast_spell_success(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test can cast when all conditions met."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=10
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        can_cast, reason = magic_manager.can_cast_spell(wizard_entity.id, "fireball")

        assert can_cast is True
        assert reason is None

    def test_can_cast_spell_not_known(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test cannot cast unknown spell."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=10
        )

        can_cast, reason = magic_manager.can_cast_spell(wizard_entity.id, "fireball")

        assert can_cast is False
        assert "not known" in reason.lower()

    def test_can_cast_spell_not_prepared(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test cannot cast unprepared spell (for preparation casters)."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=10
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        # Initialize prepared_spells to indicate this is a preparation caster
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        profile.prepared_spells = []

        can_cast, reason = magic_manager.can_cast_spell(wizard_entity.id, "fireball")

        assert can_cast is False
        assert "not prepared" in reason.lower()

    def test_can_cast_spell_insufficient_mana(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test cannot cast with insufficient mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=3
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        can_cast, reason = magic_manager.can_cast_spell(wizard_entity.id, "fireball")

        assert can_cast is False
        assert "mana" in reason.lower()

    def test_can_cast_cantrip_no_mana(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        cantrip_spell: SpellDefinition,
    ):
        """Test cantrips can be cast without mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=0
        )
        magic_manager.learn_spell(wizard_entity.id, "fire_bolt")

        can_cast, reason = magic_manager.can_cast_spell(wizard_entity.id, "fire_bolt")

        assert can_cast is True


# --- Spell Casting Tests ---


class TestSpellCasting:
    """Tests for actual spell casting."""

    def test_cast_spell_success(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        target_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test successful spell cast."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=20
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        result = magic_manager.cast_spell(
            caster_id=wizard_entity.id,
            spell_key="fireball",
            target_keys=[target_entity.entity_key],
        )

        assert result.success is True
        assert result.mana_spent == 5
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 15

    def test_cast_spell_creates_record(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        target_entity: Entity,
        fireball_spell: SpellDefinition,
        db_session: Session,
        game_session: GameSession,
    ):
        """Test that casting creates a SpellCastRecord."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=20
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        magic_manager.cast_spell(
            caster_id=wizard_entity.id,
            spell_key="fireball",
            target_keys=[target_entity.entity_key],
        )

        records = (
            db_session.query(SpellCastRecord)
            .filter(SpellCastRecord.session_id == game_session.id)
            .all()
        )
        assert len(records) == 1
        assert records[0].spell_key == "fireball"
        assert records[0].caster_entity_id == wizard_entity.id
        assert target_entity.entity_key in records[0].target_entity_keys

    def test_cast_spell_failure_no_mana(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        target_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test failed spell cast due to insufficient mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=2
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        result = magic_manager.cast_spell(
            caster_id=wizard_entity.id,
            spell_key="fireball",
            target_keys=[target_entity.entity_key],
        )

        assert result.success is False
        assert result.mana_spent == 0

    def test_cast_cantrip_free(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        target_entity: Entity,
        cantrip_spell: SpellDefinition,
    ):
        """Test that cantrips don't cost mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=5
        )
        magic_manager.learn_spell(wizard_entity.id, "fire_bolt")

        result = magic_manager.cast_spell(
            caster_id=wizard_entity.id,
            spell_key="fire_bolt",
            target_keys=[target_entity.entity_key],
        )

        assert result.success is True
        assert result.mana_spent == 0
        profile = magic_manager.get_magic_profile(wizard_entity.id)
        assert profile.current_mana == 5  # Unchanged

    def test_cast_spell_upcast(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        target_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test upcasting a spell costs more mana."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=30, current_mana=30
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        # Upcast to level 5 (2 levels higher)
        result = magic_manager.cast_spell(
            caster_id=wizard_entity.id,
            spell_key="fireball",
            target_keys=[target_entity.entity_key],
            upcast_level=5,
        )

        assert result.success is True
        # Base cost 5 + 2 extra mana per level = 5 + 4 = 9
        assert result.mana_spent == 9


# --- Spell Info and Listing Tests ---


class TestSpellInfo:
    """Tests for spell info retrieval."""

    def test_get_known_spells(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
        heal_spell: SpellDefinition,
    ):
        """Test getting list of known spells with cast info."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=10
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.learn_spell(wizard_entity.id, "cure_wounds")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        spells = magic_manager.get_known_spells(wizard_entity.id)

        assert len(spells) == 2
        fireball_info = next(s for s in spells if s.spell_key == "fireball")
        assert fireball_info.can_cast is True
        assert fireball_info.cost == 5

    def test_get_known_spells_shows_cannot_cast(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test that spell info shows when spell cannot be cast."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=20, current_mana=2
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        spells = magic_manager.get_known_spells(wizard_entity.id)

        assert len(spells) == 1
        assert spells[0].can_cast is False
        assert "mana" in spells[0].reason_if_not.lower()

    def test_get_spell_cast_history(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        target_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test getting spell cast history."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id, max_mana=50, current_mana=50
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")
        magic_manager.prepare_spell(wizard_entity.id, "fireball")

        # Cast spell twice
        magic_manager.cast_spell(wizard_entity.id, "fireball", [target_entity.entity_key])
        magic_manager.cast_spell(wizard_entity.id, "fireball", [target_entity.entity_key])

        history = magic_manager.get_spell_cast_history(wizard_entity.id)

        assert len(history) == 2
        assert all(r.spell_key == "fireball" for r in history)


# --- Context Generation Tests ---


class TestMagicContext:
    """Tests for magic context generation."""

    def test_get_magic_context(
        self,
        magic_manager: MagicManager,
        wizard_entity: Entity,
        fireball_spell: SpellDefinition,
    ):
        """Test generating magic context for GM prompts."""
        magic_manager.set_magic_profile(
            entity_id=wizard_entity.id,
            tradition=MagicTradition.ARCANE,
            max_mana=30,
            current_mana=20,
        )
        magic_manager.learn_spell(wizard_entity.id, "fireball")

        context = magic_manager.get_magic_context(wizard_entity.id)

        assert "20/30" in context or "20" in context  # Mana display
        assert "arcane" in context.lower()
        assert "fireball" in context.lower()

    def test_get_magic_context_no_profile(
        self, magic_manager: MagicManager, wizard_entity: Entity
    ):
        """Test magic context for entity without magic profile."""
        context = magic_manager.get_magic_context(wizard_entity.id)

        assert context == ""


# --- Session Isolation Tests ---


class TestSessionIsolation:
    """Tests for session isolation."""

    def test_spells_isolated_by_session(
        self,
        db_session: Session,
        game_session: GameSession,
        game_session_2: GameSession,
    ):
        """Test that spells are isolated between sessions."""
        manager1 = MagicManager(db=db_session, game_session=game_session)
        manager2 = MagicManager(db=db_session, game_session=game_session_2)

        # Create spell in session 1
        manager1.create_spell(
            spell_key="unique_spell",
            display_name="Unique Spell",
            tradition=MagicTradition.ARCANE,
            school=SpellSchool.EVOCATION,
            level=1,
            base_cost=2,
            casting_time=CastingTime.ACTION,
            range_description="30 feet",
            duration="instantaneous",
            components=["verbal"],
            description="A unique spell",
            effects={},
        )

        # Should not be visible in session 2
        spell = manager2.get_spell("unique_spell")
        assert spell is None

    def test_profiles_isolated_by_session(
        self,
        db_session: Session,
        game_session: GameSession,
        game_session_2: GameSession,
    ):
        """Test that magic profiles are isolated between sessions."""
        # Create entities in each session
        entity1 = Entity(
            session_id=game_session.id,
            entity_key="mage_1",
            display_name="Mage 1",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        entity2 = Entity(
            session_id=game_session_2.id,
            entity_key="mage_1",  # Same key, different session
            display_name="Mage 1",
            entity_type=EntityType.NPC,
            is_alive=True,
            is_active=True,
        )
        db_session.add_all([entity1, entity2])
        db_session.flush()

        manager1 = MagicManager(db=db_session, game_session=game_session)
        manager2 = MagicManager(db=db_session, game_session=game_session_2)

        # Set profile in session 1
        manager1.set_magic_profile(entity_id=entity1.id, max_mana=100)

        # Should not affect session 2's entity
        profile2 = manager2.get_magic_profile(entity2.id)
        assert profile2 is None
