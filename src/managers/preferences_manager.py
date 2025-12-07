"""Character preferences and need modifier management."""

import math
import random
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.character_preferences import (
    CharacterPreferences,
    NeedModifier,
)
from src.database.models.enums import ModifierSource
from src.database.models.session import GameSession
from src.managers.base import BaseManager
from src.schemas.settings import (
    NeedAgeCurve,
    NeedModifierSettings,
    get_setting_schema,
)


# Mapping of trait flag names to the trait key used in settings
TRAIT_FLAG_TO_KEY = {
    "is_greedy_eater": "greedy_eater",
    "is_picky_eater": "picky_eater",
    "has_high_stamina": "high_stamina",
    "has_low_stamina": "low_stamina",
    "is_insomniac": "insomniac",
    "is_heavy_sleeper": "heavy_sleeper",
    "is_social_butterfly": "social_butterfly",
    "is_loner": "loner",
    "is_alcoholic": "alcoholic",
}

# All trait flag names on CharacterPreferences
ALL_TRAIT_FLAGS = [
    "is_greedy_eater",
    "is_picky_eater",
    "is_vegetarian",
    "is_vegan",
    "is_alcoholic",
    "is_teetotaler",
    "is_social_butterfly",
    "is_loner",
    "has_high_stamina",
    "has_low_stamina",
    "is_insomniac",
    "is_heavy_sleeper",
]


