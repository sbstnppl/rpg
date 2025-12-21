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
