# RPG User Guide

## Getting Started

### Installation

#### Prerequisites
- Python 3.11 or higher
- PostgreSQL database server
- API key for Anthropic Claude or OpenAI GPT

#### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd rpg

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e .           # Basic installation
# Or for development:
pip install -e ".[dev]"    # Includes pytest, black, ruff, mypy

# 4. Set up PostgreSQL database
createdb rpg_game

# 5. Configure environment
cp .env.example .env
# Edit .env with your API keys (see below)

# 6. Run database migrations
alembic upgrade head
```

### Configuration

Edit your `.env` file with your settings:

```bash
# Database (required)
DATABASE_URL=postgresql://localhost/rpg_game

# LLM API Keys (at least one required)
ANTHROPIC_API_KEY=your-anthropic-key-here
OPENAI_API_KEY=your-openai-key-here

# LLM Provider (anthropic or openai)
LLM_PROVIDER=anthropic

# Optional: Model selection (defaults shown)
# GM_MODEL=claude-sonnet-4-20250514
# EXTRACTION_MODEL=claude-sonnet-4-20250514
# CHEAP_MODEL=claude-haiku-3

# Optional: Debug settings
# DEBUG=false
# LOG_LLM_CALLS=false
```

## Starting a New Game

### Quick Start

```bash
rpg game start
```

### How It Works

The game uses a **Quantum Branching Pipeline**:
- Pre-generates outcome branches for likely player actions
- Uses dual-model separation (reasoning + narration)
- Rolls dice at runtime to determine which branch to use
- Ensures narrative and game state stay synchronized

The unified game wizard guides you through:
1. **Setting Selection** - Choose fantasy, contemporary, or sci-fi
2. **Session Naming** - Name your game save
3. **Character Creation** - 6-section wizard (see below)
4. **World Introduction** - The GM introduces your character in the opening scene

### Character Creation Wizard

The wizard walks you through 6 sections in order:

#### 1. Name & Species
- Choose your character's name
- Select species (human, elf, dwarf, etc. based on setting)
- The AI will suggest names if you're unsure

#### 2. Appearance
- Describe physical features: age, gender, build, height
- Hair color and style
- Eye color, skin tone
- Distinguishing features (scars, tattoos, birthmarks)

#### 3. Background
- Where are you from?
- What was your childhood like?
- What is your occupation or profession?
- How many years have you practiced it?
- Any significant life events?

#### 4. Personality
- How do you interact with others?
- What are your values and motivations?
- Any quirks or habits?
- Fears or goals?

#### 5. Attributes
The game uses a **two-tier stat system**:

**Hidden Potential** (rolled secretly, never shown):
- 4d6 drop lowest for each of 6 attributes
- Represents your innate "genetic gifts"

**Current Stats** (what you see):
- Your background shapes your visible stats
- Formula: `Potential + Age + Occupation + Lifestyle`
- A blacksmith will have higher STR regardless of potential
- A scholar will have higher INT

**The 6 Attributes**:
- **Strength (STR)** - Physical power, lifting, melee damage
- **Dexterity (DEX)** - Agility, reflexes, ranged accuracy
- **Constitution (CON)** - Endurance, hit points, resistance
- **Intelligence (INT)** - Knowledge, reasoning, spellcasting
- **Wisdom (WIS)** - Perception, willpower, insight
- **Charisma (CHA)** - Social influence, leadership, personality

**Twist Narratives**: If your stats don't match your background, the game explains why:
> "Despite years of farm work, strength never came naturally - compensating with technique and determination."

#### 6. Review
- See your complete character summary
- Confirm or go back to edit sections
- Character is only saved when you confirm

### What Happens After Creation

Once you confirm your character:

1. **Starting Equipment** assigned based on setting and backstory
   - Wealthy background? Pristine condition
   - Escaped prisoner? Minimal, worn equipment
   - Soldier? Standard military gear in good condition

2. **Initial Needs** set based on your story
   - Hardship backstory? Lower comfort, morale, hygiene
   - Loner background? Lower social connection
   - Strong sense of purpose? Higher morale

3. **NPCs from Backstory** created as "shadow entities"
   - Family members, mentors, rivals mentioned
   - Relationships already established (trust, liking, respect)
   - May appear later in the game

4. **Skills Inferred** from your background
   - Blacksmith? Blacksmithing, metalworking skills
   - Soldier? Combat, tactics, survival skills
   - Scholar? Research, history, languages

## Playing the Game

### Basic Interaction

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

The game handles initiative, rolls, and damage automatically.

## Skill Checks

When you attempt something challenging, the GM calls for a skill check.

This game uses a **2d10 bell curve system** instead of d20, making skilled characters more reliable. See `docs/game-mechanics.md` for detailed mechanics.

### Auto-Success

If you're skilled enough, routine tasks succeed automatically without rolling:
- **Rule**: If DC ≤ 10 + your total modifier, you auto-succeed
- **Example**: A master locksmith (+8) auto-succeeds any lock DC 18 or below
- You'll see: "AUTO-SUCCESS - This is routine for someone with your skill"

### Interactive Rolling

When a roll is needed, you'll see your modifiers first:

**Step 1: Pre-Roll Prompt**
```
┌─ Skill Check ─────────────────────────────────┐
│ Attempting to pick the merchant's lock        │
│                                               │
│ Your modifiers (2d10 + modifier):             │
│   Lockpicking: +3 (Expert)                   │
│   Dexterity: +2                              │
│   Total: +5                                  │
│                                               │
│ This looks challenging                        │
│                                               │
│ Press ENTER to roll...                        │
└───────────────────────────────────────────────┘
```

**Step 2: Press ENTER**
Watch the dice tumble!

**Step 3: See Results**
```
┌─ Result ──────────────────────────────────────┐
│ Roll: (8+7) +5 = 20                           │
│ vs DC 15                                      │
│                                               │
│ CLEAR SUCCESS                                 │
│ (margin: +5)                                  │
└───────────────────────────────────────────────┘
```

### Proficiency Tiers

Your skill levels are categorized:

| Proficiency | Tier | Bonus |
|-------------|------|-------|
| 0-19 | Novice | +0 |
| 20-39 | Apprentice | +1 |
| 40-59 | Competent | +2 |
| 60-79 | Expert | +3 |
| 80-99 | Master | +4 |
| 100 | Legendary | +5 |

### Outcome Tiers

Results are categorized by margin (roll - DC):

| Margin | Outcome | Description |
|--------|---------|-------------|
| +10 or more | Exceptional | Beyond expectations |
| +5 to +9 | Clear Success | Clean execution |
| +1 to +4 | Narrow Success | Succeed with minor cost |
| 0 | Bare Success | Just barely |
| -1 to -4 | Partial Failure | Fail forward, reduced effect |
| -5 to -9 | Clear Failure | Fail with consequence |
| -10 or less | Catastrophic | Serious setback |

### Critical Results

- **Critical Success** (both dice show 10) - 1% chance, exceptional outcome
- **Critical Failure** (both dice show 1) - 1% chance, complication occurs

### Advantage & Disadvantage

Some situations modify your roll:
- **Advantage**: Roll 3d10, keep best 2 (favorable circumstances)
- **Disadvantage**: Roll 3d10, keep worst 2 (hindering conditions)

## Character Needs

Your character has 10 needs that affect gameplay:

| Need | Description | Effects When Low |
|------|-------------|-----------------|
| Hunger | Food satisfaction | STR/CON penalties, eventual death |
| Thirst | Hydration | Faster penalties than hunger |
| Energy | Rest level | DEX/INT penalties, collapse |
| Hygiene | Cleanliness | CHA penalties, disease risk |
| Comfort | Physical comfort | WIS penalties, irritability |
| Wellness | Pain level | Various penalties |
| Social | Social connection | Morale decrease |
| Morale | Mental state | All checks affected |
| Purpose | Sense of meaning | Long-term morale decay |
| Intimacy | Romantic/physical needs | Affects mood |

### Need Decay

Needs decrease over time based on activity:
- **Active** (adventuring): Faster decay
- **Resting**: Moderate decay
- **Sleeping**: Slow decay
- **Combat**: Fastest decay

### Satisfying Needs

The GM handles this naturally through roleplay:
- Eat food → reduces hunger
- Drink water → reduces thirst
- Sleep → restores energy
- Bathe → improves hygiene
- Talk to friends → improves social

## Special Commands

### Character Commands
| Command | Description |
|---------|-------------|
| `/status` | View character stats, needs, and conditions |
| `/inventory` | List items you're carrying |
| `/equipment` | Show equipped items with body slots |
| `/outfit` | See layered clothing by body slot |

### World Commands
| Command | Description |
|---------|-------------|
| `/location` | Current location details |
| `/nearby` | NPCs and items at your location |
| `/time` | Check current time, day, and weather |
| `/quests` | View active quests and tasks |

### Action Commands (Validated)
These commands validate constraints before the GM responds:
| Command | Description |
|---------|-------------|
| `/go <place>` | Move to a location |
| `/take <item>` | Pick up an item |
| `/drop <item>` | Drop an item |
| `/give <item> to <npc>` | Give an item to someone |
| `/attack <target>` | Start combat |

### Image Generation Commands
Generate FLUX image prompts for your scene or character:
| Command | Description |
|---------|-------------|
| `/scene [pov\|third] [photo\|art]` | Generate scene prompt |
| `/portrait [base\|current] [photo\|art]` | Generate character portrait prompt |

Options:
- `pov` = First-person view, `third` = Player visible in scene
- `base` = Appearance only, `current` = With equipment & condition
- `photo` = Photorealistic, `art` = Digital illustration

### System Commands
| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/save` | Save your game |
| `/quit` | Save and exit (or use Ctrl+C) |

