# GM Audit Context Session ID Not Set

**Status:** Done
**Priority:** Low
**Detected:** 2025-12-27
**Related Sessions:** Session 292 (GM pipeline testing)

## Problem Statement

The GM pipeline does not call `set_audit_context()` before making LLM calls, causing all logs to be written to `logs/llm/orphan/` instead of `logs/llm/session_<id>/`. This makes debugging specific sessions difficult.

## Current Behavior

LLM call logs from GM pipeline are saved as:
```
logs/llm/orphan/20251227_183542_unknown.md
logs/llm/orphan/20251227_183717_unknown.md
```

Log metadata shows:
```markdown
# LLM Call: unknown
## Metadata
- **Timestamp**: 2025-12-27T18:35:42
- **Provider**: ollama
- **Model**: qwen3:32b
```

No session ID or turn number in filename or metadata.

## Expected Behavior

LLM call logs should be organized by session:
```
logs/llm/session_292/turn_001_20251227_183542_gm.md
logs/llm/session_292/turn_002_20251227_183717_gm.md
```

Log metadata should include:
```markdown
# LLM Call: gm
## Metadata
- **Timestamp**: 2025-12-27T18:35:42
- **Session ID**: 292
- **Turn Number**: 1
- **Provider**: ollama
- **Model**: qwen3:32b
```

## Investigation Notes

The `set_audit_context()` function from `src/llm/audit_logger.py` sets thread-local context that the logging provider uses to organize logs.

Other pipelines (legacy, system-authority) call this in their nodes. The GM pipeline (`src/gm/gm_node.py`) appears to be missing this call.

Example from legacy pipeline:
```python
from src.llm.audit_logger import set_audit_context

set_audit_context(
    session_id=state.get("session_id"),
    turn_number=state.get("turn_number"),
    call_type="game_master",
)
```

## Root Cause

`src/gm/gm_node.py` does not call `set_audit_context()` before invoking the LLM provider.

## Proposed Solution

Add `set_audit_context()` call at the start of the GM node's main function, similar to legacy pipeline nodes.

## Implementation Details

In `src/gm/gm_node.py`, add before LLM call:

```python
from src.llm.audit_logger import set_audit_context

async def gm_node(state: GMState) -> GMState:
    """Main GM node that processes player input."""
    # Set audit context for LLM logging
    set_audit_context(
        session_id=state.get("session_id"),
        turn_number=state.get("turn_number"),
        call_type="gm",
    )

    # ... rest of function
```

## Files to Modify

- [x] `src/gm/gm_node.py` - Add `set_audit_context()` call

## Test Cases

- [x] Test case 1: After fix, logs appear in `logs/llm/session_<id>/`
- [x] Test case 2: Log filename includes turn number
- [x] Test case 3: Log metadata shows session_id and turn_number

## Related Issues

- None currently

## References

- `src/llm/audit_logger.py` - Audit logging implementation
- `src/gm/gm_node.py` - GM node that needs the fix
- `src/agents/nodes/game_master_node.py` - Legacy example with correct context setting
