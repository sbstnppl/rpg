# Coding Standards

## Python Version
- Target Python 3.11+
- Use modern type hints (PEP 604 union syntax: `int | None`)

## Code Style

### General
- Follow PEP 8
- Use `black` for formatting (line length 100)
- Use `ruff` for linting
- Use `mypy` for type checking

### Imports
```python
# Standard library
from datetime import datetime
from typing import Optional

# Third-party
from sqlalchemy.orm import Mapped, mapped_column

# Local
from src.database.models.base import Base
```

### Type Hints
Always use type hints:
```python
def get_entity(self, key: str) -> Entity | None:
    ...

def create_entity(
    self,
    name: str,
    entity_type: EntityType,
    **kwargs: Any,
) -> Entity:
    ...
```

### Docstrings
Use Google-style docstrings:
```python
def update_attitude(
    self,
    from_entity: str,
    to_entity: str,
    dimension: str,
    delta: int,
    reason: str,
) -> RelationshipChange:
    """Update an attitude dimension between two entities.

    Args:
        from_entity: Key of the entity whose attitude is changing
        to_entity: Key of the entity being evaluated
        dimension: One of 'trust', 'liking', 'respect', 'romantic_interest'
        delta: Amount to change (-100 to +100)
        reason: Why the change occurred

    Returns:
        The RelationshipChange record created

    Raises:
        ValueError: If dimension is invalid or delta is out of range
    """
```

## Database Patterns

### Model Definitions
```python
class Entity(Base):
    """Base entity for all characters."""
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Relationships
    session: Mapped["GameSession"] = relationship(back_populates="entities")
```

### Enum Definitions
```python
class EntityType(str, Enum):
    """Type of entity in the game world."""
    PLAYER = "player"
    NPC = "npc"
    MONSTER = "monster"
```

### Foreign Keys
Always specify `ondelete` behavior:
```python
session_id: Mapped[int] = mapped_column(
    ForeignKey("game_sessions.id", ondelete="CASCADE"),
)
```

## Manager Pattern

### Base Manager
```python
class BaseManager:
    """Base class for all managers."""

    def __init__(self, db: Session, game_session: GameSession) -> None:
        self.db = db
        self.game_session = game_session
```

### Manager Methods
```python
class EntityManager(BaseManager):
    def get_entity(self, key: str) -> Entity | None:
        """Get entity by key."""
        return (
            self.db.query(Entity)
            .filter(
                Entity.session_id == self.game_session.id,
                Entity.entity_key == key,
            )
            .first()
        )
```

## Agent Patterns

### LangGraph Nodes
```python
async def game_master_node(state: GameState) -> GameState:
    """Game Master agent node."""
    # Get context
    context = state["scene_context"]
    player_input = state["player_input"]

    # Generate response
    response = await llm.complete(...)

    # Return updated state
    return {
        **state,
        "gm_response": response,
        "next_agent": determine_next_agent(response),
    }
```

### State Updates
Always return a new dict with updates, don't mutate:
```python
# Good
return {**state, "gm_response": response}

# Bad
state["gm_response"] = response
return state
```

## Testing

### TDD Approach (Required)
All new features **must** follow Test-Driven Development:
1. **Red**: Write a failing test first
2. **Green**: Write minimum code to pass
3. **Refactor**: Improve while keeping tests green

### Test Categories
- **Model tests**: `tests/test_database/test_models/` - Test DB models, constraints, relationships
- **Manager tests**: `tests/test_managers/` - Test business logic
- **Integration tests**: `tests/test_integration/` - Test cross-component behavior

### Use Factories
Always use factories from `tests/factories.py` instead of creating models directly:
```python
from tests.factories import create_entity, create_relationship, create_game_session

def test_something(db_session, game_session):
    # Good - uses factory
    entity = create_entity(db_session, game_session, entity_key="hero")

    # Bad - creates model directly
    entity = Entity(session_id=game_session.id, ...)
```

### Test Structure
```python
class TestEntityManager:
    """Group related tests in classes."""

    def test_create_entity(self, db_session, game_session):
        """Test names describe expected behavior."""
        manager = EntityManager(db_session, game_session)
        entity = manager.create_entity(
            name="Test NPC",
            entity_type=EntityType.NPC,
        )
        assert entity.name == "Test NPC"
        assert entity.entity_type == EntityType.NPC
```

### Session Scoping Tests
Always verify session isolation when testing queries:
```python
def test_query_scopes_to_session(db_session, game_session):
    other_session = create_game_session(db_session)
    entity1 = create_entity(db_session, game_session)
    entity2 = create_entity(db_session, other_session)

    result = manager.get_entities()
    assert entity1 in result
    assert entity2 not in result  # Different session
```

### Core Fixtures (from conftest.py)
- `engine`: SQLite in-memory database (session scope)
- `db_session`: Fresh database session per test with rollback
- `game_session`: GameSession fixture with defaults

## Error Handling

### Custom Exceptions
```python
class RPGError(Exception):
    """Base exception for RPG game."""
    pass

class EntityNotFoundError(RPGError):
    """Entity not found in database."""
    pass

class InvalidAttributeError(RPGError):
    """Invalid attribute for current setting."""
    pass
```

### Raise with Context
```python
def get_entity_or_raise(self, key: str) -> Entity:
    entity = self.get_entity(key)
    if not entity:
        raise EntityNotFoundError(f"Entity '{key}' not found in session {self.game_session.id}")
    return entity
```
