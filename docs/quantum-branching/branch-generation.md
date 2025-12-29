# Branch Generation

The `BranchGenerator` creates narrative variants for each predicted action, generating full prose with state deltas.

## Overview

Branch generation creates pre-computed narratives for all possible outcomes of an action:

```
ActionPrediction: "talk to merchant"
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                   BranchGenerator                      │
│                                                        │
│  GM Decision: "no_twist"                              │
│  ┌─────────────────────────────────────────────────┐  │
│  │ SUCCESS:                                         │  │
│  │ "The merchant smiles and shows you his wares..." │  │
│  │ Δ relationship: +5 trust                         │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ FAILURE:                                         │  │
│  │ "The merchant seems distracted, barely..."       │  │
│  │ Δ relationship: 0                                │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ CRITICAL_SUCCESS:                                │  │
│  │ "The merchant recognizes your sigil and..."      │  │
│  │ Δ relationship: +15 trust, Δ fact: merchant_ally │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

## QuantumBranch Schema

```python
@dataclass
class QuantumBranch:
    branch_key: str              # "location::action_type::target::gm_decision"
    action: ActionPrediction     # Original prediction
    gm_decision: GMDecision      # GM twist decision
    variants: dict[str, OutcomeVariant]  # "success" -> variant
    generated_at: datetime       # Creation timestamp
    generation_time_ms: float    # Performance metric
    state_version: int           # For staleness detection
```

## OutcomeVariant Schema

```python
@dataclass
class OutcomeVariant:
    variant_type: VariantType    # SUCCESS, FAILURE, etc.
    narrative: str               # Full prose with [key:name] format
    state_deltas: list[StateDelta]  # State changes
    requires_dice: bool          # Whether roll needed
    dc: int | None              # Difficulty class if dice needed
    skill: str | None           # Skill for check
    time_passed_minutes: int    # Game time elapsed
```

### Variant Types

```python
class VariantType(Enum):
    SUCCESS = "success"                    # Standard success
    FAILURE = "failure"                    # Standard failure
    CRITICAL_SUCCESS = "critical_success"  # Exceptional success (double 10)
    CRITICAL_FAILURE = "critical_failure"  # Bad failure (double 1)
```

## Generation Process

### 1. Build Context

```python
async def generate_branches(
    self,
    action: ActionPrediction,
    gm_decisions: list[GMDecision],
    manifest: NarratorManifest,
    context: BranchContext,
) -> list[QuantumBranch]:
    branches = []

    for decision in gm_decisions:
        # Build generation context
        gen_context = self._build_generation_context(
            action, decision, manifest, context
        )

        # Generate variants
        variants = await self._generate_variants(gen_context)

        # Create branch
        branch = QuantumBranch(
            branch_key=self._make_branch_key(action, decision, context),
            action=action,
            gm_decision=decision,
            variants=variants,
            generated_at=datetime.now(),
            state_version=context.state_version,
        )
        branches.append(branch)

    return branches
```

### 2. Generate Variants

```python
async def _generate_variants(
    self,
    context: GenerationContext,
) -> dict[str, OutcomeVariant]:
    # Build prompt for LLM
    prompt = self._build_prompt(context)

    # Call LLM
    response = await self.llm.generate(
        messages=[Message(role="user", content=prompt)],
        response_format=BranchGenerationResponse,
    )

    # Parse and validate
    return self._parse_variants(response, context)
```

## LLM Prompt Template

```python
BRANCH_GENERATION_PROMPT = """
You are generating narrative variants for a player action in an RPG.

SCENE CONTEXT:
Location: {{ manifest.location_display }}
Description: {{ manifest.location_description }}

ENTITIES PRESENT:
{% for npc in manifest.npcs.values() %}
- [{{ npc.entity_key }}:{{ npc.display_name }}] - {{ npc.description }}
{% endfor %}
{% for item in manifest.items_at_location.values() %}
- [{{ item.entity_key }}:{{ item.display_name }}] - {{ item.description }}
{% endfor %}

PLAYER ACTION:
Type: {{ action.action_type }}
Target: {{ action.target_key }} ({{ target_display_name }})

GM DECISION: {{ gm_decision.decision_type }}
{% if gm_decision.grounding_facts %}
Twist justification: {{ gm_decision.grounding_facts | join(', ') }}
{% endif %}

INSTRUCTIONS:
Generate 2-4 narrative variants:
1. SUCCESS - Player achieves their goal
2. FAILURE - Player fails (only if dice roll required)
3. CRITICAL_SUCCESS - Exceptional outcome with bonus (optional)
4. CRITICAL_FAILURE - Bad outcome with complication (optional)

For each variant, provide:
- narrative: Full prose (2-4 paragraphs). Use [entity_key:display_name] format for ALL entity references.
- state_deltas: Array of state changes (relationship, fact, item, location)
- requires_dice: Whether this outcome needs a dice roll
- dc: Difficulty class (10-20) if dice required
- skill: Skill to check if dice required
- time_passed_minutes: Game time elapsed (1-60)

IMPORTANT:
- All entity references MUST use [key:name] format: [bartender_001:Marcus]
- Never invent entities not in the scene
- Keep narrative grounded in scene context
- State deltas must be specific and actionable

Output as JSON matching BranchGenerationResponse schema.
"""
```

## Response Schema

```python
class BranchGenerationResponse(BaseModel):
    """Structured response from branch generation LLM call."""

    variants: list[VariantResponse]

    class VariantResponse(BaseModel):
        variant_type: str
        narrative: str
        state_deltas: list[DeltaResponse]
        requires_dice: bool = False
        dc: int | None = None
        skill: str | None = None
        time_passed_minutes: int = 5

    class DeltaResponse(BaseModel):
        delta_type: str  # "relationship", "fact", "item", "location"
        entity_key: str
        operation: str   # "add", "update", "remove"
        value: dict      # Type-specific data
