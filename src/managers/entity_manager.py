"""EntityManager for entity CRUD and attribute management."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database.models.enums import EntityType
from src.database.models.entities import (
    Entity,
    EntityAttribute,
    EntitySkill,
    NPCExtension,
)
from src.database.models.session import GameSession
from src.database.models.world import Location
from src.managers.base import BaseManager


class EntityManager(BaseManager):
    """Manager for entity operations.

    Handles:
    - Entity CRUD (create, read, update)
    - Attribute management (get, set, modify)
    - Skill management
    - Location tracking
    - Status changes (death, inactive)
    """

    def get_entity(self, entity_key: str) -> Entity | None:
        """Get entity by key.

        Args:
            entity_key: Unique entity key.

        Returns:
            Entity if found, None otherwise.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_key == entity_key,
            )
            .first()
        )

    def get_entity_by_id(self, entity_id: int) -> Entity | None:
        """Get entity by ID.

        Args:
            entity_id: Entity ID.

        Returns:
            Entity if found, None otherwise.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.id == entity_id,
            )
            .first()
        )

    def get_entity_by_display_name(self, display_name: str) -> Entity | None:
        """Get entity by display name (case-insensitive).

        Used to detect duplicate entities with different keys but same name.

        Args:
            display_name: Entity display name to search for.

        Returns:
            Entity if found, None otherwise.
        """
        from sqlalchemy import func

        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                func.lower(Entity.display_name) == display_name.lower(),
            )
            .first()
        )

    def get_temporary_state(
        self,
        entity_key: str,
        property_name: str,
        default: any = None,
    ) -> any:
        """Get a property from entity's temporary_state JSON.

        Args:
            entity_key: Entity key.
            property_name: Property to get.
            default: Default value if property not found.

        Returns:
            Property value or default.
        """
        entity = self.get_entity(entity_key)
        if entity is None or entity.temporary_state is None:
            return default
        return entity.temporary_state.get(property_name, default)

    def update_temporary_state(
        self,
        entity_key: str,
        property_name: str,
        value: any,
    ) -> Entity:
        """Update entity's temporary state.

        Temporary state is transient (posture, position, etc.) and may be
        cleared on location change or other events.

        Args:
            entity_key: Entity key.
            property_name: State property (e.g., "posture").
            value: New value.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        from sqlalchemy.orm.attributes import flag_modified

        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        if entity.temporary_state is None:
            entity.temporary_state = {}

        entity.temporary_state[property_name] = value

        flag_modified(entity, "temporary_state")

        self.db.flush()
        return entity

    def clear_temporary_state(self, entity_key: str) -> None:
        """Clear entity's temporary state.

        Call this on location change or when transient state should reset.

        Args:
            entity_key: Entity key.
        """
        from sqlalchemy.orm.attributes import flag_modified

        entity = self.get_entity(entity_key)
        if entity and entity.temporary_state:
            entity.temporary_state = {}
            flag_modified(entity, "temporary_state")
            self.db.flush()

    def create_entity(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType,
        **kwargs,
    ) -> Entity:
        """Create a new entity.

        Args:
            entity_key: Unique key for the entity.
            display_name: Display name.
            entity_type: Type of entity (PLAYER, NPC, MONSTER, ANIMAL).
            **kwargs: Additional fields (appearance, background, etc.)

        Returns:
            Created Entity.
        """
        entity = Entity(
            session_id=self.session_id,
            entity_key=entity_key,
            display_name=display_name,
            entity_type=entity_type,
            is_alive=True,
            is_active=True,
            **kwargs,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def get_player(self) -> Entity | None:
        """Get the player entity for this session.

        Returns:
            Player entity if exists, None otherwise.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.PLAYER,
            )
            .first()
        )

    def get_all_npcs(self, alive_only: bool = True) -> list[Entity]:
        """Get all NPCs in the session.

        Args:
            alive_only: If True, only return living NPCs.

        Returns:
            List of NPC entities.
        """
        query = self.db.query(Entity).filter(
            Entity.session_id == self.session_id,
            Entity.entity_type == EntityType.NPC,
        )
        if alive_only:
            query = query.filter(Entity.is_alive == True)
        return query.all()

    def get_active_entities(self) -> list[Entity]:
        """Get all active and alive entities.

        Returns:
            List of entities where is_alive=True and is_active=True.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.is_alive == True,
                Entity.is_active == True,
            )
            .all()
        )

    def get_entities_at_location(self, location_key: str) -> list[Entity]:
        """Get all entities at a location.

        Uses NPCExtension.current_location to determine location.
        Also matches by display_name as fallback for data inconsistencies.

        Args:
            location_key: Location key to search.

        Returns:
            List of entities at the location.
        """
        # Get the location's display name for fallback matching
        # (handles cases where NPC location was set to display_name instead of key)
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )
        display_name = location.display_name if location else None

        # Match by either location_key OR display_name (defensive fix)
        location_filter = NPCExtension.current_location == location_key
        if display_name:
            location_filter = or_(
                NPCExtension.current_location == location_key,
                NPCExtension.current_location == display_name,
            )

        return (
            self.db.query(Entity)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                location_filter,
            )
            .all()
        )

    def get_npcs_in_scene(
        self, location_key: str, alive_only: bool = True
    ) -> list[Entity]:
        """Get NPCs at a location for scene context.

        Args:
            location_key: Location key to search (must match exactly).
            alive_only: If True, only return living NPCs.

        Returns:
            List of NPC entities at the location.
        """
        # Match ONLY by location_key - no display_name fallback to prevent
        # NPCs from appearing at wrong locations due to fuzzy matching
        query = (
            self.db.query(Entity)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                NPCExtension.current_location == location_key,
            )
        )
        if alive_only:
            query = query.filter(Entity.is_alive == True)
        return query.all()

    def get_location_inhabitants(
        self, location_key: str, alive_only: bool = True
    ) -> list[dict]:
        """Get NPCs who habitually live or work at a location.

        Unlike get_npcs_in_scene which returns NPCs currently present,
        this returns NPCs whose workplace or home_location matches,
        regardless of where they are right now.

        Also checks parent locations - if you're in 'farmhouse_kitchen',
        this will also return NPCs who work at 'family_farm' (the parent).

        Args:
            location_key: Location to query (e.g., 'family_farm').
            alive_only: If True, only return living NPCs.

        Returns:
            List of dicts with NPC info and role (lives_here/works_here).
        """
        from sqlalchemy import or_
        from src.database.models.world import Location

        # Build list of location keys to check (current + parents)
        location_keys_to_check = [location_key]

        # Get parent location keys (walk up the hierarchy)
        location = (
            self.db.query(Location)
            .filter(
                Location.session_id == self.session_id,
                Location.location_key == location_key,
            )
            .first()
        )
        while location and location.parent_location_id:
            parent = (
                self.db.query(Location)
                .filter(Location.id == location.parent_location_id)
                .first()
            )
            if parent:
                location_keys_to_check.append(parent.location_key)
                location = parent
            else:
                break

        query = (
            self.db.query(Entity)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.entity_type == EntityType.NPC,
                or_(
                    NPCExtension.home_location.in_(location_keys_to_check),
                    NPCExtension.workplace.in_(location_keys_to_check),
                ),
            )
        )
        if alive_only:
            query = query.filter(Entity.is_alive == True)

        npcs = query.all()

        result = []
        for npc in npcs:
            ext = npc.npc_extension
            # Determine role - prioritize "lives here" if both match
            if ext.home_location in location_keys_to_check:
                role = "lives here"
            else:
                role = "works here"

            result.append({
                "key": npc.entity_key,
                "name": npc.display_name,
                "role": role,
                "job": ext.job,
            })
        return result

    def update_location(self, entity_key: str, location_key: str) -> Entity:
        """Update entity's current location.

        Creates NPCExtension if it doesn't exist.

        Args:
            entity_key: Entity key.
            location_key: New location key.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        if entity.npc_extension is None:
            extension = NPCExtension(entity_id=entity.id)
            self.db.add(extension)
            self.db.flush()
            # Refresh to get the relationship
            self.db.refresh(entity)

        entity.npc_extension.current_location = location_key
        self.db.flush()
        return entity

    def update_activity(
        self,
        entity_key: str,
        activity: str,
        mood: str | None = None,
    ) -> Entity:
        """Update NPC's current activity and optionally mood.

        Args:
            entity_key: Entity key.
            activity: Current activity description.
            mood: Optional mood update.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        if entity.npc_extension is None:
            extension = NPCExtension(entity_id=entity.id)
            self.db.add(extension)
            self.db.flush()
            self.db.refresh(entity)

        entity.npc_extension.current_activity = activity
        if mood is not None:
            entity.npc_extension.current_mood = mood
        self.db.flush()
        return entity

    def get_attribute(self, entity_id: int, attribute_key: str) -> int | None:
        """Get attribute value including temporary modifier.

        Args:
            entity_id: Entity ID.
            attribute_key: Attribute key.

        Returns:
            Value + temporary_modifier, or None if not found.
        """
        attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == attribute_key,
            )
            .first()
        )
        if attr is None:
            return None
        return attr.value + attr.temporary_modifier

    def update_attribute(
        self,
        entity_id: int,
        attribute_key: str,
        value: int,
    ) -> EntityAttribute:
        """Update attribute value (creates if missing). Alias for set_attribute.

        Args:
            entity_id: Entity ID.
            attribute_key: Attribute key.
            value: New value.

        Returns:
            Created or updated EntityAttribute.
        """
        return self.set_attribute(entity_id, attribute_key, value)

    def set_attribute(
        self,
        entity_id: int,
        attribute_key: str,
        value: int,
        max_value: int | None = None,
    ) -> EntityAttribute:
        """Set attribute value (creates if missing).

        Args:
            entity_id: Entity ID.
            attribute_key: Attribute key.
            value: New value.
            max_value: Optional maximum value.

        Returns:
            Created or updated EntityAttribute.
        """
        attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == attribute_key,
            )
            .first()
        )

        if attr is None:
            attr = EntityAttribute(
                entity_id=entity_id,
                attribute_key=attribute_key,
                value=value,
                max_value=max_value,
                temporary_modifier=0,
            )
            self.db.add(attr)
        else:
            attr.value = value
            if max_value is not None:
                attr.max_value = max_value

        self.db.flush()
        return attr

    def modify_attribute(
        self,
        entity_id: int,
        attribute_key: str,
        delta: int,
    ) -> EntityAttribute:
        """Modify attribute by delta (creates if missing).

        Args:
            entity_id: Entity ID.
            attribute_key: Attribute key.
            delta: Amount to add (can be negative).

        Returns:
            Updated EntityAttribute.
        """
        attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == attribute_key,
            )
            .first()
        )

        if attr is None:
            attr = EntityAttribute(
                entity_id=entity_id,
                attribute_key=attribute_key,
                value=delta,
                temporary_modifier=0,
            )
            self.db.add(attr)
        else:
            attr.value += delta

        self.db.flush()
        return attr

    def set_temporary_modifier(
        self,
        entity_id: int,
        attribute_key: str,
        modifier: int,
    ) -> EntityAttribute:
        """Set temporary modifier for an attribute.

        Args:
            entity_id: Entity ID.
            attribute_key: Attribute key.
            modifier: Temporary modifier value.

        Returns:
            Updated EntityAttribute.

        Raises:
            ValueError: If attribute not found.
        """
        attr = (
            self.db.query(EntityAttribute)
            .filter(
                EntityAttribute.entity_id == entity_id,
                EntityAttribute.attribute_key == attribute_key,
            )
            .first()
        )

        if attr is None:
            raise ValueError(f"Attribute not found: {attribute_key}")

        attr.temporary_modifier = modifier
        self.db.flush()
        return attr

    def get_skill(self, entity_id: int, skill_key: str) -> EntitySkill | None:
        """Get skill for entity.

        Args:
            entity_id: Entity ID.
            skill_key: Skill key.

        Returns:
            EntitySkill if found, None otherwise.
        """
        return (
            self.db.query(EntitySkill)
            .filter(
                EntitySkill.entity_id == entity_id,
                EntitySkill.skill_key == skill_key,
            )
            .first()
        )

    def set_skill(
        self,
        entity_id: int,
        skill_key: str,
        level: int,
    ) -> EntitySkill:
        """Set skill level (creates if missing).

        Args:
            entity_id: Entity ID.
            skill_key: Skill key.
            level: Proficiency level.

        Returns:
            Created or updated EntitySkill.
        """
        skill = (
            self.db.query(EntitySkill)
            .filter(
                EntitySkill.entity_id == entity_id,
                EntitySkill.skill_key == skill_key,
            )
            .first()
        )

        if skill is None:
            skill = EntitySkill(
                entity_id=entity_id,
                skill_key=skill_key,
                proficiency_level=level,
            )
            self.db.add(skill)
        else:
            skill.proficiency_level = level

        self.db.flush()
        return skill

    def mark_dead(self, entity_key: str) -> Entity:
        """Mark entity as dead.

        Args:
            entity_key: Entity key.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        entity.is_alive = False
        self.db.flush()
        return entity

    def mark_inactive(self, entity_key: str) -> Entity:
        """Mark entity as inactive (left scene permanently).

        Args:
            entity_key: Entity key.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        entity.is_active = False
        self.db.flush()
        return entity

    # ==================== Appearance Methods ====================

    def update_appearance(
        self,
        entity_key: str,
        appearance_data: dict[str, str | int | None],
    ) -> Entity:
        """Update entity appearance fields and sync to JSON.

        Args:
            entity_key: Entity key.
            appearance_data: Dict of appearance field values.
                Valid keys: age, age_apparent, gender, height, build,
                hair_color, hair_style, eye_color, skin_tone, species,
                distinguishing_features, voice_description.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found or invalid field name.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        for field, value in appearance_data.items():
            entity.set_appearance_field(field, value)

        self.db.flush()
        return entity

    def get_entities_by_appearance(
        self,
        **kwargs,
    ) -> list[Entity]:
        """Find entities matching appearance criteria.

        Args:
            **kwargs: Appearance field filters (e.g., hair_color="red").
                Supports: age, gender, height, build, hair_color, eye_color,
                skin_tone, species.

        Returns:
            List of matching entities.
        """
        query = self.db.query(Entity).filter(
            Entity.session_id == self.session_id,
            Entity.is_alive == True,
        )

        valid_fields = Entity.APPEARANCE_FIELDS
        for field, value in kwargs.items():
            if field not in valid_fields:
                raise ValueError(f"Invalid appearance field: {field}")
            query = query.filter(getattr(Entity, field) == value)

        return query.all()

    def get_appearance_summary(self, entity_key: str) -> str:
        """Get human-readable appearance summary for an entity.

        Args:
            entity_key: Entity key.

        Returns:
            Formatted appearance description.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        return entity.get_appearance_summary()

    # ==================== Shadow Entity Methods ====================

    def create_shadow_entity(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType = EntityType.NPC,
        background: str | None = None,
        **kwargs,
    ) -> Entity:
        """Create a shadow entity (mentioned but not yet appeared).

        Shadow entities are created from backstory mentions and remain
        inactive until they appear in the narrative. They have minimal
        data that gets filled in on first appearance.

        Args:
            entity_key: Unique key for the entity.
            display_name: Display name.
            entity_type: Type of entity (default: NPC).
            background: Brief description from backstory.
            **kwargs: Additional fields (appearance, personality, etc.)

        Returns:
            Created shadow Entity.
        """
        entity = Entity(
            session_id=self.session_id,
            entity_key=entity_key,
            display_name=display_name,
            entity_type=entity_type,
            is_alive=True,
            is_active=False,  # Shadow entities start inactive
            background=background,
            first_appeared_turn=None,  # Not yet appeared
            **kwargs,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def activate_shadow_entity(
        self,
        entity_key: str,
        current_turn: int,
        appearance_data: dict[str, str | int | None] | None = None,
    ) -> Entity:
        """Activate a shadow entity when it first appears in the narrative.

        This locks in the entity's appearance and marks the first appearance turn.

        Args:
            entity_key: Entity key.
            current_turn: Current game turn number.
            appearance_data: Appearance details extracted from GM description.

        Returns:
            Activated Entity.

        Raises:
            ValueError: If entity not found or already active.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        if entity.is_active and entity.first_appeared_turn is not None:
            raise ValueError(f"Entity already activated: {entity_key}")

        # Mark first appearance
        entity.is_active = True
        entity.first_appeared_turn = current_turn

        # Lock in appearance if provided
        if appearance_data:
            for field, value in appearance_data.items():
                if field in Entity.APPEARANCE_FIELDS:
                    entity.set_appearance_field(field, value)

        self.db.flush()
        return entity

    def get_shadow_entities(self) -> list[Entity]:
        """Get all shadow entities (mentioned but not appeared).

        Returns:
            List of inactive entities with no first_appeared_turn.
        """
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.session_id,
                Entity.is_active == False,
                Entity.first_appeared_turn.is_(None),
            )
            .all()
        )

    def get_or_create_entity(
        self,
        entity_key: str,
        display_name: str,
        entity_type: EntityType,
        **kwargs,
    ) -> tuple[Entity, bool]:
        """Get existing entity or create new one.

        Args:
            entity_key: Entity key.
            display_name: Display name (used if creating).
            entity_type: Entity type.
            **kwargs: Additional fields for creation.

        Returns:
            Tuple of (Entity, created: bool).
        """
        entity = self.get_entity(entity_key)
        if entity is not None:
            return entity, False

        entity = self.create_entity(
            entity_key=entity_key,
            display_name=display_name,
            entity_type=entity_type,
            **kwargs,
        )
        return entity, True

    # ==================== Potential Stats Methods ====================

    def set_potential_stats(
        self,
        entity_key: str,
        potential_stats: dict[str, int],
    ) -> Entity:
        """Set hidden potential stats for an entity.

        Args:
            entity_key: Entity key.
            potential_stats: Dict of potential stat values.
                Valid keys: strength, dexterity, constitution,
                intelligence, wisdom, charisma.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found or invalid stat name.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        valid_stats = {
            "strength", "dexterity", "constitution",
            "intelligence", "wisdom", "charisma",
        }
        for stat, value in potential_stats.items():
            if stat not in valid_stats:
                raise ValueError(f"Invalid potential stat: {stat}")
            setattr(entity, f"potential_{stat}", value)

        self.db.flush()
        return entity

    def get_potential_stats(self, entity_key: str) -> dict[str, int | None]:
        """Get hidden potential stats for an entity.

        Args:
            entity_key: Entity key.

        Returns:
            Dict of potential stat values (may contain None for unset stats).

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        return {
            "strength": entity.potential_strength,
            "dexterity": entity.potential_dexterity,
            "constitution": entity.potential_constitution,
            "intelligence": entity.potential_intelligence,
            "wisdom": entity.potential_wisdom,
            "charisma": entity.potential_charisma,
        }

    def set_occupation(
        self,
        entity_key: str,
        occupation: str,
        years: int | None = None,
    ) -> Entity:
        """Set occupation for an entity.

        Args:
            entity_key: Entity key.
            occupation: Occupation name (e.g., 'blacksmith', 'farmer').
            years: Years spent in the occupation.

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        entity.occupation = occupation
        if years is not None:
            entity.occupation_years = years

        self.db.flush()
        return entity

    # ==================== Companion Methods ====================

    def set_companion_status(
        self,
        entity_key: str,
        is_companion: bool,
        turn: int | None = None,
    ) -> Entity:
        """Set whether an NPC is traveling with the player.

        Companion NPCs have their needs tracked with time-based decay,
        while non-companion NPCs use contextual inference for their state.

        Args:
            entity_key: Entity key.
            is_companion: Whether NPC is now a companion.
            turn: Turn number when status changed (used when joining).

        Returns:
            Updated Entity.

        Raises:
            ValueError: If entity not found.
        """
        entity = self.get_entity(entity_key)
        if entity is None:
            raise ValueError(f"Entity not found: {entity_key}")

        # Ensure NPC extension exists
        if entity.npc_extension is None:
            extension = NPCExtension(entity_id=entity.id)
            self.db.add(extension)
            self.db.flush()
            self.db.refresh(entity)

        entity.npc_extension.is_companion = is_companion
        if is_companion and turn is not None:
            entity.npc_extension.companion_since_turn = turn
        elif not is_companion:
            entity.npc_extension.companion_since_turn = None

        self.db.flush()
        return entity

    def get_companions(self) -> list[Entity]:
        """Get all NPCs currently traveling with the player.

        Returns:
            List of entities marked as companions.
        """
        return (
            self.db.query(Entity)
            .join(NPCExtension, Entity.id == NPCExtension.entity_id)
            .filter(
                Entity.session_id == self.session_id,
                Entity.is_alive == True,
                NPCExtension.is_companion == True,
            )
            .all()
        )
