# Character Gameplay Inference

You are analyzing a character's personality and background to infer gameplay-relevant traits, skills, and modifiers.

## Character Summary

**Name:** {character_name}
**Age:** {age}
**Background:** {background}
**Personality:** {personality}

---

## Your Task

Based on the character's background and personality, infer:

1. **Starting Skills** - What skills would this character have learned from their background?
2. **Character Preferences** - Food preferences, social tendencies, stamina traits, etc.
3. **Need Modifiers** - How their traits affect game needs (hunger, fatigue, social, etc.)

---

## Available Skill Categories

Skills should match the character's background. Examples:
- Herbalist apprentice: herbalism, botany, medicine
- Blacksmith's child: smithing, metalwork, repair
- Farmer: agriculture, animal_handling, weather_reading
- Hunter/Scout: tracking, stealth, archery, survival
- Scholar: history, languages, research
- Merchant's child: negotiation, appraisal, bookkeeping
- Noble: etiquette, riding, leadership
- Street urchin: pickpocketing, streetwise, lockpicking

Proficiency scale: 1-100 (beginner: 10-25, apprentice: 25-40, competent: 40-60)

---

## Available Preference Flags

Boolean preferences (true/false):
- `is_picky_eater` - Only likes specific foods, morale penalty for disliked
- `is_greedy_eater` - Eats faster, hunger decays quicker
- `is_vegetarian` / `is_vegan` - Dietary restrictions
- `is_social_butterfly` - Gains social faster, needs people
- `is_loner` - Social need decays slowly, prefers solitude
- `has_high_stamina` - Fatigue accumulates slower
- `has_low_stamina` - Fatigue accumulates faster
- `is_insomniac` - Difficulty sleeping
- `is_heavy_sleeper` - Needs more sleep but recovers well
- `is_teetotaler` - Refuses alcohol
- `is_alcoholic` - Has alcohol addiction

Enum preferences:
- `social_tendency`: "introvert", "ambivert", "extrovert"
- `drive_level`: "none", "low", "moderate", "high", "very_high"
- `intimacy_style`: "casual", "emotional", "monogamous", "polyamorous"
- `alcohol_tolerance`: "none", "low", "moderate", "high"

List preferences:
- `favorite_foods`: ["bread", "berries", "cheese"]
- `disliked_foods`: ["fish", "mushrooms"]
- `food_allergies`: ["nuts"]

---

## Need Modifier Rules

Modifiers change how needs behave for this character:

| Trait | Need | Modifier |
|-------|------|----------|
| is_picky_eater | hunger | satisfaction_multiplier: 0.7 |
| is_greedy_eater | hunger | decay_rate_multiplier: 1.35 |
| is_social_butterfly | social_connection | decay_rate_multiplier: 1.3 |
| is_loner | social_connection | decay_rate_multiplier: 0.5 |
| has_high_stamina | fatigue | decay_rate_multiplier: 0.7 |
| has_low_stamina | fatigue | decay_rate_multiplier: 1.5 |
| is_insomniac | fatigue | satisfaction_multiplier: 0.6 |
| is_heavy_sleeper | fatigue | satisfaction_multiplier: 1.3 |

---

## Output Format

Output a JSON object with your inferences:

```json
{{
  "inferred_skills": [
    {{"skill_key": "herbalism", "proficiency": 30, "reason": "Apprenticed with village herbalist"}},
    {{"skill_key": "botany", "proficiency": 25, "reason": "Learned plant identification"}}
  ],
  "inferred_preferences": {{
    "social_tendency": "introvert",
    "is_loner": false,
    "favorite_foods": ["berries", "fresh bread"],
    "drive_level": "low"
  }},
  "inferred_need_modifiers": [
    {{"need_name": "social_connection", "decay_rate_multiplier": 0.8, "reason": "Comfortable with solitude but not a loner"}}
  ]
}}
```

---

## Guidelines

1. **Be conservative** - Only infer traits clearly supported by the background
2. **Age-appropriate** - A 12-year-old wouldn't have high skill proficiency
3. **Background-based skills** - Skills should come from described experiences
4. **Personality-based preferences** - Traits should match described personality
5. **Don't over-apply** - Most characters are moderate/average in most traits
6. **Explain reasoning** - Include "reason" for skills and modifiers

---

Now analyze the character and output your JSON inference:
