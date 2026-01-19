# TODO: New GM Pipeline Missing Tools

## Investigation Phase
- [x] Reproduce the issue (tested sessions 79, 80)
- [x] Identify affected code paths (`src/gm/tools.py`)
- [x] Document current behavior (5 tools vs 27)
- [x] Find root cause (intentional simplification, tools not migrated)
- [x] Categorize tools by priority

## Design Phase
- [x] Decide: Add tools vs extend StateChanges?
  - **Decision:** StateChanges for mutations, Tools for queries/feedback
- [x] Identify which legacy tools are truly needed
- [x] Identify which tools can be replaced by StateChanges
- [x] Define implementation order (Tier 1 → Tier 2 → Tier 3)
- [x] Review with user

## Implementation Phase - StateChange Enhancements

### SATISFY_NEED (renamed from CONSUME)
- [x] Rename CONSUME to SATISFY_NEED in schemas.py
- [x] Extend applier to handle activities (sleeping, bathing)
- [x] Test: activity-based need satisfaction

### MOVE (extended for NPCs)
- [x] Extend applier to handle NPC movement
- [x] Test: NPC moves to different location

### RELATIONSHIP
- [x] Fix applier to use correct method (update_attitude)
- [x] Test: relationship dimensions change

## Implementation Phase - Tier 1 (Critical)

### get_npc_attitude
- [x] Add tool definition to `GMTools.get_tool_definitions()`
- [x] Implement `GMTools.get_npc_attitude()` method
- [x] Wire up in `execute_tool()`
- [x] Test: GM can query attitude

## Implementation Phase - Tier 2 (Important)

### Quest Tools
- [x] Implement assign_quest
- [x] Implement update_quest
- [x] Implement complete_quest
- [x] Test: quest lifecycle works

### Task & Appointment Tools
- [x] Implement create_task
- [x] Implement complete_task
- [x] Implement create_appointment
- [x] Implement complete_appointment
- [x] Test: task/appointment tools work

### Storage Creation
- [x] Extend create_entity for storage
- [x] Test: storage containers can be created

## Implementation Phase - Tier 3 (Nice to Have)

### Needs Enhancement
- [x] Implement apply_stimulus (cravings)
- [x] Implement mark_need_communicated (stub)

## Verification Phase
- [x] Run test suite (18 tests passing)
- [ ] Test manually in gameplay (optional)
- [ ] Run e2e testing (see docs/gm-pipeline-e2e-testing.md)

## Documentation
- [x] Update this README status
- [ ] Update CHANGELOG.md (will be done in commit)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
