# RPG Architecture

## Overview

The RPG uses a LangGraph-based multi-agent architecture where specialized agents handle different aspects of the game.

## Agent Architecture

```
START → ContextCompiler → GameMaster (Supervisor)
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
       EntityExtractor  CombatResolver  WorldSimulator
              ↓               ↓               ↓
              └───────────────┼───────────────┘
                              ↓
                        Persistence → END
```

## Agents

### ContextCompiler
**Purpose**: Assembles relevant world state for GM prompts

**Responsibilities**:
- Query all managers for current scene information
- Filter by relevance (present NPCs, current location)
- Format into structured context string
- Include secrets (GM-only information)

**Output**: Compiled context including:
- Scene overview (time, location, weather)
- NPC appearances and current activities
- Relationship attitudes
- Active tasks/appointments
- Recent events

### GameMaster (Supervisor)
**Purpose**: Primary narrative agent controlling story flow

**Responsibilities**:
- Generate narrative responses
- Maintain consistent NPC voices
- Route to specialized agents when needed
- Apply game rules

**Routes To**:
- `EntityExtractor`: After every response
- `CombatResolver`: When combat initiates
- `WorldSimulator`: When location changes or time passes

### EntityExtractor
**Purpose**: Parse GM responses to extract state changes

**Extracts**:
- New characters mentioned
- Items acquired/lost
- Facts revealed
- Relationship changes
- Appointments made
- Location changes

### CombatResolver
**Purpose**: Handle tactical combat

**Mechanics**:
- Initiative rolls
- Attack/defense resolution
- Damage calculation
- Status effects
- Loot generation

### WorldSimulator
**Purpose**: Background world updates

**Triggers**:
- Player moves to new location
- Significant time passes (30+ min)
- Periodic random event checks

**Actions**:
- Update NPC positions from schedules
- Check for missed appointments
- Generate random events
- Update weather

## Data Flow

```
Player Input
    ↓
ContextCompiler (gathers state)
    ↓
GameMaster (generates response)
    ↓
EntityExtractor (parses changes)
    ↓
Persistence Layer (saves to DB)
    ↓
Response to Player
```

## Database Architecture

### Session Layer
- `game_sessions`: Session metadata, settings
- `turns`: Immutable turn history

### Entity Layer
- `entities`: Characters (player, NPCs, monsters)
- `entity_attributes`: Flexible attribute storage
- `entity_skills`: Skills with proficiency

### World Layer
- `locations`: Places with hierarchy
- `schedules`: NPC routines
- `time_states`: Game clock
- `facts`: SPV fact store
- `world_events`: Background events

### Relationship Layer
- `relationships`: Directional attitudes
- `relationship_changes`: Audit log

### Item Layer
- `items`: All objects
- `storage_locations`: Where items are

### Task Layer
- `tasks`: Player objectives
- `appointments`: Scheduled events
- `quests`: Multi-stage stories

## Manager Pattern

Each domain has a dedicated manager class:

```python
class EntityManager:
    def get_entity(key: str) -> Entity
    def create_entity(**data) -> Entity
    def update_attribute(key: str, attr: str, value: int)
    def get_entities_at_location(location: str) -> list[Entity]

class ItemManager:
    def get_item(key: str) -> Item
    def transfer_item(item: Item, to: Entity)
    def equip_item(entity: Entity, item: Item, slot: str)
    def get_visible_equipment(entity: Entity) -> list[Item]

class RelationshipManager:
    def get_attitude(from: Entity, to: Entity) -> Relationship
    def update_attitude(from: Entity, to: Entity, dimension: str, delta: int)
    def record_meeting(entity1: Entity, entity2: Entity)

# ... etc
```

## LLM Provider Abstraction

Located in `src/llm/`, provides a unified interface for LLM providers.

### Protocol
```python
class LLMProvider(Protocol):
    provider_name: str
    default_model: str

    async def complete(messages, model, max_tokens, temperature, system_prompt) -> LLMResponse
    async def complete_with_tools(messages, tools, tool_choice, ...) -> LLMResponse
    async def complete_structured(messages, response_schema, ...) -> LLMResponse
    def count_tokens(text, model) -> int
```

### Providers
- **AnthropicProvider**: Claude models via `anthropic` SDK
- **OpenAIProvider**: GPT models + OpenAI-compatible APIs (DeepSeek, Ollama, vLLM) via configurable `base_url`

### Usage
```python
from src.llm import get_provider, Message, with_retry

# Default provider from settings
provider = get_provider()

# With retry for robustness
response = await with_retry(
    provider.complete,
    messages=[Message.user("Tell me about dragons")],
    max_tokens=500,
)

# OpenAI-compatible API (e.g., DeepSeek)
provider = get_provider("openai", model="deepseek-chat", base_url="https://api.deepseek.com")
```

### Key Types
- `Message`: Immutable message with factory methods (`.user()`, `.assistant()`, `.system()`)
- `LLMResponse`: Response with `content`, `tool_calls`, `usage` stats
- `ToolDefinition`: Tool/function definition with JSON schema conversion

## State Persistence

### Immutable Turn History
Every turn is recorded and never modified:
```python
class Turn:
    player_input: str
    gm_response: str
    entities_extracted: dict
    created_at: datetime
```

### Mutable Session Context
Current world state updated after each turn:
- NPC locations
- Item positions
- Relationship values
- Active tasks

### Checkpoints
Every N turns, create a summary:
- AI-generated narrative summary
- Current state snapshot
- Key events list
