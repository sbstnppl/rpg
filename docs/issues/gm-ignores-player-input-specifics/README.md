# GM Ignores Player Input Specifics

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Resolved:** 2025-12-30
**Related Sessions:** Session 311

## Problem Statement

The quantum pipeline's GM is not properly interpreting the specifics of player input. When asked about a specific topic (e.g., "ask Tom about any rumors he's heard"), the GM generates a generic response about a different topic (room rental) that doesn't address what the player actually asked.

## Current Behavior

Turn 2 - Player: "talk to Old Tom"
- GM narrates asking about rooms and offering a corner room for 5 gold/week

Turn 3 - Player: "ask Tom about any rumors he's heard"
- GM narrates asking about rooms AGAIN and offering a cot for 3 silver/night
- Completely ignores the "rumors" topic

The responses are similar in structure but with slightly different room prices, suggesting the GM is pattern-matching to "talk to innkeeper" without parsing the actual request.

## Expected Behavior

Turn 3 should have Tom respond about rumors, gossip, or local news - NOT about room rentals.

Example expected response:
> You lean against the bar and ask Old Tom about any rumors he's heard lately. He lowers his voice, glancing around the room. "Strange folk been passing through," he mutters. "Saw a cloaked figure heading toward the old mill three nights past..."

## Root Cause

The branch generator never received the player's actual input. In `branch_generator.py:350-353`:

```python
if action_type == ActionType.INTERACT_NPC:
    return f"Talk to/interact with {target_name}"
```

The prompt sent to the LLM said "Talk to [innkeeper_tom:Old Tom]" but NOT "ask Tom about rumors."

Even in synchronous generation (cache miss), the `player_input` was never passed to the generation prompt. The LLM guessed the conversation topic and defaulted to room rental.

Additionally, the anticipation system pre-generated branches with no topic context, and the cache key (`location::action::target::gm_decision`) ignored conversation topics entirely.

## Solution Applied

### 1. Disabled Anticipation (Interim Fix)

Pre-generation fundamentally conflicts with topic-awareness - you can't know what the player will ask before they ask it.

**File:** `src/world_server/quantum/pipeline.py:113`
```python
enabled: bool = False  # Was True
```

### 2. Pass player_input to Branch Generation

**File:** `src/world_server/quantum/branch_generator.py:81`
Added `player_input` field to `BranchContext`:
```python
player_input: str | None = None
```

**File:** `src/world_server/quantum/branch_generator.py:273-276`
Include player input in generation prompt:
```python
if context.player_input:
    player_input_context = f'\nPLAYER INPUT: "{context.player_input}"'
```

**File:** `src/world_server/quantum/pipeline.py:453`
Pass player_input when building context:
```python
context = self._build_branch_context(location_key, player_input=player_input)
```

Now the LLM prompt includes:
```
PLAYER ACTION: Talk to [innkeeper_tom:Old Tom]
PLAYER INPUT: "ask Tom about any rumors he's heard"
```

## Files Modified

- [x] `src/world_server/quantum/pipeline.py` - Disabled anticipation, pass player_input to context
- [x] `src/world_server/quantum/branch_generator.py` - Add player_input to BranchContext and prompt
- [x] `tests/test_world_server/test_quantum/test_pipeline.py` - Update tests for disabled anticipation
- [x] `docs/quantum-branching/anticipation-caching-issue.md` - Document the deeper caching problem

## Test Results

All quantum pipeline tests pass (22 passed).
All branch generator tests pass (20 passed).

## Future Work

The anticipation/caching problem needs a proper solution. See `docs/quantum-branching/anticipation-caching-issue.md` for approaches considered:
- LLM-based semantic matching
- Embedding-based similarity
- Two-tier generation (logic cached, prose at collapse)
- Topic extraction with multi-branch pre-generation

## Related Issues

- `docs/quantum-branching/anticipation-caching-issue.md` - Deeper analysis of the caching problem

## References

- `docs/quantum-branching/README.md` - Quantum pipeline documentation
- `src/world_server/quantum/pipeline.py` - Main pipeline entry point
