# TODO: GM Unkeyed Entities in Responses

## Investigation Phase
- [x] Reproduce the issue with E2E test
- [x] Read narrator prompt template to check key format instructions
- [x] Check what NarratorManifest contains (are keys provided?)
- [x] Trace grounding validator retry logic
- [x] Check if player equipment is included in scene entities
- [x] Document root cause - TWO ISSUES FOUND:
  1. Player equipment false positives (validator bug)
  2. NPC names genuinely unkeyed (LLM instruction-following)

## Part 1: Player Equipment False Positives (DONE)
- [x] Design solution: Skip player items in grounding validation
- [x] Implement fix in grounding_validator.py
- [x] Verify: Equipment mentions no longer trigger errors
- [x] Document changes in README.md

## Part 2: NPC Key Format Compliance (TODO)
- [ ] Investigate why qwen3:32b ignores [key:text] format
- [ ] Consider stronger prompt emphasis for local LLMs
- [ ] Test with different models (anthropic cloud vs local)
- [ ] Implement prompt improvements if needed

## Verification Phase
- [x] Run E2E tests - player equipment errors eliminated
- [x] Confirmed: Only legitimate NPC name errors remain
- [ ] Run full test suite (pytest)
- [ ] Verify in manual gameplay

## Completion
- [x] Update README.md status to "Partially Fixed"
- [ ] Create commit with `/commit`
- [ ] Consider creating separate issue for Part 2
