# Play Test - Interactive Gameplay Testing

Launch a gameplay session where Claude plays the game naturally while monitoring
for issues and comparing against documented expectations.

## Usage

```
/play-test
```

## Pre-requisites

- Ollama running with qwen3:32b model (for reasoning) and optionally magmell:32b (for narration)
- Database accessible
- Quantum anticipation (optional): Set `quantum_anticipation_enabled = True` in `src/config.py`

## Instructions

### Phase 1: Setup

1. **Read documentation for expectations**:
   - Read `docs/gm-pipeline-e2e-testing.md` for general expectations
   - Read `docs/quantum-branching/README.md` for quantum pipeline specifics
   - Note: LLM is qwen3 via Ollama (reasoning) and magmell (narration), not Anthropic

2. **Create game session**:
   ```bash
   source .venv/bin/activate && python -m src.main game start --auto
   ```
   - Note the session ID from output
   - Game creates: player character, starting location, initial NPCs/items

3. **Initialize tracking** (use TodoWrite):
   - Milestones: 0
   - Issues: 0
   - Turn: 0

### Phase 2: Gameplay Loop

**Repeat until stop condition:**

Execute each turn using the quantum pipeline:
   ```bash
   python -m src.main game turn -p quantum -s <session_id> "<player input>"
   ```

Alternative: Use the interactive `play` command (quantum is default):
   ```bash
   python -m src.main play -s <session_id>
   ```

1. **Decide action naturally** - Play like a human exploring:
   - Look around the environment
   - Talk to NPCs you encounter
   - Pick up interesting items
   - Try actions that seem appropriate
   - React naturally to the narrative

2. **Execute action** - Type into the game prompt

3. **Observe response** - Note from game output:
   - Narrative displayed
   - Skill check results (dice rolls)
   - Time passed
   - Any errors
   - Pipeline phase indicators (quantum_match, quantum_collapse, etc.)

4. **Inspect audit log** - Read the latest turn log:
   ```bash
   ls -t logs/llm/session_{SESSION_ID}/ | head -1
   ```
   Then read that file to see:
   - System prompt sent to LLM
   - Messages/context provided
   - Branch predictions and matches
   - Raw LLM response
   - Token usage

5. **Query database** for state verification:
   ```bash
   PGPASSWORD=bRXAKO0T8t23Wz3l9tyB psql -h 138.199.236.25 -U langgraphrpg -d langgraphrpg
   ```
   Key queries:
   - Time: `SELECT current_day, current_time FROM time_states WHERE session_id = {ID};`
   - Needs: `SELECT hunger, thirst, stamina FROM character_needs WHERE session_id = {ID};`
   - Items: `SELECT display_name, holder_id FROM items WHERE session_id = {ID};`

6. **Check quantum anticipation** (if enabled):

   In the output or logs, look for quantum pipeline phases:
   - `"Checking prepared outcomes..."` → Branch matching phase
   - `"Rolling dice..."` → Branch collapse (cache HIT - instant response)
   - `"Generating narrative..."` → Cache MISS (LLM generation required)

   Check anticipation activity:
   ```bash
   # In logs, grep for quantum anticipation
   grep -r "quantum\|branch\|cache\|anticipat" logs/llm/session_{SESSION_ID}/
   ```

   With `--anticipation` enabled, the system pre-generates likely action outcomes in the background.

