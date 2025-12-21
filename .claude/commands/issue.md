# Issue Command

Create an **issue documentation folder** for tracking and resolving a detected problem or planned feature.

## Usage

```
/issue <issue description>
```

**Examples:**
```
/issue narrator not using [key] format for entities
/issue NPC schedules not updating when time advances
/issue add crafting system
```

## Instructions

1. **Parse the issue description** from user input (everything after `/issue`)

2. **Generate folder name** from description:
   - Convert to kebab-case
   - Remove common words (the, a, an, for, to, when, not)
   - Limit to 5-6 words max
   - Example: "narrator not using [key] format" → `narrator-key-format`

3. **Create folder structure**:
   ```
   docs/issues/<folder-name>/
   ├── README.md
   └── TODO.md
   ```

4. **Generate README.md** with this template:

```markdown
# <Issue Title>

**Status:** Investigating
**Priority:** Medium
**Detected:** <today's date YYYY-MM-DD>
**Related Sessions:** <current session context if applicable>

## Problem Statement

<Expand the issue description into 2-3 sentences explaining what's wrong or what's needed>

## Current Behavior

<To be filled during investigation>

## Expected Behavior

<What should happen instead>

## Investigation Notes

<Findings, code snippets, logs go here as you investigate>

## Root Cause

<After investigation - why is this happening?>

## Proposed Solution

<High-level approach to fix>

## Implementation Details

<Specific code changes, new classes, etc.>

## Files to Modify

- [ ] `src/...`
- [ ] `src/...`

## Test Cases

- [ ] Test case 1: <description>
- [ ] Test case 2: <description>

## Related Issues

- <links to related docs/issues>

## References

- <relevant code files, docs, external links>
```

5. **Generate TODO.md** with this template:

```markdown
# TODO: <Issue Title>

## Investigation Phase
- [ ] Reproduce the issue
- [ ] Identify affected code paths
- [ ] Document current behavior
- [ ] Find root cause

## Design Phase
- [ ] Propose solution
- [ ] Identify files to modify
- [ ] Define test cases
- [ ] Review with user (if needed)

## Implementation Phase
- [ ] Implement fix/feature
- [ ] Add/update tests
- [ ] Update documentation

## Verification Phase
- [ ] Test manually
- [ ] Run test suite
- [ ] Verify fix in gameplay

## Completion
- [ ] Update README.md status to "Done"
- [ ] Create commit with `/commit`
```

6. **If context is available**, pre-fill relevant sections:
   - If error messages were shown, add them to "Current Behavior"
   - If files were recently discussed, add them to "Files to Modify"
   - If a solution was proposed, add it to "Proposed Solution"

7. **Report success**:
   ```
   Created issue folder: docs/issues/<folder-name>/
   - README.md (issue documentation)
   - TODO.md (implementation checklist)

   Next steps:
   1. Read README.md to review/expand the issue
   2. Investigate and fill in findings
   3. Use TODO.md to track progress
   ```

## Auto-Detection Mode

If no description is provided (`/issue` alone), check recent conversation for:
- Error messages
- "Issue:", "Problem:", "Bug:" mentions
- Failed validations
- Unexpected behavior descriptions

Then ask user to confirm the detected issue before creating.

## Status Values

Use these in README.md:
- **Investigating** - Just created, gathering info
- **Planned** - Understood, solution designed
- **In Progress** - Actively being worked on
- **Blocked** - Waiting on something
- **Done** - Completed and verified

## Priority Guidelines

- **High** - Breaks core gameplay, blocks progress
- **Medium** - Annoying but workaroundable
- **Low** - Nice to have, polish item

## Example

**User runs:** `/issue narrator not using [key] format for entities`

**Creates:** `docs/issues/narrator-key-format/`

**README.md includes:**
```markdown
# Narrator Key Format Issue

**Status:** Investigating
**Priority:** Medium
**Detected:** 2024-12-21

## Problem Statement

The constrained narrator is not using the required `[entity_key]` format when
referencing entities in the scene. Instead of "[wooden_bucket_001]", it outputs
"Wooden Bucket", which breaks entity tracking and reference resolution.

## Current Behavior

Narrator output:
> The Well is at the center of the scene, with a Rope attached to it.

Validation errors:
- "'Well' mentioned without [key] format. Use [well_001]."
- "'Rope' mentioned without [key] format. Use [rope_001]."
...
```
