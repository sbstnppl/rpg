# API Reference

This document provides a reference for the public APIs in the RPG game system.

## Overview

The system is organized into these main components:

- **Managers** - Business logic for game state management
- **LLM Module** - Language model provider abstraction
- **Dice Module** - Dice rolling and check mechanics
- **Agents** - LangGraph agent nodes for game orchestration

---

## Managers

All managers inherit from `BaseManager` and require a database session and game session.

### Initialization Pattern

```python
from src.managers.entity_manager import EntityManager

manager = EntityManager(db_session, game_session)
```

### EntityManager

`src/managers/entity_manager.py`

Manages entities (players, NPCs, monsters).

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_entity(key)` | `key: str` | `Entity \| None` | Get entity by key |
| `create_entity(**kwargs)` | `entity_key, display_name, entity_type, ...` | `Entity` | Create new entity |
| `update_attribute(key, attr, value)` | `key: str, attr: str, value: int` | `EntityAttribute` | Update attribute value |
| `get_entities_at_location(location)` | `location: str` | `list[Entity]` | Get entities at location |
| `get_player()` | - | `Entity \| None` | Get player entity |
| `get_npcs_in_scene(location)` | `location: str` | `list[Entity]` | Get NPCs at location |
| `get_active_entities()` | - | `list[Entity]` | Get alive and active entities |

### ItemManager

`src/managers/item_manager.py`

Manages items, inventory, and equipment.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_item(key)` | `key: str` | `Item \| None` | Get item by key |
| `create_item(**kwargs)` | `item_key, display_name, item_type, ...` | `Item` | Create new item |
| `get_inventory(entity_id)` | `entity_id: int` | `list[Item]` | Get items held by entity |
| `get_owned_items(entity_id)` | `entity_id: int` | `list[Item]` | Get items owned by entity |
| `transfer_item(key, to_entity_id)` | `key: str, to_entity_id: int` | `Item` | Transfer item to entity |
| `equip_item(key, entity_id, body_slot, body_layer)` | Various | `Item` | Equip item to body slot |
| `unequip_item(key)` | `key: str` | `Item` | Remove from body slot |
| `get_equipped_items(entity_id)` | `entity_id: int` | `list[Item]` | Get equipped items |
| `get_visible_equipment(entity_id)` | `entity_id: int` | `list[Item]` | Get visible (outermost) items |
| `update_visibility(entity_id)` | `entity_id: int` | `None` | Recalculate layer visibility |
| `get_items_at_location(location)` | `location: str` | `list[Item]` | Get items at world location |
| `set_item_condition(key, condition)` | `key: str, condition: ItemCondition` | `Item` | Update item condition |
| `damage_item(key, amount)` | `key: str, amount: int` | `Item` | Reduce durability |

### RelationshipManager

`src/managers/relationship_manager.py`

Manages relationships between entities.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_relationship(from_id, to_id)` | `from_id: int, to_id: int` | `Relationship \| None` | Get relationship |
| `get_or_create_relationship(from_id, to_id)` | `from_id: int, to_id: int` | `Relationship` | Get or create relationship |
| `get_attitude(from_id, to_id)` | `from_id: int, to_id: int` | `dict` | Get attitude dimensions |
| `update_attitude(from_id, to_id, dimension, delta, reason)` | Various | `RelationshipChange` | Modify attitude |
| `record_meeting(entity1_id, entity2_id)` | `entity1_id: int, entity2_id: int` | `None` | Record first meeting |
| `get_relationship_history(from_id, to_id)` | `from_id: int, to_id: int` | `list[RelationshipChange]` | Get change history |

### LocationManager

`src/managers/location_manager.py`

Manages world locations.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_location(key)` | `key: str` | `Location \| None` | Get location by key |
| `create_location(**kwargs)` | `location_key, display_name, ...` | `Location` | Create new location |
| `get_sublocations(parent_key)` | `parent_key: str` | `list[Location]` | Get child locations |
| `get_entities_at_location(key)` | `key: str` | `list[Entity]` | Get entities at location |
| `set_player_location(location_key)` | `location_key: str` | `None` | Update player position |

### FactManager

`src/managers/fact_manager.py`

Manages world facts using Subject-Predicate-Value pattern.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `record_fact(subject_type, subject_key, predicate, value)` | Various | `Fact` | Record new fact |
| `get_facts_about(subject_key)` | `subject_key: str` | `list[Fact]` | Get facts about subject |
| `get_facts_by_predicate(predicate)` | `predicate: str` | `list[Fact]` | Get facts by predicate |
| `get_facts_by_category(category)` | `category: str` | `list[Fact]` | Get facts by category |
| `get_secrets()` | - | `list[Fact]` | Get GM-only facts |
| `get_player_known_facts()` | - | `list[Fact]` | Get non-secret facts |
| `update_certainty(fact_id, certainty)` | `fact_id: int, certainty: float` | `Fact` | Update certainty |
| `contradict_fact(fact_id, new_value, reason)` | Various | `Fact` | Mark fact as contradicted |