## NPCs and Relationships

### How NPCs Work

NPCs in this game are fully realized characters with:
- **Appearance** - Physical description
- **Background** - History and occupation
- **Skills** - What they're good at (can teach you!)
- **Inventory** - What they carry (merchants have wares)
- **Needs** - They get hungry, tired, etc.
- **Preferences** - Food likes, social tendencies

### Relationship Dimensions

Your relationship with NPCs has 7 dimensions:

| Dimension | Description |
|-----------|-------------|
| Trust | Do they believe you? |
| Liking | Do they enjoy your company? |
| Respect | Do they admire you? |
| Fear | Are they afraid of you? |
| Familiarity | How well do they know you? |
| Romantic Interest | Are they attracted to you? |
| Sexual Tension | Physical chemistry |

### Building Relationships

- Help them → Trust & Liking increase
- Lie to them → Trust decreases
- Be charming → Liking increases
- Intimidate them → Fear increases, Liking decreases
- Keep promises → Trust increases
- Miss appointments → Trust & Liking decrease

### Companions

Some NPCs can travel with you as companions:
- Their needs are tracked over time
- They can help in combat
- They provide conversation and skills
- They might teach you their skills

## Time and Schedules

### Time Progression

Time passes as you act:
- Conversations: minutes
- Travel: varies by distance and terrain
- Combat: rounds (6 seconds each)
- Rest: hours

