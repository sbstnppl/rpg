# Character Break Detection Shows Partial Failed Responses to User

**Status:** Investigating
**Priority:** Medium
**Detected:** 2025-12-29
**Related Sessions:** Session 302, Turn 14

## Problem Statement

When the character break detection system catches a violation and retries, the partial failed response is still shown to the user before the corrected response. This breaks immersion by exposing internal validation mechanics to the player.

## Current Behavior

Player sees:
```
Character break detected (pattern: \bthe player\b): I'll first check Widow Brennan's attitude toward the player:

[widow_brennan_118:Widow Brennan] sigh...

╭────────────────────────────────────────────────────────────────────────────╮
│  "Widow Brennan sighs heavily and gestures toward her chicken coop...      │
╰────────────────────────────────────────────────────────────────────────────╯
```

The user sees:
1. The detection message ("Character break detected...")
2. The partial failed response ("[widow_brennan_118:Widow Brennan] sigh...")
3. The final corrected response in the box

## Expected Behavior

User should ONLY see the final corrected response:
```
╭────────────────────────────────────────────────────────────────────────────╮
│  "Widow Brennan sighs heavily and gestures toward her chicken coop...      │
╰────────────────────────────────────────────────────────────────────────────╯
```

All intermediate validation failures should be silent (logged only, not displayed).

## Investigation Notes

The character break detection in `src/gm/gm_node.py:_validate_character()` catches patterns like `\bthe player\b` and triggers a retry. However, the output mechanism appears to print intermediate results.

The validation message format suggests it's being printed during the validation loop rather than suppressed.

## Root Cause

The CLI display logic or the GM node is outputting intermediate responses before the final successful response is ready. The retry loop isn't properly suppressing failed attempts from user-visible output.

## Proposed Solution

1. Buffer all responses until validation passes
2. Only output the final successful response
3. Log validation failures to audit log only (not stdout)

## Implementation Details

In `src/gm/gm_node.py`:
1. Collect responses in a buffer during tool loop
2. Only return/print the final validated response
3. Move validation failure messages to logger only

In `src/cli/commands/game.py`:
1. Ensure only final GM response is displayed
2. Don't print intermediate retry attempts

## Files to Modify

- [ ] `src/gm/gm_node.py` - Buffer responses, suppress intermediate output
- [ ] `src/cli/commands/game.py` - Ensure clean output

## Test Cases

- [ ] Test case 1: Character break retry doesn't show failed attempts
- [ ] Test case 2: Grounding retry doesn't show failed attempts
- [ ] Test case 3: Final response is displayed correctly

## Related Issues

- Related to character break detection working correctly
- Output/display layer issue

## References

- `src/gm/gm_node.py:_validate_character()` - Character break detection
- `src/cli/commands/game.py` - CLI output
- `logs/llm/session_302/turn_014_*` - Audit log with example
