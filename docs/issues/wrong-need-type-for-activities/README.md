# Wrong Need Type for Activities

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-27
**Related Sessions:** Session 293, Turns 6, 9

## Problem Statement

When the LLM calls `satisfy_need` or chooses between need-related tools, it often selects the wrong need type for the activity. Drinking satisfies hunger instead of thirst, asking for water triggers stimulus instead of satisfaction.

## Current Behavior

### Turn 6: Drinking ale
Player input: "I take a drink from the ale"

LLM called:
```json
{
  "tool": "satisfy_need",
  "need": "hunger",  // WRONG - should be "thirst"
  "activity": "drinking ale",
  "amount": 25
}
```

Result: Hunger went 80→100, Thirst stayed at 80

### Turn 9: Asking for water
Player input: "I feel thirsty. I ask for some water"

LLM called:
```json
{
  "tool": "apply_stimulus",  // WRONG TOOL - should be satisfy_need
  "stimulus_type": "drink_sight",
  "stimulus_description": "water offered in response to thirst"
}
```

Result: Thirst stayed at 80 (stimulus creates craving, doesn't satisfy)

## Expected Behavior

- Drinking → `satisfy_need(need="thirst")`
- Eating → `satisfy_need(need="hunger")`
- Resting → `satisfy_need(need="stamina")`
- Sleeping → `satisfy_need(need="sleep_pressure")`
- Bathing → `satisfy_need(need="hygiene")`

## Investigation Notes

Current tool description for `satisfy_need`:
> Satisfy a character need through an activity or consumption. Use when player eats, drinks, rests, sleeps, bathes, or engages in social activity. Amount guide: 10=snack/sip, 25=light meal/drink, 40=full meal, 65=feast.

The description mentions "drinks" but doesn't explicitly map drinking to thirst.

## Root Cause

1. **Ambiguous tool description**: No explicit activity-to-need mapping
2. **No examples**: Description lists activities but not which need each satisfies
3. **Model confusion**: qwen3 guesses based on context, often wrong

## Proposed Solution

Update `satisfy_need` tool description with explicit mapping:

```python
description = """Satisfy a character need through an activity or consumption.

ACTIVITY TO NEED MAPPING (use these exact mappings):
- eat/eating/meal/food → need="hunger"
- drink/drinking/water/ale/beverage → need="thirst"
- rest/resting/sit down → need="stamina"
- sleep/sleeping/nap → need="sleep_pressure"
- bathe/bathing/wash → need="hygiene"
- talk/socialize/conversation → need="social_connection"

AMOUNT GUIDE:
- 10 = snack, sip, brief rest
- 25 = light meal, drink, short rest
- 40 = full meal, good rest
- 65 = feast, long rest, full bath
"""
```

## Implementation Details

Update tool definition in `src/gm/tools.py`:

```python
{
    "name": "satisfy_need",
    "description": """Satisfy a character need through an activity.

REQUIRED: Match activity to the correct need:
- Eating/food → need="hunger"
- Drinking/beverages → need="thirst"
- Resting/sitting → need="stamina"
- Sleeping/napping → need="sleep_pressure"
- Bathing/washing → need="hygiene"
- Socializing/talking → need="social_connection"

Amount: 10=small, 25=moderate, 40=full, 65=large""",
    ...
}
```

## Files to Modify

- [ ] `src/gm/tools.py` - Update `satisfy_need` description
- [ ] `tests/test_gm/test_tools.py` - Add tests for correct need mapping

## Test Cases

- [ ] Test: "I drink water" → satisfy_need(need="thirst")
- [ ] Test: "I eat bread" → satisfy_need(need="hunger")
- [ ] Test: "I rest by the fire" → satisfy_need(need="stamina")
- [ ] Test: "I take a nap" → satisfy_need(need="sleep_pressure")

## Related Issues

- Related to tool output leak (both are LLM behavior issues)
- Could add validation to reject hunger+drinking combinations

## References

- `src/gm/tools.py:get_tool_definitions()` - Tool definitions
- `logs/llm/session_293/turn_006_*.md` - Drinking ale logs
- `logs/llm/session_293/turn_009_*.md` - Water request logs
