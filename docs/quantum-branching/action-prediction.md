# Action Prediction

The `ActionPredictor` component analyzes scene context to predict likely player actions before they happen.

## Overview

Action prediction enables proactive branch generation by identifying what players are likely to do based on:
- Scene contents (NPCs, items, exits)
- Recent player behavior patterns
- Game state and narrative context

## ActionPrediction Schema

```python
@dataclass
class ActionPrediction:
    action_type: ActionType      # What kind of action
    target_key: str | None       # Target entity key
    input_patterns: list[str]    # Regex patterns to match
    probability: float           # Likelihood (0.0 - 1.0)
    reason: PredictionReason     # Why we predicted this
```

### Action Types

```python
class ActionType(Enum):
    INTERACT_NPC = "interact_npc"      # Talk to, ask, greet
    MANIPULATE_ITEM = "manipulate_item" # Take, use, examine
    MOVE = "move"                       # Go, walk, travel
    OBSERVE = "observe"                 # Look, examine area
    DIALOGUE = "dialogue"               # Specific conversation
    COMBAT = "combat"                   # Attack, fight
    SKILL_USE = "skill_use"             # Use specific skill
```

### Prediction Reasons

```python
class PredictionReason(Enum):
    NPC_LOCATION = "npc_location"           # NPC is present
    NPC_FOCUS = "npc_focus"                 # NPC is scene focus
    ITEM_VISIBLE = "item_visible"           # Item is visible
    ITEM_INTERACTABLE = "item_interactable" # Item can be used
    EXIT_AVAILABLE = "exit_available"       # Exit exists
    RECENT_TOPIC = "recent_topic"           # Continues conversation
    QUEST_OBJECTIVE = "quest_objective"     # Related to quest
    ALWAYS_AVAILABLE = "always_available"   # Generic action
```

## Prediction Algorithm

### 1. NPC Interactions

For each NPC in the scene:

```python
for npc in manifest.npcs.values():
    # Base probability based on presence
    prob = 0.15

    # Boost if NPC is scene focus
    if npc.is_focus:
        prob = 0.35

    # Boost if recent conversation
    if npc.entity_key in recent_conversation_targets:
        prob += 0.10

    # Boost if quest-related
    if self._is_quest_target(npc, game_session):
        prob += 0.15

    predictions.append(ActionPrediction(
        action_type=ActionType.INTERACT_NPC,
        target_key=npc.entity_key,
        input_patterns=self._npc_patterns(npc),
        probability=min(prob, 0.95),
        reason=PredictionReason.NPC_FOCUS if npc.is_focus else PredictionReason.NPC_LOCATION,
    ))
```

### 2. Item Manipulations

For each visible item:

```python
for item in manifest.items_at_location.values():
    prob = 0.10

    # Boost for interactable items
    if item.is_interactable:
        prob = 0.20

    # Boost for quest items
    if self._is_quest_item(item, game_session):
        prob += 0.25

    # Reduce for mundane items
    if item.is_mundane:
        prob *= 0.5

    predictions.append(ActionPrediction(
        action_type=ActionType.MANIPULATE_ITEM,
        target_key=item.entity_key,
        input_patterns=self._item_patterns(item),
        probability=prob,
        reason=PredictionReason.ITEM_VISIBLE,
    ))
```

### 3. Movement

For each exit:

```python
for exit in manifest.exits.values():
    prob = 0.15

    # Boost if destination is quest-related
    if self._is_quest_destination(exit.location_key, game_session):
        prob = 0.30

    # Boost if player just arrived (exploration)
    if game_session.turns_at_location < 2:
        prob += 0.10

    predictions.append(ActionPrediction(
        action_type=ActionType.MOVE,
        target_key=exit.location_key,
        input_patterns=self._exit_patterns(exit),
        probability=prob,
        reason=PredictionReason.EXIT_AVAILABLE,
    ))
```

### 4. Observation

Always predict observation:

```python
predictions.append(ActionPrediction(
    action_type=ActionType.OBSERVE,
    target_key=None,
    input_patterns=["look", "examine", "observe", "inspect"],
    probability=0.15,
    reason=PredictionReason.ALWAYS_AVAILABLE,
))
```

