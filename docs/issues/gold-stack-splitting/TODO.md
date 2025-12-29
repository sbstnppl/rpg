# TODO: Gold Stack Splitting

## Investigation Phase
- [x] Reproduce the issue
- [x] Identify affected code paths
- [x] Document current behavior
- [x] Find root cause

## Design Phase
- [ ] Decide on approach (quantity field vs workaround)
- [ ] Identify files to modify
- [ ] Define test cases
- [ ] Review with user (if needed)

## Implementation Phase
- [ ] Add quantity field to Item model
- [ ] Create migration
- [ ] Update drop_item/take_item/give_item tools
- [ ] Implement stack splitting logic
- [ ] Add/update tests

## Verification Phase
- [ ] Test manually with gold/currency
- [ ] Test with other stackable items
- [ ] Run test suite
- [ ] Verify fix in gameplay

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