### ScheduleManager

`src/managers/schedule_manager.py`

Manages NPC schedules.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_schedule(entity_id)` | `entity_id: int` | `list[Schedule]` | Get entity's schedule |
| `set_schedule_entry(entity_id, day, time, location, activity)` | Various | `Schedule` | Set schedule entry |
| `get_activity_at_time(entity_id, day, time)` | Various | `Schedule \| None` | Get activity at time |
| `get_npcs_at_location_time(location, day, time)` | Various | `list[Entity]` | NPCs at location/time |
| `clear_schedule(entity_id)` | `entity_id: int` | `None` | Clear all schedule entries |
| `copy_schedule(from_id, to_id)` | `from_id: int, to_id: int` | `None` | Copy schedule |

### TimeManager

`src/managers/time_manager.py`

Manages game time.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_current_time()` | - | `TimeState` | Get current time state |
| `advance_time(minutes)` | `minutes: int` | `TimeState` | Advance time |
| `set_weather(weather)` | `weather: str` | `TimeState` | Set current weather |
| `get_day_of_week()` | - | `str` | Get day name |

### EventManager

`src/managers/event_manager.py`

Manages world events.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `create_event(type, summary, details)` | Various | `WorldEvent` | Create event |
| `get_unprocessed_events()` | - | `list[WorldEvent]` | Get pending events |
| `mark_processed(event_id)` | `event_id: int` | `None` | Mark event processed |
| `get_events_at_location(location)` | `location: str` | `list[WorldEvent]` | Events at location |
| `get_events_involving(entity_id)` | `entity_id: int` | `list[WorldEvent]` | Events involving entity |
| `get_recent_events(limit)` | `limit: int` | `list[WorldEvent]` | Get recent events |

### TaskManager

`src/managers/task_manager.py`

Manages tasks, quests, and appointments.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `create_task(description, category, **kwargs)` | Various | `Task` | Create task |
| `complete_task(task_id)` | `task_id: int` | `Task` | Mark task complete |
| `fail_task(task_id, reason)` | `task_id: int, reason: str` | `Task` | Mark task failed |
| `get_active_tasks()` | - | `list[Task]` | Get active tasks |
| `get_appointments_for_day(day)` | `day: int` | `list[Appointment]` | Appointments on day |
| `check_missed_appointments()` | - | `list[Appointment]` | Check for missed appointments |

### NeedsManager

`src/managers/needs.py`

Manages character needs (hunger, fatigue, etc.).

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_needs_state(entity_id)` | `entity_id: int` | `CharacterNeeds \| None` | Get needs state |
| `apply_time_decay(entity_id, minutes)` | `entity_id: int, minutes: int` | `CharacterNeeds` | Apply time-based decay |
| `modify_need(entity_id, need, amount)` | Various | `CharacterNeeds` | Modify specific need |
| `get_active_effects(entity_id)` | `entity_id: int` | `list[dict]` | Get stat penalties |
| `get_npc_urgency(entity_id)` | `entity_id: int` | `str \| None` | Get urgent need |

### InjuryManager

`src/managers/injuries.py`

Manages injuries and body damage.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `add_injury(entity_id, body_part, severity, description)` | Various | `BodyInjury` | Add injury |
| `get_injuries(entity_id)` | `entity_id: int` | `list[BodyInjury]` | Get all injuries |
| `get_activity_impact(entity_id, activity)` | Various | `dict` | Get activity penalties |
| `apply_healing(injury_id, amount)` | `injury_id: int, amount: int` | `BodyInjury` | Apply healing |
| `sync_pain_to_needs(entity_id)` | `entity_id: int` | `None` | Sync pain to needs |

### DeathManager

`src/managers/death.py`

Manages death and revival mechanics.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `take_damage(entity_id, damage, damage_type)` | Various | `EntityVitalState` | Apply damage |
| `make_death_save(entity_id)` | `entity_id: int` | `tuple[bool, int]` | Roll death save |
| `attempt_revival(entity_id)` | `entity_id: int` | `bool` | Attempt revival |

### GriefManager

`src/managers/grief.py`

Manages grief states based on Kubler-Ross model.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `trigger_grief(entity_id, deceased_id)` | `entity_id: int, deceased_id: int` | `GriefCondition` | Start grief |
| `advance_grief_stage(entity_id)` | `entity_id: int` | `GriefCondition` | Advance to next stage |
| `get_grief_state(entity_id)` | `entity_id: int` | `GriefCondition \| None` | Get current grief |

### CombatManager

`src/managers/combat_manager.py`

Manages combat state and resolution.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `initialize_combat(combatants)` | `combatants: list[Combatant]` | `CombatState` | Start combat |
| `roll_initiatives(combat_state)` | `combat_state: CombatState` | `CombatState` | Roll all initiatives |
| `resolve_attack(attacker, target, weapon)` | Various | `AttackResult` | Resolve attack |
| `apply_damage(target, damage)` | Various | `Combatant` | Apply damage |
| `advance_turn(combat_state)` | `combat_state: CombatState` | `CombatState` | Next turn |

### ContextCompiler

`src/managers/context_compiler.py`

Aggregates world state for GM prompt.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `compile_scene(npcs, location)` | `npcs: list[Entity], location: str` | `str` | Compile scene context |

### ConsistencyValidator

`src/managers/consistency.py`

Validates world state consistency.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `check_possession(item_key, entity_id)` | Various | `bool` | Verify possession |
| `check_spatial(entity_id, location)` | Various | `bool` | Verify location |
| `check_temporal(event_time)` | `event_time: datetime` | `bool` | Verify timeline |

---

## LLM Module

`src/llm/`

### Provider Protocol

```python
from src.llm import LLMProvider

