"""Death and vital state management."""

from dataclasses import dataclass
from datetime import datetime
from random import random
from typing import Literal

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.enums import (
    BodyPart,
    InjurySeverity,
    InjuryType,
    MentalConditionType,
    VitalStatus,
)
from src.database.models.injuries import BodyInjury
from src.database.models.mental_state import MentalCondition
from src.database.models.session import GameSession
from src.database.models.vital_state import EntityVitalState
from src.managers.base import BaseManager


SettingType = Literal["fantasy", "contemporary", "scifi", "custom"]


@dataclass
class DeathSaveResult:
    """Result of a death save roll."""

    success: bool
    roll: int
    dc: int
    saves_remaining: int
    saves_failed: int
    stabilized: bool
    died: bool


@dataclass
class RevivalResult:
    """Result of attempting to revive a character."""

    success: bool
    method: str
    cost: str
    consequences: list[str]
    new_status: VitalStatus


class DeathManager(BaseManager):
    """Manages vital states, death saves, and revival mechanics."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        setting: SettingType = "fantasy",
        injury_manager: "InjuryManager | None" = None,
    ) -> None:
        super().__init__(db, game_session)
        self.setting = setting
        self._injury_manager = injury_manager

    @property
    def injury_manager(self) -> "InjuryManager":
        """Lazy-load InjuryManager to avoid circular imports."""
        if self._injury_manager is None:
            from src.managers.injuries import InjuryManager
            self._injury_manager = InjuryManager(self.db, self.game_session)
        return self._injury_manager

    def get_vital_state(self, entity_id: int) -> EntityVitalState | None:
        """Get vital state for an entity."""
        return (
            self.db.query(EntityVitalState)
            .filter(
                EntityVitalState.entity_id == entity_id,
                EntityVitalState.session_id == self.session_id,
            )
            .first()
        )

    def get_or_create_vital_state(self, entity_id: int) -> EntityVitalState:
        """Get or create vital state for an entity."""
        state = self.get_vital_state(entity_id)
        if state is None:
            state = EntityVitalState(
                entity_id=entity_id,
                session_id=self.session_id,
                vital_status=VitalStatus.HEALTHY,
            )
            self.db.add(state)
            self.db.flush()
        return state

    def set_vital_status(
        self,
        entity_id: int,
        status: VitalStatus,
        cause: str | None = None,
    ) -> EntityVitalState:
        """Set the vital status of an entity.

        Args:
            entity_id: Entity to update
            status: New vital status
            cause: What caused this status change

        Returns:
            Updated EntityVitalState
        """
        state = self.get_or_create_vital_state(entity_id)

        # Handle death states
        if status in (VitalStatus.DEAD, VitalStatus.CLINICALLY_DEAD, VitalStatus.PERMANENTLY_DEAD):
            state.is_dead = True
            state.death_timestamp = datetime.utcnow()
            state.death_turn = self.current_turn
            state.death_cause = cause

            # Update entity is_alive
            entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
            if entity:
                entity.is_alive = False

        # Reset death saves if entering dying state
        if status == VitalStatus.DYING:
            state.death_saves_remaining = 3
            state.death_saves_failed = 0
            state.stabilized_at = None
            state.stabilized_turn = None

        state.vital_status = status
        self.db.flush()
        return state

    def take_damage(
        self,
        entity_id: int,
        damage: int,
        current_hp: int,
        max_hp: int,
        damage_type: str = "physical",
        body_part: BodyPart | None = None,
        create_injury: bool = True,
    ) -> tuple[VitalStatus, int, BodyInjury | None]:
        """Process damage and update vital status, optionally creating injuries.

        Args:
            entity_id: Entity taking damage
            damage: Amount of damage
            current_hp: Current HP before damage
            max_hp: Maximum HP
            damage_type: Type of damage (physical, fire, cold, etc.)
            body_part: Which body part was hit (optional)
            create_injury: Whether to create an injury record

        Returns:
            (new_status, new_hp, injury_or_none)
        """
        new_hp = current_hp - damage
        state = self.get_or_create_vital_state(entity_id)
        injury = None

        # Create injury if body part is specified and damage is significant
        if create_injury and body_part and damage > 0:
            injury = self._create_injury_from_damage(
                entity_id, damage, max_hp, damage_type, body_part
            )

        # Calculate HP thresholds
        critical_threshold = max_hp * 0.25
        wounded_threshold = max_hp * 0.50

        if new_hp <= -max_hp:
            # Massive damage - instant death
            self.set_vital_status(entity_id, VitalStatus.DEAD, f"Massive {damage_type} damage")
            return VitalStatus.DEAD, 0, injury

        elif new_hp <= 0:
            # Dropped to 0 or below - dying
            self.set_vital_status(entity_id, VitalStatus.DYING, f"{damage_type} damage")
            return VitalStatus.DYING, 0, injury

        elif new_hp <= critical_threshold:
            state.vital_status = VitalStatus.CRITICAL
            self.db.flush()
            return VitalStatus.CRITICAL, max(0, new_hp), injury

        elif new_hp <= wounded_threshold:
            state.vital_status = VitalStatus.WOUNDED
            self.db.flush()
            return VitalStatus.WOUNDED, new_hp, injury

        else:
            state.vital_status = VitalStatus.HEALTHY
            self.db.flush()
            return VitalStatus.HEALTHY, new_hp, injury

    def _create_injury_from_damage(
        self,
        entity_id: int,
        damage: int,
        max_hp: int,
        damage_type: str,
        body_part: BodyPart,
    ) -> BodyInjury | None:
        """Create an injury based on damage taken.

        Converts damage amount and type to an appropriate injury.
        """
        # Calculate severity based on damage relative to max HP
        severity = self._damage_to_severity(damage, max_hp)

        # Map damage type to injury type
        injury_type = self._damage_type_to_injury(damage_type)

        # Create the injury
        injury = self.injury_manager.add_injury(
            entity_id=entity_id,
            body_part=body_part,
            injury_type=injury_type,
            severity=severity,
            caused_by=damage_type,
            has_medical_care=False,
        )

        # Sync pain to needs
        self.injury_manager.sync_pain_to_needs(entity_id)

        return injury

    def _damage_to_severity(self, damage: int, max_hp: int) -> InjurySeverity:
        """Convert damage amount to injury severity.

        Based on percentage of max HP:
        - < 10%: MINOR
        - 10-25%: MODERATE
        - 25-50%: SEVERE
        - > 50%: CRITICAL
        """
        damage_percent = (damage / max_hp) * 100

        if damage_percent < 10:
            return InjurySeverity.MINOR
        elif damage_percent < 25:
            return InjurySeverity.MODERATE
        elif damage_percent < 50:
            return InjurySeverity.SEVERE
        else:
            return InjurySeverity.CRITICAL

    def _damage_type_to_injury(self, damage_type: str) -> InjuryType:
        """Map damage type to appropriate injury type."""
        damage_type_lower = damage_type.lower()

        # Direct mappings
        damage_to_injury = {
            "slashing": InjuryType.CUT,
            "slash": InjuryType.CUT,
            "cutting": InjuryType.CUT,
            "piercing": InjuryType.LACERATION,
            "pierce": InjuryType.LACERATION,
            "stab": InjuryType.LACERATION,
            "bludgeoning": InjuryType.BRUISE,
            "blunt": InjuryType.BRUISE,
            "impact": InjuryType.BRUISE,
            "fire": InjuryType.BURN,
            "flame": InjuryType.BURN,
            "heat": InjuryType.BURN,
            "acid": InjuryType.BURN,
            "falling": InjuryType.FRACTURE,
            "fall": InjuryType.FRACTURE,
            "crushing": InjuryType.FRACTURE,
            "psychic": InjuryType.CONCUSSION,
            "force": InjuryType.INTERNAL_BLEEDING,
            "necrotic": InjuryType.NERVE_DAMAGE,
            "poison": InjuryType.INTERNAL_BLEEDING,
            "cold": InjuryType.BURN,  # Frostbite is similar to burns
        }

        return damage_to_injury.get(damage_type_lower, InjuryType.CUT)  # Default to cut

    def make_death_save(
        self,
        entity_id: int,
        roll: int,
        dc: int = 10,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> DeathSaveResult:
        """Make a death saving throw.

        Args:
            entity_id: Dying entity
            roll: The d20 roll (1-20)
            dc: Difficulty class (default 10)
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            DeathSaveResult with outcome
        """
        state = self.get_or_create_vital_state(entity_id)

        if state.vital_status != VitalStatus.DYING:
            return DeathSaveResult(
                success=True,
                roll=roll,
                dc=dc,
                saves_remaining=state.death_saves_remaining,
                saves_failed=state.death_saves_failed,
                stabilized=False,
                died=False,
            )

        # Natural 20 = stabilize immediately
        if roll == 20:
            state.vital_status = VitalStatus.CRITICAL
            state.stabilized_at = datetime.utcnow()
            state.stabilized_turn = self.current_turn
            self.db.flush()
            return DeathSaveResult(
                success=True,
                roll=roll,
                dc=dc,
                saves_remaining=state.death_saves_remaining,
                saves_failed=state.death_saves_failed,
                stabilized=True,
                died=False,
            )

        # Natural 1 = counts as 2 failures
        if roll == 1:
            state.death_saves_failed += 2
        elif roll >= dc:
            state.death_saves_remaining -= 1
        else:
            state.death_saves_failed += 1

        # Check for stabilization (3 successes used up saves)
        stabilized = False
        if state.death_saves_remaining <= 0 and state.death_saves_failed < 3:
            state.vital_status = VitalStatus.CRITICAL
            state.stabilized_at = datetime.utcnow()
            state.stabilized_turn = self.current_turn
            stabilized = True

        # Check for death (3 failures)
        died = False
        if state.death_saves_failed >= 3:
            self.set_vital_status(entity_id, VitalStatus.DEAD, "Failed death saving throws")
            died = True

        self.db.flush()

        return DeathSaveResult(
            success=roll >= dc,
            roll=roll,
            dc=dc,
            saves_remaining=state.death_saves_remaining,
            saves_failed=state.death_saves_failed,
            stabilized=stabilized,
            died=died,
        )

    def stabilize(self, entity_id: int, method: str = "medical care") -> bool:
        """Stabilize a dying character.

        Args:
            entity_id: Entity to stabilize
            method: How they were stabilized

        Returns:
            True if successfully stabilized
        """
        state = self.get_or_create_vital_state(entity_id)

        if state.vital_status != VitalStatus.DYING:
            return False

        state.vital_status = VitalStatus.CRITICAL
        state.stabilized_at = datetime.utcnow()
        state.stabilized_turn = self.current_turn
        self.db.flush()
        return True

    def attempt_revival(
        self,
        entity_id: int,
        method: str,
        caster_level: int = 1,
        materials_available: bool = True,
    ) -> RevivalResult:
        """Attempt to revive a dead character.

        Args:
            entity_id: Entity to revive
            method: Revival method (spell name, medical procedure, etc.)
            caster_level: Level of the caster/doctor
            materials_available: Required materials available

        Returns:
            RevivalResult with outcome
        """
        state = self.get_or_create_vital_state(entity_id)

        if not state.is_dead:
            return RevivalResult(
                success=False,
                method=method,
                cost="",
                consequences=["Target is not dead"],
                new_status=state.vital_status,
            )

        if state.vital_status == VitalStatus.PERMANENTLY_DEAD:
            return RevivalResult(
                success=False,
                method=method,
                cost="",
                consequences=["Target cannot be revived - death is permanent"],
                new_status=VitalStatus.PERMANENTLY_DEAD,
            )

        # Setting-specific revival logic
        if self.setting == "fantasy":
            return self._fantasy_revival(entity_id, state, method, caster_level, materials_available)
        elif self.setting == "scifi":
            return self._scifi_revival(entity_id, state, method)
        else:
            # Contemporary - very limited revival
            return self._contemporary_revival(entity_id, state, method)

    def _fantasy_revival(
        self,
        entity_id: int,
        state: EntityVitalState,
        method: str,
        caster_level: int,
        materials_available: bool,
    ) -> RevivalResult:
        """Fantasy setting revival mechanics."""
        consequences = []
        cost = ""

        # Check time since death (10 minute window for basic revival)
        if state.death_timestamp:
            time_dead = (datetime.utcnow() - state.death_timestamp).total_seconds()
            minutes_dead = time_dead / 60

            if minutes_dead > 10 and method.lower() not in ("resurrection", "true_resurrection", "wish"):
                return RevivalResult(
                    success=False,
                    method=method,
                    cost="",
                    consequences=["Too much time has passed for this revival method"],
                    new_status=state.vital_status,
                )

        if not materials_available:
            return RevivalResult(
                success=False,
                method=method,
                cost="",
                consequences=["Required material components not available"],
                new_status=state.vital_status,
            )

        # Successful revival
        state.is_dead = False
        state.vital_status = VitalStatus.CRITICAL
        state.has_been_revived = True
        state.revival_count += 1
        state.last_revival_turn = self.current_turn
        state.revival_method = method

        # Update entity
        entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if entity:
            entity.is_alive = True

        # Calculate costs based on method
        if method.lower() in ("raise_dead", "revivify"):
            cost = "Diamond worth 500gp consumed, -1 permanent CON"
            consequences.append("Permanent -1 CON from revival trauma")
        elif method.lower() == "resurrection":
            cost = "Diamond worth 1000gp consumed"
        elif method.lower() == "true_resurrection":
            cost = "Diamond worth 25000gp consumed"

        state.revival_cost = cost

        # Add PTSD from death experience
        self._add_death_trauma(entity_id)
        consequences.append("PTSD condition acquired from death experience")

        self.db.flush()

        return RevivalResult(
            success=True,
            method=method,
            cost=cost,
            consequences=consequences,
            new_status=VitalStatus.CRITICAL,
        )

    def _scifi_revival(
        self,
        entity_id: int,
        state: EntityVitalState,
        method: str,
    ) -> RevivalResult:
        """Sci-fi setting revival mechanics."""
        consequences = []

        if not state.has_consciousness_backup:
            return RevivalResult(
                success=False,
                method=method,
                cost="",
                consequences=["No consciousness backup exists - death is permanent"],
                new_status=state.vital_status,
            )

        # Calculate memory loss since last backup
        turns_since_backup = 0
        if state.last_backup_turn:
            turns_since_backup = self.current_turn - state.last_backup_turn

        # Successful clone revival
        state.is_dead = False
        state.vital_status = VitalStatus.HEALTHY  # Clone body is fresh
        state.has_been_revived = True
        state.revival_count += 1
        state.last_revival_turn = self.current_turn
        state.revival_method = "consciousness_restoration"

        # Update entity
        entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if entity:
            entity.is_alive = True

        cost = f"Clone body consumed, memories from last {turns_since_backup} turns lost, 20% XP loss"
        state.revival_cost = cost
        consequences.append(f"Lost memories of last {turns_since_backup} turns since backup")
        consequences.append("20% experience points lost")

        # Add existential crisis from being a copy
        self._add_existential_crisis(entity_id)
        consequences.append("Existential crisis condition acquired")

        self.db.flush()

        return RevivalResult(
            success=True,
            method="consciousness_restoration",
            cost=cost,
            consequences=consequences,
            new_status=VitalStatus.HEALTHY,
        )

    def _contemporary_revival(
        self,
        entity_id: int,
        state: EntityVitalState,
        method: str,
    ) -> RevivalResult:
        """Contemporary setting revival - very limited."""
        # Only clinical death can be revived (CPR, defibrillator)
        if state.vital_status != VitalStatus.CLINICALLY_DEAD:
            return RevivalResult(
                success=False,
                method=method,
                cost="",
                consequences=["In realistic settings, death is permanent"],
                new_status=state.vital_status,
            )

        # Check golden hour
        if state.death_timestamp:
            time_dead = (datetime.utcnow() - state.death_timestamp).total_seconds()
            if time_dead > 360:  # 6 minutes for brain death
                state.vital_status = VitalStatus.PERMANENTLY_DEAD
                self.db.flush()
                return RevivalResult(
                    success=False,
                    method=method,
                    cost="",
                    consequences=["Brain death has occurred - revival impossible"],
                    new_status=VitalStatus.PERMANENTLY_DEAD,
                )

        # Success chance based on time and method
        success_chance = 0.7 - (time_dead / 600)  # Decreases over time
        if method.lower() in ("cpr", "defibrillator", "aed"):
            success_chance += 0.1

        if random() > success_chance:
            return RevivalResult(
                success=False,
                method=method,
                cost="",
                consequences=["Revival attempt failed"],
                new_status=state.vital_status,
            )

        # Successful revival
        state.is_dead = False
        state.vital_status = VitalStatus.CRITICAL
        state.has_been_revived = True
        state.revival_count += 1
        state.revival_method = method

        entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if entity:
            entity.is_alive = True

        consequences = ["Potential brain damage from oxygen deprivation"]
        self._add_death_trauma(entity_id)
        consequences.append("PTSD condition acquired from near-death experience")

        self.db.flush()

        return RevivalResult(
            success=True,
            method=method,
            cost="Emergency medical care",
            consequences=consequences,
            new_status=VitalStatus.CRITICAL,
        )

    def _add_death_trauma(self, entity_id: int) -> None:
        """Add PTSD from death experience."""
        condition = MentalCondition(
            entity_id=entity_id,
            session_id=self.session_id,
            condition_type=MentalConditionType.PTSD_NEAR_DEATH,
            severity=60,
            is_permanent=False,
            trigger_description="memories of dying, near-death situations",
            triggers={"situations": ["combat", "near_death", "darkness"]},
            stat_penalties={"morale": -20, "WIS": -1},
            behavioral_effects={"nightmare_chance": 0.3, "panic_in_combat": 0.1},
            acquired_turn=self.current_turn,
            acquired_reason="Died and was revived",
        )
        self.db.add(condition)

    def _add_existential_crisis(self, entity_id: int) -> None:
        """Add existential crisis from being a clone/copy."""
        condition = MentalCondition(
            entity_id=entity_id,
            session_id=self.session_id,
            condition_type=MentalConditionType.EXISTENTIAL_CRISIS,
            severity=50,
            is_permanent=False,
            trigger_description="questions of identity, meeting people who knew the 'original'",
            triggers={"situations": ["identity_questions", "philosophical_discussions"]},
            stat_penalties={"morale": -15},
            behavioral_effects={"identity_doubt": 0.4},
            acquired_turn=self.current_turn,
            acquired_reason="Consciousness restored to clone body",
        )
        self.db.add(condition)

    def create_backup(self, entity_id: int, location: str) -> bool:
        """Create a consciousness backup (sci-fi setting).

        Args:
            entity_id: Entity to backup
            location: Where the backup is stored

        Returns:
            True if backup created
        """
        if self.setting != "scifi":
            return False

        state = self.get_or_create_vital_state(entity_id)
        state.has_consciousness_backup = True
        state.last_backup_turn = self.current_turn
        state.backup_location = location
        self.db.flush()
        return True

    def get_vital_summary(self, entity_id: int) -> dict:
        """Get summary of vital state for context/display."""
        state = self.get_vital_state(entity_id)

        if state is None:
            return {"has_vital_state": False, "status": "healthy"}

        return {
            "has_vital_state": True,
            "status": state.vital_status.value,
            "is_dead": state.is_dead,
            "death_saves_remaining": state.death_saves_remaining,
            "death_saves_failed": state.death_saves_failed,
            "revival_count": state.revival_count,
            "has_backup": state.has_consciousness_backup,
            "death_cause": state.death_cause,
        }
