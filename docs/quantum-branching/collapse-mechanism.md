# Collapse Mechanism

The `BranchCollapseManager` handles the critical moment when player observation "collapses" a quantum branch into a single reality - by rolling dice.

## Overview

The collapse mechanism is where the quantum metaphor becomes concrete:

```
Multiple Branches Exist (Superposition)
        │
        │  Player acts: "talk to merchant"
        ▼
┌───────────────────────────────────────┐
│         BranchCollapseManager          │
│                                        │
│  1. Match player input to branch       │
│  2. Validate branch still valid        │
│  3. ROLL DICE (the meaningful moment!) │
│  4. Select appropriate variant         │
│  5. Apply state deltas atomically      │
│  6. Return narrative                   │
│                                        │
└───────────────────────────────────────┘
        │
        ▼
Single Reality Manifests
"The merchant smiles warmly..."
```

## Dice Rolling

### 2d10 System

The game uses a 2d10 system for skill checks:

```python
class DiceRoller:
    def roll_skill_check(
        self,
        skill: str,
        dc: int,
        skill_bonus: int = 0,
    ) -> DiceResult:
        # Roll 2d10
        die1 = random.randint(1, 10)
        die2 = random.randint(1, 10)
        total = die1 + die2 + skill_bonus

        return DiceResult(
            dice=[die1, die2],
            total=total,
            dc=dc,
            is_success=total >= dc,
            is_critical_success=(die1 == 10 and die2 == 10),
            is_critical_failure=(die1 == 1 and die2 == 1),
        )
```

### Critical Results

| Roll | Result | Notes |
|------|--------|-------|
| Double 10 | Critical Success | Exceptional outcome regardless of DC |
| >= DC | Success | Standard success |
| < DC | Failure | Standard failure |
| Double 1 | Critical Failure | Bad outcome regardless of DC |

## CollapseResult Schema

```python
@dataclass
class CollapseResult:
    narrative: str              # Display-ready narrative (keys stripped)
    raw_narrative: str          # Original with [key:name] format
    state_changes: list[StateDelta]  # Applied deltas
    time_passed_minutes: int    # Game time elapsed
    was_cache_hit: bool         # Performance indicator
    dice_result: DiceResult | None  # If dice were rolled
    latency_ms: float           # Processing time
```

## Collapse Process

### 1. Branch Selection

```python
async def collapse_branch(
    self,
    branch: QuantumBranch,
    player_input: str,
    turn_number: int,
) -> CollapseResult:
    start_time = time.time()

    # Step 1: Validate branch not stale
    if not await self._validate_branch_state(branch):
        raise StaleStateError(
            f"Branch {branch.branch_key} is stale - world state changed"
        )
```

### 2. Variant Selection

```python
    # Step 2: Determine which variant to use
    variant, dice_result = await self._select_variant(branch)
```

The selection logic:

```python
async def _select_variant(
    self,
    branch: QuantumBranch,
) -> tuple[OutcomeVariant, DiceResult | None]:
    # Check if any variant requires dice
    success_variant = branch.variants.get("success")

    if not success_variant.requires_dice:
        # No dice needed - return success
        return success_variant, None

    # ROLL DICE - This is the meaningful moment!
    dice_result = self.dice_roller.roll_skill_check(
        skill=success_variant.skill,
        dc=success_variant.dc,
        skill_bonus=self._get_skill_bonus(success_variant.skill),
    )

    # Select variant based on roll
    if dice_result.is_critical_success:
        variant = branch.variants.get(
            "critical_success",
            branch.variants["success"]  # Fallback
        )
    elif dice_result.is_success:
        variant = branch.variants["success"]
    elif dice_result.is_critical_failure:
        variant = branch.variants.get(
            "critical_failure",
            branch.variants.get("failure", branch.variants["success"])
        )
    else:
        variant = branch.variants.get(
            "failure",
            branch.variants["success"]  # Fallback if no failure variant
        )

    return variant, dice_result
```

### 3. Delta Validation

```python
    # Step 3: Validate deltas still applicable
    if not await self._validate_deltas(variant.state_deltas):
        raise StaleStateError("State deltas no longer valid")
```

Validation checks:

```python
async def _validate_deltas(
    self,
    deltas: list[StateDelta],
) -> bool:
    for delta in deltas:
        if delta.delta_type == DeltaType.RELATIONSHIP:
            # Entity must still exist
            entity = await self._get_entity(delta.entity_key)
            if not entity:
                return False

        elif delta.delta_type == DeltaType.ITEM:
            # Item must be in expected state
            item = await self._get_item(delta.entity_key)
            if not item or item.holder_id != delta.value.get("expected_holder"):
                return False

        elif delta.delta_type == DeltaType.LOCATION:
            # Target location must be accessible
            if not await self._location_accessible(delta.value["location_key"]):
                return False

    return True
```

### 4. Delta Application

```python
    # Step 4: Apply deltas atomically
    try:
        await self._apply_deltas(variant.state_deltas, turn_number)
    except Exception as e:
        # Rollback and re-raise
        await self._rollback_deltas(variant.state_deltas)
        raise CollapseError(f"Failed to apply deltas: {e}")
```

Atomic application:

