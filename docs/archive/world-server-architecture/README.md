# World Server Architecture

This folder contains the implementation plan for the World Server - a background system that pre-generates game content to hide LLM latency.

## Core Concept

> "The world exists in potential states until observed, then collapses to concrete reality."

While the player reads narrative text (48-120 seconds), background processes pre-generate likely next locations, making transitions feel instant.

## Documents

| Document | Description |
|----------|-------------|
| [Implementation Plan](./implementation-plan.md) | Phased implementation with actionable tasks |
| [Architecture](./architecture.md) | Component design and data flow |
| [Timing Analysis](./timing-analysis.md) | Latency calculations and optimization |

## Quick Start

1. Install vLLM on your server (see Phase 2)
2. Implement AnticipationEngine (Phase 1)
3. Integrate with game loop
4. Test and iterate

## Key Insight

```
Player reading time:  48-120 seconds
LLM generation time:  50-80 seconds (qwen3:32b)
                      ─────────────
Overlap:              Near-perfect match
```

With vLLM's parallel processing, we can pre-generate 3 adjacent locations simultaneously.