class PreferencesManager(BaseManager):
    """Manages character preferences and need modifiers.

    Handles:
    - CRUD operations for CharacterPreferences
    - Trait flag management with automatic modifier syncing
    - Age-based modifier generation using two-stage normal distribution
    - NeedModifier management
    """

    # =========================================================================
    # Preferences CRUD
    # =========================================================================

    def get_preferences(self, entity_id: int) -> CharacterPreferences | None:
        """Get character preferences for an entity.

        Args:
            entity_id: The entity ID to look up.

        Returns:
            CharacterPreferences or None if not found.
        """
        return (
            self.db.query(CharacterPreferences)
            .filter(
                CharacterPreferences.entity_id == entity_id,
                CharacterPreferences.session_id == self.session_id,
            )
            .first()
        )

    def get_or_create_preferences(self, entity_id: int) -> CharacterPreferences:
        """Get or create character preferences for an entity.

        Args:
            entity_id: The entity ID.

        Returns:
            Existing or newly created CharacterPreferences.
        """
        prefs = self.get_preferences(entity_id)
        if prefs is None:
            prefs = self.create_preferences(entity_id)
        return prefs

    def create_preferences(
        self,
        entity_id: int,
        **kwargs: Any,
    ) -> CharacterPreferences:
        """Create new character preferences with optional custom values.

        Args:
            entity_id: The entity ID.
            **kwargs: Optional overrides for preference fields.

        Returns:
            Newly created CharacterPreferences.
        """
        prefs = CharacterPreferences(
            entity_id=entity_id,
            session_id=self.session_id,
            **kwargs,
        )
        self.db.add(prefs)
        self.db.flush()
        return prefs

    def update_preferences(
        self,
        entity_id: int,
        **updates: Any,
    ) -> CharacterPreferences:
        """Update preference fields for an entity.

        Args:
            entity_id: The entity ID.
            **updates: Fields to update.

        Returns:
            Updated CharacterPreferences.
        """
        prefs = self.get_or_create_preferences(entity_id)
        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        self.db.flush()
        return prefs

    # =========================================================================
    # Trait Flag Methods
    # =========================================================================

    def get_trait_flags(self, entity_id: int) -> dict[str, bool]:
        """Get all trait flags as a dictionary.

        Args:
            entity_id: The entity ID.

        Returns:
            Dict mapping trait flag names to their boolean values.
        """
        prefs = self.get_or_create_preferences(entity_id)
        return {
            flag: getattr(prefs, flag, False)
            for flag in ALL_TRAIT_FLAGS
        }

    def set_trait(
        self,
        entity_id: int,
        trait_name: str,
        value: bool,
    ) -> CharacterPreferences:
        """Set a trait flag and sync corresponding modifiers.

        Args:
            entity_id: The entity ID.
            trait_name: Name of the trait flag (e.g., "is_greedy_eater").
            value: True or False.

        Returns:
            Updated CharacterPreferences.
        """
        prefs = self.get_or_create_preferences(entity_id)
        if hasattr(prefs, trait_name):
            setattr(prefs, trait_name, value)
            self.db.flush()

        # Sync this specific trait to modifiers
        self._sync_single_trait_modifier(entity_id, trait_name, value)

        return prefs

    def _sync_single_trait_modifier(
        self,
        entity_id: int,
        trait_flag: str,
        is_active: bool,
    ) -> None:
        """Sync a single trait flag to its modifier(s).

        Args:
            entity_id: The entity ID.
            trait_flag: The trait flag name.
            is_active: Whether the trait is active.
        """
        trait_key = TRAIT_FLAG_TO_KEY.get(trait_flag)
        if not trait_key:
            return  # Not a trait with modifiers

        # Get trait effects from settings
        schema = get_setting_schema(self.game_session.setting)
        trait_effects = schema.need_modifiers.trait_effects.get(trait_key, {})

        for need_name, effect in trait_effects.items():
            if is_active:
                # Create or update modifier
                existing = (
                    self.db.query(NeedModifier)
                    .filter(
                        NeedModifier.entity_id == entity_id,
                        NeedModifier.session_id == self.session_id,
                        NeedModifier.need_name == need_name,
                        NeedModifier.modifier_source == ModifierSource.TRAIT,
                        NeedModifier.source_detail == trait_key,
                    )
                    .first()
                )
                if existing:
                    existing.decay_rate_multiplier = effect.decay_rate_multiplier
                    existing.satisfaction_multiplier = effect.satisfaction_multiplier
                    existing.is_active = True
                else:
                    self.create_modifier(
                        entity_id=entity_id,
                        need_name=need_name,
                        source=ModifierSource.TRAIT,
                        source_detail=trait_key,
                        decay_rate_multiplier=effect.decay_rate_multiplier,
                        satisfaction_multiplier=effect.satisfaction_multiplier,
                    )
            else:
                # Remove modifier
                (
                    self.db.query(NeedModifier)
                    .filter(
                        NeedModifier.entity_id == entity_id,
                        NeedModifier.session_id == self.session_id,
                        NeedModifier.need_name == need_name,
                        NeedModifier.modifier_source == ModifierSource.TRAIT,
                        NeedModifier.source_detail == trait_key,
                    )
                    .delete()
                )
        self.db.flush()

    def sync_trait_modifiers(self, entity_id: int) -> list[NeedModifier]:
        """Sync all trait flags to NeedModifier records.

        Creates modifiers for active traits, removes modifiers for inactive traits.

        Args:
            entity_id: The entity ID.

        Returns:
            List of active trait modifiers after sync.
        """
        flags = self.get_trait_flags(entity_id)

        for flag_name, is_active in flags.items():
            self._sync_single_trait_modifier(entity_id, flag_name, is_active)

        # Return all trait modifiers
        return (
            self.db.query(NeedModifier)
            .filter(
                NeedModifier.entity_id == entity_id,
                NeedModifier.session_id == self.session_id,
                NeedModifier.modifier_source == ModifierSource.TRAIT,
            )
            .all()
        )

    # =========================================================================
    # Modifier Management
    # =========================================================================

    def get_modifiers_for_entity(
        self,
        entity_id: int,
        need_name: str | None = None,
    ) -> list[NeedModifier]:
        """Get all modifiers for an entity.

        Args:
            entity_id: The entity ID.
            need_name: Optional filter by need name.

        Returns:
            List of NeedModifier records.
        """
        query = self.db.query(NeedModifier).filter(
            NeedModifier.entity_id == entity_id,
            NeedModifier.session_id == self.session_id,
            NeedModifier.is_active == True,
        )
        if need_name:
            query = query.filter(NeedModifier.need_name == need_name)
        return query.all()

    def create_modifier(
        self,
        entity_id: int,
        need_name: str,
        source: ModifierSource,
        source_detail: str | None = None,
        decay_rate_multiplier: float = 1.0,
        satisfaction_multiplier: float = 1.0,
        max_intensity_cap: int | None = None,
        threshold_adjustment: int = 0,
        expires_at_turn: int | None = None,
    ) -> NeedModifier:
        """Create a new need modifier.

        Args:
            entity_id: The entity ID.
            need_name: Which need this modifies.
            source: Source of the modifier (TRAIT, AGE, etc.).
            source_detail: Specific source (e.g., "greedy_eater").
            decay_rate_multiplier: Multiplier for decay rate.
            satisfaction_multiplier: Multiplier for satisfaction.
            max_intensity_cap: Maximum intensity cap.
            threshold_adjustment: Adjustment to urgency threshold.
            expires_at_turn: Turn when modifier expires.

        Returns:
            Newly created NeedModifier.
        """
        modifier = NeedModifier(
            entity_id=entity_id,
            session_id=self.session_id,
            need_name=need_name,
            modifier_source=source,
            source_detail=source_detail,
            decay_rate_multiplier=decay_rate_multiplier,
            satisfaction_multiplier=satisfaction_multiplier,
            max_intensity_cap=max_intensity_cap,
            threshold_adjustment=threshold_adjustment,
            expires_at_turn=expires_at_turn,
            is_active=True,
        )
        self.db.add(modifier)
        self.db.flush()
        return modifier

    def remove_modifier(self, modifier_id: int) -> None:
        """Remove a modifier by ID.

        Args:
            modifier_id: The modifier ID to remove.
        """
        self.db.query(NeedModifier).filter(NeedModifier.id == modifier_id).delete()
        self.db.flush()

    # =========================================================================
    # Age-Based Modifier Calculation
    # =========================================================================

    def calculate_age_modifier(self, age: int, curve: NeedAgeCurve) -> float:
        """Calculate the expected modifier value for a given age.

        Uses asymmetric normal distribution:
        - For ages below peak: uses std_dev_lower (sharper decline)
        - For ages above peak: uses std_dev_upper (gradual decline)

        Args:
            age: Character's age in years.
            curve: The age curve configuration.

        Returns:
            Expected modifier value (within min_value to max_value).
        """
        dist = curve.distribution
        peak_age = dist.peak_age
        peak_value = dist.peak_value

        if age == peak_age:
            return min(dist.max_value, max(dist.min_value, peak_value))

        # Choose std_dev based on which side of peak we're on
        if age < peak_age:
            std_dev = dist.std_dev_lower
            distance = peak_age - age
        else:
            std_dev = dist.std_dev_upper
            distance = age - peak_age

        # Calculate decay using normal distribution formula
        # value = peak_value * exp(-0.5 * (distance / std_dev)^2)
        decay_factor = math.exp(-0.5 * (distance / std_dev) ** 2)
        value = peak_value * decay_factor

        # Clamp to bounds
        return min(dist.max_value, max(dist.min_value, value))

    def generate_individual_variance(
        self,
        expected: float,
        variance_std: float,
    ) -> float:
        """Add individual variance to expected value using normal distribution.

        Stage 2 of the two-stage calculation.

        Args:
            expected: The age-based expected value.
            variance_std: Standard deviation for individual variation.

        Returns:
            Final value with individual variance applied.
        """
        # Add random variance from normal distribution
        variance = random.gauss(0, variance_std)
        return max(0, min(100, expected + variance))

    def generate_age_modifiers(
        self,
        entity_id: int,
        age: int,
        setting_name: str = "fantasy",
    ) -> list[NeedModifier]:
        """Generate and store age-based modifiers for an entity.

        Uses two-stage calculation:
        1. Age -> Expected value (asymmetric distribution)
        2. Expected -> Actual (individual variance)

        Args:
            entity_id: Entity to generate modifiers for.
            age: Entity's age.
            setting_name: Setting to load curves from.

        Returns:
            List of created NeedModifier records.
        """
        schema = get_setting_schema(setting_name)
        modifiers: list[NeedModifier] = []

        for curve in schema.need_modifiers.age_curves:
            # Stage 1: Age -> Expected value
            expected = self.calculate_age_modifier(age, curve)

            # Stage 2: Add individual variance
            actual = self.generate_individual_variance(
                expected, curve.individual_variance_std
            )

            # Convert to multiplier (0-100 scale -> 0-1 multiplier)
            decay_multiplier = actual / 100.0 if curve.affects_decay else 1.0
            max_cap = int(actual) if curve.affects_max_intensity else None

            # Check if modifier already exists
            existing = (
                self.db.query(NeedModifier)
                .filter(
                    NeedModifier.entity_id == entity_id,
                    NeedModifier.session_id == self.session_id,
                    NeedModifier.need_name == curve.need_name,
                    NeedModifier.modifier_source == ModifierSource.AGE,
                )
                .first()
            )

            if existing:
                existing.decay_rate_multiplier = decay_multiplier
                existing.max_intensity_cap = max_cap
                existing.source_detail = f"age_{age}"
                modifiers.append(existing)
            else:
                modifier = self.create_modifier(
                    entity_id=entity_id,
                    need_name=curve.need_name,
                    source=ModifierSource.AGE,
                    source_detail=f"age_{age}",
                    decay_rate_multiplier=decay_multiplier,
                    max_intensity_cap=max_cap,
                )
                modifiers.append(modifier)

        return modifiers
