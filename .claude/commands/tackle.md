# Tackle Command

Load and work on an **existing issue** from the docs folder, or verify a completed fix.

## Usage

```
/tackle <issue-folder-name>          # Work on an issue
/tackle verify <issue-folder-name>   # Record verification result
/tackle                              # Lists available issues
```

**Examples:**
```
/tackle narrator-key-format
/tackle verify item-state-desync-ref-based
/tackle                      # Shows list to choose from
```

## Instructions

### If `verify` subcommand - Record verification result:

1. **Verify folder exists**: `docs/issues/<issue-name>/README.md`

2. **Check status** - Must be "Awaiting Verification" or "In Progress"

3. **Ask for verification result**:
   ```
   Verification Result for: <issue-name>

   Did the fix work correctly during play-testing?

   1. ✓ Pass - Issue appears fixed
   2. ✗ Fail - Issue still occurs or regressed
   ```

4. **On PASS**:
   - Read current verification count (e.g., `0/3`)
   - Increment count (e.g., `1/3`)
   - Update "Last Verified" to today's date (YYYY-MM-DD)
   - If count reaches threshold (e.g., `3/3`):
     - Set Status to "Verified"
     - Move entire folder to `docs/issues/archived/<issue-name>/`
     - Report: "Issue verified and archived!"
   - Otherwise:
     - Keep Status as "Awaiting Verification"
     - Report: "Verification recorded: 1/3. Need X more successful play-tests."

5. **On FAIL**:
   - Reset verification count to `0/N` (keep the threshold)
   - Set Status back to "In Progress"
   - Update "Last Verified" to today's date
   - Report: "Verification failed - regression detected. Issue reopened."

6. **Display updated status**:
   ```
   ═══════════════════════════════════════════════════════════════
   VERIFICATION: <issue-name>
   ═══════════════════════════════════════════════════════════════

   Result: PASS ✓  (or FAIL ✗)
   Count: 2/3 → 3/3
   Status: Awaiting Verification → Verified

   Issue archived to: docs/issues/archived/<issue-name>/
   ═══════════════════════════════════════════════════════════════
   ```

### If no argument provided - List available issues:

1. **Scan docs/issues/ for issue folders** (folders with README.md containing "Status:")
   ```bash
   ls docs/issues/*/README.md
   ```

2. **For each folder, extract**:
   - Folder name
   - Status (from README.md)
   - Priority (from README.md)
   - First line of Problem Statement

3. **Display as table**:
   ```
   Available Issues:

   | Folder                              | Status        | Priority |
   |-------------------------------------|---------------|----------|
   | narrator-key-format                 | Investigating | High     |
   | context-aware-location-resolution   | Planned       | Medium   |

   Run: /tackle <folder-name>
   ```

4. **Wait for user to specify which issue**

### If argument provided - Load the issue:

1. **Verify folder exists**: `docs/issues/<issue-name>/README.md`

2. **Read README.md** to understand:
   - Problem Statement
   - Current Behavior
   - Expected Behavior
   - Proposed Solution (if any)
   - Files to Modify
   - Test Cases

3. **Read TODO.md** to get task list

4. **Update status** in README.md to "In Progress" if currently "Investigating" or "Planned"

5. **Load tasks into TodoWrite**:
   - Parse TODO.md checkboxes
   - Convert `- [ ]` items to pending todos
   - Convert `- [x]` items to completed todos
   - Group by phase (Investigation, Design, Implementation, Verification)

6. **Display issue summary**:
   ```
   ═══════════════════════════════════════════════════════════════
   TACKLING: Narrator Key Format Issue
   ═══════════════════════════════════════════════════════════════

   Priority: High
   Status: In Progress (was: Investigating)

   PROBLEM:
   The constrained narrator is not using the required [entity_key] format
   when referencing entities in the scene.

   CURRENT PHASE: Investigation

   NEXT TASKS:
   □ Read src/narrator/scene_narrator.py to understand current implementation
   □ Check what prompt is being sent to the LLM
   □ Verify NarratorManifest is correctly passed to narrator

   FILES TO CHECK:
   - src/narrator/scene_narrator.py
   - src/agents/nodes/constrained_narrator_node.py

   ═══════════════════════════════════════════════════════════════
   ```

