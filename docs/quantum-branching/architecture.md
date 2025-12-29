# Quantum Branching Architecture

## Design Philosophy

The Quantum Branching architecture is inspired by quantum mechanics' concept of superposition - all possible outcomes exist simultaneously until observation collapses them to a single reality.

In our system:
- **Superposition**: Multiple outcome branches exist in cache
- **Observation**: Player input triggers branch selection
- **Collapse**: Dice roll determines which reality manifests

This mirrors how experienced tabletop GMs think ahead: "If the player talks to the merchant, here's what happens. If they try to steal, here's the consequence."

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     QuantumPipeline                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Action    │  │    GM       │  │    Branch              │  │
│  │  Predictor  │──│   Oracle    │──│   Generator            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                                      │                 │
│         ▼                                      ▼                 │
│  ┌─────────────┐                    ┌─────────────────────────┐  │
│  │   Action    │                    │   QuantumBranchCache   │  │
│  │   Matcher   │◄───────────────────│   (LRU + TTL)          │  │
│  └─────────────┘                    └─────────────────────────┘  │
│         │                                      │                 │
│         ▼                                      │                 │
│  ┌─────────────────────────────────────────────┘                 │
│  │                                                               │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  └─►│  Collapse   │──│    Dice     │──│   State Delta       │   │
│     │  Manager    │  │   Roller    │  │   Applier           │   │
│     └─────────────┘  └─────────────┘  └─────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│                      ┌─────────────┐                             │
│                      │  Validator  │                             │
│                      │   Layer     │                             │
│                      └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Turn Processing (Cache Hit)

```
Player Input: "talk to the merchant"
        │
        ▼
┌───────────────────┐
│  ActionMatcher    │ ─── Match input to cached predictions
│  confidence: 0.87 │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Cache Lookup     │ ─── Find branch: "market::INTERACT_NPC::merchant_001::no_twist"
│  hit: true        │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  CollapseManager  │ ─── Roll 2d10: 14 vs DC 10
│  result: SUCCESS  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Apply Deltas     │ ─── Update relationship, record facts
│  commit: true     │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Display          │ ─── Show narrative, latency: 47ms
└───────────────────┘
```

### Turn Processing (Cache Miss)

```
Player Input: "examine the strange rune on the wall"
        │
        ▼
┌───────────────────┐
│  ActionMatcher    │ ─── No cached prediction matches
│  confidence: 0.42 │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Sync Generation  │ ─── Generate branch on-demand
│  latency: 4200ms  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  CollapseManager  │ ─── Same flow as cache hit
└───────────────────┘
```

## Core Components

### QuantumPipeline

The main orchestrator that coordinates all components:

```python
class QuantumPipeline:
    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        anticipation_config: AnticipationConfig,
    ):
        self.action_predictor = ActionPredictor(db, game_session)
        self.action_matcher = ActionMatcher()
        self.gm_oracle = GMDecisionOracle(db, game_session)
        self.branch_generator = BranchGenerator(db, game_session)
        self.branch_cache = QuantumBranchCache()
        self.collapse_manager = BranchCollapseManager(db, game_session)
        self.validator = BranchValidator()

    async def process_turn(
        self,
        player_input: str,
        location_key: str,
        turn_number: int,
    ) -> TurnResult:
        # 1. Try cache lookup
        # 2. Fall back to sync generation
        # 3. Collapse branch with dice roll
        # 4. Return result
```

### ActionPredictor

Analyzes scene context to predict likely player actions:

```python
class ActionPredictor:
    def predict_actions(
        self,
        location_key: str,
        manifest: GroundingManifest,
        recent_turns: list[Turn],
    ) -> list[ActionPrediction]:
        # Score actions based on:
        # - NPC presence and focus
        # - Item visibility and interactability
        # - Available exits
        # - Recent player behavior
```

### GMDecisionOracle

Predicts whether the GM would add a twist:

```python
class GMDecisionOracle:
    def predict_decisions(
        self,
        action: ActionPrediction,
        world_state: WorldState,
    ) -> list[GMDecision]:
        # Consider:
        # - World facts that could trigger twists
        # - Player reputation/relationships
        # - Story tension level
        # - Recent events
```

### BranchGenerator

Generates narrative variants with state deltas:

```python
class BranchGenerator:
    async def generate_branches(
        self,
        action: ActionPrediction,
        gm_decisions: list[GMDecision],
        manifest: NarratorManifest,
        context: BranchContext,
    ) -> list[QuantumBranch]:
        # For each action + GM decision combo:
        # 1. Build generation prompt
        # 2. Call LLM for narrative variants
        # 3. Parse state deltas
        # 4. Validate consistency
```

### BranchCollapseManager

Handles the "observation" moment:

```python
class BranchCollapseManager:
    async def collapse_branch(
        self,
        branch: QuantumBranch,
        player_input: str,
        turn_number: int,
    ) -> CollapseResult:
        # 1. Check if dice roll needed
        # 2. Roll dice (LIVE - the meaningful moment!)
        # 3. Select variant based on roll
        # 4. Validate state deltas still valid
        # 5. Apply deltas atomically
        # 6. Return narrative
```

