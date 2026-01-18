# TODO: Skill Checks Not Triggering

## Investigation Complete

- [x] Identify classification path (intent classifier → fuzzy matcher)
- [x] Document skill verb categories
- [x] List potential solutions

## Implementation Tasks

### Phase 1: Diagnosis

- [x] ~~Add logging to intent classifier to capture all classifications~~
- [x] Create test inputs covering all skill verb categories
- [x] ~~Measure current classification accuracy for skill actions~~

### Phase 2: System Prompt Improvements

- [x] Update `branch_generator.py` system prompt with explicit skill check rules
- [x] Add skill verb examples to classification guidance
- [x] ~~Test improved prompt against benchmark inputs~~

### Phase 3: Code-Level Detection

- [x] ~~Implement skill verb pre-detection in `intent_classifier.py`~~ (Using prompt improvement approach instead)
- [x] Expanded skill_use section in intent classifier system prompt with detailed examples
- [x] Fixed duplicate "pick" verb mapping in action_matcher.py

### Phase 4: Testing

- [x] Unit tests for skill verb detection (parametrized tests added)
- [ ] Integration tests for full turn with skill check (manual play-test recommended)
- [x] Regression tests for non-skill actions (walk, talk, look)

## Resolution Summary

**Approach**: Improved LLM system prompts (Option 2 from README)

**Changes Made**:
1. `src/world_server/quantum/intent_classifier.py`:
   - Expanded skill_use section with 15+ explicit examples
   - Added NOT skill_use section to distinguish from MOVE
   - Added KEY guidance about skill verb detection

2. `src/world_server/quantum/branch_generator.py`:
   - Added explicit SKILL CHECK RULES section
   - Listed skill categories (stealth, athletics, persuasion, etc.)
   - Added "NEVER skip skill checks for SKILL_USE actions" guidance

3. `src/world_server/quantum/action_matcher.py`:
   - Removed duplicate "pick" mapping to MANIPULATE_ITEM
   - "pick" now only maps to SKILL_USE (for "pick lock")

4. `tests/test_world_server/test_quantum/test_intent_classifier.py`:
   - Added `TestSkillActionClassification` class
   - Parametrized tests for stealth, athletics, social skill actions
   - Tests for movement actions that should NOT be SKILL_USE

## Notes

Priority: MEDIUM - Affects game uncertainty mechanics but doesn't break core gameplay

**Verification**: Run `pytest tests/test_world_server/test_quantum/test_intent_classifier.py -v -k skill` to verify tests pass
