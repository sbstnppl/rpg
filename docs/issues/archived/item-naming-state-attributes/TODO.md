# TODO: Item Naming Technical Debt

## Investigation Phase
- [x] Reproduce the issue
- [x] Identify affected code paths
- [x] Document current behavior
- [x] Find root cause

## Design Phase
- [x] Propose solution
- [x] Identify files to modify
- [x] Define state adjective list
- [x] Define display name composition logic
- [x] Consider migration for existing items

## Implementation Phase
- [x] Create state adjective extractor utility (`src/services/item_state_extractor.py`)
- [x] Update spawn_item key generation
- [x] Update acquire_item key generation
- [x] Update create_entity in GM tools
- [x] Add display name composition method (`ItemManager.update_item_state()`)
- [x] Add/update tests (35 new tests)

## Verification Phase
- [x] Test new item creation
- [x] Test property changes update state
- [x] Test existing items still work
- [x] Run test suite (all relevant tests pass)

## Completion
- [x] Update README.md status to "Done"
- [ ] Create commit with `/commit`
