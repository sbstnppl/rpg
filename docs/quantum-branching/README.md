# Quantum Branching World Server

A unified pipeline that pre-generates multiple outcome branches for predicted player actions, then selects the appropriate branch based on runtime dice rolls.

**Key Insight**: Dice rolls happen LIVE at runtime. We prepare for all possible outcomes in advance - like a tabletop GM who thinks ahead about what might happen.

## Overview

The Quantum Branching architecture replaces traditional sequential turn processing with a predictive, cache-first approach:

```
Traditional Pipeline:
Player Input → Parse → GM Decision → Narrate → Display (50-80 seconds)

Quantum Pipeline (Cache Hit):
Player Input → Match → Select Branch → Roll Dice → Display (<100ms)
```

## Quick Start

### Enable Quantum Pipeline

The quantum pipeline is now the default. To play a game:

```bash
# Start a new game (quantum is default)
python -m src.main game play <session_id>

# Explicitly use quantum pipeline
python -m src.main game play <session_id> --pipeline quantum

# Enable background anticipation (pre-generates branches)
python -m src.main game play <session_id> --anticipation
```

### Configuration

In `.env` or environment:

```bash
# Enable anticipation by default
QUANTUM_ANTICIPATION_ENABLED=true

# Number of top actions to pre-generate per cycle
QUANTUM_MAX_ACTIONS_PER_CYCLE=5

# Number of GM decisions to pre-generate per action
QUANTUM_MAX_GM_DECISIONS=2

# Delay between anticipation cycles (seconds)
QUANTUM_CYCLE_DELAY=0.5

# Minimum confidence for cache match (0.0 - 1.0)
QUANTUM_MIN_MATCH_CONFIDENCE=0.7
```

## How It Works

### 1. Action Prediction

When a player enters a scene, the `ActionPredictor` analyzes the scene manifest to predict likely actions:

```python
# Predicted actions for a tavern scene
[
    ActionPrediction(type=INTERACT_NPC, target="bartender_001", probability=0.35),
    ActionPrediction(type=MANIPULATE_ITEM, target="ale_mug_001", probability=0.25),
    ActionPrediction(type=MOVE, target="tavern_exit_north", probability=0.20),
    ActionPrediction(type=OBSERVE, target=None, probability=0.20),
]
```

### 2. Branch Generation

For each predicted action, the `BranchGenerator` creates multiple outcome variants:

```python
QuantumBranch(
    action="talk to bartender",
    gm_decision="no_twist",
    variants={
        "success": OutcomeVariant(narrative="The bartender smiles warmly..."),
        "failure": OutcomeVariant(narrative="The bartender ignores you..."),
        "critical_success": OutcomeVariant(narrative="The bartender recognizes you..."),
    }
)
```

### 3. Runtime Collapse

When the player acts:

1. **Match**: `ActionMatcher` finds the best matching cached branch
2. **Roll**: Dice are rolled LIVE to determine success/failure
3. **Select**: The appropriate variant is chosen based on the roll
4. **Apply**: State deltas are applied atomically
5. **Display**: Narrative is shown to the player

```
Player: "Ask the bartender about rumors"
→ Matched: INTERACT_NPC(bartender_001) [confidence: 0.92]
→ Roll: 2d10 = 15 vs DC 12 (Charisma)
→ Result: SUCCESS
→ Display: "The bartender leans in conspiratorially..."
→ Latency: 47ms (cache hit)
```

## Architecture

```
src/world_server/quantum/
├── __init__.py           # Public API exports
├── schemas.py            # Core data structures
├── action_predictor.py   # Predicts likely player actions
├── action_matcher.py     # Fuzzy matches input to predictions
├── gm_oracle.py          # Predicts GM twist decisions
├── branch_generator.py   # Generates narrative variants
├── cache.py              # LRU cache for branches
├── collapse.py           # Rolls dice, applies state changes
├── pipeline.py           # Main entry point
├── validation.py         # Consistency validators
└── metrics.py            # Performance tracking
```

## Key Components

| Component | Purpose |
|-----------|---------|
| `ActionPredictor` | Predicts likely actions from scene context |
| `ActionMatcher` | Fuzzy matches player input to predictions |
| `GMDecisionOracle` | Predicts whether GM would add a twist |
| `BranchGenerator` | Generates narrative variants for each branch |
| `QuantumBranchCache` | LRU cache for pre-generated branches |
| `BranchCollapseManager` | Rolls dice and commits selected branch |
| `QuantumPipeline` | Main entry point for turn processing |

## Documentation

- [Architecture](./architecture.md) - Detailed system design
- [Action Prediction](./action-prediction.md) - How actions are predicted
- [Branch Generation](./branch-generation.md) - How branches are generated
- [Collapse Mechanism](./collapse-mechanism.md) - How branches collapse on observation
- [Caching Strategy](./caching-strategy.md) - Cache design and eviction
- [Migration Guide](./migration-guide.md) - Migrating from old pipelines

## Performance Metrics

Target performance characteristics:

| Metric | Target | Notes |
|--------|--------|-------|
| Cache Hit Rate | >60% | For common actions |
| Cache Hit Latency | <100ms | Branch selection + dice roll |
| Cache Miss Latency | 3-8s | Synchronous generation |
| Memory Usage | <100MB | Branch cache |
| Anticipation Cycle | <2s | Per cycle |

## See Also

- [Main Architecture](../architecture.md) - Overall system architecture
- [Scene-First Architecture](../scene-first-architecture/) - Previous pipeline design
