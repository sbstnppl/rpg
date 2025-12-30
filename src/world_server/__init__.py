"""World Server - Quantum Pipeline for turn processing.

The quantum pipeline is the unified approach for processing player turns:
1. Predicts likely player actions from scene context
2. Pre-generates multiple outcome branches (success/failure/critical)
3. Matches player input to predicted actions
4. Rolls dice at runtime to select the appropriate branch
5. Collapses the branch and applies state changes
"""

from src.world_server.quantum import (
    QuantumPipeline,
    TurnResult,
    AnticipationConfig,
)

__all__ = [
    "QuantumPipeline",
    "TurnResult",
    "AnticipationConfig",
]
