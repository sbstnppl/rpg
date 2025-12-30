# Dual-Model Separation (Future Enhancement)

**Status:** Not Implemented
**Priority:** Medium
**Created:** 2025-12-30

## Overview

The quantum pipeline was designed with dual-model separation in mind:
- **Reasoning model (qwen3)**: Logic, predictions, structured decisions
- **Narrator model (magmell)**: Prose generation, atmospheric writing

However, this separation was **never implemented**. Currently, qwen3 handles everything including narrative generation.

## Current State

```python
# In pipeline.py
self._reasoning_llm = get_reasoning_provider()
self._narrator_llm = llm_provider or get_narrator_provider()  # Created but NEVER USED

# BranchGenerator uses reasoning model for everything including narrative
self.branch_generator = BranchGenerator(db, game_session, self._reasoning_llm)
```

The `_narrator_llm` is dead code - created but never called.

## Current Workflow

```
Player Input
     │
     ▼
ActionPredictor ◄── qwen3
     │
     ▼
BranchGenerator ◄── qwen3 (generates BOTH logic AND narrative)
     │
     ▼
CollapseManager
     │
     ▼
Narrative Output
```

## Intended Workflow

```
Player Input
     │
     ▼
ActionPredictor ◄── qwen3 (reasoning)
     │
     ▼
BranchGenerator ◄── qwen3 (reasoning)
│   Returns: outcome_type, state_deltas, time_passed
│   Does NOT generate prose
     │
     ▼
Narrator ◄── magmell (narrator)
│   Takes: scene context, outcome, deltas
│   Returns: atmospheric prose narrative
     │
     ▼
CollapseManager
     │
     ▼
Narrative Output
```

## Benefits of Separation

1. **Specialized models**: Each model optimized for its task
2. **Better prose**: Narrator model (magmell) trained for creative writing
3. **Cleaner JSON**: Reasoning model doesn't need to generate prose in structured output
4. **Flexibility**: Can swap narrator model without affecting logic

## Implementation Plan

### Step 1: Modify BranchGenerator output schema

Remove `narrative` from `OutcomeVariant`, add `outcome_summary`:

```python
class OutcomeVariant(BaseModel):
    outcome_type: str  # "success", "failure", "critical_success", etc.
    outcome_summary: str  # Brief description for narrator context
    state_deltas: list[StateDeltaSchema]
    time_passed_minutes: int
    # NO narrative field
```

### Step 2: Create NarratorStep

New component that takes branch output and generates prose:

```python
class NarratorStep:
    def __init__(self, llm: LLMProvider, manifest: GroundingManifest):
        self.llm = llm  # magmell
        self.manifest = manifest

    async def narrate(
        self,
        context: BranchContext,
        outcome: OutcomeVariant,
        player_input: str,
    ) -> str:
        """Generate atmospheric prose for the outcome."""
        # Build narrator prompt with scene, outcome, entities
        # Call magmell for prose generation
        # Validate entity references
        return narrative
```

### Step 3: Integrate into pipeline

```python
# In QuantumPipeline.process_turn()
branch = await self.branch_generator.generate(context, action)
narrative = await self.narrator.narrate(context, branch.selected_variant, player_input)
```

### Step 4: Update collapse flow

CollapseManager receives narrative separately from branch data.

## Files to Modify

- [ ] `src/world_server/quantum/schemas.py` - Remove narrative from OutcomeVariant
- [ ] `src/world_server/quantum/branch_generator.py` - Stop generating narrative
- [ ] `src/world_server/quantum/narrator.py` - New file for NarratorStep
- [ ] `src/world_server/quantum/pipeline.py` - Wire up narrator step
- [ ] `src/world_server/quantum/collapse.py` - Accept narrative parameter

## Considerations

- **Latency**: Two LLM calls instead of one (can be optimized with parallel calls where possible)
- **Context sharing**: Narrator needs full scene context for grounded references
- **Caching**: Pre-generated branches won't have narrative - need to generate at collapse time
- **Fallback**: If narrator fails, use reasoning model as fallback

## Related

- `docs/llm-deployment.md` - Model configuration
- `src/config.py` - NARRATOR and REASONING settings