### NPC Schedules

NPCs have daily routines:
- The blacksmith works 8 AM - 6 PM
- The tavern owner is there evenings
- Guards patrol in shifts

Visit at the right time to find who you're looking for!

### Day/Night Effects

- Some locations are closed at night
- Some NPCs sleep
- Visibility affects stealth
- Some creatures are nocturnal

## Navigation and Travel

### Zone System

The world is divided into terrain zones:
- Forests, roads, hills, rivers, etc.
- Each zone has terrain type affecting travel
- Some zones require skills to cross (swimming, climbing)

### Fog of War

You only know about zones and locations you've discovered:
- Explore to find new areas
- NPCs can tell you about locations
- Maps reveal multiple locations at once

### Travel Commands

When traveling between locations:
- The GM simulates the journey
- Random encounters may occur
- Terrain affects travel time

## Tips for New Players

1. **Be Specific**: "I check the desk drawers for hidden compartments" is better than "I search the room"

2. **Talk to NPCs**: They have information, quests, items, and skills to teach

3. **Manage Your Needs**: Don't let hunger or exhaustion catch up with you

4. **Build Relationships**: Trusted allies can help in many situations

5. **Keep Appointments**: Missing meetings damages relationships

6. **Explore**: The world has secrets waiting to be found

7. **Actions Have Consequences**: Steal from the baker, and the town might hear about it

8. **Use Your Skills**: Try actions related to your trained skills

9. **Pay Attention to Time**: NPCs follow schedules, shops close

10. **Save Progress**: The game auto-saves, but `/save` before risky actions

## Troubleshooting

### "API key not found"
Check your `.env` file has valid API keys.

### "Database connection failed"
Ensure PostgreSQL is running and DATABASE_URL is correct.

### "Command not recognized"
Type naturally - the game understands plain English. Use `/help` for commands.

### Skill check seems unfair
Check your character's skills with `/status`. You might not have training in that skill.

### NPC isn't where expected
Check the time with `/time`. NPCs follow schedules and might be elsewhere.

## Game Management

### Listing Games
```bash
rpg game list
```
Shows all your saved games with character names.

### Deleting Games
```bash
rpg game delete
```
Select a game to delete (with confirmation).

### Continuing a Game
```bash
rpg game play
```
Resume your most recent game or select from a list.