```

## State Delta Types

### Relationship Delta

```python
StateDelta(
    delta_type=DeltaType.RELATIONSHIP,
    entity_key="merchant_001",
    operation="update",
    value={
        "dimension": "trust",
        "change": 5,  # +5 trust
    }
)
```

### Fact Delta

```python
StateDelta(
    delta_type=DeltaType.FACT,
    entity_key="world",
    operation="add",
    value={
        "subject": "merchant_001",
        "predicate": "shared_secret_with",
        "object": "player",
    }
)
```

### Item Delta

```python
StateDelta(
    delta_type=DeltaType.ITEM,
    entity_key="healing_potion_001",
    operation="update",
    value={
        "holder_id": "player",  # Player now holds item
    }
)
```

### Location Delta

```python
StateDelta(
    delta_type=DeltaType.LOCATION,
    entity_key="player",
    operation="update",
    value={
        "location_key": "market_square",
    }
)
```

## GM Decision Integration

The `GMDecisionOracle` determines which twists to generate:

```python
class GMDecisionOracle:
    def predict_decisions(
        self,
        action: ActionPrediction,
        world_state: WorldState,
    ) -> list[GMDecision]:
        decisions = [
            GMDecision("no_twist", 0.70, [])  # Base case
        ]

        # Check for grounded twists
        if action.action_type == ActionType.MOVE:
            if world_state.has_fact("recent_theft", action.target_key):
                decisions.append(GMDecision(
                    "theft_accusation",
                    0.15,
                    grounding_facts=["recent_theft", "player_is_stranger"]
                ))

        if action.action_type == ActionType.INTERACT_NPC:
            if world_state.has_fact("npc_has_secret", action.target_key):
                decisions.append(GMDecision(
                    "secret_reveal",
                    0.10,
                    grounding_facts=["npc_has_secret"]
                ))

        return decisions
```

## Narrative Quality

### Entity Reference Format

All entity references use `[key:name]` format:

```
[marcus_001:Marcus] pours you an ale and slides it across the bar.
"That'll be two coppers," he says with a wink.

You notice [serving_girl_002:Elena] watching from the kitchen doorway.
```

This format:
- Grounds narrative in actual entities
- Enables parsing for state extraction
- Allows display stripping for clean output

### Consistency Rules

1. **No invented entities**: Only reference entities in manifest
2. **Correct pronouns**: Match entity gender
3. **Time continuity**: Events follow logically
4. **State accuracy**: Deltas match narrative events

## Validation

Generated branches are validated before caching:

```python
class BranchValidator:
    def validate(
        self,
        branch: QuantumBranch,
        manifest: GroundingManifest,
    ) -> ValidationResult:
        issues = []

        # Validate each variant
        for variant_type, variant in branch.variants.items():
            # Check narrative consistency
            narrative_result = self.narrative_validator.validate(
                variant.narrative, manifest
            )
            issues.extend(narrative_result.issues)

            # Check delta validity
            delta_result = self.delta_validator.validate(
                variant.state_deltas
            )
            issues.extend(delta_result.issues)

        # Ensure required variants exist
        if "success" not in branch.variants:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="missing_success_variant",
                message="Branch must have success variant",
            ))

        return ValidationResult(issues=issues)
```

## Performance Optimization

### Batched Generation

Generate all variants in a single LLM call:

```python
# Instead of 4 separate calls for 4 variants
# Generate all in one structured response
response = await self.llm.generate(
    prompt=self._build_prompt(context),
    response_format=BranchGenerationResponse,  # Returns all variants
)
```

### Parallel Branch Generation

Generate branches for multiple actions concurrently:

```python
async def generate_all_branches(
    self,
    actions: list[ActionPrediction],
    gm_decisions_map: dict[str, list[GMDecision]],
    manifest: NarratorManifest,
    context: BranchContext,
) -> list[QuantumBranch]:
    tasks = []
    for action in actions:
        decisions = gm_decisions_map.get(action.target_key, [])
        task = self.generate_branches(action, decisions, manifest, context)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return [branch for branches in results for branch in branches]
```

## Error Handling

```python
async def generate_branches(self, ...) -> list[QuantumBranch]:
    try:
        response = await self.llm.generate(...)
        variants = self._parse_variants(response, context)

        # Validate before returning
        validation = self.validator.validate_variants(variants, manifest)
        if not validation.is_valid:
            logger.warning(f"Branch validation issues: {validation.issues}")
            # Fix common issues or regenerate
            variants = self._fix_common_issues(variants, validation.issues)

        return self._create_branches(variants, ...)

    except LLMResponseParseError as e:
        logger.error(f"Failed to parse branch response: {e}")
        raise BranchGenerationError("Invalid LLM response format")

    except ValidationError as e:
        logger.error(f"Branch validation failed: {e}")
        raise BranchGenerationError("Generated branch failed validation")
```
