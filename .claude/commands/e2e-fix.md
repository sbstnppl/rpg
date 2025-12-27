# E2E Fix Command

Run E2E tests, analyze results, and fix issues autonomously.

## Usage

```
/e2e-fix
```

## Instructions

### 1. Display Start Banner

```
═══════════════════════════════════════════════════════════
E2E FIX ITERATION
═══════════════════════════════════════════════════════════
```

### 2. Run E2E Tests

```bash
rm -f logs/gm_e2e/live.log
.venv/bin/python scripts/gm_e2e_immersive_runner.py --quick --verbose 2>&1
```

Wait for tests to complete and capture the output.

### 3. Analyze Results

Parse the output for:
- **Scenario pass rate**: "Scenarios: X/Y passed"
- **Turn pass rate**: "Turns: X/Y passed (N%)"
- **Failure patterns**:
  - "Response is duplicate" → GM duplicate response issue
  - "Unkeyed:" → Grounding validation issue
  - "Tool '...' error:" → Tool execution issue
  - "No scene entities mentioned" → Hallucination issue

### 4. Decision Tree

**If 100% scenarios pass** (e.g., "Scenarios: 5/5 passed"):
```
═══════════════════════════════════════════════════════════
RESULT: PASS
- Tests: 5/5 scenarios passing
- Action: No fixes needed
═══════════════════════════════════════════════════════════
```
Exit cleanly (this signals success to the bash loop).

**If issues found**:

1. **Check existing issues**: Look in `docs/issues/` for related issue folders
2. **Identify the most common/severe failure type**
3. **Investigate**:
   - Read relevant source files
   - Understand the root cause
   - Determine if a code fix is feasible

4. **If fix is feasible**:
   - Implement the fix
   - Run tests again to verify improvement
   - If improved → Use `/commit` pattern to commit
   - Display result:
   ```
   ═══════════════════════════════════════════════════════════
   RESULT: FIXED
   - Tests: X/Y scenarios passing (was: A/B)
   - Action: Fixed <description of fix>
   ═══════════════════════════════════════════════════════════
   ```

5. **If fix requires human input**:
   - Document findings in existing or new issue folder
   - Display result:
   ```
   ═══════════════════════════════════════════════════════════
   RESULT: BLOCKED
   - Tests: X/Y scenarios passing
   - Action: Documented issue, needs human decision
   - Issue: docs/issues/<folder>/
   ═══════════════════════════════════════════════════════════
   ```

6. **If no actionable fix found**:
   - Update issue docs with findings
   - Display result:
   ```
   ═══════════════════════════════════════════════════════════
   RESULT: NO_ACTION
   - Tests: X/Y scenarios passing
   - Action: No fix identified this iteration
   ═══════════════════════════════════════════════════════════
   ```

## Common Issue Patterns

| Pattern | Root Cause Area | Files to Check |
|---------|-----------------|----------------|
| "Response is duplicate (100% similar)" | GM not varying responses | `src/gm/gm_node.py`, `src/gm/prompts.py` |
| "Unkeyed: <name>" | Grounding validation | `src/gm/grounding_validator.py` |
| "Tool '...' error:" | Tool implementation | `src/gm/tools.py` |
| "No scene entities mentioned" | Context/hallucination | `src/gm/context_builder.py` |
| "Character break detected" | Prompt leaking | `src/gm/prompts.py` |

## Rules

1. **One fix per iteration**: Fix one issue, commit, then exit
2. **Don't break existing functionality**: Run tests before and after
3. **Document everything**: Update issue docs with findings
4. **Use /commit pattern**: Proper commit messages with CHANGELOG updates
5. **Exit cleanly**: Always end with a RESULT banner
