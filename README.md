# RPG Game

An agentic console-based role-playing game using LangGraph for multi-agent orchestration.

## Features

- **LangGraph Multi-Agent System**: Specialized agents for narrative, combat, world simulation
- **Persistent World State**: PostgreSQL database with comprehensive state tracking
- **Flexible Character System**: Setting-dependent attributes (fantasy, contemporary, sci-fi)
- **Dice-Based Mechanics**: D&D-style combat and skill checks
- **Relationship Tracking**: Trust, liking, respect, romantic interest (0-100 scale)
- **NPC Schedules**: Rule-based routines with AI-driven dynamic events
- **Dual LLM Support**: Both Anthropic Claude and OpenAI GPT

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd rpg

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Create database
createdb rpg_game

# Run migrations
alembic upgrade head
```

## Quick Start

```bash
# Start a new game (interactive wizard)
rpg game start

# Continue playing (or start if no session exists)
rpg play
# Or: rpg game play

# List saved games
rpg game list

# Delete a game
rpg game delete <id>
```

## Configuration

Create a `.env` file with:

```
DATABASE_URL=postgresql://localhost/rpg_game
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
LLM_PROVIDER=anthropic
```

## Architecture

```
src/
├── agents/         # LangGraph agents (GameMaster, Combat, WorldSim)
├── database/       # SQLAlchemy models
├── managers/       # Business logic layer
├── llm/            # LLM provider abstraction
├── cli/            # Typer CLI
└── schemas/        # Setting configurations
```

## Documentation

- [Project Outline](docs/project-outline.md)
- [Architecture](docs/architecture.md)
- [User Guide](docs/user-guide.md)
- [Implementation Plan](docs/implementation-plan.md)

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src

# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## License

MIT
