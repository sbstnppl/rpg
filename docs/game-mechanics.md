# Game Mechanics

This document describes how this RPG's game mechanics deviate from D&D 5th Edition. The system prioritizes **realism over drama** while staying as close as possible to familiar D&D concepts.

## Design Philosophy

> "I want to feel like exactly the character and experience the world like it's the real world."

**Core principle**: Experts should reliably succeed at tasks within their competence. A master climber shouldn't fail a moderate cliff 30% of the time.

---

## What Stays the Same (D&D Compatibility)

| Mechanic | Implementation |
|----------|---------------|
| Six Attributes | STR, DEX, CON, INT, WIS, CHA |
| Ability Modifier | (score - 10) // 2 |
| Skill-to-Attribute Mapping | climbing→STR, stealth→DEX, etc. |
| DC Scale | 5 (Trivial) to 30 (Legendary) |
| Advantage/Disadvantage | Concept preserved (adapted for 2d10) |
| Combat Attack Rolls | 1d20 (combat remains swingy) |
| Initiative | 1d20 + DEX modifier |

---

## What Changes (Deviations from D&D)

### 1. Skill Checks Use 2d10 Instead of d20

| Aspect | D&D 5e | This System |
|--------|--------|-------------|
| Die roll | 1d20 | 2d10 |
| Range | 1-20 (flat) | 2-20 (bell curve) |
| Mean | 10.5 | 11 |
| Variance | 33.25 | 8.25 (4x more consistent) |

**Why**: The bell curve makes results cluster around the mean. Experts perform consistently; failures are less random and more meaningful.

**Impact on Success Rates**:

| Scenario | d20 Success | 2d10 Success |
|----------|-------------|--------------|
| Master (+8) vs DC 15 | 70% | 88% |
| Expert (+5) vs DC 15 | 55% | 72% |
| Untrained (+0) vs DC 15 | 30% | 21% |

### 2. Auto-Success for Routine Tasks (Take 10 Rule)

If `DC ≤ 10 + total_modifier`, the character automatically succeeds without rolling.

**Example**: A master climber (STR 18 → +4, Climbing 85 → +4, total +8) auto-succeeds any DC 18 or below.

**Why**: Experts shouldn't need to roll for tasks well within their abilities. A professional locksmith doesn't fumble basic locks.

### 3. Revised Critical System

| Condition | D&D 5e | This System |
|-----------|--------|-------------|
| Critical Success | Natural 20 (5%) | Both dice = 10 (1%) |
| Critical Failure | Natural 1 (5%) | Both dice = 1 (1%) |
| Auto-fail on 1 | Yes | No (only double-1) |
| Auto-succeed on 20 | Yes | No (only double-10) |

**Why**: Experts shouldn't catastrophically fail routine tasks. A 5% fumble chance is unrealistic.

### 4. Degree of Success (Margin System)

Success and failure come in degrees based on the margin (roll + modifier - DC):

| Margin | Outcome | Narrative Effect |
|--------|---------|-----------------|
| ≥10 | Exceptional | Beyond expectations, bonus effect |
| 5-9 | Clear Success | Clean, efficient execution |
| 1-4 | Narrow Success | Succeed with minor cost or delay |
| 0 | Bare Success | Just barely made it |
| -1 to -4 | Partial Failure | Fail forward, reduced effect |
| -5 to -9 | Clear Failure | Fail with consequence |
| ≤-10 | Catastrophic | Fail badly, serious consequence |

**Why**: Binary pass/fail is unrealistic. Degree of success allows for nuanced outcomes like "you pick the lock, but it takes longer than expected" or "you slip but catch yourself."

### 5. Advantage/Disadvantage Uses 3d10

| Condition | Dice | Keep |
|-----------|------|------|
| Normal | 2d10 | Both |
| Advantage | 3d10 | Best 2 |
| Disadvantage | 3d10 | Worst 2 |

**Probability Impact**:
- Normal: Mean 11
- Advantage: Mean ~13.2 (+2.2 shift)
- Disadvantage: Mean ~8.8 (-2.2 shift)

**Why**: The third die represents the circumstance affecting the action. "The guard's distraction gives you an edge - roll an extra die." This preserves the bell curve while providing meaningful advantage.

**Frequency Guidelines** (20-40% of skill checks):
- **Environmental**: High ground, good lighting, favorable weather
- **Preparation**: Studied patterns, proper tools, rehearsed
- **Relationships**: NPC trusts you, reputation precedes you
- **Never stack**: Either advantage, normal, or disadvantage

### 6. Saving Throws Use 2d10

