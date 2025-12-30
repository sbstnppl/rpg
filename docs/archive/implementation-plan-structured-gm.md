# Implementation Plan: Structured GM Output with Autonomous NPCs

**Status:** Planning Complete - Ready for Implementation
**Created:** 2025-12-10
**Last Updated:** 2025-12-10

---

## Executive Summary

This plan replaces the current two-stage GM system (narrative generation → entity extraction) with a unified approach where:

1. **The GM LLM creates NPCs/items via tools** during generation, receiving full character data back
2. **NPCs have emergent traits** - personality, preferences, attractions are generated (not prescribed), and the GM discovers who they are
3. **NPCs are situationally aware** - they notice the environment, react to their needs, see player's items
4. **NPCs pursue autonomous goals** - they act off-screen, appear at locations organically based on their motivations
5. **Output is structured JSON** - narrative + manifest, eliminating the extraction LLM call

---

## Table of Contents

1. [Current System Problems](#current-system-problems)
2. [New Architecture](#new-architecture)
3. [Part 1: Tool-Based Entity Creation](#part-1-tool-based-entity-creation)
4. [Part 2: Autonomous NPC Goals](#part-2-autonomous-npc-goals)
5. [Part 3: Context Compiler Enhancements](#part-3-context-compiler-enhancements)
6. [Part 4: GM Output Schema](#part-4-gm-output-schema)
7. [Part 5: Files to Create/Modify](#part-5-files-to-createmodify)
8. [Part 6: Implementation Phases](#part-6-implementation-phases)
9. [Part 7: Example Scenarios](#part-7-example-scenarios)
10. [Part 8: Success Criteria](#part-8-success-criteria)

---

## Current System Problems

```
CURRENT FLOW:
Player Input
    ↓
Context Compiler (builds scene context)
    ↓
GM LLM → Freeform narrative + ---STATE--- text block
    ↓
Entity Extractor LLM → Parses narrative for entities/facts (SECOND LLM CALL)
    ↓
NPC Generator LLM → Creates full character data (THIRD LLM CALL, if new NPCs)
    ↓
Persistence
```

**Problems:**
- **Multiple LLM calls per turn** - Cost and latency
- **Extraction can miss or misinterpret** - GM's intent doesn't always match extracted data
- **No guarantee of consistency** - Narrative says one thing, extraction captures another
- **GM doesn't know NPCs deeply** - Introduces "a shy woman" but doesn't know her goals, attractions, needs
- **NPCs are reactive only** - They don't pursue their own agendas

---

## New Architecture

```
                    ┌─────────────────┐
                    │  World Simulator │
                    │  (between turns) │
                    │                  │
                    │  - NPC goals     │
                    │  - Schedules     │
                    │  - Need decay    │
                    └────────┬────────┘
                             │
         Processes NPC goals, moves NPCs, updates world state
                             │
                             ▼
┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Player    │───▶│  Context        │───▶│  GM LLM          │
│   Input     │    │  Compiler       │    │  (with tools)    │
└─────────────┘    │                 │    │                  │
                   │  - Location     │    │  Tools:          │
                   │  - NPCs + WHY   │    │  - create_npc()  │
                   │  - Player state │    │  - create_item() │
                   │  - Active goals │    │  - query_npc()   │
                   │  - Entity reg.  │    │  - skill_check() │
                   └─────────────────┘    │  - satisfy_need()│
                                          └────────┬─────────┘
                                                   │
                             ┌─────────────────────┘
                             ▼
                   ┌─────────────────┐
                   │  Structured     │
                   │  JSON Output    │
                   │                 │
                   │  - narrative    │ ← Pure prose, no tags
                   │  - state        │ ← Time, location, combat
                   │  - manifest     │ ← Entities, changes, goals
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Persistence    │
                   │  (direct save)  │ ← No extraction needed
                   └─────────────────┘
```

**Benefits:**
- **Single LLM call** (with tool rounds) produces everything
- **GM has full NPC knowledge** before writing narrative
- **Manifest is authoritative** - No extraction guesswork
- **NPCs feel alive** - They pursue goals, appear organically
- **Emergent storytelling** - GM discovers NPC traits, doesn't prescribe them

---

## Part 1: Tool-Based Entity Creation

### Philosophy: GM Discovers, Not Prescribes

**Old approach:** GM decides "I need a shy woman who likes the player"
**New approach:** GM requests "I need a female customer" → System generates full personality → GM discovers she's shy AND attracted (or not!)

This creates emergent, surprising interactions. The GM works with what the system generates, leading to more authentic storytelling.

### `create_npc()` Tool

```python
def create_npc(
    role: str,                      # "shopkeeper", "guard", "customer", "traveler"
    location_key: str,              # Where this NPC is
    scene_context: SceneContext,    # What's visible in the scene
    constraints: dict | None = None # Optional: hard requirements when GM needs them
) -> NPCFullState:
    """
    Creates NPC with EMERGENT personality, needs, and preferences.
    NPC is immediately persisted to database with full precise data.

    Philosophy: Emergent by default, constrained when necessary.

    constraints (optional) - Use when GM needs specific traits for story:
        - personality: list[str] - e.g., ["shy", "suspicious"]
        - gender: str - "male", "female", "non-binary"
        - age_range: str - "child", "teen", "young_adult", "middle_aged", "elderly"
        - age_exact: int - Specific age if needed
        - occupation: str - Specific job
        - hostile_to_player: bool - Must be antagonistic
        - friendly_to_player: bool - Must be welcoming
        - attracted_to_player: bool - Forces positive attraction check
        - wealth_level: str - "destitute", "poor", "modest", "comfortable", "wealthy"
        - name: str - Specific name if needed

    If no constraints provided, ALL traits are randomly generated.

    scene_context includes:
        - entities_present: list[str] - entity_keys of everyone present (including player)
        - visible_items: list[ItemRef] - items NPCs can see
        - environment: list[str] - "warm", "smells of bread", "noisy", etc.
        - player_visible_state: PlayerSummary - player's appearance, visible items, condition

    Returns:
        NPCFullState with:
        - Full identity (name, age, appearance, background)
        - Personality (traits, values, flaws)
        - Preferences (attractions, favorites, dislikes, fears)
        - Current needs (hunger, thirst, fatigue, social, etc.)
        - Environmental reactions (what they notice, how they react)
        - Behavioral prediction (what they're likely to do)
    """
```

### NPC Full State Response

**Critical:** The tool returns and persists PRECISE data, plus narrative-friendly descriptions for the GM.

```json
{
  "entity_key": "customer_elara",
  "display_name": "Elara Thornwood",

  "appearance": {
    "age": 23,
    "age_description": "early twenties",
    "gender": "female",
    "height_cm": 168,
    "height_description": "average height",
    "weight_kg": 62,
    "build": "athletic",
    "hair": "auburn, worn in a practical braid",
    "eyes": "bright green",
    "skin": "fair with freckles across nose and cheeks",
    "notable_features": ["calloused hands from herbalist work", "small scar on chin"],
    "clothing": "simple green dress, worn leather boots, herb-stained apron"
  },

  "background": {
    "occupation": "herbalist apprentice",
    "birthplace": "Millbrook",
    "family": "parents deceased, raised by aunt",
    "education": "apprenticed to town herbalist since age 15",
    "hidden_backstory": "secretly dreams of adventure beyond the village"
  },

  "personality": {
    "traits": ["shy", "curious", "romantic", "hardworking", "observant"],
    "values": ["honesty", "nature", "loyalty", "knowledge"],
    "flaws": ["indecisive", "overthinks", "too trusting", "fear of rejection"],
    "quirks": ["touches hair when nervous", "hums while working"]
  },

  "preferences": {
    "attracted_to_physical": ["lean build", "dark hair", "sharp features", "kind eyes"],
    "attracted_to_personality": ["confidence", "wit", "kindness", "adventurous spirit"],
    "favorite_foods": ["honey cakes", "roasted chicken", "chamomile tea"],
    "favorite_activities": ["gathering herbs", "reading", "stargazing"],
    "dislikes": ["arrogance", "cruelty", "loud crowds", "dishonesty"],
    "fears": ["rejection", "being alone forever", "disappointing her mentor"]
  },

  "current_needs": {
    "hunger": 45,
    "thirst": 78,
    "fatigue": 30,
    "social": 65,
    "comfort": 50,
    "hygiene": 70,
    "morale": 55
  },

  "current_state": {
    "mood": "bored but hopeful",
    "health": "healthy",
    "conditions": ["slightly dehydrated", "warm from walking"],
    "current_activity": "shopping for dried goods for herbalist supplies",
    "current_location": "general_store"
  },

  "environmental_reactions": [
    {
      "notices": "player's water bottle",
      "need_triggered": "thirst",
      "intensity": "strong",
      "internal_thought": "That water looks so refreshing... I've been walking all morning.",
      "likely_behavior": "keeps glancing at bottle, might work up courage to ask"
    },
    {
      "notices": "player (appearance)",
      "reaction_type": "attraction",
      "match_score": {
        "physical": 0.7,
        "personality": 0.3,
        "overall": 0.5
      },
      "internal_thought": "He's kind of cute... and he has water...",
      "likely_behavior": "combination of thirst + attraction may override natural shyness"
    },
    {
      "notices": "smell of fresh bread",
      "need_triggered": "hunger",
      "intensity": "mild",
      "likely_behavior": "might buy some later, but thirst is more pressing"
    }
  ],

  "immediate_goals": [
    {"goal": "buy dried herbs and supplies", "priority": "primary"},
    {"goal": "get something to drink", "priority": "urgent"},
    {"goal": "maybe talk to interesting stranger", "priority": "opportunity"}
  ],

  "behavioral_prediction": "Thirst + attraction creates strong motivation to approach player. Her natural shyness would normally prevent direct approach, but desperation for water combined with finding player attractive may override this. Likely to initiate contact, possibly using water as excuse."
}
```

### `create_item()` Tool

```python
def create_item(
    item_type: str,           # "weapon", "armor", "food", "clothing", "tool", "container", "misc"
    context: str,             # "hunting knife on display", "loaf of bread on shelf"
    location_key: str,        # Where the item is
    constraints: dict | None = None
) -> ItemFullState:
    """
    Creates item with full properties, value, and narrative hooks.
    Item is immediately persisted to database.

    constraints (optional):
        - name: str - Specific name
        - quality: str - "poor", "common", "good", "excellent", "masterwork"
        - value_range: tuple[int, int] - Min/max value in copper
        - owner_key: str - Entity that owns it
        - holder_key: str - Entity currently holding it
        - magical: bool - Has magical properties

    Returns:
        - item_key, display_name, description
        - item_type, subtype
        - properties (damage for weapons, nutrition for food, etc.)
        - value in copper pieces
        - weight in kg
        - condition
        - owner_key, holder_key, location_note
    """
```

### `query_npc()` Tool

```python
def query_npc(
    entity_key: str,
    scene_context: SceneContext  # Updated scene state
) -> NPCReactions:
    """
    For EXISTING NPCs, evaluate current reactions to scene.
    Use when:
    - Scene changes (new person enters, item revealed)
    - Checking NPC's current feelings/state
    - Before writing NPC behavior after time has passed

    Returns:
        - current_needs (updated)
        - current_mood
        - environmental_reactions (to current scene)
        - behavioral_prediction
    """
```

---

## Part 2: Autonomous NPC Goals

### Goal Structure

NPCs pursue goals that drive their behavior even when "off-screen."

```python
class NPCGoal(BaseModel):
    """A goal that an NPC is actively pursuing."""

    goal_id: str                    # Unique identifier
    entity_key: str                 # Who has this goal
    session_id: int                 # Scoped to game session

    # What they want
    goal_type: Literal[
        "acquire",        # Get item/resource (miller needs grain)
        "meet_person",    # Find and interact with someone (Elara wants to see player)
        "go_to",          # Travel to location
        "learn_info",     # Discover information
        "avoid",          # Stay away from person/place
        "protect",        # Keep someone/something safe
        "earn_money",     # Work, trade, sell
        "romance",        # Pursue romantic interest
        "social",         # Make friends, build relationships
        "revenge",        # Get back at someone
        "survive",        # Meet basic needs (find food/water)
        "duty",           # Fulfill obligation/job
        "craft",          # Create something
        "heal",           # Recover from injury/illness
    ]
    target: str  # entity_key, location_key, item_key, or description
    description: str  # Human-readable goal description

    # Why they want it
    motivation: list[str]  # ["physical_attraction", "thirst", "duty", "curiosity"]
    triggered_by: str | None  # Event/turn that created this goal

    # Priority and timing
    priority: Literal["background", "low", "medium", "high", "urgent"]
    deadline: datetime | None  # Game time deadline
    deadline_description: str | None  # "before nightfall", "within 3 days"

    # How they'll pursue it
    strategies: list[str]  # Ordered steps to achieve goal
    current_step: int = 0
    blocked_reason: str | None = None  # Why they can't proceed

    # Completion
    success_condition: str
    failure_condition: str | None
    status: Literal["active", "completed", "failed", "abandoned", "blocked"]

    # Metadata
    created_at_turn: int
    completed_at_turn: int | None = None
```

### Goal Examples

**Elara after positive interaction with player:**
```json
{
  "goal_id": "goal_elara_001",
  "entity_key": "customer_elara",
  "goal_type": "romance",
  "target": "player",
  "description": "Get to know the interesting stranger better",
  "motivation": ["physical_attraction", "gratitude_for_water", "curiosity", "loneliness"],
  "triggered_by": "positive_interaction_turn_5",
  "priority": "medium",
  "deadline_description": null,
  "strategies": [
    "Find out where the stranger is staying",
    "Learn his name and background",
    "Visit places he might frequent",
    "Create opportunity for conversation",
    "Find excuse to spend time together"
  ],
  "current_step": 0,
  "success_condition": "Have meaningful conversation and learn player's name",
  "failure_condition": "Player leaves town or shows clear disinterest",
  "status": "active",
  "created_at_turn": 5
}
```

**Miller with business need:**
```json
{
  "goal_id": "goal_miller_001",
  "entity_key": "miller_thornton",
  "goal_type": "acquire",
  "target": "grain",
  "description": "Restock grain supplies before tomorrow's orders",
  "motivation": ["business_need", "duty", "livelihood", "reputation"],
  "triggered_by": "grain_stock_below_threshold",
  "priority": "urgent",
  "deadline_description": "before tomorrow morning",
  "strategies": [
    "Close mill temporarily",
    "Travel to market district",
    "Negotiate with grain merchant",
    "Purchase sufficient grain",
    "Transport grain back to mill",
    "Reopen mill for business"
  ],
  "current_step": 0,
  "success_condition": "grain_stock >= 50 units",
  "failure_condition": "Unable to purchase grain, miss tomorrow's orders",
  "status": "active",
  "created_at_turn": 8
}
```

**Guard with survival need:**
```json
{
  "goal_id": "goal_guard_001",
  "entity_key": "guard_marcus",
  "goal_type": "survive",
  "target": "food",
  "description": "Find something to eat",
  "motivation": ["extreme_hunger"],
  "triggered_by": "hunger_exceeded_80",
  "priority": "high",
  "strategies": [
    "Check if anyone has food to share or sell",
    "Visit tavern when shift ends",
    "Ask cook at barracks for early meal"
  ],
  "current_step": 0,
  "success_condition": "hunger below 50",
  "status": "active"
}
```

### World Simulator

Runs between turns (or when significant time passes) to process NPC autonomous behavior.

```python
class WorldSimulator:
    """
    Processes NPC goals, needs, and autonomous behavior.
    Makes the world feel alive even when player isn't watching.
    """

    async def simulate(
        self,
        game_session: GameSession,
        time_advanced_minutes: int,
        db: Session
    ) -> WorldSimulationResult:
        """
        Advance the world state by the given time.

        Steps:
        1. Update all NPC needs based on time passed
        2. Check for need-driven goal creation
        3. Process active goals (NPCs take actions)
        4. Update NPC locations based on goal pursuit
        5. Reconcile schedules with goals
        6. Generate narrative hooks for significant events
        """

        results = WorldSimulationResult()
        npcs = self._get_active_npcs(game_session)

        for npc in npcs:
            # 1. Decay needs over time
            self._update_needs(npc, time_advanced_minutes)

            # 2. Create goals from critical needs
            if npc.needs.hunger > 80 and not self._has_goal_type(npc, "survive", "food"):
                goal = self._create_need_goal(npc, "hunger")
                results.goals_created.append(goal)

            if npc.needs.thirst > 85 and not self._has_goal_type(npc, "survive", "drink"):
                goal = self._create_need_goal(npc, "thirst")
                results.goals_created.append(goal)

            # 3. Process active goals
            for goal in self._get_active_goals(npc):
                if self._can_pursue_goal(npc, goal):
                    step_result = await self._execute_goal_step(npc, goal)
                    results.merge(step_result)

            # 4. Update schedule if goals conflict
            self._reconcile_schedule(npc)

        return results

    async def _execute_goal_step(
        self,
        npc: Entity,
        goal: NPCGoal
    ) -> GoalStepResult:
        """Execute one step of goal pursuit."""

        step = goal.strategies[goal.current_step]

        # Different goal types have different execution logic
        if "find out where" in step.lower() or "learn" in step.lower():
            return await self._execute_info_gathering(npc, goal, step)

        elif "travel to" in step.lower() or "go to" in step.lower():
            return self._execute_travel(npc, goal, step)

        elif "purchase" in step.lower() or "buy" in step.lower():
            return self._execute_purchase(npc, goal, step)

        elif "visit" in step.lower():
            return self._execute_visit(npc, goal, step)

        # ... more step types

    async def _execute_info_gathering(
        self,
        npc: Entity,
        goal: NPCGoal,
        step: str
    ) -> GoalStepResult:
        """NPC tries to learn information by asking around."""

        # Find NPCs who might know
        location = self._get_npc_location(npc)
        potential_sources = self._get_npcs_at_location(location)

        for source in potential_sources:
            # Check if relationship allows asking
            if self._relationship_allows_asking(npc, source):
                # Check if source knows the information
                if self._npc_knows_about(source, goal.target):
                    # Transfer knowledge
                    info = self._get_npc_knowledge(source, goal.target)
                    self._npc_learns_fact(npc, goal.target, info)

                    goal.current_step += 1
                    return GoalStepResult(
                        success=True,
                        facts_learned=[(npc.entity_key, "knows_location_of", goal.target)],
                        narrative_hook=f"{npc.display_name} learned where {goal.target} is staying"
                    )

        # Couldn't find info here, try different approach
        return GoalStepResult(
            success=False,
            will_retry=True,
            note=f"{npc.display_name} couldn't find information about {goal.target}"
        )

    def _execute_travel(
        self,
        npc: Entity,
        goal: NPCGoal,
        step: str
    ) -> GoalStepResult:
        """NPC travels to a destination."""

        destination = self._extract_destination(step)
        travel_time = self._calculate_travel_time(npc.current_location, destination)

        # Update NPC location
        npc.current_location = destination
        npc.current_activity = f"arrived at {destination}"

        goal.current_step += 1

        return GoalStepResult(
            npc_moved=True,
            new_location=destination,
            time_consumed=travel_time,
            narrative_hook=f"{npc.display_name} traveled to {destination}"
        )
```

---

## Part 3: Context Compiler Enhancements

### Enhanced NPC Context

The Context Compiler must tell the GM not just WHO is present, but WHY they're there.

```markdown
## NPCs Present

### Elara (customer_elara)
- **Why here:** GOAL PURSUIT - Looking for player (goal: "romance", priority: medium)
- **Background:** Herbalist apprentice, 23, shy but curious
- **Current state:** Nervous but determined
- **Needs:** thirst: 40 (satisfied), social: 70 (wanting connection), morale: 65
- **Environmental reactions:** Relieved and excited to finally find player
- **Behavioral prediction:** Will approach, might be tongue-tied at first, looking for excuse to talk longer

### Miller Thornton (miller_thornton)
- **Why here:** GOAL PURSUIT - Buying grain (goal: "acquire", priority: urgent, deadline: tomorrow)
- **Background:** Town miller, 52, hardworking and stressed
- **Current state:** Frustrated, haggling intensely with merchant
- **Needs:** hunger: 55, fatigue: 60, stress: 75
- **Environmental reactions:** Annoyed by grain prices, barely notices others
- **Behavioral prediction:** Focused on transaction, might ask passerby for help carrying if purchase succeeds

### Greta (shopkeeper_greta)
- **Why here:** SCHEDULED - This is her shop, regular work hours
- **Background:** Shop owner, 45, shrewd businesswoman
- **Current state:** Alert, watching customers carefully
- **Needs:** All moderate, slightly bored
- **Environmental reactions:** Suspicious of player's worn clothes, watching for shoplifting
- **Behavioral prediction:** Polite but watchful, keeps hand near cudgel under counter
```

### Entity Registry

Provides GM with valid entity_keys for the manifest.

```markdown
## Entity Registry

### NPCs at Location (reference by entity_key in manifest)
- shopkeeper_greta: "Greta" (F, 45, shopkeeper) - SCHEDULED: work
- customer_elara: "Elara" (F, 23, herbalist) - GOAL: looking for player
- miller_thornton: "Thornton" (M, 52, miller) - GOAL: buying grain

### NPCs Nearby (might arrive/be mentioned)
- blacksmith_harren: "Harren" (M, 38, blacksmith) - at forge next door
- innkeeper_marta: "Marta" (F, 55, innkeeper) - at Prancing Pony inn

### Player Inventory (visible to NPCs)
- water_bottle: "Water Bottle" - half full, on belt
- silver_coins_3: "Silver Coins" - visible in belt pouch
- bread_loaf: "Loaf of Bread" - tucked under arm

### Items at Location
- hunting_knives_display: "Hunting Knives" - 5 silver each, near window
- bread_shelf: "Fresh Bread" - warm, aromatic, near counter
- dried_goods_shelf: "Dried Goods" - herbs, preserved foods
```

---

## Part 4: GM Output Schema

### Full Response Structure

```python
class GMResponse(BaseModel):
    """Complete structured response from the GM."""

    narrative: str = Field(
        description="Pure prose narrative. Vivid, immersive storytelling. NO entity tags or references - just natural writing."
    )

    state: GMStateChanges

    manifest: GMManifest


class GMStateChanges(BaseModel):
    """Core state changes from this turn."""

    time_advance_minutes: int = Field(ge=0, le=480)
    location_change: str | None = None  # New location_key if player moved
    combat_initiated: bool = False
    combat_ended: bool = False


class GMManifest(BaseModel):
    """
    Structured data about what happened in this turn.
    All entities referenced here were either:
    - Already in context (existing NPCs/items)
    - Created via create_npc()/create_item() tools during this turn
    """

    # Who/what is in the scene
    npcs_in_scene: list[str] = []  # entity_keys
    items_introduced: list[str] = []  # item_keys

    # NPC actions that occurred
    npc_actions: list[NPCAction] = []

    # Item state changes
    item_changes: list[ItemChange] = []

    # Relationship changes
    relationship_changes: list[RelationshipChange] = []

    # Facts revealed (SPV triples)
    facts_revealed: list[FactReveal] = []

    # Stimuli affecting needs/cravings
    stimuli: list[Stimulus] = []

    # Goal changes
    goals_created: list[GoalCreation] = []
    goal_updates: list[GoalUpdate] = []


class NPCAction(BaseModel):
    """An action an NPC took during this turn."""
    entity_key: str
    action: str  # "approaches_player", "leaves_scene", "attacks", etc.
    motivation: list[str]  # ["goal:see_player_again", "need:social"]
    dialogue: str | None = None  # What they said, if anything
    target: str | None = None  # entity_key of action target


class ItemChange(BaseModel):
    """A change in item state."""
    item_key: str
    action: Literal["acquired", "dropped", "given", "stolen", "consumed", "equipped", "unequipped", "destroyed"]
    from_entity: str | None = None  # Who had it
    to_entity: str | None = None  # Who has it now
    location_note: str | None = None  # If dropped somewhere specific


class RelationshipChange(BaseModel):
    """A change in how one entity feels about another."""
    from_entity: str  # entity_key
    to_entity: str  # entity_key
    dimension: Literal["trust", "liking", "respect", "fear", "romantic_interest", "familiarity"]
    delta: int = Field(ge=-50, le=50)
    reason: str


class FactReveal(BaseModel):
    """A fact revealed or established during this turn."""
    subject: str  # entity_key or topic
    predicate: str  # "works_at", "is_married_to", "knows_secret"
    value: str
    is_secret: bool = False  # GM-only information


class Stimulus(BaseModel):
    """Something that affects an entity's needs or triggers cravings."""
    target: str  # entity_key (usually "player")
    need: Literal["hunger", "thirst", "fatigue", "social", "comfort", "hygiene", "pain", "morale", "intimacy", "purpose"]
    intensity: Literal["mild", "moderate", "strong", "overwhelming"]
    source: str  # What caused it
    craving_triggered: bool = False


class GoalCreation(BaseModel):
    """A new goal created for an NPC."""
    entity_key: str
    goal_type: str
    target: str
    description: str
    priority: Literal["background", "low", "medium", "high", "urgent"]
    motivation: list[str]
    triggered_by: str


class GoalUpdate(BaseModel):
    """An update to an existing goal."""
    goal_id: str
    status: Literal["active", "completed", "failed", "abandoned", "blocked"] | None = None
    current_step: int | None = None
    outcome: str | None = None
    note: str | None = None
```

### Example Complete Response

```json
{
  "narrative": "The bell above the door chimes as you slip inside. The general store is warm and cluttered, shelves crammed with everything from rope coils to jars of pickled vegetables.\n\nBehind the counter, a heavyset woman in her forties looks up from her ledger. Her shrewd eyes catalog your worn clothes in an instant, and though her expression remains professionally neutral, you notice her hand drift casually toward something beneath the counter.\n\nA young man in an expensive coat examines hunting knives by the window, barely sparing you a glance—clearly, you're beneath his notice. But the woman near the dried goods section... she looks up as you enter, and for a moment your eyes meet. She's young, maybe early twenties, with auburn hair pulled back in a practical braid and bright green eyes that widen slightly at the sight of you.\n\nShe quickly looks away, tucking a strand of hair behind her ear, but not before you catch the flush creeping up her neck. Her gaze darts to the water bottle at your hip, then back to her shopping basket.\n\n'Can I help you find something?' the shopkeeper asks. Her tone is polite, but her eyes say she'd prefer you didn't linger.",

  "state": {
    "time_advance_minutes": 2,
    "location_change": "millbrook_general_store",
    "combat_initiated": false
  },

  "manifest": {
    "npcs_in_scene": ["shopkeeper_greta", "wealthy_marcus", "customer_elara"],
    "items_introduced": ["hunting_knives_display", "bread_shelf"],

    "npc_actions": [],

    "item_changes": [],

    "relationship_changes": [
      {
        "from_entity": "shopkeeper_greta",
        "to_entity": "player",
        "dimension": "trust",
        "delta": -5,
        "reason": "suspicious of worn clothing, potential shoplifter"
      },
      {
        "from_entity": "customer_elara",
        "to_entity": "player",
        "dimension": "romantic_interest",
        "delta": 15,
        "reason": "physically attracted to player"
      },
      {
        "from_entity": "customer_elara",
        "to_entity": "player",
        "dimension": "familiarity",
        "delta": 5,
        "reason": "noticed player, made eye contact"
      }
    ],

    "facts_revealed": [
      {
        "subject": "shopkeeper_greta",
        "predicate": "keeps_weapon",
        "value": "cudgel under counter",
        "is_secret": true
      }
    ],

    "stimuli": [
      {
        "target": "player",
        "need": "hunger",
        "intensity": "mild",
        "source": "smell of fresh bread",
        "craving_triggered": false
      }
    ],

    "goals_created": [
      {
        "entity_key": "customer_elara",
        "goal_type": "survive",
        "target": "water",
        "description": "Get water from the interesting stranger",
        "priority": "high",
        "motivation": ["thirst", "attraction", "excuse_to_interact"],
        "triggered_by": "seeing_player_water_bottle"
      }
    ],

    "goal_updates": []
  }
}
```

---

## Part 5: Files to Create/Modify

### New Files to Create

| File | Purpose |
|------|---------|
| `src/agents/schemas/gm_response.py` | GMResponse, GMManifest, and all sub-schemas |
| `src/agents/schemas/npc_state.py` | NPCFullState, EnvironmentalReaction, SceneContext |
| `src/agents/schemas/goals.py` | NPCGoal, GoalCreation, GoalUpdate, GoalStepResult |
| `src/agents/tools/npc_tools.py` | create_npc(), query_npc() tool implementations |
| `src/agents/tools/item_tools.py` | create_item() tool implementation |
| `src/managers/goal_manager.py` | GoalManager - CRUD for goals, goal queries |
| `src/managers/world_simulator.py` | WorldSimulator - autonomous NPC behavior |
| `src/database/models/goal.py` | Goal SQLAlchemy model (if not exists) |
| `tests/test_managers/test_goal_manager.py` | Goal system tests |
| `tests/test_managers/test_world_simulator.py` | World simulation tests |

### Files to Modify

| File | Changes |
|------|---------|
| `src/agents/nodes/game_master_node.py` | Add new tools, switch to structured output via `complete_structured()` |
| `src/agents/nodes/npc_generator_node.py` | Refactor core logic to be callable as tool, add situational awareness |
| `src/managers/context_compiler.py` | Add entity registry, NPC motivations, goals context, "why here" info |
| `src/agents/graph.py` | Add world_simulator call, simplify post-GM flow (remove extractor path) |
| `src/agents/nodes/persistence_node.py` | Accept manifest directly, persist goals |
| `src/agents/tools/gm_tools.py` | Register new tools |
| `data/templates/game_master.md` | Complete rewrite for tools + structured output |
| `src/database/models/__init__.py` | Export Goal model |
| `alembic/versions/` | Migration for goals table (if needed) |

---

## Part 6: Implementation Phases

### Phase 1: Core Infrastructure (3-4 days)

**Goal:** Build the foundational schemas and goal system.

1. **Create goal schema and database model**
   - `src/agents/schemas/goals.py` - NPCGoal Pydantic model
   - `src/database/models/goal.py` - SQLAlchemy Goal model
   - Migration for goals table
   - Test: Goal model CRUD works

2. **Create NPCFullState schema**
   - `src/agents/schemas/npc_state.py`
   - Include EnvironmentalReaction, SceneContext
   - Precise data + narrative descriptions pattern
   - Test: Schema validates correctly

3. **Create GoalManager**
   - `src/managers/goal_manager.py`
   - CRUD operations for goals
   - Query goals by entity, type, priority
   - Test: All manager methods work

4. **Write comprehensive tests**
   - Goal creation, updates, completion
   - Goal queries and filters
   - Edge cases (deadlines, failures)

### Phase 2: NPC Creation Tools (3-4 days)

**Goal:** Build tools that create fully-realized NPCs with situational awareness.

5. **Build create_npc() tool**
   - `src/agents/tools/npc_tools.py`
   - Accept constraints (optional) for when GM needs specific traits
   - Generate emergent personality, preferences, needs
   - Include attraction calculation vs player
   - Persist NPC to database immediately
   - Return NPCFullState with narrative descriptions
   - Test: NPCs are created with all required data

6. **Build situational awareness**
   - Environmental reactions based on scene_context
   - Notice visible items, other entities
   - React to needs (hungry NPC notices food)
   - Test: Reactions are generated correctly

7. **Build attraction/compatibility calculation**
   - Compare NPC preferences to player traits
   - Generate match scores (physical, personality, overall)
   - Determine behavioral predictions
   - Test: Attraction scores are reasonable

8. **Build create_item() tool**
   - `src/agents/tools/item_tools.py`
   - Generate full item properties
   - Persist immediately
   - Test: Items created correctly

9. **Build query_npc() tool**
   - Update existing NPC reactions to new scene
   - Test: Reactions update correctly

### Phase 3: World Simulator (3-4 days)

**Goal:** Make NPCs pursue goals autonomously.

10. **Create WorldSimulator manager**
    - `src/managers/world_simulator.py`
    - Main `simulate()` method
    - Called between turns or on time advance
    - Test: Basic simulation runs

11. **Implement goal pursuit logic**
    - `_execute_goal_step()` for each goal type
    - Info gathering (asking around)
    - Travel (moving between locations)
    - Purchase (acquiring items)
    - Social (meeting people)
    - Test: Goals advance through steps

12. **Implement need-driven goal creation**
    - Automatic goals when needs are critical
    - Hunger > 80 → "find food" goal
    - Thirst > 85 → "find drink" goal
    - Test: Goals created at thresholds

13. **Implement schedule reconciliation**
    - Goals can override normal schedules
    - High priority goals take precedence
    - Test: Schedules update correctly

14. **Integrate with game loop**
    - Call WorldSimulator after GM node
    - Pass time_advance from GM response
    - Test: Integration works end-to-end

### Phase 4: Context & Output (2-3 days)

**Goal:** GM receives rich context and outputs structured JSON.

15. **Update ContextCompiler**
    - Add "why here" for each NPC
    - Include active goals in context
    - Add behavioral predictions
    - Test: Context includes all new info

16. **Add entity registry to context**
    - NPCs at location with entity_keys
    - Player visible inventory
    - Items at location
    - Test: Registry is accurate

17. **Create GMResponse schema**
    - `src/agents/schemas/gm_response.py`
    - All manifest sub-schemas
    - Test: Schema validates real responses

18. **Update GM node for structured output**
    - Switch to `complete_structured()`
    - Register new tools
    - Parse GMResponse
    - Test: GM returns valid structured output

### Phase 5: Integration (2-3 days)

**Goal:** Wire everything together, deprecate old system.

19. **Update graph flow**
    - GM → WorldSimulator → Persistence
    - Remove entity_extractor from default path
    - Keep extractor as fallback (feature flag)
    - Test: Graph flows correctly

20. **Update persistence for new format**
    - Accept manifest directly
    - Persist goals from manifest
    - Handle all change types
    - Test: All data persists correctly

21. **Feature flag for fallback**
    - Environment variable to use old extraction
    - Gradual rollout capability
    - Test: Flag works

22. **End-to-end testing**
    - Full gameplay scenarios
    - NPC appears organically
    - Goals progress over turns
    - Test: Multi-turn scenarios work

### Phase 6: Polish (2-3 days)

**Goal:** Tune for quality and performance.

23. **Tune NPC generation prompts**
    - Ensure emergent traits are interesting
    - Attraction calculations feel realistic
    - Behavioral predictions are useful
    - Test: Qualitative review

24. **Test emergent scenarios**
    - Elara finds player at inn
    - Miller goes to market for grain
    - Guard notices player's food
    - Test: Scenarios play out naturally

25. **Performance optimization**
    - Profile tool call latency
    - Optimize database queries
    - Cache where appropriate
    - Test: Response times acceptable

26. **Documentation**
    - Update architecture docs
    - Document new tools
    - Update implementation plan
    - Test: Docs are accurate

---

## Part 7: Example Scenarios

### Scenario 1: Elara Finds Player at Inn

```
Turn 5: Player enters general store
  → GM calls create_npc(role="customer", constraints={"gender": "female"})
  → System generates Elara: shy, curious, attracted to lean dark-haired men
  → Elara sees player (matches her type!), notices water bottle, is thirsty
  → GM writes scene with Elara stealing glances

Turn 5 continued: Player shares water with Elara
  → Manifest: relationship_changes[trust +10, romantic_interest +15]
  → Manifest: goals_created[elara wants to see player again]
  → Goal stored: "romance" type, target: "player"

Turn 6-10: Player explores town
  → WorldSimulator runs each turn
  → Elara executes goal step: "find out where player is staying"
  → Elara asks shopkeeper Greta about the stranger
  → Greta mentions seeing him head toward the inn
  → Elara learns fact: player staying at Prancing Pony
  → Goal advances to step 2: "visit places player might frequent"
  → Elara updates her schedule: visit inn this evening

Turn 11: Player returns to inn at evening
  → Context Compiler includes: "Elara is HERE because goal:romance (looking for player)"
  → GM writes organic reunion scene
  → Elara approaches, nervous but determined
```

### Scenario 2: Miller Needs Grain

```
World state check: miller_thornton.grain_stock = 15 (threshold: 30)
  → WorldSimulator creates goal: "acquire grain", priority: urgent
  → Goal strategies: close mill, travel to market, buy grain, return

Turn N: Player visits mill at 14:30
  → Context: "Mill is CLOSED - Thornton pursuing goal:acquire at market"
  → GM describes: locked door, sign says "Back soon - gone to market"
  → Player can choose to follow or do something else

Turn N+1: Player visits market
  → Context: "Thornton is HERE because goal:acquire (buying grain, urgent)"
  → Thornton is stressed, haggling with merchant
  → GM can involve player: offer to help carry? Overhear merchant gossip?

Turn N+2: If player helped Thornton
  → Manifest: relationship_changes[trust +15, liking +10]
  → Thornton might remember this favor later
  → Could become quest hook or ally
```

### Scenario 3: Hungry Guard Notices Player's Food

```
Turn setup: guard_marcus exists, hunger = 85 (critical)

Turn N: Player enters guardhouse with bread loaf visible
  → GM calls query_npc(entity_key="guard_marcus", scene_context=current_scene)
  → Returns environmental_reactions: notices bread, strong hunger reaction
  → Behavioral prediction: "will try to acquire food, might ask to buy/trade"

  → GM writes: "The guard's eyes drift to the bread tucked under your arm.
               'That from Marta's bakery?' he asks, a bit too casually.
               His stomach growls audibly, and he grimaces in embarrassment."

  → Player choice:
    - Share bread → trust +20, guard owes favor
    - Sell bread → guard appreciates, neutral transaction
    - Refuse → guard disappointed, slight trust decrease
    - Taunt → guard angry, possible conflict

  → This creates emergent gameplay from NPC needs, not scripted events
```

### Scenario 4: NPC Pursues Revenge Goal

```
Turn N: Player pickpockets merchant successfully
  → Merchant doesn't notice immediately
  → Player leaves area

Turn N+3: Merchant discovers theft
  → WorldSimulator: merchant checks inventory, notices missing coins
  → Goal created: "revenge" type, target: "player"
  → Priority: high
  → Strategies: report to guard, hire thief-catcher, watch for player

Turn N+5: Merchant executes goal
  → Talks to town guard
  → Guard now watching for player
  → Fact stored: player has bounty (minor theft)

Turn N+8: Player returns to market
  → Context: "Guard is HERE because duty + watching for player"
  → Merchant spots player, alerts guard
  → Confrontation scene
```

---

## Part 8: Success Criteria

### Core Functionality
- [ ] NPCs have emergent personalities (generated, not prescribed by GM)
- [ ] GM can use constraints when story requires specific traits
- [ ] NPCs notice environment and react to player's visible items/state
- [ ] Attraction calculated from NPC preferences vs player actual traits
- [ ] Goals created from interactions, needs, and events
- [ ] World Simulator advances NPC goals between turns
- [ ] NPCs appear at locations organically based on goal pursuit
- [ ] Context shows WHY each NPC is present

### Output Quality
- [ ] GM writes authentic behavior based on full NPC knowledge
- [ ] Single structured output (no extraction LLM call needed)
- [ ] Narrative quality maintained (pure prose, no tags)
- [ ] Manifest accurately captures all state changes

### Technical Requirements
- [ ] All data persisted with precise values (age: 23, not "early twenties")
- [ ] Entity references validated before persistence
- [ ] Feature flag allows fallback to old extraction system
- [ ] Performance acceptable (response time < 10s for typical turn)

### Testing
- [ ] Unit tests for all new managers
- [ ] Integration tests for full turn flow
- [ ] Multi-turn scenario tests (Elara finds player, miller restocks)
- [ ] Edge case handling (invalid references, goal failures)

---

## Appendix: Key Design Decisions

### Why Emergent Traits?
Rather than GM deciding "I need a shy woman who likes the player," the system generates a complete character and the GM discovers their traits. This creates:
- More authentic storytelling (GM works with what's generated)
- Surprising interactions (maybe she's NOT attracted!)
- Consistent characters (traits come from data, not narrative whim)

### Why Tool-Based Creation?
The GM needs to know NPC details BEFORE writing their behavior. By calling `create_npc()` first, the GM receives full personality, needs, and attraction data, enabling authentic portrayal from the first interaction.

### Why Autonomous Goals?
NPCs should feel like they have lives outside player interaction. The miller needs grain whether or not the player visits. Elara would look for the player even if the player isn't there. This creates a living world.

### Why Structured Output?
Eliminates the extraction LLM call entirely. The GM is authoritative about what happened - no second-guessing by an extractor. Single source of truth, lower cost, faster response.

### Precise vs Narrative Data
Database stores precise data (age: 23, height_cm: 168). GM receives narrative-friendly descriptions too (age_description: "early twenties"). This ensures consistency while enabling natural prose.
