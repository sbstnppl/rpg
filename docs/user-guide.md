# RPG User Guide

## Getting Started

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd rpg

# Install dependencies
pip install -e .

# Set up database
createdb rpg_game
alembic upgrade head

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Create a `.env` file:
```
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
DATABASE_URL=postgresql://localhost/rpg_game
```

## Starting a New Game

### Quick Start

```bash
rpg start
```

The game will guide you through:
1. Choosing a setting (fantasy, contemporary, sci-fi, or custom)
2. Describing your character
3. Setting up the initial scenario

### Character Creation

When prompted, describe your character naturally:

```
> I want to play a young wizard named Aldric with grey eyes and a
> mysterious past. He's good at fire magic but terrible at social
> situations.
```

The AI will ask clarifying questions:
- Physical details (height, build, distinguishing features)
- Personality traits
- Background and motivations
- Starting equipment

Or say "surprise me" for a random character!

## Playing the Game

### Basic Commands

Just type what you want to do:
```
> I walk into the tavern and look around
> I draw my sword and confront the guard
> "Hello there, I'm looking for work" I say to the bartender
```

### Dialogue

Use quotes for speech:
```
> "Where can I find the blacksmith?" I ask the merchant
```

### Actions

Describe physical actions:
```
> I carefully pick the lock on the chest
> I climb through the window
> I search the body for valuables
```

### Combat

Combat triggers automatically when you engage hostiles:
```
> I attack the goblin with my axe
```

The game will roll dice and narrate the result.

### Special Commands

| Command | Description |
|---------|-------------|
| `/status` | View character stats |
| `/inventory` | List items you're carrying |
| `/equipment` | Show equipped items |
| `/tasks` | View active tasks and appointments |
| `/map` | Show known locations |
| `/time` | Check current time and day |
| `/save [name]` | Save game with optional name |
| `/load [name]` | Load a saved game |
| `/quit` | Exit game |

## Game Mechanics

### Attribute Checks

When you attempt something difficult, the game rolls dice:
```
You try to lift the heavy boulder...
[Strength Check: 15 + 3 = 18 vs DC 15] Success!
```

### Combat

Combat is turn-based with initiative:
1. Initiative rolled at start
2. Each turn, describe your action
3. Dice determine success/failure
4. Enemies act on their turns

### Time

Time passes as you act:
- Conversations: minutes
- Travel: varies by distance
- Combat: rounds (6 seconds each)
- Rest: hours

NPCs follow schedules, so the blacksmith might be closed at night!

### Relationships

NPCs remember you:
- Help them → Trust increases
- Lie to them → Trust decreases
- Be charming → Liking increases
- Miss appointments → Trust & Liking decrease

## Tips

1. **Be Specific**: "I check the desk drawers for hidden compartments" is better than "I search the room"

2. **Talk to NPCs**: They have information, quests, and items

3. **Keep Appointments**: Missing meetings hurts relationships

4. **Explore**: The world has secrets waiting to be found

5. **Actions Have Consequences**: Steal from the baker, and the town might hear about it

6. **Save Often**: Use `/save` before risky actions

## Troubleshooting

### "API key not found"
Check your `.env` file has valid API keys.

### "Database connection failed"
Ensure PostgreSQL is running and DATABASE_URL is correct.

### "Command not recognized"
Type naturally - the game understands plain English. Use `/help` for special commands.