Unlike D&D which uses d20 for all saves, this system uses:
- **Skill checks**: 2d10 (realistic)
- **Saving throws**: 2d10 (realistic)
- **Attack rolls**: 1d20 (combat should be swingy)
- **Initiative**: 1d20

**Why**: Saving throws represent resisting effects based on training and constitution. Experts should be reliable at what they're trained for.

---

## Proficiency System

Skill proficiency uses a 1-100 scale that converts to a modifier:

| Proficiency Level | Modifier | Tier Name |
|-------------------|----------|-----------|
| 0-19 | +0 | Novice |
| 20-39 | +1 | Apprentice |
| 40-59 | +2 | Competent |
| 60-79 | +3 | Expert |
| 80-99 | +4 | Master |
| 100 | +5 | Legendary |

**Maximum Combined Modifier**: +10 (Attribute +5 + Proficiency +5)

---

## Difficulty Classes

| DC | Name | Master (+8) | Expert (+5) | Untrained (+0) |
|----|------|-------------|-------------|----------------|
| 5 | Trivial | Auto | Auto | 97% |
| 10 | Easy | Auto | Auto | 64% |
| 15 | Moderate | Auto | 72% | 21% |
| 20 | Hard | 64% | 45% | 6% |
| 25 | Very Hard | 36% | 21% | 1% |
| 30 | Legendary | 15% | 6% | <1% |

---

## Probability Reference Table

### 2d10 Success Rates by Target Number (DC - Modifier)

| Target | Success % | Interpretation |
|--------|-----------|----------------|
| ≤2 | 100% | Auto-success threshold |
| 3 | 99% | Near certain |
| 4 | 97% | Very likely |
| 5 | 94% | Likely |
| 6 | 90% | Good chance |
| 7 | 85% | Favorable |
| 8 | 79% | Above average |
| 9 | 72% | Decent |
| 10 | 64% | Coin flip+ |
| 11 | 55% | Slight edge |
| 12 | 45% | Slight disadvantage |
| 13 | 36% | Unfavorable |
| 14 | 28% | Poor odds |
| 15 | 21% | Unlikely |
| 16 | 15% | Very unlikely |
| 17 | 10% | Long shot |
| 18 | 6% | Near impossible |
| 19 | 3% | Desperate |
| 20 | 1% | Miracle |

---

## Example: Master Climber

**Character**: STR 18 (+4 modifier), Climbing skill 85 (+4 proficiency), Total: +8

### DC 15 Moderate Cliff
- Auto-success threshold: 10 + 8 = 18
- DC 15 < 18 → **AUTO-SUCCESS** (no roll)
- *"Your practiced hands find every hold. You scale the cliff without incident."*

### DC 20 Hard Cliff
- DC 20 > 18 → Must roll
- Need: 20 - 8 = 12 on 2d10
- Success rate: 45%
- **On roll 14** (total 22, margin +2): Narrow success
  - *"You make it up, though one handhold crumbles beneath you."*
- **On roll 9** (total 17, margin -3): Partial failure
  - *"You slip halfway up. You can try again or seek another route."*

### DC 25 Sheer Ice Wall
- Need: 25 - 8 = 17 on 2d10
- Success rate: 10%
- This IS genuinely difficult - even masters struggle
- *"The ice offers almost nothing to grip. This will require extraordinary luck or better equipment."*

---

## Combat vs Non-Combat

| Roll Type | Die | Reason |
|-----------|-----|--------|
| Skill checks | 2d10 | Realism, expert reliability |
| Saving throws | 2d10 | Consistent with skill philosophy |
| Attack rolls | 1d20 | Combat should feel dangerous, unpredictable |
| Initiative | 1d20 | Combat chaos |
| Damage | Various | Per weapon/spell |

**Design rationale**: Out-of-combat situations benefit from predictability - experts should feel competent. Combat benefits from volatility - even skilled warriors can be surprised.

---

## GM Guidance

### When to Grant Advantage
- Environmental factors favor the character
- Character has properly prepared
- NPC relationship provides an edge
- Tactical positioning helps

### When to Apply Disadvantage
- Character is injured, exhausted, or impaired
- Environmental conditions hinder
- NPC distrust or hostility
- Poor positioning or timing

### Narrating Degree of Success

| Outcome | Narration Style |
|---------|-----------------|
| Exceptional | Describe bonus effects, impressiveness |
| Clear Success | Efficient, professional execution |
| Narrow Success | Mention minor costs or close calls |
| Bare Success | Emphasize how close it was |
| Partial Failure | Describe reduced effect, partial progress |
| Clear Failure | Consequence happens, but recoverable |
| Catastrophic | Serious setback, may need new approach |
