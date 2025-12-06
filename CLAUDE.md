# RPG Game - Claude Code Instructions

## Custom Subagents

This project has specialized subagents in `.claude/agents/`. **Proactively use them** for relevant tasks:

| Agent | Invoke When |
|-------|-------------|
| `langgraph-expert` | Building LangGraph graphs, agent nodes, state schemas, async patterns |
| `database-architect` | Creating/modifying SQLAlchemy models, writing migrations, query optimization |
| `game-designer` | Designing dice mechanics, attribute systems, combat balance, skill checks |
| `prompt-engineer` | Writing LLM prompts, entity extraction, structured output parsing |
| `storyteller` | Creating NPCs, quests, locations, narrative content, world-building |

### When to Use Subagents

- **Complex implementation tasks**: Spawn the relevant expert agent
- **Design decisions**: Use `game-designer` for mechanics, `storyteller` for content
- **Multiple domains**: Spawn multiple agents in parallel for comprehensive solutions
- **Code review**: Have relevant expert review implementation

**Example**: "Building the CombatResolver agent" → spawn both `langgraph-expert` (for the agent structure) and `game-designer` (for combat mechanics)

---

## Project Overview

An agentic console-based RPG using LangGraph for multi-agent orchestration. The game features:
- Persistent world state with SQL database
- Flexible character attributes (setting-dependent)
- Dice-based combat and skill checks
- NPC schedules and dynamic events
- Relationship tracking (trust, liking, respect, romantic interest)

## Tech Stack

- **Python 3.11+**
- **LangGraph** - Multi-agent orchestration
- **SQLAlchemy 2.0+** - ORM with async support
- **PostgreSQL** - Database
- **Alembic** - Migrations
- **Typer + Rich** - CLI
- **Anthropic + OpenAI** - Dual LLM support

## Quick Commands

```bash
# Run the game
python -m src.main

# Run tests
pytest

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

## Project Structure

```
rpg/
├── src/
│   ├── database/models/    # SQLAlchemy models
│   ├── managers/           # Business logic (Manager pattern)
│   ├── agents/             # LangGraph agents
│   ├── llm/                # LLM provider abstraction
│   ├── cli/                # Typer CLI commands
│   ├── dice/               # Dice rolling mechanics
│   └── schemas/            # Setting configurations
├── tests/
├── docs/                   # User documentation
├── .claude/docs/           # Claude-specific docs
├── data/
│   ├── settings/           # Setting templates (fantasy, etc.)
│   └── templates/          # Prompt templates
└── alembic/                # Database migrations
```

## Key Documentation

- `docs/architecture.md` - System architecture
- `docs/implementation-plan.md` - Implementation checklist
- `.claude/docs/coding-standards.md` - Code style guide
- `.claude/docs/agent-prompts.md` - LLM prompt templates
- `.claude/docs/database-conventions.md` - DB patterns

## Core Patterns

### Manager Pattern
Each domain has a dedicated manager class:
```python
class EntityManager(BaseManager):
    def get_entity(self, key: str) -> Entity | None
    def create_entity(self, **data) -> Entity
```

### LangGraph State
```python
class GameState(TypedDict):
    session_id: int
    player_input: str
    gm_response: str | None
    scene_context: str
    next_agent: str
```

### Database Session Scoping
Every query must filter by `session_id`:
```python
self.db.query(Entity).filter(Entity.session_id == self.game_session.id)
```

## Important Design Decisions

1. **Owner vs Holder**: Items have `owner_id` (permanent) and `holder_id` (who has it now)
2. **Body Slots + Layers**: Clothing uses `body_slot` and `body_layer` for realistic outfit tracking
3. **SPV Facts**: Subject-Predicate-Value pattern for flexible world facts
4. **Immutable Turns**: Turn history never modified; session context is mutable

## Environment Variables

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
DATABASE_URL=postgresql://localhost/rpg_game
LLM_PROVIDER=anthropic  # or openai
```

## Testing

**TDD Required**: All new features must be developed using Test-Driven Development:
1. Write failing tests first
2. Implement minimum code to pass
3. Refactor while keeping tests green

### Test Structure
```
tests/
├── conftest.py                    # Core fixtures (db_session, game_session)
├── factories.py                   # Test data factories
├── test_database/test_models/     # Model tests (319 tests)
├── test_managers/                 # Manager tests (158 tests)
└── test_integration/              # Integration tests (23 tests)
```

### Commands
```bash
# Run all tests (500 tests, ~1 second)
pytest

# Run specific test file
pytest tests/test_managers/test_needs_manager.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src
```

### Writing Tests
Use factories from `tests/factories.py`:
```python
from tests.factories import create_entity, create_relationship

def test_something(db_session, game_session):
    entity = create_entity(db_session, game_session, entity_key="hero")
    # ... test logic
```

## Documentation Requirements

**MANDATORY**: Documentation MUST be updated after any changes, feature implementations, bug fixes, or refactoring. The documentation MUST always reflect the current project and implementation status.

### After Every Change, Update:

1. **`CHANGELOG.md`** - Add entry under `[Unreleased]` section (Added/Changed/Fixed/Removed)
2. **`docs/implementation-plan.md`** - Mark completed items with `[x]`, add new methods/features to the appropriate section
3. **Code docstrings** - All public methods MUST have Google-style docstrings with Args, Returns, and Raises sections
4. **`docs/architecture.md`** - Update if architectural changes are made (new managers, agents, patterns)
5. **`CLAUDE.md`** - Update if new patterns, conventions, or workflows are established

### Documentation Checklist (run after implementation):
- [ ] CHANGELOG.md updated with new entry
- [ ] Implementation plan updated with completed items
- [ ] New methods have docstrings
- [ ] Test count updated if significantly changed
- [ ] Architecture doc updated (if applicable)
- [ ] Commit message describes changes clearly

### Key Documentation Files:
| File | Update When |
|------|-------------|
| `CHANGELOG.md` | **Every change** - Add entry under [Unreleased] section |
| `docs/implementation-plan.md` | Any feature completion, new methods added |
| `docs/architecture.md` | New components, patterns, or system changes |
| `docs/user-guide.md` | New CLI commands, user-facing features |
| `.claude/docs/coding-standards.md` | New coding conventions established |
| `.claude/docs/database-conventions.md` | New DB patterns or model conventions |

## Common Tasks

### Add a new entity type (TDD)
1. Write tests in `tests/test_database/test_models/test_entities.py`
2. Add enum value to `src/database/models/enums.py`
3. Create extension model if needed (like `NPCExtension`)
4. Run tests - verify they pass
5. Write manager tests in `tests/test_managers/`
6. Update manager methods
7. Add migration

### Add a new manager (TDD)
1. Write tests in `tests/test_managers/test_<manager_name>.py`
2. Create manager in `src/managers/`
3. Implement methods until tests pass
4. Add integration tests if needed

### Add a new agent
1. Create agent file in `src/agents/`
2. Add node to graph in `src/agents/graph.py`
3. Create prompt template in `data/templates/`
4. Add tools in `src/agents/tools/`

### Add a new CLI command
1. Create command file in `src/cli/commands/`
2. Register with Typer app in `src/cli/main.py`

## Reference Project

The `../story-learning/` project uses similar patterns:
- Manager pattern for state
- SPV fact store
- Attitude tracking (0-100 scale)
- Item ownership model

Refer to it for implementation examples.