7. **Begin work**:
   - Start with first uncompleted task from TODO.md
   - Read relevant files identified in "Files to Modify"
   - Update findings in README.md as you discover things

## During Work

As you work on the issue:

1. **Update README.md** with findings:
   - Add to "Investigation Notes" section
   - Fill in "Root Cause" when discovered
   - Update "Proposed Solution" when designed

2. **Update TODO.md** as tasks complete:
   - Change `- [ ]` to `- [x]` for completed items
   - Add new tasks if discovered

3. **Use TodoWrite** to track progress in current session

4. **When phase completes**, summarize progress:
   ```
   ✓ Investigation Phase Complete

   Root Cause: The narrator prompt doesn't include entity keys in context.

   Moving to: Design Phase
   Next: Propose solution approach
   ```

## Completion

When all implementation tasks are done:

1. **Update README.md**:
   - Set Status to "Awaiting Verification"
   - Set Verification to `0/3` (or custom threshold)
   - Fill in all sections
   - Add completion date

2. **Prompt for commit**:
   ```
   Implementation complete! Run /commit to commit the fix?

   Note: Issue now needs 3 successful play-test verifications.
   After each play-test, run: /tackle verify <issue-name>
   ```

## Status Transitions

```
Investigating → In Progress (when tackled)
Planned → In Progress (when tackled)
In Progress → Awaiting Verification (when implementation complete)
In Progress → Blocked (if waiting on something)
Awaiting Verification → Verified (when verification count reaches threshold)
Awaiting Verification → In Progress (when verification fails - regression)
```

## Verification Fields

Add these fields to README.md after Status/Priority:
```markdown
**Verification:** 0/3
**Last Verified:** -
```

- **Format**: `current/required` (e.g., `0/3`, `2/5`)
- **Default threshold**: 3 (configurable per-issue by changing the number)
- **Last Verified**: date (YYYY-MM-DD) or `-` if never verified

## Example Session

**User:** `/tackle`

**Claude:**
```
Available Issues:

| Folder                              | Status        | Priority |
|-------------------------------------|---------------|----------|
| narrator-key-format                 | Investigating | High     |
| context-aware-location-resolution   | Planned       | Medium   |

Which issue do you want to tackle?
```

**User:** `/tackle narrator-key-format`

**Claude:**
```
═══════════════════════════════════════════════════════════════
TACKLING: Narrator Key Format Issue
═══════════════════════════════════════════════════════════════

Priority: High
Status: In Progress

PROBLEM:
The constrained narrator is not using the required [entity_key] format...

Starting Investigation Phase...
Reading src/narrator/scene_narrator.py...
```

*[Claude reads files, updates findings, completes tasks]*

---

**User:** `/tackle verify narrator-key-format`

**Claude:**
```
Verification Result for: narrator-key-format

Did the fix work correctly during play-testing?

1. ✓ Pass - Issue appears fixed
2. ✗ Fail - Issue still occurs or regressed
```

**User:** 1

**Claude:**
```
═══════════════════════════════════════════════════════════════
VERIFICATION: narrator-key-format
═══════════════════════════════════════════════════════════════

Result: PASS ✓
Count: 0/3 → 1/3
Status: Awaiting Verification

Need 2 more successful play-tests to verify this fix.
Next: Play-test and run /tackle verify narrator-key-format
═══════════════════════════════════════════════════════════════
```

---

**User:** `/tackle verify narrator-key-format` (after 2 more passes)

**Claude:**
```
═══════════════════════════════════════════════════════════════
VERIFICATION: narrator-key-format
═══════════════════════════════════════════════════════════════

Result: PASS ✓
Count: 2/3 → 3/3
Status: Awaiting Verification → Verified

Issue archived to: docs/issues/archived/narrator-key-format/
═══════════════════════════════════════════════════════════════
```
