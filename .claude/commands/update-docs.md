# Update Docs Command

Audit and update project documentation to match the current codebase state.

## Prerequisites

**Before proceeding**, verify the working tree is clean:
```bash
git status
```

If there are uncommitted or untracked files:
1. Display: "Working tree has uncommitted changes. Running /commit first..."
2. Execute the `/commit` skill
3. After commit completes, proceed with documentation update

## Instructions

### Phase 1: Analysis (Run in Parallel)

Execute these three analysis tasks simultaneously:

#### 1A. Changelog Investigation
Read `CHANGELOG.md` and extract:
- All items under `[Unreleased]` section
- Note feature names, file paths mentioned
- Count entries in `### Added`, `### Fixed`, `### Changed`

#### 1B. Git History Analysis
```bash
git log --oneline -30
```
Extract:
- Recent commit messages (especially `feat:`, `fix:`, `refactor:`)
- Commits that may need documentation but lack it
- Feature themes and patterns

#### 1C. Codebase Statistics
Count current components:

```bash
# Manager classes
find src/managers -name "*.py" -not -name "__init__.py" | wc -l

# Agent nodes
find src/agents/nodes -name "*.py" -not -name "__init__.py" | wc -l

# Database models
find src/database/models -name "*.py" -not -name "__init__.py" | wc -l

# CLI command modules
find src/cli/commands -name "*.py" -not -name "__init__.py" | wc -l

# Test files and test functions
find tests -name "test_*.py" | wc -l
grep -r "^def test_\|^    def test_\|^async def test_" tests --include="*.py" | wc -l

# Subagents and slash commands
ls .claude/agents/*.md | wc -l
ls .claude/commands/*.md | wc -l
```

Store these counts for comparison.

### Phase 2: Comparison (Run in Parallel)

Compare documentation with codebase to identify gaps:

#### 2A. CLAUDE.md Audit
Read `CLAUDE.md` and compare:

| Section | Check Against |
|---------|---------------|
| Project Statistics table | Actual counts from 1C |
| Subagent table | Files in `.claude/agents/` |
| Key Documentation list | Files in `.claude/docs/` |
| Quick Commands | Actual CLI commands |

#### 2B. architecture.md Audit
Read `docs/architecture.md` and compare:

| Section | Check Against |
|---------|---------------|
| Game Pipelines | Actual pipelines in `src/agents/graph.py` |
| Manager Pattern list | Files in `src/managers/` |
| Agent descriptions | Files in `src/agents/nodes/` |

#### 2C. implementation-plan.md Audit
Read `docs/implementation-plan.md` and compare:

| Check | Action |
|-------|--------|
| Unchecked items `- [ ]` | Verify if actually implemented |
| Test counts | Compare with actual test count |
| Phase completion status | Verify all items are checked |

#### 2D. User Guide Audit
Read `docs/user-guide.md` and compare:

| Section | Check Against |
|---------|---------------|
| Special Commands tables | Actual commands in game.py |
| Pipeline Options | Current pipelines available |

### Phase 3: Update Documentation

For each discrepancy found, apply updates:

#### 3A. Update CLAUDE.md

**Statistics Table** (always update if changed):
```markdown
| Category | Count |
|----------|-------|
| **Test Functions** | {count} across {file_count} test files |
| **Manager Classes** | {count} specialized managers in `src/managers/` |
| **Agent Nodes** | {count} LangGraph nodes in `src/agents/nodes/` |
| **Database Models** | {count} model files in `src/database/models/` |
| **CLI Commands** | {count} command modules in `src/cli/commands/` |
```

**Subagent Table**: Add any agents in `.claude/agents/` not in the table.

#### 3B. Update architecture.md

**New Managers**: Add to Manager Pattern section.
**New Agent Nodes**: Add to appropriate pipeline section.
**New Models**: Add to Database Architecture section.

#### 3C. Update implementation-plan.md

**Mark Completed Items**: Change `- [ ]` to `- [x]` for implemented features.
**Update Counts**: Fix any outdated component counts.

#### 3D. Update user-guide.md

**New Commands**: Add to Special Commands tables.
**Pipeline Changes**: Update Pipeline Options section.

### Phase 4: Report

Generate a summary report:

```
═══════════════════════════════════════════════════════════════
DOCUMENTATION UPDATE REPORT
═══════════════════════════════════════════════════════════════

STATISTICS UPDATED:
  - Test functions: 3,186 → 3,372 (+186)
  - Manager classes: 52 → 53 (+1)

FILES MODIFIED:
  ✓ CLAUDE.md - Updated statistics table
  ✓ docs/architecture.md - Added new manager section

ITEMS NEEDING MANUAL ATTENTION:
  ⚠ New manager needs architecture description
  ⚠ CHANGELOG [Unreleased] has many items - consider release

NO CHANGES NEEDED:
  ✓ docs/user-guide.md - Already up to date

═══════════════════════════════════════════════════════════════
```

## Documentation Files to Update

| File | Check | Update |
|------|-------|--------|
| CLAUDE.md | Statistics, tables | Counts, subagents |
| docs/architecture.md | Managers, agents, pipelines | Add/remove components |
| docs/implementation-plan.md | Checkboxes, counts | Mark complete, update stats |
| docs/user-guide.md | CLI commands | Add new commands |

## Important Rules

1. **Clean working tree first** - Run /commit if dirty
2. **NEVER guess content** - Only document what exists
3. **NEVER modify code** - Documentation only
4. **Flag uncertainties** - Add to "Manual Attention" list
5. **Preserve formatting** - Match existing document styles
6. **Be specific** - Include file paths in all references
7. **Count accurately** - Run actual commands, don't estimate

## Things That Need Manual Attention

Always flag these for human review:
- New architectural patterns (need design documentation)
- Complex features (need expanded explanations)
- Breaking changes (need migration guides)
- Unclear component purposes (need investigation)

## Example Workflow

**User runs**: `/update-docs`

**Working tree check**:
```
Working tree is clean. Proceeding with documentation audit...
```

**Phase 1 output**:
```
Analyzing codebase...
  ✓ CHANGELOG.md: 8 items in [Unreleased]
  ✓ Git log: 30 commits analyzed
  ✓ Statistics gathered:
    - 53 managers (was 52 in docs)
    - 24 agent nodes (was 18 in docs)
```

**Phase 2 output**:
```
Comparing documentation...
  ⚠ CLAUDE.md: Statistics table outdated
  ⚠ architecture.md: Missing 6 new agent nodes
  ✓ implementation-plan.md: All items checked correctly
```

**Phase 3** (Claude edits files):
```
Updating CLAUDE.md...
  - Updated Project Statistics table
Updating architecture.md...
  - Added NeedsValidatorNode section
```

**Phase 4 report**: (shows summary)

**Done**:
```
Documentation updates complete. Run /commit to commit these changes.
```
