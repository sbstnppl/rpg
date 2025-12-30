# LLM Deployment Guide

This document covers model selection, deployment configuration, and optimization for the RPG game's dual-model architecture.

## Architecture Overview

The game uses a **dual-model separation** for different tasks:

| Role | Purpose | Current Model | Recommended Upgrade |
|------|---------|---------------|---------------------|
| **Reasoning** | Logic, tool calls, combat, entity extraction | qwen3-32b | Qwen3-Next-80B-A3B-Instruct-FP8 |
| **Narrator** | Prose generation, scene descriptions, dialogue | magmell-12b | Keep (specialized for narrative) |

### Why Dual-Model?

Different tasks have different requirements:

- **Reasoning**: Needs structured output, tool calling, logical consistency
- **Narration**: Needs evocative prose, atmosphere, character voice, literary devices

A specialized 12B narrative model can outperform a general 80B model at prose generation.

---

## Hardware: ASUS Ascent GX10 (GB10)

| Spec | Value |
|------|-------|
| **GPU** | NVIDIA GB10 Grace Blackwell Superchip |
| **Memory** | 128GB unified LPDDR5x |
| **AI Performance** | 1 petaFLOP |
| **Architecture** | Blackwell (native FP4/FP8 tensor cores) |
| **Expandable** | 2x via NVLink-C2C |

### Memory Budget

| Config | Reasoning | Narrator | Headroom |
|--------|-----------|----------|----------|
| Current | qwen3-32b (~64GB) | magmell-12b (~24GB) | ~40GB |
| Upgraded | Qwen3-Next-80B-FP8 (~80GB) | magmell-12b (~24GB) | ~24GB |
| Consolidated | Qwen3-Next-80B-FP8 (~80GB) | (same model) | ~48GB |

---

## Model Recommendations

### Reasoning Model: Qwen3-Next-80B-A3B-Instruct-FP8

**Why upgrade from qwen3-32b:**

| Benchmark | Qwen3-32B | Qwen3-Next-80B | Improvement |
|-----------|-----------|----------------|-------------|
| MMLU-Pro | 71.9 | 80.6 | +12% |
| MMLU-Redux | 85.7 | 90.9 | +6% |
| GPQA | 54.6 | 72.9 | +33% |
| LiveCodeBench | - | 56.6 | Beats 235B |

**Architecture highlights:**

- **80B total / 3B active** (MoE with 512 experts, 11 activated per token)
- **Hybrid attention**: Gated DeltaNet (75%) + Gated Attention (25%)
- **Context**: 262K native, up to 1M with YaRN
- **Multi-Token Prediction (MTP)**: Faster inference

**Why Instruct over Thinking:**

| Aspect | Instruct | Thinking |
|--------|----------|----------|
| Context Length | 262K tokens | 131K tokens |
| Output Mode | Direct answers | `<think></think>` traces |
| Speed | Faster | Slower (reasoning tokens) |
| Best For | Tool calling, agents | Complex math proofs |

For RPG game logic, Instruct is the better choice.

### Narrator Model: Magmell-12B (MN-12B-Mag-Mell-R1)

**Keep for now** - specialized for creative writing.

| Aspect | Details |
|--------|---------|
| Architecture | Mistral-Nemo merge (7 models) |
| Size | 12.2B parameters |
| Specialty | Creative writing, worldbuilding, prose |
| Components | Hero (RP/tropes) + Monk (intelligence) + Deity (prose flair) |
| Optimal Settings | Temp 1.25, MinP 0.2, ChatML |

**Alternative narrator models** (if upgrade desired):

| Model | Size | Notes |
|-------|------|-------|
| Midnight-Miqu-70B | 70B | Popular for RP/narrative |
| Magnum-v4-72B | 72B | Strong creative writing merge |
| Rocinante-12B | 12B | Newer narrative-focused Mistral merge |

---

## vLLM Deployment

### Installation

```bash
uv venv
source .venv/bin/activate
uv pip install -U vllm --torch-backend auto
```

### Reasoning Model (Port 8150)

**Basic deployment:**

```bash
vllm serve Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 \
  --port 8150 \
  --served-model-name qwen3-next \
  --max-model-len 65536
```

**Optimized for Blackwell (GB10):**

```bash
VLLM_USE_FLASHINFER_MOE_FP8=1 \
VLLM_FLASHINFER_MOE_BACKEND=latency \
VLLM_USE_DEEP_GEMM=0 \
VLLM_USE_TRTLLM_ATTENTION=0 \
VLLM_ATTENTION_BACKEND=FLASH_ATTN \
vllm serve Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 \
  --port 8150 \
  --served-model-name qwen3-next \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.85
```