7. **Validate anticipated branches** (if anticipation enabled):

   The quantum pipeline validates pre-generated branches before use. Check validation health:

   ```bash
   # Check for validation issues in logs
   grep -rE "ValidationIssue|grounding.*ERROR|ai_identity|StaleStateError" logs/llm/session_{SESSION_ID}/

   # Check branch cache metrics
   grep -r "cache_hit\|cache_miss\|branch_expired\|branch_invalidated" logs/llm/session_{SESSION_ID}/

   # Check delta post-processing (repairs, clarifications, regenerations)
   grep -rE "Repaired|RegenerationNeeded|clarify|unknown_key" logs/llm/session_{SESSION_ID}/
   ```

   **Validation checks performed by quantum pipeline:**

   | Validator | Checks | Error = Branch Rejected |
   |-----------|--------|-------------------------|
   | Grounding | `[key:text]` refs exist in manifest | Invalid entity keys |
   | AI Identity | No "I'm an AI/assistant" leaks | Character break in pre-gen |
   | Meta-questions | No "what would you do?" endings | Immersion-breaking prompts |
   | Placeholders | No `[TODO]`, `<placeholder>` | Incomplete generation |
   | Delta conflicts | No CREATE+DELETE same entity | Inconsistent state changes |
   | Staleness | Expected state = current state | World changed since generation |
   | **DeltaPostProcessor** | Unknown keys, missing creates, value ranges | Auto-repaired or clarified |

   **What to look for:**

   | Log Pattern | Meaning | Action |
   |-------------|---------|--------|
   | `grounding.*ERROR` | Invalid entity reference | Create /issue |
   | `ai_identity` | Character break in cached branch | Create /issue |
   | `StaleStateError` | Branch rejected at collapse (OK) | Note in observations |
   | `branch_expired` | TTL exceeded (normal) | Note if excessive |
   | `branch_invalidated` | Location state changed (normal) | Note count |
   | `Repaired.*delta` | DeltaPostProcessor auto-fixed issues (OK) | Note pattern |
   | `RegenerationNeeded` | Deltas unfixable, branch regenerated | Note frequency |
   | `clarify.*unknown` | LLM asked to clarify entity key | Note if excessive |

   **Healthy anticipation metrics:**
   - Cache hit rate > 30% after 5+ turns
   - Zero grounding ERRORs
   - Zero AI identity leaks
   - Some StaleStateErrors OK (shows detection working)
   - Delta repairs occasional (shows auto-fix working)
   - Zero RegenerationNeeded (repairs should handle most issues)
   - Clarifications rare (LLM usually gets keys right)

8. **Compare against expectations**:

   | Check | Expected |
   |-------|----------|
   | Narrative length | >= 50 chars |
   | Perspective | Second-person ("you" not "the player") |
   | Character breaks | None: "my name is", "i'm an ai", "feel free to ask", etc. |
   | Skill checks | Appropriate for uncertain outcomes |
   | Time passed | Reasonable (dialog < 10 min, travel 10-30 min) |
   | State changes | Match narrative |
   | Branch collapse | Dice rolled at runtime, not pre-determined |

   **Time expectations reference:**
   | Action | Duration |
   |--------|----------|
   | Greeting/brief dialog | < 1 min |
   | Full conversation | 2-10 min |
   | Take/drop item | < 1 min |
   | Local movement | 1-2 min |
   | Travel (nearby) | 10-30 min |
   | Eating | 5-30 min |
   | Drinking | 1-5 min |
   | Skill check | 1-10 min |

9. **Record milestone** if criteria met:
   - First good narrative → "Scene Introduction"
   - NPC dialog → "Dialog Exchange"
   - Item take/drop/use → "Item Interaction"
   - Dice roll with visible result → "Skill Check"
   - Time > 5 min → "Time Passage"
   - Quantum branch cache hit → "Branch Cache Hit" (if anticipation enabled)
   - Zero validation errors in branches → "Clean Branch Validation" (if anticipation enabled)
   - Ref-based entity resolution works → "Ref-Based Resolution" (if --ref-based enabled)

10. **Create issue** if problem found:
   - Run `/issue <brief description of problem>`
   - Let the issue command create the folder and README
   - Continue playing after creating issue

### Phase 3: Stop Conditions

Stop the loop when ANY of these occur:
- **5+ milestones** reached (success case)
- **100 turns** played (timeout)
- **Reasonable issue count** - enough to discuss (usually 3-5 significant issues)

To quit the game: type `quit` or `/quit`

### Phase 4: Final Report

Display summary in this format:

```
═══════════════════════════════════════════
PLAY TEST REPORT
═══════════════════════════════════════════

Session ID: {id}
Pipeline: Quantum
Turns Played: {n}
Milestones Reached: {m}/7

MILESTONES:
[✓] Scene Introduction - Turn 1
[✓] Dialog Exchange - Turn 3
[ ] Item Interaction
[ ] Skill Check
[ ] Time Passage
[ ] Branch Cache Hit (if anticipation enabled)
[ ] Clean Branch Validation (if anticipation enabled)
[ ] Ref-Based Resolution (if --ref-based enabled)

ISSUES CREATED:
1. {issue-folder-1} - {brief description}
2. {issue-folder-2} - {brief description}

OBSERVATIONS:
- {Any patterns noticed}
- {Recommendations}

Log location: logs/llm/session_{id}/
```

