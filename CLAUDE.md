# RPG Game - Claude Code Instructions

> ⚠️ **Before finishing every response**: Check user's English for unnatural phrasing → [SoCal Feedback](#socal-english-feedback)

## Custom Subagents

This project has specialized subagents in `.claude/agents/`. **Proactively use them** for relevant tasks:

| Agent | Invoke When |
|-------|-------------|
| `langgraph-expert` | Building LangGraph graphs, agent nodes, state schemas, async patterns |
| `database-architect` | Creating/modifying SQLAlchemy models, writing migrations, query optimization |
| `game-designer` | Designing dice mechanics, attribute systems, combat balance, skill checks |
| `prompt-engineer` | Writing LLM prompts, entity extraction, structured output parsing |
| `storyteller` | Creating NPCs, quests, locations, narrative content, world-building |
| `realism-validator` | **Required in planning mode** for game mechanics - cross-domain realism check |
| `physiology-validator` | Validating body mechanics: sleep, fatigue, hunger, thirst, health |
| `temporal-validator` | Validating time/duration accuracy for activities |
| `social-validator` | Validating NPC behavior and relationship dynamics |
| `physics-validator` | Validating environmental effects and object physics |

### When to Use Subagents

- **Complex implementation tasks**: Spawn the relevant expert agent
- **Design decisions**: Use `game-designer` for mechanics, `storyteller` for content
- **Multiple domains**: Spawn multiple agents in parallel for comprehensive solutions
- **Code review**: Have relevant expert review implementation

**Example**: "Building the CombatResolver agent" → spawn both `langgraph-expert` (for the agent structure) and `game-designer` (for combat mechanics)

### Realism Validation (REQUIRED)

This game prioritizes real-world accuracy in its mechanics. **When proposing game mechanics during planning mode, realism validation is mandatory.**

#### Reference Document
Read `.claude/docs/realism-principles.md` for the principles that guide realistic mechanics across four domains:
- **Physiology**: How bodies work (sleep, fatigue, hunger, thirst)
- **Temporal**: How long things take (activity durations, travel times)
- **Social**: How people interact (conversations, relationships, trust)
- **Physical**: How the world behaves (weather, objects, environment)

#### When Validation is Required

**During Planning Mode** (MANDATORY):
- Proposing new game mechanics (needs, combat, crafting, etc.)
- Modifying existing mechanics that affect player experience
- Designing NPC behavior systems
- Any feature touching physiology, time, social dynamics, or physics

**During Implementation** (Recommended):
- When writing code that implements game mechanics
- When tests reveal unexpected behavior

#### Validation Process

1. **Identify domains**: Which of the 4 domains does this mechanic touch?
2. **Invoke `realism-validator`**: For cross-domain quick check
3. **Invoke domain-specific validators**: For deep review on complex mechanics
4. **Address issues**: Fix any unrealistic abstractions before presenting plan

#### Common Realism Mistakes to Avoid

| Mistake | Reality |
|---------|---------|
| Merging distinct needs (e.g., "energy" for both sleep and stamina) | Sleep and stamina are separate systems with different recovery mechanisms |
| Fixed durations (e.g., "sleep always takes 8 hours") | Duration depends on fatigue level, conditions, interruptions |
| Instant relationships (e.g., "one quest = trusted ally") | Trust builds gradually through multiple interactions |
| Ignoring environment (e.g., "rain has no effect") | Weather affects comfort, speed, visibility, equipment |

---

## Project Overview

An agentic console-based RPG using a quantum branching pipeline for turn processing. The game features:
- **Quantum Pipeline**: Pre-generates outcome branches, rolls dice at runtime
- **Dual-Model Separation**: qwen3 for reasoning, magmell for narration
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

## Project Statistics

| Category | Count |
|----------|-------|
| **Test Functions** | ~2,200 across ~100 test files |
| **Manager Classes** | 53 specialized managers in `src/managers/` |
| **Quantum Pipeline** | Single pipeline in `src/world_server/quantum/` |
| **Database Models** | 28 model files in `src/database/models/` |
| **CLI Commands** | 5 command modules in `src/cli/commands/` |

*Update these counts when adding significant new components.*

## Database Access

**Before any database work, read `.claude/docs/database-reference.md`** for connection details and table schemas.

Quick connect (from `.env`):
```bash
PGPASSWORD=bRXAKO0T8t23Wz3l9tyB psql -h 138.199.236.25 -U langgraphrpg -d langgraphrpg
```

**Always run `\dt` and `\d table_name` first** - never guess table/column names.

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

