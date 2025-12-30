# Scene-First Architecture - Troubleshooting Guide

## Common Issues and Solutions

### Issue: Narrator Invents Entities

**Symptom**: Narrator mentions NPCs or items that aren't in the manifest.

**Cause**: Narrator didn't follow [key] format rules or validation wasn't triggered.

**Solution**:
1. Check `validate_narrator_node.py` is in the graph
2. Verify `NarratorValidator._detect_unkeyed_references()` is working
3. Check narrator prompt includes manifest reference guide
4. Enable debug logging to see validation results

```python
# In validate_narrator_node.py
import logging
logging.getLogger(__name__).setLevel(logging.DEBUG)
```

---

### Issue: Reference Resolution Fails

**Symptom**: Player says "talk to Marcus" but system can't find the entity.

**Cause**: Entity not in manifest or name mismatch.

**Solution**:
1. Check manifest contents:
```python
# Debug in resolve_references_node.py
print(f"Manifest entities: {narrator_manifest.entities}")
print(f"Looking for: {target}")
```

2. Verify entity was persisted:
```sql
SELECT entity_key, display_name FROM entities
WHERE session_id = ? AND location_key = ?;
```

3. Check ReferenceResolver matching logic in `src/resolver/reference_resolver.py`

---

### Issue: Pronoun Ambiguity Not Detected

**Symptom**: "Talk to her" resolves incorrectly when multiple women are present.

**Cause**: Pronoun candidates not properly tracked.

**Solution**:
1. Check manifest has gender info for all NPCs
2. Verify `ReferenceResolver._try_pronoun()` finds multiple candidates
3. Check `needs_clarification` is set in state

---

### Issue: Scene Not Generated on Location Change

**Symptom**: Player enters new location but no scene description appears.

**Cause**: `just_entered_location` not set or routing skipped world_mechanics.

**Solution**:
1. Check `route_after_parse_scene_first()` logic
2. Verify `location_changed` is set in state
3. Check `is_scene_request` flag

```python
# Debug routing
print(f"location_changed: {state.get('location_changed')}")
print(f"just_entered_location: {state.get('just_entered_location')}")
```

---

### Issue: Actions Not Executing

**Symptom**: Player action parses but nothing happens.

**Cause**: Resolution failed or subturn_processor skipped.

**Solution**:
1. Check `resolved_actions` in state after resolve_references_node
2. Look for `resolution_failed: True` in action dicts
3. Verify routing goes to subturn_processor

---

### Issue: Validation Loop (Narrator Keeps Retrying)

**Symptom**: Narrator validation fails repeatedly, eventually falls back.

**Cause**: Narrator consistently violates rules despite retry prompts.

**Solution**:
1. Check narrator prompt is clear about [key] format
2. Verify manifest reference guide is included
3. Review failed validation errors:
```python
print(f"Validation errors: {state.get('narrator_validation_errors')}")
```
4. Consider adjusting retry limit or validation strictness

---

### Issue: Pipeline Selection Not Working

**Symptom**: `--pipeline scene-first` still uses system-authority.

**Cause**: Pipeline alias not recognized or graph not built.

**Solution**:
1. Check `PIPELINE_ALIASES` in `src/cli/commands/game.py`
2. Verify `get_pipeline_graph()` returns correct graph
3. Check console output for "Using Scene-First pipeline"

---

## Debugging Commands

### Check Which Pipeline is Active
```python
# In game loop
print(f"Pipeline: {pipeline_name}")
```

### Dump State at Any Node
```python
async def debug_node(state: GameState) -> dict:
    import json
    print(json.dumps({k: v for k, v in state.items() if not k.startswith('_')}, indent=2, default=str))
    return {}
```

### Test Reference Resolution
```python
from src.resolver.reference_resolver import ReferenceResolver
from src.world.schemas import NarratorManifest

manifest = NarratorManifest(entities=[...])
resolver = ReferenceResolver(manifest)
result = resolver.resolve("the guard")
print(f"Resolved: {result.resolved}, Entity: {result.entity}")
```

### Test Event-Driven NPCs
```python
from src.world.world_mechanics import WorldMechanics

wm = WorldMechanics(db, game_session)
event_npcs = wm.get_event_driven_npcs("tavern_main")
print(f"Event NPCs: {[n.entity_key for n in event_npcs]}")
```

### Test Story-Driven NPCs (async)
```python
import asyncio
from src.world.world_mechanics import WorldMechanics

wm = WorldMechanics(db, game_session, llm_provider=llm)
story_npcs = asyncio.run(wm.get_story_driven_npcs(
    "tavern_main", "tavern", "Player just arrived in town"
))
print(f"Story NPCs: {[n.entity_key for n in story_npcs]}")
```

### Test Container Contents Generation
```python
import asyncio
from src.world.scene_builder import SceneBuilder

sb = SceneBuilder(db, game_session, llm_provider=llm)
contents = asyncio.run(sb.generate_container_contents(chest_item, location))
print(f"Container contents: {[i.display_name for i in contents]}")
```

### Test Narrator Validation
```python
from src.narrator.validator import NarratorValidator
from src.world.schemas import NarratorManifest

manifest = NarratorManifest(entities=[...])
validator = NarratorValidator(manifest)
result = validator.validate("You see [marcus_001] sitting here.")
print(f"Valid: {result.valid}, Errors: {result.errors}")
```

---

## Performance Considerations

### Two LLM Calls Before Narrator
Scene-first adds WorldMechanics and SceneBuilder calls before narration.

**Mitigations**:
1. Cache scene manifests for subsequent turns at same location
2. Skip WorldMechanics when no time has passed
3. Use Haiku for WorldMechanics and SceneBuilder (structured output is simpler)

### Memory Usage
Scene manifests can be large for complex locations.

**Mitigations**:
1. Limit furniture/item counts in SceneBuilder
2. Use `filter_by_observation_level()` to reduce manifest size
3. Clear manifest from state after persistence

---

## Fallback Behavior

If validation keeps failing after max retries, the system falls back:

1. **Narrator Fallback**: Uses `_generate_fallback()` for simple description
2. **Resolution Fallback**: Leaves target unresolved, action may fail gracefully
3. **Clarification**: Prompts player for specific reference

These fallbacks ensure the game continues even when the new system encounters issues.