## Important Notes

- **Pipeline**: Quantum branching pipeline (pre-generates action outcomes)
- **LLM Models**: qwen3:32b (reasoning/tools) and magmell:32b (narration) via Ollama
- **Play naturally**: Don't follow a script, explore like a curious player
- **Be thorough**: Check audit logs and database, don't just trust the output
- **Create issues promptly**: Use /issue for each problem, don't batch them
- **Keep playing**: Don't stop for minor issues, document and continue

## Architecture Modes

The quantum pipeline supports different internal architectures for entity resolution:

| Mode | Flag | Description |
|------|------|-------------|
| Default | (none) | Original branch generator with fuzzy entity matching |
| Split | `--split` | Separates reasoning (Phase 2) from narration (Phase 4) |
| **Ref-Based** | `--ref-based` | Uses A/B/C refs for deterministic entity resolution |

### Ref-Based Architecture (Recommended for Testing)

The ref-based architecture eliminates fuzzy matching by assigning single-letter refs to entities:

```bash
# Single turn with ref-based
python -m src.main game turn --ref-based -s <session_id> "pick up the sword"

# Interactive play with ref-based
python -m src.main play --ref-based -s <session_id>
```

**How it works:**
1. Entities get refs: `[A] rusty sword - on the table`, `[B] rusty sword - on the wall`
2. LLM outputs: `{"entity": "A"}` instead of display names
3. Code does direct lookup: `A → rusty_sword_01` (no fuzzy matching)
4. Invalid refs produce clear errors (not guessed)

**Benefits:**
- Deterministic entity resolution
- No ambiguity with duplicate display names
- Clear error messages for invalid refs

## Pipeline Options

| Pipeline | Command | Use Case |
|----------|---------|----------|
| `quantum` (default) | `-p quantum` or `-p q` | Pre-generated branches, instant responses |
| `gm` | `-p gm` | Simplified GM pipeline, tool-based |
| `system-authority` | `-p system-authority` | System decides outcomes mechanically |
| `legacy` | `-p legacy` | Original LLM-decides-everything |

## Troubleshooting

- **Ollama not running**: Start with `ollama serve`
- **Database connection failed**: Check `.env` for DATABASE_URL
- **No audit logs**: Check `logs/llm/` directory exists
- **Game crashes**: Check for stack trace, create /issue
- **Slow responses**: Check if anticipation is enabled (`quantum_anticipation_enabled` in config)
- **No cache hits**: Anticipation pre-generates after first turn; try multiple turns
- **Branch mismatch**: Player input didn't match predicted actions; falls back to LLM generation
- **Grounding errors in branches**: Check `GroundingManifest` includes all scene entities
- **AI identity in cached content**: Branch generator prompt needs stricter character rules
- **Excessive StaleStateErrors**: Anticipation cycle too slow, state changing before collapse
- **Delta conflicts**: Usually auto-repaired; if `RegenerationNeeded`, check branch generator prompt
- **Invalid ref error**: LLM output a ref (like "X") that doesn't exist in manifest
- **Excessive clarifications**: LLM keeps using wrong entity keys; may need better context in prompt
- **RegenerationNeeded loops**: DeltaPostProcessor can't fix errors; check for structural issues
- **Ref-based fallback**: Check if `reason_with_refs()` prompt includes entity list correctly

## Config Reference

Key settings in `src/config.py`:
```python
# Task-specific models
narrator: str = "ollama:magmell:32b"   # Prose narration
reasoning: str = "ollama:qwen3:32b"    # Tools, extraction, intent

# Quantum pipeline settings
quantum_anticipation_enabled: bool = False  # Enable background pre-generation
quantum_max_actions_per_cycle: int = 5      # Actions to pre-generate
quantum_min_match_confidence: float = 0.7   # Minimum match score
```
