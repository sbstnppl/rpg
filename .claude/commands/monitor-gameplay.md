# Gameplay Monitoring Session

You are starting a gameplay monitoring and testing session. Your role is to observe the game as the user plays, verify that systems work correctly, and help debug any issues.

## Setup Instructions

1. First, read the gameplay testing guide to understand the system:
   - Read `.claude/docs/gameplay-testing-guide.md`

2. Review recent changes to understand what's new:
   - Run `git log --oneline -10` to see recent commits

3. Get the current session ID (if game is running):
   - The user will provide this, or check the database for active sessions

## Your Responsibilities During Monitoring

### Watch For
- **State/Narrative Drift**: GM describing things that didn't mechanically happen
- **Database Consistency**: Data being written to correct tables with correct values
- **Pipeline Flow**: Actions being parsed, validated, and executed correctly
- **Need System**: Needs decaying and being satisfied appropriately
- **Inventory**: Items moving correctly between owner/holder, body slots
- **Relationships**: Trust/liking/respect changing as expected

### When Issues Occur
1. Identify the symptom (what the user observed)
2. Check relevant database tables
3. Trace through the pipeline to find root cause
4. Propose and implement a fix if needed

### Useful Commands
- Database queries are in the testing guide
- Use `pytest -k "keyword"` to run relevant tests after fixes
- Check `src/cli/commands/game.py` for game loop logic
- Check `src/agents/nodes/` for pipeline node implementations

## Quick Reference

**Key Tables**: `turns`, `entities`, `items`, `character_needs`, `relationships`, `time_states`

**Key Managers**: `NeedsManager`, `ItemManager`, `EntityManager`, `LocationManager`, `RelationshipManager`

**Pipeline Flow**: ContextCompiler -> ParseIntent -> ValidateActions -> ComplicationOracle -> ExecuteActions -> Narrator -> Persistence

---

Ready to monitor. Please describe what you're testing or share any issues you observe.
