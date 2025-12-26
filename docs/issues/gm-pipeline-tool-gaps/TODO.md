# TODO: GM Pipeline Tool Gaps

## Implementation Phase

### Phase 1: Item Tools
- [x] Add `take_item` tool definition to `get_tool_definitions()`
- [x] Add `drop_item` tool definition
- [x] Add `give_item` tool definition
- [x] Add routing in `execute_tool()` for all three
- [x] Implement `take_item()` method
- [x] Implement `drop_item()` method
- [x] Implement `give_item()` method

### Phase 2: Need Satisfaction Tool
- [x] Add `satisfy_need` tool definition
- [x] Add routing in `execute_tool()`
- [x] Implement `satisfy_need()` method

### Phase 3: Prompt Updates
- [x] Restructure TOOLS section in GM_SYSTEM_PROMPT
- [x] Add skill_check USE/SKIP guidance
- [x] Add item tools section
- [x] Add needs tools section with amounts
- [x] Add record_fact guidance
- [x] Add time estimation guidelines

### Phase 4: Time Estimation Fix
- [x] Remove keyword matching (was causing false positives)
- [x] Implement tool-based time inference
- [x] Add activity-based timing from tool results

## Verification Phase
- [x] Run E2E test suite
- [x] Verify Skill Challenges 3/3
- [~] Verify Exploration and Dialog 4/5 (record_fact not called)
- [~] Verify Item Discovery - tools work, RNG dependency
- [~] Verify Needs and Activities - tools work, wrong need selected

## Remaining (LLM Behavior)
- [ ] Refine prompt for better need selection (stamina vs comfort)
- [ ] Add few-shot examples for record_fact usage
- [ ] Consider unit tests for new tools

## Completion
- [x] Update README.md status
- [ ] Create commit with `/commit`
