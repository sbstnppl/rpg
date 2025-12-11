# NPC Voice Generator

Generate a distinctive, memorable voice template for an NPC in a **{setting}** RPG.

## Character Details

- **Name**: {display_name}
- **Age**: {age} ({age_apparent})
- **Gender**: {gender}
- **Species**: {species}
- **Occupation**: {occupation} ({occupation_years} years)
- **Social Status**: {social_status}
- **Personality Traits**: {personality_traits}
- **Origin/Region**: {origin}
- **Background**: {background_summary}

## Physical Voice Characteristics

- **Voice Description**: {voice_description}

## Current Scene Context

{scene_context}

## Instructions

Create a unique, memorable voice for this NPC that:

1. **Fits their occupation and social status** in a {setting} setting
2. **Reflects their personality traits** - a nervous person speaks differently than a confident one
3. **Is setting-appropriate** - avoid anachronisms
4. **Has memorable verbal tics or catchphrases** that make them recognizable
5. **Provides practical examples** the GM can reference during play

### Setting-Specific Considerations

**For {setting}:**
{setting_guidance}

### Occupation Influence

Consider how their job shapes their speech:
- Technical vocabulary from their trade
- Communication habits from their work (commanding soldiers vs. soothing patients)
- Social norms of their profession

### Personality Influence

Consider how personality affects delivery:
- Nervous: Hesitations, self-corrections, trailing off
- Confident: Direct statements, fewer qualifiers
- Friendly: Warm greetings, inclusive language
- Hostile: Clipped responses, dismissive tone
- Mysterious: Cryptic statements, never fully answering

## Example Voice Patterns

### Fantasy Setting Examples:
- **Noble**: "I do believe we haven't been properly introduced. I am Lord Ashworth, and you would be...?"
- **Commoner**: "Oi, you new 'round here? Well, watch yerself, the guard's been tetchy lately."
- **Scholar**: "Fascinating, truly fascinating. The implications of this discovery cannot be overstated."
- **Mercenary**: "Gold up front, half now, half when it's done. No questions, no problems."

### Contemporary Setting Examples:
- **Corporate**: "Let's circle back on that. I'll have my assistant schedule a sync."
- **Surfer**: "Dude, that wave was absolutely gnarly. You totally should've been there, bro."
- **Physician**: "I need to run some tests. Don't worry, we'll figure out what's going on."
- **Teenager**: "Literally can't even. This is, like, so random."

### Sci-Fi Setting Examples:
- **Starship Captain**: "Set course for the outer colonies. All hands, prepare for FTL transition."
- **Android**: "I have processed your request. The probability of success is 73.2 percent."
- **Alien Trader**: "Human currency acceptable. Exchange rate... favorable for you, yes?"
- **Hacker**: "I'm in. Firewalls were garbage. Give me thirty seconds."

## Output

Return a JSON object matching the GeneratedVoiceTemplate schema:

```json
{{
  "vocabulary_level": "moderate",
  "sentence_structure": "short_direct",
  "formality": "casual",
  "speaking_pace": "measured",
  "verbal_tics": ["y'know", "thing is"],
  "speech_patterns": ["Uses work metaphors", "Asks confirming questions"],
  "filler_words": ["well", "so"],
  "favorite_expressions": ["Fair enough", "That's the way of it"],
  "greetings": ["Hey there", "Mornin'"],
  "farewells": ["Take care", "See ya"],
  "affirmatives": ["Aye", "Sure thing"],
  "negatives": ["Nah", "Can't do it"],
  "swearing_style": "mild_occupational",
  "swear_examples": ["Bloody hell", "Damn rust"],
  "example_dialogue": {{
    "greeting_stranger": "Hey, you new around here? Name's [Name].",
    "greeting_friend": "There you are! Was wondering when you'd show up.",
    "angry": "Now hold on just a minute. That's not how we do things.",
    "nervous": "I, uh... well, thing is... it's complicated.",
    "pleased": "Ha! Now that's what I like to hear.",
    "refusing_request": "Sorry, can't help you there. Rules are rules."
  }},
  "accent_notes": "Slight regional drawl, emphasizes certain syllables",
  "dialect_features": ["Drops final g", "Uses 'ain't'"],
  "vocabulary_notes": "Uses trade terminology frequently",
  "formal_context_changes": "Becomes stiff and overly polite, over-enunciates",
  "stress_context_changes": "Speech becomes faster, more clipped",
  "voice_summary": "A practical, no-nonsense worker with a friendly demeanor and regional accent."
}}
```

Generate the voice template now.
