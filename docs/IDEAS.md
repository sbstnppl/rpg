# Ideas & Future Considerations

Ideas that need discussion before committing to implementation. These are NOT on the active roadmap.

---

## Location Templates

**Status**: Needs discussion
**Origin**: Scene-first architecture Phase 3.3

### The Idea
Pre-defined templates for common location types (bedroom, tavern, shop) to speed up scene generation and ensure consistency.

### Open Questions
1. **Setting-specific**: The original list (tavern, smithy, forest) is fantasy-biased. How would this work for sci-fi (cantina, repair bay) or contemporary (bar, garage) settings?
2. **Maintenance burden**: Would we need separate template sets per setting?
3. **Is it even needed?**: The Scene Builder LLM already generates setting-appropriate content, and results are cached on return visits.

### Arguments For
- Faster generation (skip LLM call)
- Consistent results across locations of same type
- Cost savings

### Arguments Against
- Setting-specific maintenance nightmare
- LLM already handles this well with setting context
- Templates might feel repetitive
- More code to maintain

### Decision
Deferred. Revisit if we see problems with LLM-generated scene contents (inconsistency, weird results, cost issues).

---

## Needs Validator (Post-Processing Fallback)

**Status**: Deferred (keyword approach doesn't work)
**Origin**: GM Time Awareness issue (sessions 79-81)

### The Idea
A post-processing node that scans GM narrative for action keywords (wash, eat, drink) and auto-applies need updates if the GM forgot to call `satisfy_need`.

### What Was Tried
Created `src/agents/nodes/needs_validator_node.py` with regex patterns like `r"\bwash\w*\b"`. This was integrated into the GM pipeline after the applier node.

### Why It Failed
Keyword matching is too naive. False positives everywhere:
- "clean clothes" triggered hygiene (just looking at clothes)
- "I remember bathing 3 weeks ago" would trigger hygiene (past tense memory)
- "the water is clean" would trigger thirst (describing water)
- "I ate my words" would trigger hunger (idiom)

### Possible Future Approaches
1. **LLM verification call**: After keyword match, ask a small/fast LLM "Did the player actually perform this action right now?" Adds latency but accurate.
2. **Tool call tracking**: Check if GM actually called `satisfy_need` during tool execution, only warn if not. Requires better tool result tracking.
3. **Prompt-only**: Just improve GM prompts and accept occasional misses.

### Current State
- Code exists at `src/agents/nodes/needs_validator_node.py` (not integrated)
- Tests exist at `tests/test_agents/test_needs_validator.py`
- Disabled from GM pipeline, relying on GM prompts only

### Decision
Deferred. The keyword approach is fundamentally flawed. Revisit if GM consistently forgets to call tools, consider LLM-based verification.

---

## Template for New Ideas

```markdown
## [Idea Name]

**Status**: Needs discussion | Under consideration | Rejected | Accepted → moved to TODO
**Origin**: Where this idea came from

### The Idea
Brief description.

### Open Questions
1. Question 1
2. Question 2

### Arguments For
- Pro 1
- Pro 2

### Arguments Against
- Con 1
- Con 2

### Decision
Current status and reasoning.
```
