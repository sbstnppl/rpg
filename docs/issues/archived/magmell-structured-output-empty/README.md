# Magmell-12b Structured Output Failing

**Status:** Done
**Priority:** High
**Detected:** 2025-12-30
**Related Sessions:** Play-test session 305

## Problem Statement

The magmell-12b model (via vLLM at 192.168.178.35:8151) is failing to return valid structured output for branch generation. Despite consuming 4096 completion tokens (max limit), the response is empty or unparseable, causing the quantum pipeline to fall back to generic narratives.

## Current Behavior

From logs (`logs/llm/orphan/20251230_115821_unknown.md`):

```
## Metadata
- Provider: openai
- Model: magmell-12b
- Method: complete_structured

## Parameters
- max_tokens: 4096
- response_schema: BranchGenerationResponse

## Response
## Usage
- Prompt Tokens: 664
- Completion Tokens: 4096
- Total Tokens: 4760

## Duration
- Total Time: 451.26s
```

Issues observed:
1. **Response section is empty** - no actual content logged
2. **4096 tokens consumed** - hitting max_tokens limit every time
3. **451 seconds per call** - extremely slow (7.5 minutes)
4. Pipeline falls back to generic: "You successfully observe." / "You successfully interact with innkeeper_tom."

## Expected Behavior

The model should return valid JSON matching `BranchGenerationResponse` schema with:
- `success` variant with narrative
- Optional `failure`, `critical_success`, `critical_failure` variants
- Each variant having narrative, state_deltas, time_passed_minutes

Response time should be ~10-30 seconds for a 12B model.

## Investigation Notes

**Prompt sent to model:**
```
Generate narrative variants for this player action.

SCENE: The Rusty Tankard
TIME: Day 1, 09:00
AVAILABLE ENTITIES (use [key:name] format):
NPCs:
  - [innkeeper_tom:Old Tom] - Innkeeper
...

PLAYER ACTION: Talk to/interact with [innkeeper_tom:Old Tom]

Generate outcome variants as JSON. Include:
- "success": The action succeeds as intended
...
```

**Possible causes:**
1. Model generating non-JSON output (prose instead of structured)
2. JSON truncated at 4096 tokens (incomplete)
3. vLLM structured output mode not working correctly
4. Model not fine-tuned for JSON generation
5. Temperature 0.7 may be too high for structured output

## Root Cause

**Wrong model being used for structured output.**

The `QuantumPipeline` was passing `self._narrator_llm` (magmell) to `BranchGenerator`, but branch generation requires **structured JSON output** (the `BranchGenerationResponse` schema). Magmell is a creative writing model meant for prose narration, not JSON generation.

The code even had comments explaining the dual-model separation:
```python
# Dual-model separation:
# - Reasoning (qwen3): Logic, predictions, tool decisions
# - Narrator (magmell): Prose generation, narrative output
```

But then incorrectly used the narrator model for structured output.

## Proposed Solution

Use the **reasoning model** (qwen3) for `BranchGenerator` since it needs structured JSON output.

## Fix Applied

Changed line 166 in `src/world_server/quantum/pipeline.py`:
```python
# Before (wrong):
self.branch_generator = BranchGenerator(db, game_session, self._narrator_llm)

# After (correct):
# BranchGenerator needs structured JSON output → use reasoning model
self.branch_generator = BranchGenerator(db, game_session, self._reasoning_llm)
```

## Implementation Details

TBD

## Files to Modify

- [ ] `src/world_server/quantum/branch_generator.py` - Branch generation logic
- [ ] `src/llm/providers/openai_provider.py` - OpenAI-compatible provider (vLLM)
- [ ] `src/config.py` - May need separate model config for branch generation

## Test Cases

- [ ] Test case 1: Branch generation returns valid JSON with at least success variant
- [ ] Test case 2: Response time under 60 seconds for branch generation
- [ ] Test case 3: Narrative contains entity references in [key:text] format

## Related Issues

- `docs/issues/timestate-day-number-attribute/` - Fixed attribute errors in same session

## References

- `logs/llm/orphan/20251230_115821_unknown.md` - Log showing empty response
- `logs/llm/orphan/20251230_115002_unknown.md` - Earlier log, same issue
- `src/world_server/quantum/branch_generator.py` - Branch generation code
- `docs/llm-deployment.md` - LLM configuration reference