**With Multi-Token Prediction (faster inference):**

```bash
VLLM_USE_FLASHINFER_MOE_FP8=1 \
VLLM_FLASHINFER_MOE_BACKEND=latency \
vllm serve Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 \
  --port 8150 \
  --served-model-name qwen3-next \
  --max-model-len 65536 \
  --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'
```

**Extended context (256K):**

```bash
vllm serve Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 \
  --port 8150 \
  --served-model-name qwen3-next \
  --max-model-len 262144 \
  --gpu-memory-utilization 0.9
```

### Narrator Model (Port 8151)

```bash
vllm serve inflatebot/MN-12B-Mag-Mell-R1 \
  --port 8151 \
  --served-model-name magmell-12b \
  --max-model-len 32768
```

### Troubleshooting

**CUDA illegal memory access error:**

```bash
# Add this flag if you encounter IMA errors
--compilation_config.cudagraph_mode=PIECEWISE
```

**Memory issues:**

```bash
# Reduce context length
--max-model-len 32768

# Or reduce memory utilization
--gpu-memory-utilization 0.8
```

---

## Environment Configuration

Update `.env` for the new models:

```bash
# vLLM endpoints (OpenAI-compatible)
NARRATOR_BASE_URL=http://localhost:8151/v1
REASONING_BASE_URL=http://localhost:8150/v1
CHEAP_BASE_URL=http://localhost:8150/v1

# Task-Specific LLM (format: provider:model)
NARRATOR=openai:magmell-12b
REASONING=openai:qwen3-next
CHEAP=openai:qwen3-next
```

---

## Sampling Parameters

### Reasoning (Qwen3-Next)

```python
# Recommended by Qwen
temperature = 0.7
top_p = 0.8
top_k = 20
min_p = 0
presence_penalty = 0.5  # Reduces repetition
max_tokens = 16384
```

### Narrator (Magmell)

```python
# Recommended for creative output
temperature = 1.25
min_p = 0.2
max_tokens = 2048
```

---

## Quantization Options

### FP8 (Recommended for GB10)

- **Model**: `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8`
- **Size**: ~80GB
- **Quality**: Minimal degradation
- **Speed**: Native Blackwell tensor core support

### NVFP4 (Experimental)

For even more memory headroom:

- **Size**: ~40GB
- **Quality**: Some degradation
- **Use case**: Very long context or running both models with headroom

LLM Compressor supports Qwen3-Next quantization:

```bash
pip install llmcompressor
# See: https://docs.vllm.ai/projects/llm-compressor/
```

---

## Abliterated Models: Not Recommended

"Abliterated" models (e.g., `huihui-ai/Huihui-Qwen3-Next-80B-A3B-*-abliterated`) remove safety filters. **Don't use them** because:

1. No official benchmarks - quality impact unknown
2. RPG game doesn't need to bypass safety
3. No official FP8 versions available
4. Extra risk for zero benefit

Use the official Qwen FP8 models instead.

---

## Performance Expectations

### Qwen3-Next-80B-A3B vs Qwen3-32B

| Metric | Qwen3-32B | Qwen3-Next-80B |
|--------|-----------|----------------|
| Active Params | 32B | 3B |
| Inference Speed | Baseline | Similar or faster (MoE) |
| Quality | Good | Significantly better |
| Context | 41K | 262K |
| Memory (FP8) | ~64GB | ~80GB |

The MoE architecture means only 3B parameters are active per token, so inference speed is comparable despite the larger total size.

### Long-Context Performance (1M RULER Benchmark)

| Context Length | Accuracy |
|----------------|----------|
| 4K | 98.5% |
| 256K | 93.5% |
| 512K | 86.9% |
| 1M | 80.3% |

---

## References

- [Qwen3-Next-80B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct)
- [Qwen3-Next-80B-A3B-Instruct-FP8](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8)
- [MN-12B-Mag-Mell-R1](https://huggingface.co/inflatebot/MN-12B-Mag-Mell-R1)
- [vLLM Qwen3-Next Guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3-Next.html)
- [NVIDIA DGX Spark vLLM Playbook](https://build.nvidia.com/spark/vllm)
- [EQ-Bench Creative Writing Leaderboard](https://eqbench.com/creative_writing.html)
