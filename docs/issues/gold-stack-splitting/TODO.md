# TODO: Gold Stack Splitting

## Investigation Phase
- [x] Reproduce the issue
- [x] Identify affected code paths
- [x] Document current behavior
- [x] Find root cause

## Design Phase
- [x] Decide on approach (quantity field vs workaround)
- [x] Identify files to modify
- [x] Define test cases
- [x] Review with user (if needed)

## Implementation Phase
- [x] Add quantity field to Item model (already existed!)
- [x] Create migration (not needed - fields existed)
- [x] Add ItemManager stacking methods (split_stack, merge_stacks, find_mergeable_stack, transfer_quantity)
- [x] Update drop_item/take_item/give_item tools with quantity parameter
- [x] Add tests for ItemManager stacking (23 tests)
- [x] Add tests for GM tools stacking (9 tests)

## Verification Phase
- [x] Test with stackable items (gold/currency)
- [x] Test with non-stackable items (error handling)
- [x] Run test suite (32 new tests passing)
- [x] Verify fix works for original scenario

## Completion
- [x] Update README.md status to "Done"
- [x] Create commit with `/commit`