class LLMProvider(Protocol):
    provider_name: str
    default_model: str

    def complete(
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: str | None = None,
    ) -> LLMResponse

    def complete_with_tools(
        messages: list[Message],
        tools: list[ToolDefinition],
        **kwargs
    ) -> LLMResponse

    def complete_structured(
        messages: list[Message],
        output_schema: type[T],
        **kwargs
    ) -> T
```

### Factory Functions

```python
from src.llm import get_provider, get_cheap_provider

# Get specific provider
provider = get_provider("anthropic")

# Get cost-effective provider for extraction
cheap = get_cheap_provider()
```

| Function | Returns | Description |
|----------|---------|-------------|
| `get_provider(name)` | `LLMProvider` | Get provider by name |
| `get_gm_provider()` | `LLMProvider` | Get provider for GM responses |
| `get_extraction_provider()` | `LLMProvider` | Get provider for entity extraction |
| `get_cheap_provider()` | `LLMProvider` | Get cost-effective provider |

### Message Types

```python
from src.llm import Message, MessageRole

message = Message(
    role=MessageRole.USER,
    content="Hello, world!"
)
```

| Type | Fields | Description |
|------|--------|-------------|
| `Message` | `role: MessageRole, content: str` | Chat message |
| `MessageRole` | `USER, ASSISTANT, SYSTEM, TOOL` | Message roles |
| `LLMResponse` | `content: str, tool_calls: list, usage: UsageStats` | Response |
| `ToolCall` | `id: str, name: str, arguments: dict` | Tool invocation |
| `UsageStats` | `prompt_tokens: int, completion_tokens: int` | Token usage |

### Exceptions

| Exception | Description |
|-----------|-------------|
| `LLMError` | Base exception |
| `RateLimitError` | Rate limit exceeded |
| `AuthenticationError` | Invalid API key |
| `InvalidRequestError` | Malformed request |
| `ServiceUnavailableError` | Provider unavailable |

---

## Dice Module

`src/dice/`

### Core Functions

```python
from src.dice import roll, parse_dice, make_skill_check

# Roll dice
result = roll("2d6+3")
print(result.total)  # e.g., 11

# Skill check
check = make_skill_check(
    modifier=5,
    dc=15,
    advantage=AdvantageType.ADVANTAGE
)
print(check.success)  # True or False
```

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `roll(expression)` | `expression: str` | `RollResult` | Roll dice expression |
| `parse_dice(expression)` | `expression: str` | `DiceExpression` | Parse notation |
| `roll_dice(expression)` | `expression: DiceExpression` | `RollResult` | Roll parsed expression |
| `roll_with_advantage(expression, advantage)` | Various | `RollResult` | Roll with advantage |

### Skill Checks

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `calculate_ability_modifier(score)` | `score: int` | `int` | D&D-style modifier |
| `make_skill_check(modifier, dc, advantage)` | Various | `SkillCheckResult` | Skill check |
| `make_saving_throw(modifier, dc)` | Various | `SkillCheckResult` | Saving throw |

### Combat

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `make_attack_roll(attack_bonus, target_ac)` | Various | `AttackRollResult` | Attack roll |
| `roll_damage(expression, is_critical)` | Various | `DamageRollResult` | Damage roll |
| `roll_initiative(modifier)` | `modifier: int` | `int` | Initiative roll |

### Types

| Type | Fields | Description |
|------|--------|-------------|
| `DiceExpression` | `count: int, sides: int, modifier: int` | Parsed expression |
| `RollResult` | `total: int, dice: list[int], modifier: int` | Roll result |
| `SkillCheckResult` | `success: bool, margin: int, is_critical: bool` | Check result |
| `AttackRollResult` | `hits: bool, is_critical: bool, roll: int` | Attack result |
| `AdvantageType` | `NONE, ADVANTAGE, DISADVANTAGE` | Advantage enum |

### DC Constants

```python
from src.dice import DC_EASY, DC_MODERATE, DC_HARD

