"""Item and storage models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base, TimestampMixin
from src.database.models.enums import ItemCondition, ItemType, StorageLocationType

if TYPE_CHECKING:
    from src.database.models.entities import Entity
    from src.database.models.session import GameSession
    from src.database.models.world import Location


class StorageLocation(Base, TimestampMixin):
    """A storage location (body, container, or place)."""

    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    location_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'player_body', 'chest_01')",
    )
    location_type: Mapped[StorageLocationType] = mapped_column(
        Enum(StorageLocationType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    # Ownership
    owner_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Entity who owns this storage (for ON_PERSON/CONTAINER)",
    )

    # Location linkage (for PLACE type)
    world_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Link to world location for PLACE type",
    )

    # Container properties
    container_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Type: backpack, chest, bag, shelf, etc.",
    )
    capacity: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Max items this can hold",
    )

    # Hierarchy (for nested containers)
    parent_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("storage_locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lifecycle
    is_temporary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Temporary storage (destroyed when emptied)",
    )
    destroyed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Relationships
    stored_items: Mapped[list["Item"]] = relationship(
        back_populates="storage_location",
        cascade="all, delete-orphan",
    )
    owner_entity: Mapped["Entity | None"] = relationship(
        foreign_keys=[owner_entity_id],
    )
    world_location: Mapped["Location | None"] = relationship()
    parent_location: Mapped["StorageLocation | None"] = relationship(
        remote_side="StorageLocation.id",
        foreign_keys=[parent_location_id],
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "location_key", name="uq_storage_session_key"),
    )

    def __repr__(self) -> str:
        return f"<StorageLocation {self.location_key} ({self.location_type.value})>"


class Item(Base, TimestampMixin):
    """An item in the game world."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    item_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'player_sword', 'healing_potion_01')",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    item_type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, values_callable=lambda obj: [e.value for e in obj]),
        default=ItemType.MISC,
        nullable=False,
    )

    # Ownership (who it BELONGS to - important for borrowed items)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Entity who owns this item (not necessarily who has it)",
    )

    # Current holder (who HAS it right now)
    holder_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Entity who currently possesses the item",
    )

    # Location (where it currently IS)
    storage_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("storage_locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Body placement (only used when storage is ON_PERSON type)
    body_slot: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
        comment="Body slot when worn/carried (e.g., 'upper_body', 'right_hand')",
    )
    body_layer: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Layer: 0=innermost, 1=over 0, 2=over 1, etc.",
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False if covered by outer layer",
    )

    # Clothing bonus: slots this item provides when worn
    provides_slots: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Slots this provides when worn (e.g., ['pocket_left', 'pocket_right'])",
    )

    # Condition
    condition: Mapped[ItemCondition] = mapped_column(
        Enum(ItemCondition, values_callable=lambda obj: [e.value for e in obj]),
        default=ItemCondition.GOOD,
        nullable=False,
    )
    durability: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="0-100 durability",
    )

    # Physical properties
    weight: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Weight in pounds (for encumbrance calculation)",
    )

    # Stacking (for consumables)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    is_stackable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Item properties (setting-specific)
    properties: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Item-specific properties (damage, armor, effects)",
    )

    # Tracking
    acquired_turn: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Turn when item was acquired",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    owner: Mapped["Entity | None"] = relationship(
        foreign_keys=[owner_id],
    )
    holder: Mapped["Entity | None"] = relationship(
        foreign_keys=[holder_id],
    )
    storage_location: Mapped["StorageLocation | None"] = relationship(
        back_populates="stored_items",
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("session_id", "item_key", name="uq_item_session_key"),
    )

    def __repr__(self) -> str:
        loc_str = ""
        if self.storage_location_id:
            loc_str = f" @ storage_{self.storage_location_id}"
        slot_str = ""
        if self.body_slot:
            slot_str = f" [{self.body_slot} L{self.body_layer}]"
        qty_str = f" x{self.quantity}" if self.quantity > 1 else ""
        return f"<Item {self.display_name}{qty_str}{slot_str}{loc_str}>"