## Input Pattern Generation

Patterns are generated based on entity names and common verbs:

### NPC Patterns

```python
def _npc_patterns(self, npc: NPCManifestEntry) -> list[str]:
    name = npc.display_name.lower()
    patterns = [
        f"talk.*{name}",
        f"speak.*{name}",
        f"ask.*{name}",
        f"greet.*{name}",
        f"{name}",  # Just the name
    ]
    # Add title patterns if applicable
    if npc.title:
        title = npc.title.lower()
        patterns.extend([f"talk.*{title}", f"ask.*{title}"])
    return patterns
```

### Item Patterns

```python
def _item_patterns(self, item: ItemManifestEntry) -> list[str]:
    name = item.display_name.lower()
    return [
        f"take.*{name}",
        f"grab.*{name}",
        f"pick.*{name}",
        f"examine.*{name}",
        f"use.*{name}",
        f"{name}",
    ]
```

### Exit Patterns

```python
def _exit_patterns(self, exit: ExitManifestEntry) -> list[str]:
    patterns = [
        f"go.*{exit.direction}",
        f"walk.*{exit.direction}",
        f"leave.*{exit.direction}",
        f"exit.*{exit.direction}",
    ]
    if exit.display_name:
        name = exit.display_name.lower()
        patterns.extend([f"go.*{name}", f"enter.*{name}"])
    return patterns
```

## Probability Calibration

### Base Probabilities

| Action Type | Base Probability | Notes |
|-------------|-----------------|-------|
| NPC (focus) | 0.35 | Main scene character |
| NPC (regular) | 0.15 | Background NPCs |
| Item (interactable) | 0.20 | Can be used/taken |
| Item (mundane) | 0.05 | Scenery items |
| Exit | 0.15 | Available exits |
| Observe | 0.15 | Always available |

### Boost Factors

| Condition | Boost | Max Total |
|-----------|-------|-----------|
| Quest target | +0.15 to +0.25 | 0.95 |
| Recent conversation | +0.10 | 0.95 |
| Scene focus | +0.20 | 0.95 |
| Player exploring | +0.10 | 0.95 |

## Recent Turn Analysis

The predictor analyzes recent turns to improve predictions:

```python
def _analyze_recent_turns(
    self,
    recent_turns: list[Turn],
    predictions: list[ActionPrediction],
) -> list[ActionPrediction]:
    # Identify conversation threads
    active_npc = self._get_active_conversation_npc(recent_turns)
    if active_npc:
        # Boost continuing conversation
        for pred in predictions:
            if pred.target_key == active_npc:
                pred.probability += 0.15
                pred.probability = min(pred.probability, 0.95)

    # Identify exploration patterns
    if self._is_exploring(recent_turns):
        for pred in predictions:
            if pred.action_type == ActionType.MOVE:
                pred.probability += 0.05

    return predictions
```

## Prediction Limits

To avoid overwhelming the cache:

```python
# In QuantumPipeline
predictions = await self.action_predictor.predict_actions(
    location_key, manifest, recent_turns
)

# Only generate branches for top N predictions
top_predictions = sorted(
    predictions,
    key=lambda p: p.probability,
    reverse=True
)[:config.max_actions_per_cycle]  # Default: 5
```

## Testing Predictions

```python
def test_predicts_npc_interaction(db_session, game_session):
    """Test that NPC in scene generates interaction prediction."""
    # Create scene with bartender
    location = create_location(db_session, game_session, "tavern")
    npc = create_entity(db_session, game_session, "bartender_001",
                        entity_type=EntityType.NPC, location=location)

    manifest = build_manifest(db_session, game_session, location)
    predictor = ActionPredictor(db_session, game_session)

    predictions = predictor.predict_actions(location.location_key, manifest, [])

    # Should predict talking to bartender
    npc_predictions = [p for p in predictions if p.action_type == ActionType.INTERACT_NPC]
    assert any(p.target_key == "bartender_001" for p in npc_predictions)
```

## Performance Considerations

- Prediction is synchronous and fast (<10ms typically)
- Patterns are pre-compiled for efficiency
- Recent turn analysis is limited to last 5 turns
- Predictions are sorted once and cached
