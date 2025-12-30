# Scene-First Architecture - Quick Start Guide

## For Starting a New Implementation Session

Read this first if you're continuing implementation from a new session.

---

## 1. Understand the Problem (2 min)

The current system has the narrator inventing entities that may not get persisted, causing:
- Orphaned entities
- Fragmented reference resolution (5 different places)
- Deferred spawning complexity (3 tracking systems)

**The Solution**: Build the world BEFORE narrating it.

```
World Mechanics → Scene Builder → Persist → Parse → Resolve → Execute → Narrate
```

---

## 2. Key Files to Read

| File | Purpose | Read When |
|------|---------|-----------|
| `docs/scene-first-architecture/TODO.md` | Implementation checklist | First |
| `docs/scene-first-architecture/architecture.md` | Detailed design | Understanding flow |
| `docs/scene-first-architecture/schemas.md` | All Pydantic models | Implementing code |
| `docs/scene-first-architecture/prompts.md` | LLM prompts | Implementing LLM calls |
| `docs/scene-first-architecture/findings.md` | Why we made these choices | Context |

---

## 3. Current Progress

Check the "Progress Tracking" table at the bottom of `TODO.md` for current status.

---

## 4. Implementation Order

### If Starting Fresh

1. **Phase 1**: Create `src/world/schemas.py` with all Pydantic models
2. **Phase 2**: Create `src/world/constraints.py` with realistic limits
3. **Phase 3**: Create `src/world/world_mechanics.py`
4. **Phase 4**: Create `src/world/scene_builder.py`
5. Continue with TODO.md phases...

### If Resuming

1. Check TODO.md for last completed task
2. Run existing tests: `pytest tests/test_world/`
3. Continue from next unchecked item

---

## 5. Key Patterns

### Structured LLM Output

```python
from src.world.schemas import WorldUpdate

response = await llm.complete_structured(
    messages=[Message.user(prompt)],
    response_schema=WorldUpdate,
    temperature=0.3,
    system_prompt=WORLD_MECHANICS_SYSTEM,
)

update = response.parsed_content
```

### Narrator [key] Format

Narrator outputs:
```
"You see [marcus_001] sitting on [bed_001]."
```

Validation:
```python
import re
KEY_PATTERN = re.compile(r'\[([a-z0-9_]+)\]')
keys = KEY_PATTERN.findall(narrator_output)
for key in keys:
    if key not in manifest.entities:
        # Invalid reference
```

Display (keys stripped):
```
"You see Marcus sitting on the bed."
```

### Constraint Checking

```python
limits = SocialLimits.for_player(player_personality)
if current_close_friends >= limits.max_close_friends:
    # Cannot add new close friend
    return ConstraintResult(allowed=False, reason="Max close friends reached")
```

---

## 6. Testing Commands

```bash
# Run all world tests
pytest tests/test_world/ -v

# Run specific test file
pytest tests/test_world/test_world_mechanics.py -v

# Run with coverage
pytest tests/test_world/ --cov=src/world

# Run integration tests
pytest tests/test_integration/test_scene_first_flow.py -v
```

---

## 7. Common Issues

### Issue: LLM returns wrong schema

**Solution**: Check prompt has correct output instructions. Use `complete_structured()` with Pydantic model.

### Issue: Narrator invents entities

**Solution**: Validation should catch this. Check `NarratorValidator._detect_unkeyed_references()`.

### Issue: Constraint violation not caught

**Solution**: Add test case, fix in `RealisticConstraintChecker`.

---

## 8. Files You'll Create

```
src/
├── world/
│   ├── __init__.py
│   ├── schemas.py              # All Pydantic models
│   ├── constraints.py          # Realistic limits
│   ├── world_mechanics.py      # World simulation
│   ├── scene_builder.py        # Scene generation
│   └── scene_persister.py      # DB persistence
├── narrator/
│   ├── constrained_narrator.py # Constrained narrator
│   └── validator.py            # Output validation
├── resolver/
│   ├── __init__.py
│   └── reference_resolver.py   # Simple resolution
└── agents/nodes/
    ├── world_mechanics_node.py
    ├── scene_builder_node.py
    ├── persist_scene_node.py
    ├── resolve_references_node.py
    ├── constrained_narrator_node.py
    └── validate_narrator_node.py

data/templates/
├── world_mechanics.jinja2
├── scene_builder.jinja2
├── constrained_narrator.jinja2
├── narrator_retry.jinja2
├── clarification.jinja2
└── narrator_fallback.jinja2

tests/
├── test_world/
│   ├── __init__.py
│   ├── test_schemas.py
│   ├── test_constraints.py
│   ├── test_world_mechanics.py
│   ├── test_scene_builder.py
│   └── test_scene_persister.py
├── test_narrator/
│   ├── test_validator.py
│   └── test_constrained_narrator.py
├── test_resolver/
│   └── test_reference_resolver.py
└── test_integration/
    └── test_scene_first_flow.py
```

---

## 9. Questions to Ask User

If unclear about anything, ask:

1. "Should furniture be a separate model or Item with `is_furniture=True`?"
2. "When should container contents be generated - on creation or on open?"
3. "What social limits feel right for this setting?"
4. "Should World Mechanics run every turn or only on location change?"

---

## 10. Success Criteria

The implementation is complete when:

- [ ] All phases in TODO.md are checked
- [ ] All tests pass
- [ ] Can play through: enter location → see scene → take action → proper narration
- [ ] Pronouns resolve correctly
- [ ] Ambiguous references trigger clarification
- [ ] No orphaned entities
- [ ] Narrator validation catches invented entities
