# Skill Checks Not Triggering

**Status**: Fixed
**Priority**: MEDIUM
**Discovered**: Session 347 Play Test (2026-01-18)
**Fixed**: 2026-01-18

## Problem

Actions that should require skill checks (like "try to sneak into the alley") are misclassified as MOVE actions instead of SKILL_USE. This bypasses the uncertainty system - players can sneak, climb, hide, etc. without any dice rolls.

### Observed Behavior

1. Player inputs: "I try to sneak into the alley"
2. Intent classifier categorizes as: `MOVE`
3. System processes as simple movement
4. No skill check occurs
5. Player "succeeds" at sneaking automatically

### Expected Behavior

1. Player inputs: "I try to sneak into the alley"
2. Intent classifier recognizes: `SKILL_USE` (stealth skill)
3. Branch generator creates success/failure branches
4. Dice roll determines outcome
5. Narrative reflects success OR failure based on roll

## Root Cause Analysis

### Intent Classification Path

The classification goes through multiple stages:

1. **LLM Intent Classifier** (`intent_classifier.py`)
   - Asks LLM to categorize the action
   - May return low confidence for ambiguous inputs
   - "sneak into alley" is ambiguous (movement + skill)

2. **Fuzzy Matcher Fallback** (`action_matcher.py:72`)
   - Used when LLM confidence is low
   - `ACTION_VERBS` mapping weights keywords
   - "into" + location name → heavily weighted toward MOVE

3. **Branch Generator** (`branch_generator.py:242-366`)
   - System prompt says "if a skill check is reasonable"
   - No explicit criteria for WHEN skill checks are required
   - LLM has discretion, often skips for convenience

### The Core Problem

**No definitive guidance on skill check triggers.** The system relies on LLM judgment with vague instructions, leading to inconsistent behavior.

## Files Involved

| File | Lines | Role |
|------|-------|------|
| `intent_classifier.py` | - | Primary intent classification |
| `action_matcher.py` | 72 | `ACTION_VERBS` - fuzzy matching weights |
| `branch_generator.py` | 242-366 | System prompt - vague skill check guidance |
| `pipeline.py` | 744-749 | OBSERVE/WAIT fix pattern (reference) |

## Skill Check Trigger Verbs

Actions containing these verbs should trigger skill checks:

| Verb | Skill | Notes |
|------|-------|-------|
| sneak, creep, slip | Stealth | Unless explicitly safe location |
| climb, scale, scramble | Athletics | Unless trivial (stairs, ladder) |
| hide, conceal | Stealth | Always requires check if observers present |
| persuade, convince, charm | Persuasion | Social skill check |
| intimidate, threaten | Intimidation | Social skill check |
| deceive, lie, bluff | Deception | Social skill check |
| pick (lock), lockpick | Sleight of Hand | Always requires check |
| search, investigate | Investigation | Depends on complexity |
| notice, perceive, spot | Perception | Passive vs active |

## Potential Solutions

### Option 1: Skill Verb Detection Pre-Filter

Add a pre-classification step that detects skill verbs:
```python
SKILL_VERBS = {"sneak", "climb", "hide", "pick", "persuade", ...}
if any(verb in player_input.lower() for verb in SKILL_VERBS):
    force_intent = IntentType.SKILL_USE
```

**Pros**: Fast, deterministic
**Cons**: May miss contextual variations ("quietly move" = sneak)

### Option 2: Explicit Guidance in System Prompt

Update `branch_generator.py` system prompt with explicit rules:
```
SKILL CHECK REQUIRED when action involves:
- Stealth: sneaking, hiding, moving quietly past observers
- Physical: climbing, jumping gaps, forcing doors
- Social: persuading, deceiving, intimidating NPCs
- Technical: picking locks, disabling traps
```

**Pros**: Uses existing LLM capability
**Cons**: LLM may still ignore guidance

### Option 3: Dual Classification

Run both MOVE and SKILL_USE classification, prefer SKILL_USE if both match:
```python
move_confidence = classify_as_move(input)
skill_confidence = classify_as_skill(input)
if skill_confidence > 0.3:  # Lower threshold for skill
    return IntentType.SKILL_USE
```

**Pros**: Catches edge cases
**Cons**: More LLM calls, latency

### Option 4: Follow OBSERVE/WAIT Pattern

The `pipeline.py:744-749` fix for OBSERVE/WAIT shows the pattern:
- Certain intents skip target matching entirely
- Could add SKILL_USE to similar special handling

## Recommended Approach

**Option 1 + Option 2 combined:**

1. Add skill verb detection as a hint (not override)
2. Update system prompt with explicit skill check criteria
3. Bias the intent classifier toward SKILL_USE when verbs detected

This gives deterministic detection with LLM flexibility for edge cases.

## Related Issues

- `gm-player-agency` - Related to player action handling
- `grounding-manifest-create-entity` - Similar pattern of LLM discretion issues

## Reproduction Steps

1. Start game session in a location with restricted areas
2. Input: "I try to sneak past the guard"
3. Observe intent classification in debug logs
4. Note: No skill check, no dice roll, automatic success

## Test Coverage Needed

- [ ] Test: "sneak" verb triggers SKILL_USE intent
- [ ] Test: "climb" verb triggers SKILL_USE intent
- [ ] Test: Ambiguous input "quietly go to" triggers skill check
- [ ] Test: Explicit "I walk to X" does NOT trigger skill check
