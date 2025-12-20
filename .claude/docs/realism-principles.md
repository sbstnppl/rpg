# Realism Principles

This document defines the principles for maintaining real-world accuracy in game mechanics. Use these principles when designing, reviewing, or validating game systems.

**Purpose**: Catch unrealistic abstractions before they become code. The goal is a simulation that "feels right" because it mirrors how the real world works.

**How to Use**: When proposing game mechanics, check each relevant domain's principles. Ask yourself: "Would this work this way in reality?"

---

## Physiology (Body Mechanics)

How human bodies actually function.

### Core Principles

1. **Distinct Needs Have Distinct Systems**
   - Different bodily needs operate on different timescales and mechanisms
   - Satisfying one need doesn't automatically satisfy related-but-different needs
   - *Illustration*: Sleep and rest are not interchangeable. You can rest without sleeping, but only sleep clears sleep debt. Resting when exhausted makes you more tired, not less.

2. **Non-Linear Recovery**
   - Bodies don't recover in straight lines
   - Recovery rates depend on how depleted you are
   - *Illustration*: The first hour of sleep is more restorative than the fifth. Eating when starving satisfies hunger faster than snacking when already full.

3. **Gating Mechanisms**
   - Some states must be reached before actions become possible
   - You can't force biological processes
   - *Illustration*: You can't fall asleep on command without fatigue. You can't eat comfortably when already full. Wounds must reach certain healing before exertion is safe.

4. **Cumulative Effects**
   - Deprivation accumulates over time
   - Short-term fixes don't erase long-term deficits
   - *Illustration*: One good night's sleep doesn't fix a week of poor sleep. Dehydration builds up; a sip of water doesn't cure severe thirst.

5. **Activity-Specific Costs**
   - Different activities drain different resources
   - Mental and physical exertion are separate
   - *Illustration*: Reading a book doesn't tire your legs. Running doesn't tire your mind (though total exhaustion affects everything).

### Questions to Ask
- Are we merging distinct biological processes into one number?
- Does recovery depend on current state or is it always fixed?
- Can the character be forced into states that wouldn't occur naturally?
- Are we respecting that some needs gate others?

---

## Temporal (Duration & Timing)

How long real-world activities actually take.

### Core Principles

1. **Duration Depends on Context**
   - The same activity takes different time based on conditions
   - Skill, tools, environment, and interruptions all matter
   - *Illustration*: Cooking a meal takes longer without proper tools. Walking uphill takes longer than downhill. A skilled craftsman works faster than a novice.

2. **Activities Have Minimums**
   - Some things simply cannot be rushed
   - Speed has diminishing returns
   - *Illustration*: You can't "quick nap" away serious sleep debt. Traveling 10 miles takes time no matter how motivated. Conversations have natural pacing.

3. **Transition Time Exists**
   - Moving between activities takes time
   - Context switches aren't instant
   - *Illustration*: Going from sleeping to fully alert takes time. Traveling between locations has duration. Setting up for a task has overhead.

4. **Time Passes During Actions**
   - The world doesn't pause while you act
   - Long activities mean time advancement
   - *Illustration*: If you spend 6 hours sleeping, NPCs have 6 hours to do their own things. Crafting a sword takes days, not minutes.

5. **Realistic Variability**
   - Identical actions don't always take identical time
   - External factors introduce variation
   - *Illustration*: Some conversations run long, others are brief. Foraging takes unpredictable time. Travel times vary with conditions.

### Questions to Ask
- Would this activity really take this long (or this short) in the real world?
- Are we ignoring transition/setup time?
- Does our duration account for skill, tools, and environment?
- Are we allowing for realistic variation?

---

## Social (Human Interaction)

How real people actually interact.

### Core Principles

1. **Relationships Develop Gradually**
   - Trust, respect, and intimacy build over time
   - Single interactions have limited impact
   - *Illustration*: A stranger doesn't become a trusted friend from one conversation. Romantic interest develops through repeated positive interactions. Betraying trust takes one moment; rebuilding it takes much longer.

2. **Context Shapes Interaction**
   - Who, where, when, and who's watching all matter
   - People behave differently in different contexts
   - *Illustration*: A merchant acts differently when alone vs. with customers. People share secrets in private, not in crowds. Formal settings constrain behavior.

3. **Memory and Consistency**
   - People remember past interactions
   - Behavior should be consistent with character and history
   - *Illustration*: An NPC you robbed doesn't forget when you return. Promises made must be remembered. People reference shared experiences.

4. **Social Norms Exist**
   - Cultures have expectations about behavior
   - Violating norms has consequences
   - *Illustration*: Strangers don't share life stories immediately. Certain topics are taboo. Entering someone's home uninvited is rude. Haggling has cultural rules.

5. **Conversations Have Structure**
   - Real dialogue has natural flow
   - Topics shift, people interrupt, conversations end
   - *Illustration*: People don't answer questions with information dumps. Conversations meander and revisit topics. Uncomfortable silences happen. People get tired of talking.

### Questions to Ask
- Would a real person react this way to a stranger?
- Are we allowing relationships to develop too fast?
- Does context (location, audience, time) affect the interaction?
- Are NPCs remembering and referencing past interactions?

---

## Physical (World Mechanics)

How the physical world actually behaves.

### Core Principles

1. **Environment Affects Everything**
   - Weather, terrain, and conditions impact activities
   - Physical states propagate to character states
   - *Illustration*: Rain makes surfaces slippery and characters wet. Cold temperatures require appropriate clothing. Darkness limits vision and actions.

2. **Objects Have Properties**
   - Things have weight, size, fragility, and state
   - Properties constrain what's possible
   - *Illustration*: Heavy objects slow you down. Fragile items break if dropped. Wet clothes stay wet until dried. Sharp things can cut.

3. **Conservation Matters**
   - Things don't appear or disappear without cause
   - Resources are consumed, not infinite
   - *Illustration*: Torches burn out. Food gets eaten. Injuries leave evidence. Coins spent are gone.

4. **Cause and Effect**
   - Actions have physical consequences
   - Effects propagate through the environment
   - *Illustration*: Loud noises attract attention. Fires spread. Knocked objects fall. Blood leaves stains.

5. **Distance and Position Matter**
   - Space is real and constraining
   - You can't act on things not in range
   - *Illustration*: You must travel to reach destinations. You can't pickpocket from across a room. Line of sight affects perception.

### Questions to Ask
- Are we ignoring environmental effects that would obviously apply?
- Do objects behave according to their physical properties?
- Are resources being consumed appropriately?
- Are we respecting spatial constraints?

---

## Cross-Domain Interactions

Some issues span multiple domains:

| Scenario | Domains |
|----------|---------|
| Sleep mechanics | Physiology (sleep pressure) + Temporal (duration) |
| Weather effects | Physical (environment) + Physiology (comfort/temperature) |
| Building relationships | Social (trust development) + Temporal (time required) |
| Combat exhaustion | Physiology (stamina) + Physical (movement/actions) |
| Travel | Temporal (duration) + Physical (terrain) + Physiology (fatigue) |

When designing mechanics that span domains, validate against each relevant domain's principles.

---

## Using This Document

**During Planning**: Before proposing game mechanics, identify which domains are affected and verify the design against those principles.

**During Review**: Use the "Questions to Ask" as a checklist for each affected domain.

**When Uncertain**: If unsure whether something is realistic, default to the more realistic option. Players notice when things feel wrong.