## State Management

### QuantumBranch Structure

```python
@dataclass
class QuantumBranch:
    branch_key: str              # "location::action::target::gm_decision"
    action: ActionPrediction     # What player is doing
    gm_decision: GMDecision      # GM twist decision
    variants: dict[str, OutcomeVariant]  # outcome_type -> variant
    generated_at: datetime       # For TTL expiry
    generation_time_ms: float    # Performance tracking
    state_version: int           # For staleness detection
```

### StateDelta

Atomic state changes that can be validated and applied:

```python
@dataclass
class StateDelta:
    delta_type: DeltaType        # RELATIONSHIP, FACT, ITEM, LOCATION, etc.
    entity_key: str              # Target entity
    operation: str               # "add", "update", "remove"
    value: dict                  # Delta-specific data
```

### Staleness Detection

Branches can become stale when world state changes:

```python
class BranchCollapseManager:
    async def _validate_deltas(self, deltas: list[StateDelta]) -> bool:
        for delta in deltas:
            if delta.delta_type == DeltaType.RELATIONSHIP:
                # Check entity still exists
                if not self._entity_exists(delta.entity_key):
                    return False
            elif delta.delta_type == DeltaType.ITEM:
                # Check item still in expected location
                if not self._item_available(delta.entity_key):
                    return False
        return True
```

## Background Anticipation

### Anticipation Loop

```python
async def _anticipation_loop(self) -> None:
    while self._running:
        location = self._current_location
        if not location:
            await asyncio.sleep(1.0)
            continue

        # Build manifest for current scene
        manifest = await self._build_manifest(location)

        # Predict likely actions
        predictions = await self.action_predictor.predict_actions(
            location, manifest, self._get_recent_turns()
        )

        # Generate branches for top N predictions
        for action in predictions[:config.max_actions_per_cycle]:
            if await self._action_cached(location, action):
                continue

            gm_decisions = self.gm_oracle.predict_decisions(action, world_state)

            branches = await self.branch_generator.generate_branches(
                action, gm_decisions[:config.max_gm_decisions], manifest, context
            )

            await self.branch_cache.put_branches(branches)

        await asyncio.sleep(config.cycle_delay_seconds)
```

### Configuration

```python
@dataclass
class AnticipationConfig:
    enabled: bool = False
    max_actions_per_cycle: int = 5
    max_gm_decisions_per_action: int = 2
    cycle_delay_seconds: float = 0.5
```

## Validation Layer

Three validators ensure generated content is consistent:

### NarrativeConsistencyValidator

```python
class NarrativeConsistencyValidator:
    def validate(self, narrative: str, manifest: GroundingManifest) -> ValidationResult:
        issues = []

        # Check all entity references are grounded
        for ref in self._extract_references(narrative):
            if ref.key not in manifest.all_entity_keys:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="ungrounded_entity",
                    message=f"Entity {ref.key} not in manifest",
                ))

        # Check for meta-questions
        if self._has_meta_question(narrative):
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="meta_question",
                message="Narrative ends with meta-question",
            ))

        return ValidationResult(issues=issues)
```

### DeltaValidator

```python
class DeltaValidator:
    def validate(self, deltas: list[StateDelta], world_state: WorldState) -> ValidationResult:
        # Check delta consistency
        # Verify entities exist
        # Check for conflicts
```

### BranchValidator

```python
class BranchValidator:
    def validate(self, branch: QuantumBranch, manifest: GroundingManifest) -> ValidationResult:
        # Validate all variants
        # Check branch structure
        # Ensure at least success variant exists
```

## Error Handling

### Graceful Degradation

```python
async def process_turn(self, player_input: str, ...) -> TurnResult:
    try:
        # Try cache hit path
        branch = await self._try_cache_hit(player_input, location)
        if branch:
            return await self._collapse_branch(branch, player_input)
    except StaleStateError:
        # Branch became stale, regenerate
        pass

    try:
        # Sync generation
        return await self._generate_sync(player_input, location)
    except BranchGenerationError as e:
        # Fallback to constrained narrator
        return await self._narrator_fallback(player_input, e.context)
```

### Metrics Collection

```python
@dataclass
class QuantumMetrics:
    cache_hits: int = 0
    cache_misses: int = 0
    stale_branches: int = 0
    generation_times: list[float] = field(default_factory=list)
    collapse_times: list[float] = field(default_factory=list)

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
```

## Integration Points

### CLI Integration

```python
# src/cli/commands/game.py
if is_quantum:
    quantum_pipeline = QuantumPipeline(
        db=db,
        game_session=game_session,
        anticipation_config=anticipation_config,
    )

    turn_result = await quantum_pipeline.process_turn(
        player_input=enhanced_input,
        location_key=player_location,
        turn_number=game_session.total_turns,
    )
```

### Database Integration

The quantum pipeline uses the same database models as other pipelines:
- `Turn` - Turn history
- `Entity` - Game entities
- `Relationship` - NPC relationships
- `WorldFact` - SPV facts

State deltas are applied through existing managers to maintain consistency.
