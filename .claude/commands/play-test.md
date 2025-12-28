# Play Test - Interactive Gameplay Testing

Launch a gameplay session where Claude plays the game naturally while monitoring
for issues and comparing against documented expectations.

## Usage

```
/play-test
```

## Pre-requisites

- Ollama running with qwen3:32b model
- Database accessible

## Instructions

### Phase 1: Setup

1. **Read documentation for expectations**:
   - Read `docs/gm-pipeline-e2e-testing.md`
   - Note: LLM is qwen3 via Ollama, not Anthropic

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

Execute each turn by
   ```bash
   python -m src.main game turn -p gm -s <session_id> "<player input>"
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
   - Tool calls shown (if verbose)
   - Time passed
   - Any errors

4. **Inspect audit log** - Read the latest turn log:
   ```bash
   ls -t logs/llm/session_{SESSION_ID}/ | head -1
   ```
   Then read that file to see:
   - System prompt sent to LLM
   - Messages/context provided
   - Tool calls made and results
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

6. **Compare against expectations**:

   | Check | Expected |
   |-------|----------|
   | Narrative length | >= 50 chars |
   | Perspective | Second-person ("you" not "the player") |
   | Character breaks | None: "my name is", "i'm an ai", "feel free to ask", etc. |
   | Tool calls | Appropriate for action type |
   | Time passed | Reasonable (dialog < 10 min, travel 10-30 min) |
   | State changes | Match narrative |

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

7. **Record milestone** if criteria met:
   - First good narrative → "Scene Introduction"
   - NPC dialog → "Dialog Exchange"
   - Item take/drop/use → "Item Interaction"
   - Dice roll (skill_check tool) → "Skill Check"
   - Time > 5 min → "Time Passage"

8. **Create issue** if problem found:
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
Turns Played: {n}
Milestones Reached: {m}/5

MILESTONES:
[✓] Scene Introduction - Turn 1
[✓] Dialog Exchange - Turn 3
[ ] Item Interaction
[ ] Skill Check
[ ] Time Passage

ISSUES CREATED:
1. {issue-folder-1} - {brief description}
2. {issue-folder-2} - {brief description}

OBSERVATIONS:
- {Any patterns noticed}
- {Recommendations}

Log location: logs/llm/session_{id}/
```

## Important Notes

- **LLM Model**: qwen3 via Ollama (not Anthropic)
- **Play naturally**: Don't follow a script, explore like a curious player
- **Be thorough**: Check audit logs and database, don't just trust the output
- **Create issues promptly**: Use /issue for each problem, don't batch them
- **Keep playing**: Don't stop for minor issues, document and continue

## Troubleshooting

- **Ollama not running**: Start with `ollama serve`
- **Database connection failed**: Check `.env` for DATABASE_URL
- **No audit logs**: Check `logs/llm/` directory exists
- **Game crashes**: Check for stack trace, create /issue