- `docs/architecture.md` - System architecture (quantum pipeline)
- `docs/implementation-plan.md` - Implementation checklist
- `.claude/docs/coding-standards.md` - Code style guide
- `.claude/docs/agent-prompts.md` - LLM prompt templates
- `.claude/docs/database-conventions.md` - DB patterns
- `.claude/docs/database-reference.md` - **DB connection, tables, common queries** (READ FIRST for DB work)
- `.claude/docs/gameplay-testing-guide.md` - How to observe/debug gameplay
- `.claude/docs/realism-principles.md` - **Realism validation principles** (READ for game mechanics)

## Core Patterns

### Manager Pattern
Each domain has a dedicated manager class:
```python
class EntityManager(BaseManager):
    def get_entity(self, key: str) -> Entity | None
    def create_entity(self, **data) -> Entity
```

### Quantum Pipeline
The unified turn processing pipeline with dual-model separation:
```python
# Turn processing flow
pipeline = QuantumPipeline(db, game_session)

# Process turn - predicts actions, generates branches, rolls dice
result = await pipeline.process_turn(
    player_input="pick up the sword",
    location_key="village_tavern",
    turn_number=5,
)

# Dual-model separation:
# - Reasoning (qwen3): Logic, predictions, tool decisions
# - Narrator (magmell): Prose generation, narrative output
```

### Grounding Pattern
Entities are validated against the scene manifest before narration:
```python
# GMContextBuilder creates scene context
context = GMContextBuilder(db, game_session).build_context(location_key)

# GroundingManifest validates entity references
manifest = GroundingManifest(entities, items, locations)
validated = manifest.validate_references(narrative)
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
├── test_database/test_models/     # Model tests
├── test_managers/                 # Manager tests
└── test_integration/              # Integration tests
```

### Commands
```bash
# Run all tests (3372 tests, ~2.5 minutes)
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

**CRITICAL**: Documentation MUST be updated in the **SAME COMMIT** as code changes. This is not optional - undocumented changes create technical debt.

### The /commit Command (RECOMMENDED)

Use the `/commit` slash command to automatically handle documentation. It will:
1. Analyze your code changes
2. Add appropriate CHANGELOG.md entries
3. Update implementation-plan.md for new features
4. Update architecture.md for new patterns
5. Stage documentation and code together
6. Create a properly formatted commit

This ensures documentation is never forgotten.

### Manual Documentation Checklist

If not using `/commit`, update these files manually:

| Commit Type | CHANGELOG.md | implementation-plan.md | architecture.md |
|-------------|--------------|------------------------|-----------------|
| `feat:` | ✓ Add to `### Added` | ✓ Add new items | ✓ If new pattern |
| `fix:` | ✓ Add to `### Fixed` | - | - |
| `refactor:` | Optional `### Changed` | - | ✓ If pattern changes |
| `docs:` | - | - | - |
| `test:` | - | - | - |

### Documentation Quality Standards

1. **Be specific**: "Add SnapshotManager for session state capture" not "Add new manager"
2. **Include file paths**: Reference key files in changelog entries
3. **Update counts**: Keep Project Statistics section current
4. **Add docstrings**: All public methods need Google-style docstrings

### Key Documentation Files:
| File | Update When |
|------|-------------|
| `CHANGELOG.md` | **Every feat/fix** - Entry under [Unreleased] |
| `docs/implementation-plan.md` | New features, phases, test count changes |
| `docs/architecture.md` | New managers, agents, pipelines, patterns |
| `CLAUDE.md` | New conventions, updated statistics |
| `docs/user-guide.md` | New CLI commands, user-facing features |

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

---

## SoCal English Feedback

The user is a native German speaker learning American English (SoCal dialect, including slang).

**After every response**, review the user's input text for naturalness:

1. **Assess as real conversation**: Compare to how people actually talk in professional settings - coworkers in an office, freelancers collaborating, etc. NOT adjusted for CLI/chat brevity.
2. **Always give feedback**: If natural, add "✓ English sounds natural". If issues found, list them.
3. **Be specific**: Quote the exact phrase that sounds off
4. **Provide the natural alternative**: How a SoCal native would actually say it
5. **Include slang when appropriate**: Casual speech, contractions, common expressions
6. **Placement**: Always at the END of your response, after completing the main task

**Format**:
```
---
**SoCal English Check:**
- "your phrase" → "native phrasing" - brief explanation

✓ Rest sounds natural
```

Or if everything is natural:
```
---
✓ English sounds natural
```

### Examples
| You wrote | Native would say | Why |
|-----------|------------------|-----|
| "proceed implementing" | "go ahead and implement" | Need "with" after "proceed", or rephrase |
| "Does this diminish the quality" | "Does this hurt the quality" | "diminish" is formal; "hurt" is everyday |
| "Provide me feedback" | "Give me feedback" | "Provide" sounds formal; "give" is casual |
