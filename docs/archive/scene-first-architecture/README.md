# Scene-First Architecture

This directory contains the implementation plan for the Scene-First Architecture refactor.

## Documents

| File | Description |
|------|-------------|
| [TODO.md](./TODO.md) | Implementation checklist with all tasks |
| [architecture.md](./architecture.md) | Detailed architecture description |
| [findings.md](./findings.md) | Analysis of current problems and design decisions |
| [schemas.md](./schemas.md) | All Pydantic schemas for the new system |
| [prompts.md](./prompts.md) | LLM prompts for World Mechanics, Scene Builder, Narrator |

## Quick Summary

### The Problem
The current system has narrator inventing entities that may or may not get persisted, leading to:
- Orphaned entities (mentioned but not spawned)
- Fragmented reference resolution (5 different places try to resolve "her")
- Deferred spawning complexity (3 separate tracking systems)

### The Solution
**Scene-First Architecture**: Build the world BEFORE narrating it.

```
World Mechanics → Scene Builder → Persist → Parse Intent → Resolve → Execute → Narrate
     |                |              |                         |            |
  CAN INVENT      CAN INVENT     ATOMIC              SIMPLE LOOKUP    CANNOT INVENT
  (constrained)   (physical)                                          (validated)
```

### Key Principles
1. **World exists before observation** - Things are there whether player looks or not
2. **Structured output for creation** - LLMs output schemas, not prose, when creating
3. **Narrator cannot invent** - Only describes what exists, validated with [key] format
4. **Realistic constraints** - World Mechanics respects social/physical limits
