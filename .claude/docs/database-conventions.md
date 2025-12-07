# Database Conventions

## Table Naming

- Use lowercase with underscores: `game_sessions`, `entity_attributes`
- Use plural nouns: `entities`, `items`, `locations`
- Prefix related tables: `entity_attributes`, `entity_skills`

## Column Naming

- Use lowercase with underscores: `entity_key`, `created_at`
- Foreign keys: `{referenced_table_singular}_id` (e.g., `session_id`, `entity_id`)
- Booleans: `is_*` or `has_*` (e.g., `is_active`, `has_pockets`)
- Timestamps: `*_at` (e.g., `created_at`, `updated_at`, `completed_at`)
- Counts: `*_count` (e.g., `turn_count`, `failure_count`)

## Primary Keys

Always use auto-incrementing integer `id`:
```python
id: Mapped[int] = mapped_column(primary_key=True, index=True)
```

## Session Scoping

Every game-specific table must have `session_id`:
```python
session_id: Mapped[int] = mapped_column(
    ForeignKey("game_sessions.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
```

## Indexes

Add indexes for:
- Foreign keys (automatic in some DBs, explicit in PostgreSQL)
- Frequently queried columns
- Unique constraints

```python
entity_key: Mapped[str] = mapped_column(String(100), index=True)
```

## Unique Constraints

Use `UniqueConstraint` for composite uniqueness:
```python
__table_args__ = (
    UniqueConstraint('session_id', 'entity_key', name='uq_entity_session_key'),
)
```

## Enums

Store as strings for readability:
```python
class EntityType(str, Enum):
    PLAYER = "player"
    NPC = "npc"

# In model:
entity_type: Mapped[EntityType] = mapped_column(
    Enum(EntityType, values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
```

## JSON Columns

Use for flexible data:
```python
# Appearance details
appearance: Mapped[dict | None] = mapped_column(JSON, nullable=True)

# Properties that vary by setting
properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

## Appearance Field Consistency

The `entities` table uses a hybrid approach: dedicated columns for queryable
appearance fields AND a JSON `appearance` field for flexibility.

### Dedicated Columns (12 fields)
```python
age, age_apparent, gender, height, build,
hair_color, hair_style, eye_color, skin_tone,
species, distinguishing_features, voice_description
```

### Consistency Rules

**Dedicated columns are the SOURCE OF TRUTH**. The JSON field mirrors and extends them.

1. **Always use Entity methods to update appearance**:
   ```python
   # Good - uses sync method
   entity.set_appearance_field("hair_color", "red")

   # Bad - breaks sync
   entity.hair_color = "red"  # JSON not updated!
   ```

2. **Bulk updates must call sync**:
   ```python
   entity.hair_color = "red"
   entity.eye_color = "blue"
   entity.sync_appearance_to_json()  # Required!
   ```

3. **EntityManager provides safe helpers**:
   ```python
   entity_manager.update_appearance(entity_key, {
       "hair_color": "red",
       "eye_color": "blue",
   })  # Automatically synced
   ```

4. **Never write synced fields directly to JSON**:
   ```python
   # Bad - columns not updated
   entity.appearance["hair_color"] = "red"

   # Good - use the method
   entity.set_appearance_field("hair_color", "red")
   ```

### Extended JSON Data

The JSON `appearance` field can contain extra data beyond the synced columns:
```python
# Setting-specific extras (not in dedicated columns)
entity.appearance["elf_ears"] = "pointed"
entity.appearance["cybernetic_arm"] = True
entity.appearance["tattoos"] = ["dragon on back", "rune on wrist"]
```

## Shadow Entity Pattern

Shadow entities are NPCs mentioned in backstory but not yet appeared on-screen.

### Creating Shadow Entities
```python
entity = entity_manager.create_shadow_entity(
    entity_key="grandmother_elara",
    display_name="Grandmother Elara",
    entity_type=EntityType.NPC,
    background="Player's grandmother, lives with player",
)
# is_active=False, first_appeared_turn=None
```

### Activating Shadow Entities
When they appear in the narrative, lock in their appearance:
```python
entity_manager.activate_shadow_entity(
    entity_key="grandmother_elara",
    current_turn=5,
    appearance_data={
        "age": 68,
        "hair_color": "silver",
        "eye_color": "warm brown",
    },
)
# is_active=True, first_appeared_turn=5, appearance locked
```

### Canonical Locking
Once `first_appeared_turn` is set, appearance should only change through:
- Player actions ("I dye my hair red")
- Significant events (dragon scars face)
- Time passage (natural aging)

## Timestamps

Standard timestamp columns:
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime,
    default=datetime.utcnow,
    nullable=False,
)
updated_at: Mapped[datetime] = mapped_column(
    DateTime,
    default=datetime.utcnow,
    onupdate=datetime.utcnow,
    nullable=False,
)
```

## Soft Deletes

For entities that shouldn't be hard deleted:
```python
is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

## Foreign Key Behavior

Always specify `ondelete`:
- `CASCADE`: Delete children when parent deleted (most common)
- `SET NULL`: Set FK to NULL when parent deleted
- `RESTRICT`: Prevent deletion of parent with children

```python
# Child deleted when session deleted
session_id: Mapped[int] = mapped_column(
    ForeignKey("game_sessions.id", ondelete="CASCADE"),
)

# Keep item if owner deleted, just clear owner
owner_id: Mapped[int | None] = mapped_column(
    ForeignKey("entities.id", ondelete="SET NULL"),
)
```

## Relationship Definitions

Always define both sides:
```python
# In GameSession
entities: Mapped[list["Entity"]] = relationship(
    back_populates="session",
    cascade="all, delete-orphan",
)

# In Entity
session: Mapped["GameSession"] = relationship(back_populates="entities")
```

## Migration Rules

### Naming
```
{revision}_{description}.py
001_initial_schema.py
002_add_quest_system.py
```

### Best Practices
1. One logical change per migration
2. Always provide `downgrade()` that reverses `upgrade()`
3. Test both directions before committing
4. Never modify released migrations

### Adding Columns
```python
def upgrade():
    op.add_column('entities', sa.Column('mood', sa.String(50), nullable=True))

def downgrade():
    op.drop_column('entities', 'mood')
```

### Adding Tables
```python
def upgrade():
    op.create_table(
        'quests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('game_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
    )
    op.create_index('ix_quests_session_id', 'quests', ['session_id'])

def downgrade():
    op.drop_index('ix_quests_session_id')
    op.drop_table('quests')
```

## Query Patterns

### Always filter by session
```python
# Good
self.db.query(Entity).filter(Entity.session_id == self.game_session.id)

# Bad - might return entities from other sessions
self.db.query(Entity).filter(Entity.entity_key == key)
```

### Use selectinload for related data
```python
from sqlalchemy.orm import selectinload

entity = (
    self.db.query(Entity)
    .options(selectinload(Entity.attributes))
    .filter(Entity.id == entity_id)
    .first()
)
```

### Bulk operations
```python
# Instead of loop with individual commits
for item in items:
    self.db.add(item)
    self.db.commit()  # Bad - N commits

# Use single commit
for item in items:
    self.db.add(item)
self.db.commit()  # Good - 1 commit
```
