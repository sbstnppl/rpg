# LLM Skips Mandatory Tool Calls for Need-Satisfying Actions

**Status:** Investigating
**Priority:** High
**Detected:** 2025-12-30
**Related Sessions:** Session 304

## Problem Statement

When a player performs an action that should satisfy a character need (like having a conversation for social_connection), the LLM skips calling the mandatory `satisfy_need` tool. This causes the game state to become inconsistent - the narrative describes the action happening, but the need stat doesn't change.

## Current Behavior

Player input: "I climb down and go back to the tavern to have a long conversation with Old Tom about the village"

LLM response:
- Did NOT call `move_to` to return to tavern
- Did NOT call `satisfy_need(need="social_connection")` for the conversation
- Did NOT call `get_npc_attitude` before generating NPC dialog
- Went straight to narrative, got grounding error, fixed grounding, but never called tools

Result:
- `social_connection` need stayed at 50 (baseline) instead of increasing
- Player location may not have updated properly

From logs (`turn_007_20251230_065443_gm.md`):
```
### [USER]
I climb down and go back to the tavern to have a long conversation with Old Tom about the village

### [USER]
GROUNDING ERROR - Please fix your narrative...
```

No tool calls between the user message and the grounding error!

## Expected Behavior

The LLM should:
1. Call `move_to(destination="village_tavern")` for the return trip
2. Call `get_npc_attitude(from_entity="innkeeper_tom", to_entity="test_hero")` before dialog
3. Call `satisfy_need(need="social_connection", amount=22, activity="conversation")` for socializing
4. THEN generate narrative based on tool results

The system prompt clearly documents these as MANDATORY tool calls with trigger words like "talk", "chat", "converse".

## Investigation Notes

The system prompt includes:
```
### NEED-SATISFYING ACTIONS → satisfy_need
...
| social_connection | chat, talk, converse | "I chat with them" → satisfy_need(...) |
...
WHY: If you describe a need-satisfying action without calling satisfy_need, the stat won't change!
```

And:
```
⚠️ NEVER narrate an action from the above categories without calling its tool first.
The tool call updates the game state. Your narrative describes what happened.
```

The LLM (qwen3:32b via Ollama) appears to ignore this instruction in some cases.

## Root Cause

Possible causes:
1. System prompt too long - mandatory tools section gets lost
2. Chained actions confuse the LLM (climb down + go back + have conversation)
3. Need trigger words not matching ("long conversation" vs "chat")
4. qwen3 model doesn't reliably follow tool-calling instructions

## Proposed Solution

Options:
1. Validate that need-satisfying actions called appropriate tools before accepting response
2. Add a pre-check that parses player input for trigger words and enforces tool calls
3. Shorten/restructure system prompt to emphasize mandatory tools more
4. Add retry loop that explicitly prompts for missing tool calls

## Files to Modify

- [ ] `src/gm/gm_node.py` - Add tool call validation
- [ ] `src/gm/prompts.py` - Restructure system prompt
- [ ] `src/gm/validator.py` - Add missing tool check

## Test Cases

- [ ] "Chat with NPC" should call satisfy_need(social_connection)
- [ ] "Eat bread" should call satisfy_need(hunger)
- [ ] "Take a nap" should call satisfy_need(stamina)
- [ ] Chained actions should call all relevant tools

## Related Issues

- `docs/issues/grounding-retry-repeats-previous-turn/` - Related retry handling issue

## References

- `logs/llm/session_304/turn_007_20251230_065443_gm.md` - Failed turn log
- `src/gm/prompts.py` - System prompt with mandatory tool documentation
