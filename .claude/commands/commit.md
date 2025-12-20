# Commit Command

Create a git commit with **automatic documentation updates**.

## Instructions

1. Check git status to see changed/staged files
2. Show diff of changes (staged and unstaged)
3. Review recent commits for message style

## Documentation Updates (AUTOMATIC)

4. **Analyze the changes** and determine commit type:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `refactor:` - Code refactoring
   - `docs:` / `test:` / `chore:` - No doc updates needed

5. **For feat: or fix: commits**, update documentation:

   a. **Update CHANGELOG.md**:
      - Read current CHANGELOG.md to find `[Unreleased]` section
      - Add entry under `### Added` (feat) or `### Fixed` (fix)
      - Format: `- **Feature Name** - Brief description`
      - Include key file paths: `(key file: \`src/path/file.py\`)`
      - Use Edit tool to add the entry

   b. **For new files, update implementation-plan.md**:
      - New managers in `src/managers/` → Add to relevant phase
      - New agents/nodes in `src/agents/` → Add to agent phase
      - New models in `src/database/models/` → Add to database phase
      - Use Edit tool to add entries with `[x]` checkmarks

   c. **For architectural changes, update architecture.md**:
      - New manager classes → Add manager section with methods
      - New pipeline nodes → Add to flow diagram
      - New patterns → Document the pattern

   d. **Check for missing docstrings** in new public methods:
      - If a new public method lacks a docstring, add one
      - Use Google-style: Args, Returns, Raises

6. **Stage all documentation updates**:
   ```bash
   git add CHANGELOG.md docs/*.md  # if modified
   ```

7. **Create commit** with message:
   ```
   type(scope): brief description

   - Key change 1
   - Key change 2

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
   ```

8. Show git status after commit to verify success

## Documentation Update Templates

### CHANGELOG Entry Format
```markdown
- **Feature Name** - Brief one-line description
  - Detail 1 (key file: `src/path/file.py`)
  - Detail 2
```

### Implementation Plan Entry Format
```markdown
- [x] Create `src/path/file.py` - ClassName
  - `method_name()` - What it does
```

## Important Rules

- **ALWAYS** update documentation for `feat:` and `fix:` commits
- **DO NOT** commit files with secrets (.env, credentials.json, etc.)
- **NEVER** push unless explicitly asked
- **NEVER** skip documentation - this creates technical debt
- Use HEREDOC for multi-line commit messages
- Use Edit tool for all documentation updates

## Commit Type Documentation Matrix

| Type | CHANGELOG | impl-plan | architecture |
|------|-----------|-----------|--------------|
| feat | ✓ Required | ✓ If new files | ✓ If new patterns |
| fix | ✓ Required | - | - |
| refactor | Optional | - | ✓ If patterns change |
| docs | - | - | - |
| test | - | - | - |
| chore | - | - | - |

## Example Workflow

**User runs**: `/commit`

**Changes detected**: New `SnapshotManager` class in `src/managers/snapshot_manager.py`

**Claude actions**:
1. Reads CHANGELOG.md
2. Edits to add under `### Added`:
   ```markdown
   - **Game History & Reset System** - Session state management with snapshots
     - New `SnapshotManager` class (`src/managers/snapshot_manager.py`)
     - `game history` and `game reset` CLI commands
   ```
3. Reads implementation-plan.md
4. Edits to add Phase 17: Session Management section
5. Stages: `git add CHANGELOG.md docs/implementation-plan.md src/managers/snapshot_manager.py`
6. Creates commit:
   ```
   feat(session): add game history and reset commands with snapshot system

   - SnapshotManager captures all session tables at each turn
   - game history command shows turn history
   - game reset command restores to previous state

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
   ```
7. Shows `git status` confirming clean working tree
