# TODO: CREATE_ENTITY Delta Invalid 'location_key' Argument

## Investigation Phase
- [ ] Reproduce the issue
- [ ] Check Entity model for valid fields
- [ ] Check StateDelta schema for field definitions
- [ ] Find where 'location_key' is being added to delta

## Design Phase
- [ ] Map location_key to correct Entity field
- [ ] Define proper delta schema for entity creation
- [ ] Define test cases

## Implementation Phase
- [ ] Fix delta schema to use valid Entity fields
- [ ] Add validation for delta fields
- [ ] Add/update tests

## Verification Phase
- [ ] Test entity creation manually
- [ ] Run test suite
- [ ] Verify items are created in correct location

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
