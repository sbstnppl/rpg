# Anticipation and Caching: Topic-Awareness Problem

**Status:** Deferred
**Created:** 2025-12-30
**Related Issue:** `docs/issues/gm-ignores-player-input-specifics/`

## Problem Statement

The quantum pipeline's anticipation system pre-generates branches before knowing what the player will actually say. This works well for simple actions (move, pick up item) but fails for NPC conversations where the **topic** matters.

### Example Failure

1. Player at tavern, anticipation pre-generates: `interact_npc::innkeeper_tom::no_twist`
2. Branch generated with prompt: "Talk to [innkeeper_tom:Old Tom]" (no topic context)
3. LLM generates: "Tom offers you a room for the night"
4. Player actually says: "Ask Tom about any rumors he's heard"
5. Cache hit! But response is about rooms, not rumors

The player's intent (conversation topic) is lost because:
- Pre-generation happens before player input
- Cache keys don't include topic: `location::action::target::gm_decision`
- Generated narrative is topic-agnostic

## Why This Is Hard

### The Fundamental Conflict

| Requirement | Implication |
|-------------|-------------|
| Fast responses | Pre-generate branches before player acts |
| Topic-awareness | Need to know what player wants to discuss |
| Caching | Reuse branches for similar inputs |

Pre-generation and topic-awareness are inherently conflicting. You can't know the conversation topic until the player provides it.

### Topic Granularity Problem

Even if we pre-generate multiple topics:

| Broad Topic | Specific Player Input |
|-------------|----------------------|
| "rumors" | "rumors about ME specifically" |
| "rooms" | "the cheapest room you have" |
| "help" | "help finding the blacksmith's shop" |

Player specificity can't be fully anticipated.

## Approaches Considered

### A. Disable Anticipation for NPC Dialogue (Current Solution)

**How:** Set `AnticipationConfig.enabled = False` and always generate synchronously with full player input.

**Pros:**
- Simple to implement
- Always accurate
- No caching complexity

**Cons:**
- ~2-3 second latency for every NPC interaction
- Loses the "instant response" value proposition

**Status:** Implemented as interim fix.

### B. LLM-Based Semantic Matching

**How:**
1. Pre-generate branches with natural language descriptions: "Ask Tom about room prices", "Ask Tom about local gossip"
2. At runtime, use LLM to compare player input to descriptions
3. Select best match or regenerate if no good match

**Pros:**
- Semantic understanding of similarity
- Works for nuanced matching

**Cons:**
- Extra LLM call (~500ms) per turn
- Relies on LLM judgment
- Still misses when player intent is too specific

### C. Embedding-Based Similarity

**How:**
1. Pre-generate branches with descriptions, embed them
2. Embed player input at runtime
3. Cosine similarity for matching

**Pros:**
- Fast matching (~50ms)
- Semantic understanding

**Cons:**
- Requires embedding model
- Threshold tuning is tricky
- "Rumors about me" vs "rumors in town" would score similarly

### D. Two-Tier Generation

**How:**
1. Pre-generate "skeleton" branches with generic NPC response structure
2. At collapse time, pass player_input to narrator to "fill in" specifics
3. Cache logic/structure, generate prose at runtime

**Pros:**
- Keeps reasoning/logic cached
- Narrator is fast (prose only)
- Player specificity handled at collapse

**Cons:**
- More complex architecture
- Narrator needs enough context to stay coherent
- Still some latency at collapse

### E. Topic Extraction + Multi-Branch

**How:**
1. For each NPC, identify common topics: rooms, rumors, directions, trade
2. Pre-generate branches for each topic combination
3. Match player input to topic, select appropriate branch

**Pros:**
- Full pre-generation for common topics
- Fast runtime for predicted topics

**Cons:**
- Exponential branch explosion: 5 NPCs x 4 topics x 2 GM decisions = 40 branches
- Still misses unexpected topics
- Memory/generation cost

## Current Decision

**Anticipation is disabled** pending a proper solution. All NPC dialogue generates synchronously with full player input context.

This trades latency for accuracy. Future work should explore:

1. **Hybrid approach**: Cache common interactions, sync-generate rare ones
2. **Two-tier generation**: Cache reasoning, generate prose at collapse
3. **Smart invalidation**: Regenerate when topic doesn't match cached branch

## Implementation Notes

### Where Topics Are Lost (Code Paths)

| File | Lines | Issue |
|------|-------|-------|
| `action_matcher.py` | 257-292 | `_extract_verb_and_target()` discards topic |
| `action_predictor.py` | 190-198 | Predictions don't include topic |
| `schemas.py` | 194-204 | Cache key omits topic |
| `branch_generator.py` | 350-353 | Prompt says "Talk to NPC" not "Ask about X" |

### Fix Applied

`pipeline.py:_generate_sync()` now passes `player_input` to branch generator, which includes it in the prompt:

```
PLAYER ACTION: Talk to [innkeeper_tom:Old Tom]
PLAYER INPUT: "ask Tom about any rumors he's heard"
```

This fixes sync generation. Anticipation remains disabled.

## Future Work

1. Design topic-aware caching strategy
2. Implement semantic matching (LLM or embeddings)
3. Consider two-tier generation for performance
4. Re-enable anticipation with topic awareness