```python
async def _apply_deltas(
    self,
    deltas: list[StateDelta],
    turn_number: int,
) -> None:
    for delta in deltas:
        if delta.delta_type == DeltaType.RELATIONSHIP:
            await self.relationship_manager.update_relationship(
                npc_key=delta.entity_key,
                dimension=delta.value["dimension"],
                change=delta.value["change"],
            )

        elif delta.delta_type == DeltaType.FACT:
            await self.fact_manager.record_fact(
                subject=delta.value["subject"],
                predicate=delta.value["predicate"],
                object_=delta.value["object"],
                turn_number=turn_number,
            )

        elif delta.delta_type == DeltaType.ITEM:
            await self.inventory_manager.transfer_item(
                item_key=delta.entity_key,
                new_holder=delta.value["holder_id"],
            )

        elif delta.delta_type == DeltaType.LOCATION:
            await self.movement_manager.move_entity(
                entity_key=delta.entity_key,
                target_location=delta.value["location_key"],
            )
```

### 5. Narrative Stripping

```python
    # Step 5: Strip entity keys for display
    display_narrative = strip_entity_references(variant.narrative)

    # Record turn
    await self._record_turn(
        player_input=player_input,
        narrative=variant.narrative,  # Keep keys for history
        turn_number=turn_number,
    )

    return CollapseResult(
        narrative=display_narrative,
        raw_narrative=variant.narrative,
        state_changes=variant.state_deltas,
        time_passed_minutes=variant.time_passed_minutes,
        was_cache_hit=True,
        dice_result=dice_result,
        latency_ms=(time.time() - start_time) * 1000,
    )
```

## Entity Reference Stripping

```python
def strip_entity_references(narrative: str) -> str:
    """
    Convert [key:name] format to just name.

    Input:  "[marcus_001:Marcus] smiles at you."
    Output: "Marcus smiles at you."
    """
    pattern = r'\[([a-z_0-9]+):([^\]]+)\]'
    return re.sub(pattern, r'\2', narrative)


def extract_entity_references(narrative: str) -> list[tuple[str, str]]:
    """
    Extract all entity references from narrative.

    Returns: [("marcus_001", "Marcus"), ...]
    """
    pattern = r'\[([a-z_0-9]+):([^\]]+)\]'
    return re.findall(pattern, narrative)
```

## Staleness Handling

### StaleStateError

When world state changes between generation and collapse:

```python
class StaleStateError(Exception):
    """Branch is stale due to world state changes."""

    def __init__(self, message: str, branch_key: str | None = None):
        super().__init__(message)
        self.branch_key = branch_key
```

### Handling in Pipeline

```python
async def process_turn(self, player_input: str, ...) -> TurnResult:
    match_result = self.action_matcher.match(player_input, predictions, manifest)

    if match_result:
        action, confidence = match_result
        branch = await self.branch_cache.get_branch(location, action, gm_decision)

        if branch:
            try:
                result = await self.collapse_manager.collapse_branch(
                    branch, player_input, turn_number
                )
                return TurnResult(narrative=result.narrative, was_cache_hit=True)

            except StaleStateError:
                # Invalidate stale branches for this location
                await self.branch_cache.invalidate_location(location)
                # Fall through to sync generation

    # Sync generation for cache miss or stale branch
    return await self._generate_sync(player_input, location, turn_number)
```

## Turn Recording

Each collapsed branch creates a turn record:

```python
async def _record_turn(
    self,
    player_input: str,
    narrative: str,
    turn_number: int,
) -> Turn:
    turn = Turn(
        session_id=self.game_session.id,
        turn_number=turn_number,
        player_input=player_input,
        gm_response=narrative,  # Keeps [key:name] format
        timestamp=datetime.now(),
    )
    self.db.add(turn)
    await self.db.commit()
    return turn
```

## Performance

### Target Latencies

| Operation | Target | Notes |
|-----------|--------|-------|
| Branch lookup | <5ms | Hash table access |
| Delta validation | <10ms | Database checks |
| Dice roll | <1ms | RNG |
| Delta application | <20ms | Database writes |
| Reference stripping | <1ms | Regex |
| **Total collapse** | **<50ms** | Cache hit path |

### Optimization Techniques

1. **Batch delta application**: Apply all deltas in single transaction
2. **Cached entity lookups**: Keep frequently accessed entities in memory
3. **Pre-compiled regex**: Compile reference pattern once
4. **Connection pooling**: Reuse database connections

## Error Recovery

### Rollback on Failure

```python
async def _apply_deltas_with_rollback(
    self,
    deltas: list[StateDelta],
    turn_number: int,
) -> None:
    applied = []

    try:
        for delta in deltas:
            await self._apply_delta(delta, turn_number)
            applied.append(delta)

    except Exception as e:
        # Rollback in reverse order
        for delta in reversed(applied):
            await self._rollback_delta(delta)
        raise
```

### Retry Logic

```python
MAX_COLLAPSE_RETRIES = 2

async def collapse_with_retry(
    self,
    branch: QuantumBranch,
    player_input: str,
    turn_number: int,
) -> CollapseResult:
    for attempt in range(MAX_COLLAPSE_RETRIES):
        try:
            return await self.collapse_branch(branch, player_input, turn_number)
        except StaleStateError:
            if attempt < MAX_COLLAPSE_RETRIES - 1:
                # Refresh and retry
                await self._refresh_branch_state(branch)
            else:
                raise
```