DC_TRIVIAL = 5
DC_EASY = 10
DC_MODERATE = 15
DC_HARD = 20
DC_VERY_HARD = 25
DC_LEGENDARY = 30
```

---

## Agent Nodes

`src/agents/nodes/`

### Game State

```python
from src.agents.state import GameState, create_initial_state

state = create_initial_state(
    session_id=1,
    player_id=1,
    player_location="tavern",
    player_input="I look around",
    turn_number=1,
)
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `int` | Game session ID |
| `player_id` | `int` | Player entity ID |
| `player_input` | `str` | Current player action |
| `player_location` | `str` | Current location key |
| `turn_number` | `int` | Current turn |
| `gm_response` | `str \| None` | GM narrative response |
| `scene_context` | `str` | Compiled context |
| `next_agent` | `str` | Next node to execute |
| `combat_active` | `bool` | Combat state flag |
| `time_advance_minutes` | `int` | Time to advance |
| `location_changed` | `bool` | Location change flag |
| `extracted_entities` | `list[dict]` | Extracted entities |
| `extracted_facts` | `list[dict]` | Extracted facts |
| `errors` | `list[str]` | Error messages |

### Agent Nodes

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| `context_compiler_node` | State with location | `scene_context` | Compiles scene |
| `game_master_node` | State with context | `gm_response`, routing | Generates narrative |
| `entity_extractor_node` | State with response | `extracted_*` lists | Extracts state changes |
| `combat_resolver_node` | State with combat | Combat resolution | Resolves combat |
| `world_simulator_node` | State with time | World updates | Simulates world |
| `persistence_node` | State with extractions | Database writes | Persists changes |

### Graph

```python
from src.agents.graph import build_game_graph

graph = build_game_graph()
compiled = graph.compile()

result = await compiled.ainvoke(initial_state)
```

---

## CLI Display

`src/cli/display.py`

### Display Functions

| Function | Parameters | Description |
|----------|------------|-------------|
| `display_narrative(text)` | `text: str` | Display GM narrative in panel |
| `display_character_status(name, stats, needs, conditions)` | Various | Character status tables |
| `display_inventory(items)` | `items: list[dict]` | Inventory table |
| `display_equipment(slots)` | `slots: dict` | Equipment by slot |
| `display_error(message)` | `message: str` | Red error message |
| `display_success(message)` | `message: str` | Green success message |
| `display_info(message)` | `message: str` | Dim info message |

### Progress Indicators

```python
from src.cli.display import progress_spinner, progress_bar

# Spinner for unknown duration
with progress_spinner("Processing..."):
    await long_operation()

# Bar for known steps
with progress_bar("Loading", total=100) as (progress, task):
    for i in range(100):
        progress.advance(task)
```

---

## Settings Schema

`src/schemas/settings.py`

### SettingSchema

```python
from src.schemas.settings import get_setting_schema, SettingSchema

schema = get_setting_schema("fantasy")
print(schema.name)  # "fantasy"
print(schema.attributes)  # List of AttributeDefinition
print(schema.starting_equipment)  # List of StartingItem
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Setting name |
| `description` | `str` | Setting description |
| `attributes` | `list[AttributeDefinition]` | Character attributes |
| `point_buy_total` | `int` | Point-buy budget |
| `equipment_slots` | `list[EquipmentSlot]` | Available slots |
| `starting_equipment` | `list[StartingItem]` | Starting items |

### StartingItem

| Field | Type | Description |
|-------|------|-------------|
| `item_key` | `str` | Unique item key |
| `display_name` | `str` | Display name |
| `item_type` | `str` | ItemType enum value |
| `body_slot` | `str \| None` | Equip slot |
| `body_layer` | `int` | Layer (0=innermost) |
| `description` | `str` | Item description |
| `properties` | `dict \| None` | Custom properties |
