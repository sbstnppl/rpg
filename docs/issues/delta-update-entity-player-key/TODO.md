# TODO: Delta UPDATE_ENTITY Fails - Wrong Entity Key "player"

## Investigation Phase
- [ ] Reproduce the issue (movement action triggers delta)
- [ ] Find where "player" key is being set in delta
- [ ] Check branch generator for hardcoded "player" references
- [ ] Trace how player entity key flows through quantum pipeline

## Design Phase
- [ ] Propose fix for player key resolution
- [ ] Identify all places "player" is used as placeholder
- [ ] Define test cases for entity key validation

## Implementation Phase
- [ ] Fix branch generator to use actual player entity key
- [ ] Add validation in delta applier for entity existence
- [ ] Add/update tests

## Verification Phase
- [ ] Test movement action manually
- [ ] Run test suite
- [ ] Verify player location updates correctly

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
