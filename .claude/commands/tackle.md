# Tackle Command

Load and work on an **existing issue** from the docs folder.

## Usage

```
/tackle <issue-folder-name>
/tackle                      # Lists available issues
```

**Examples:**
```
/tackle narrator-key-format
/tackle context-aware-location-resolution
/tackle                      # Shows list to choose from
```

## Instructions

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

When all tasks are done:

1. **Update README.md**:
   - Set Status to "Done"
   - Fill in all sections
   - Add completion date

2. **Prompt for commit**:
   ```
   Issue resolved! Run /commit to commit the fix?
   ```

## Status Transitions

```
Investigating → In Progress (when tackled)
Planned → In Progress (when tackled)
In Progress → Done (when all tasks complete)
In Progress → Blocked (if waiting on something)
```

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
