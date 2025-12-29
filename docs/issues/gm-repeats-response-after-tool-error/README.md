# GM Repeats Previous Turn Response After Tool Error + Grounding Retry

**Status:** ✅ RESOLVED
**Priority:** High
**Detected:** 2025-12-28
**Resolved:** 2025-12-29
**Related Sessions:** 301

## Resolution

Fixed in `src/gm/gm_node.py`. The fix:
1. Added `_current_player_input` and `_current_turn_number` instance variables (lines 310-311)
2. Store player input at start of run() method (lines 550-552)
3. Include explicit turn number and player input in grounding retry message (lines 732-735):
   - "IMPORTANT: This is Turn N. The player said: '<input>'. Your response MUST address THIS input."
4. Applied same fix to character validation retry (lines 823-824)

This ensures the LLM always knows which turn to respond to, preventing it from echoing previous responses.

## Problem Statement

When the GM makes a tool call that returns an error, and then a grounding validation retry occurs, the GM responds with the narrative from the PREVIOUS turn instead of addressing the current player input. This creates a confusing gameplay experience where player actions are ignored.

## Current Behavior

Sequence of events observed in Turn 3:
1. Player input: "Can I get a mug of ale?"
2. GM calls `take_item(item_key='ale_mug_001')` - item doesn't exist
3. Tool returns error: `{"error": "Item not found: ale_mug_001"}`
4. GM calls `get_scene_details()` to recover
5. Grounding validation fails (unkeyed "Village Square")
6. Grounding retry message sent
7. **GM responds with Turn 2's response** about "Hey Tom, how's it going?" instead of addressing the ale request

Audit log snippet:
```
### [USER]
Can I get a mug of ale?

### [ASSISTANT]
(tool_use: take_item with item_key='ale_mug_001')

### [TOOL]
{"error": "Item not found: ale_mug_001"}

### [ASSISTANT]
(tool_use: get_scene_details)

### [TOOL]
{...scene details...}

### [USER]
GROUNDING ERROR - Please fix your narrative...

## Response
You ask, "Hey Tom, how's it going?" [innkeeper_tom:Old Tom] pauses...
```

The response is clearly for Turn 2, not Turn 3.

## Expected Behavior

After a tool error + grounding retry, the GM should:
1. Acknowledge the tool error gracefully in-story (e.g., "Tom shakes his head, 'Sorry, we're fresh out of ale.'")
2. OR use `create_entity()` to create the ale item if appropriate
3. Respond to the CURRENT player input, not repeat a previous turn

## Investigation Notes

- The issue may be in conversation history management
- The grounding retry message may be confusing the model about which turn to respond to
- Previous turn's assistant response is in the conversation history, which may be being echoed

## Root Cause

<After investigation - why is this happening?>

## Proposed Solution

Options:
1. Include the current player input again in the grounding retry message
2. Clear indication in retry message: "The player said: <current input>. Respond to THIS."
3. Better error recovery flow that doesn't trigger grounding retry loop

## Implementation Details

<Specific code changes, new classes, etc.>

## Files to Modify

- [ ] `src/gm/gm_node.py` - grounding retry logic
- [ ] `src/gm/validator.py` - validation feedback format
- [ ] `src/gm/context_builder.py` - conversation history handling

## Test Cases

- [ ] Test case 1: Tool error + grounding retry returns correct turn response
- [ ] Test case 2: Multiple tool errors don't cause response duplication
- [ ] Test case 3: Grounding retry includes current player context

## Related Issues

- Grounding validation system

## References

- `logs/llm/session_301/turn_003_20251228_203411_gm.md` - audit log with issue
- `src/gm/gm_node.py` - GM node implementation
