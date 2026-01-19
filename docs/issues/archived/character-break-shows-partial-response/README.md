# Character Break Detection Shows Partial Failed Responses to User

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-29
**Resolved:** 2025-12-29
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

The `logger.warning()` call in `src/gm/gm_node.py:815` was outputting validation failure messages at WARNING level, which appears on the console during normal gameplay. This exposed internal validation mechanics to the user.

Additionally, when `show_tokens=True` is enabled (debugging mode), streamed tokens appear before validation runs. This is acceptable as `show_tokens` is an opt-in debugging feature.

## Solution

Changed log levels from user-visible (warning/error/info) to debug-only:

- `src/gm/gm_node.py:815` - `logger.warning` → `logger.debug` (detection message)
- `src/gm/gm_node.py:859` - `logger.error` → `logger.debug` (retry failure)
- `src/gm/gm_node.py:865` - `logger.info` → `logger.debug` (retry success)

## Files Modified

- [x] `src/gm/gm_node.py` - Changed log levels to debug

## Verification

- [x] All 282 GM tests pass
- [x] Character break detection still functions correctly
- [x] Validation messages no longer appear at WARNING level

## Related Issues

- Related to character break detection working correctly
- Output/display layer issue

## References

- `src/gm/gm_node.py:_validate_character()` - Character break detection
- `src/cli/commands/game.py` - CLI output
- `logs/llm/session_302/turn_014_*` - Audit log with example
