# Hardware Comparison — LLM Inference (Local, Cloud, and Air-Gap)

Comparing the RTX 5090, RTX PRO 6000, Mac Studio M3 Ultra (256GB), Framework Desktop Strix Halo (128GB), NVIDIA DGX systems, and private cloud GPU instances for LLM inference across coding, reasoning, and agentic workloads.

> This analysis focuses on practical capability gains relative to cost — not just what hardware *can* run, but whether the upgrade is worth it. Includes an air-gap-compliant private cloud option for teams that need data privacy without buying hardware.

---

## Hardware Specs

| Spec | RTX 5090 | RTX PRO 6000 | Mac Studio M3 Ultra 256GB | Strix Halo 128GB |
|---|---|---|---|---|
| **Memory** | 32 GB GDDR7 | 96 GB GDDR7 ECC | 256 GB unified LPDDR5 | 128 GB LPDDR5X |
| **Bandwidth** | ~1,792 GB/s | ~1,792 GB/s | ~819 GB/s | ~215 GB/s |
| **FP16 Compute** | ~105 TFLOPS | ~125 TFLOPS | ~27 TFLOPS | ~59 TFLOPS |
| **FP4 (Tensor)** | ~380 TFLOPS | ~380 TFLOPS | N/A | N/A |
| **Software Stack** | CUDA | CUDA + ECC | Metal / MLX | ROCm / Vulkan |
| **Approx Price** | ~$2,000 (GPU) | ~$6,500+ (GPU) | ~$8,000-10,000 (system) | ~$2,500 (system) |
| **TDP** | 575W (GPU) | 600W (GPU) | ~480W (system) | ~65W (APU) |
| **Standalone?** | No (needs PC) | No (needs workstation) | Yes | Yes |

---

## What Fits Where

| Model | Type | Size | 5090 (32GB) | PRO 6000 (96GB) | M3 Ultra (256GB) | Strix Halo (128GB) |
|---|---|---|---|---|---|---|
| Qwen3.5 27B Q4_K_M | Dense | ~17 GB | Yes | Yes | Yes | Yes |
| GLM-4.7 Flash (MoE, 3B active) | MoE | ~17 GB | Yes | Yes | Yes | Yes |
| Qwen3 Coder 30B (MoE, 3B active) | MoE | ~17 GB | Yes | Yes | Yes | Yes |
| Qwen 2.5 Coder 32B Q4_K_M | Dense | ~19 GB | Yes | Yes | Yes | Yes |
| DeepSeek R1 32B Q4_K_M | Dense | ~19 GB | Yes | Yes | Yes | Yes |
| Qwen3-72B Q4_K_M | Dense | ~48 GB | **No** | Yes | Yes | Yes |
| Llama 3.3 70B Q6_K | Dense | ~54 GB | **No** | Yes | Yes | Yes |
| GPT-OSS 120B MXFP4 | MoE (ISWA) | ~59 GB | **No** | Yes | Yes | Yes |
| Llama 4 Scout 109B Q4_K_M | MoE (17B active) | ~61 GB | **No** | Yes | Yes | Yes |
| Qwen 3.5 122B-A10B MXFP4 | MoE (10B active) | ~70 GB | **No** | Yes | Yes | Yes |
| dots1 142B Q4_K_XL | MoE | ~84 GB | **No** | Yes | Yes | Yes |
| Qwen3-235B Q3_K_M | MoE (22B active) | ~105 GB | **No** | **No** | Yes | Yes (barely) |
| Qwen3-235B Q4_K_M | MoE (22B active) | ~140 GB | **No** | **No** | Yes | **No** |
| Qwen3-235B Q6_K | MoE (22B active) | ~180 GB | **No** | **No** | Yes | **No** |
| Qwen3-Coder-480B Q2-Q3 | MoE (35B active) | ~200-220 GB | **No** | **No** | Yes | **No** |

---

## Estimated Token Generation Speeds

Token generation is primarily memory-bandwidth-bound. MoE models only read active parameters per token, so they run disproportionately fast relative to their total size.

### Models that fit all hardware

| Model | 5090 | PRO 6000 | M3 Ultra 256GB | Strix Halo 128GB |
|---|---|---|---|---|
| Qwen3.5 27B Q4 | ~80-90 tok/s | ~80-90 tok/s | ~40-45 tok/s | ~10-12 tok/s |
| GLM-4.7 Flash (MoE) | ~150+ tok/s | ~150+ tok/s | ~70-80 tok/s | ~54 tok/s |
| Qwen3 Coder 30B (MoE) | ~150+ tok/s | ~150+ tok/s | ~70-80 tok/s | ~70 tok/s |
| DeepSeek R1 32B Q4 | ~60-80 tok/s | ~60-80 tok/s | ~30-35 tok/s | ~11 tok/s |

### Models that require >32GB (exclude 5090)

| Model | PRO 6000 | M3 Ultra 256GB | Strix Halo 128GB |
|---|---|---|---|
| Qwen3-72B Q4_K_M | ~40-45 tok/s | ~18-20 tok/s | ~5 tok/s |
| Llama 3.3 70B Q6_K | ~30-33 tok/s | ~14-16 tok/s | ~3.8 tok/s |
| GPT-OSS 120B MXFP4 | ~200+ tok/s | ~90-100 tok/s | ~51 tok/s |
| Qwen 3.5 122B-A10B MXFP4 | ~120-150 tok/s | ~55-65 tok/s | ~18 tok/s |
| Llama 4 Scout 109B Q4_K_M | ~100-130 tok/s | ~45-55 tok/s | ~19 tok/s |

### Models that require >96GB (exclude 5090 and PRO 6000)

| Model | M3 Ultra 256GB | Strix Halo 128GB |
|---|---|---|
| Qwen3-235B Q3_K_M | ~6-8 tok/s | ~7.8 tok/s |
| Qwen3-235B Q4_K_M | ~5-6 tok/s | Does not fit |
| Qwen3-235B Q6_K | ~3-4 tok/s | Does not fit |
| Qwen3-Coder-480B Q2-Q3 | ~3-5 tok/s (MoE helps) | Does not fit |

---

## Why MoE Models Dominate on Bandwidth-Limited Hardware

Mixture-of-Experts (MoE) models activate only a fraction of their total parameters per token. This is transformative on bandwidth-limited hardware:

| Model | Total Params | Active Params | Strix Halo tok/s | Why |
|---|---|---|---|---|
| Qwen3 Coder 30B | 30B | 3B | 69.6 | ~6x faster than dense 32B |
| DeepSeek Coder V2 16B | 16B | ~2B | 68.0 | ~6x faster than dense 16B |
| GLM-4.7 Flash | — | — | 54.1 | Small active set |
| GPT-OSS 120B | 120B | — | 51.1 | ISWA architecture |
| Llama 4 Scout | 109B | 17B | 19.2 | ~4x faster than dense 70B |
| Qwen 3.5 122B-A10B | 122B | 10B | 18.3 | ~4x faster than dense 70B |
| Qwen3-235B | 235B | 22B | 7.8 | Largest that fits |

**Key insight:** A dense 27B model activates *more* compute per token than a 122B MoE with 10B active parameters. Total parameter count is misleading — active parameters determine per-token quality, while total parameters determine the breadth of the expert pool.

---

## Category Analysis

### 1. Coding

| Hardware | Best Available Model | SWE-bench Class | Speed | Experience |
|---|---|---|---|---|
| **5090** | Qwen3.5 27B, GLM-4.7 Flash, Qwen3 Coder 30B | ~70-75% | 80-150 tok/s | Instant, fluid |
| **PRO 6000** | Qwen 3.5 122B-A10B, Qwen3-72B | ~75-78% | 40-150 tok/s | Instant, fluid |
| **M3 Ultra 256GB** | Qwen3-Coder-480B (Q2-Q3), Qwen3-235B (Q4+) | ~76-80% (but Q2 degrades this) | 3-6 tok/s | Slow, functional |
| **Strix Halo 128GB** | Qwen3-235B (Q3), Qwen 3.5 122B-A10B | ~70-78% | 7.8-18 tok/s | Usable to slow |

- Qwen3-Coder-480B (35B active, 480B total) is the open-source SWE-bench SOTA — comparable to Claude Sonnet 4. Only fits on M3 Ultra 256GB, but at Q2 quantization the quality degrades significantly.
- Qwen 2.5 Coder 32B on the 5090 is listed as "Best Quality" for coding even in the Strix Halo community model guide.
- **The jump from 5090-tier to PRO-6000-tier models is ~3-5% on benchmarks — incremental, not transformational.**

### 2. Reasoning

| Hardware | Best Available Model | AIME 2025 Class | Speed | Experience |
|---|---|---|---|---|
| **5090** | GLM-4.7 Flash, DeepSeek R1 32B | ~95% | 60-150 tok/s | Instant |
| **PRO 6000** | Qwen3-72B, DeepSeek R1 70B | ~96% | 30-45 tok/s | Fast |
| **M3 Ultra 256GB** | Qwen3-235B Q4-Q6 | ~97% | 3-6 tok/s | Slow |
| **Strix Halo 128GB** | Qwen3-235B Q3 | ~96-97% | ~7.8 tok/s | Slow |

- GLM-4.7 Flash already hits 95.7% on AIME 2025 and fits in 17GB — hard to meaningfully beat.
- Qwen3-235B at Q4-Q6 is genuinely the strongest open reasoner, but chain-of-thought outputs of 2,000-5,000 tokens take 5-17 minutes at 3-6 tok/s.
- **The reasoning quality gap between 5090-tier and M3-Ultra-tier models is real but narrow (~2-3%).**
- The gap matters most on PhD-level science, multi-step proofs, and novel problem-solving — not typical development tasks.

### 3. Agentic / Tool Calling

| Hardware | Best Available Model | Agent Benchmark | Speed | Experience |
|---|---|---|---|---|
| **5090** | GLM-4.7 Flash (87.4% t2-bench), Qwen3 14B (0.971 BFCL F1) | Top tier | 150+ tok/s | Excellent |
| **PRO 6000** | Same as 5090, plus Hermes 4 70B for quality | Top tier | 40-150 tok/s | Excellent |
| **M3 Ultra 256GB** | Qwen3-Coder-480B (agent RL trained) | Top tier | 3-5 tok/s | Sluggish |
| **Strix Halo 128GB** | GLM-4.7 Flash, Qwen3 Coder 30B | Top tier | 50-70 tok/s | Good |

- Agentic workflows are latency-bound — many rapid round-trips where speed per turn matters enormously.
- A 10-step agent loop: 5090 completes in ~50 seconds, M3 Ultra with large model takes ~10 minutes.
- The best agentic models (GLM-4.7 Flash, Qwen3 14B) all fit in 32GB — more parameters do not significantly help tool coordination.
- **No hardware upgrade improves agentic performance over what the 5090 already provides.**

---

## Strix Halo Assessment

The Strix Halo (128GB LPDDR5X, ~215 GB/s) sits in an awkward middle ground:

- **vs 5090:** 4x more memory but ~8x less bandwidth. Models that fit in 32GB run 6-8x slower.
- **vs PRO 6000:** 32GB more capacity (128 vs 96) but ~8x less bandwidth. Nearly everything the Strix Halo can run, the PRO 6000 runs faster — except Qwen3-235B Q3 (105GB).
- **vs M3 Ultra 256GB:** Half the memory, ~4x less bandwidth. Strictly worse in every dimension except price.

**Where Strix Halo makes sense:**
- Budget constraint (~$2,500 for a complete system)
- Low power / compact form factor (65W TDP)
- Running MoE models in the 60-100GB range at modest speeds (19-51 tok/s for MoE models)
- You don't have or want a discrete GPU workstation

**Where it doesn't:**
- Any scenario where a 5090 or PRO 6000 is available — they're faster at every model size they can fit.
- Dense 70B models crawl at 3.8-5 tok/s.
- The sole exclusive model (Qwen3-235B Q3 at ~105GB) runs at 7.8 tok/s — marginal practical value.

---

## Is Upgrading From a 5090 Worth It?

### The 5090 baseline (what you already have)

| Area | Best Model | Benchmark | Speed |
|---|---|---|---|
| Coding | Qwen3.5 27B, GLM-4.7 Flash, Qwen3 Coder 30B | ~73-75% SWE-bench | 80-150 tok/s |
| Reasoning | GLM-4.7 Flash, DeepSeek R1 32B | ~95% AIME | 60-150 tok/s |
| Agentic | GLM-4.7 Flash (87.4% t2-bench) | Top tier | 150+ tok/s |

This puts you at roughly the **90th percentile** of local inference capability.

### What each upgrade buys

| | +PRO 6000 ($6,500+) | +M3 Ultra 256GB ($8-10K) | +Strix Halo ($2,500) |
|---|---|---|---|
| **New models accessible** | 32-96GB tier (70B dense, 120B MoE) | 32-220GB tier (235B, 480B) | 32-105GB tier |
| **Coding improvement** | +3-5% SWE-bench | +5-8% (but Q2 quant degrades it) | +3-5% |
| **Reasoning improvement** | +1% AIME | +2-3% AIME | +1-2% |
| **Agentic improvement** | None meaningful | None meaningful | None meaningful |
| **Speed of new models** | 40-200 tok/s (excellent) | 3-6 tok/s (slow) | 5-51 tok/s (varies) |
| **Cost per % improvement** | ~$1,300-2,100 per % | ~$1,000-2,000 per % | ~$500-800 per % |

### The API alternative

For a few hundred dollars per year in API costs, you get access to models that beat everything you could run locally:

| API Model | SWE-bench | Cost per M tokens (in/out) | Speed |
|---|---|---|---|
| Claude Sonnet 4 | ~79.6% | $3 / $15 | ~60-80 tok/s |
| Claude Opus 4 | ~80.8% | $15 / $75 | ~30-40 tok/s |
| GPT-5.2 | ~80% | Varies | Fast |
| DeepSeek V3.2 (API) | ~73% | $0.27 / $1.1 | ~33 tok/s |

---

## Recommendations

### If you have a 5090 and nothing else

1. **Don't upgrade for LLM capability alone.** The 5090 is already in the top tier for local inference. The marginal quality gains from larger hardware don't justify the cost.
2. **Use API calls for hard problems.** $200-300/year in API credits gives you frontier model quality (Claude, GPT-5, DeepSeek) at faster speeds than any local hardware.
3. **Wait 6-12 months.** The 32B-class models are improving so rapidly that next year's 32B will likely match today's 70B — all on your existing 5090.

### If you need a second machine for other reasons

- **PRO 6000** makes sense if you have non-LLM professional needs for 96GB VRAM (ML training, rendering, large datasets) and the LLM capability is a bonus. It runs 70B-class models at interactive speeds — a genuine comfort upgrade.
- **M3 Ultra 256GB** makes sense if you need a standalone Mac for professional work, have privacy/air-gap requirements that prohibit API use, or specifically need frontier 200B+ models locally.
- **Strix Halo** makes sense only on a tight budget or if you need a low-power, compact, self-contained LLM box.

### Best two-machine combos (if upgrading)

| Combo | Coverage | Strength | Weakness |
|---|---|---|---|
| **5090 + PRO 6000** | 0-96GB models | Everything runs at max bandwidth | No access to 100GB+ models |
| **5090 + M3 Ultra 256GB** | 0-220GB models | Widest model coverage | 32-96GB tier runs at half the PRO 6000's speed |
| **5090 + Strix Halo** | 0-105GB models | Budget friendly | Strix Halo is slow for everything, narrow exclusive tier |

---

## Beyond Desktop: Enterprise and Homelab Hardware

### NVIDIA DGX Station (Deskside — Homelab Ceiling)

| Spec | Value |
|---|---|
| Chip | GB300 Grace Blackwell Ultra Desktop Superchip |
| GPU | 1x Blackwell Ultra |
| GPU Memory | 252 GB HBM3e @ 7.1 TB/s |
| CPU | 1x Grace 72-Core Neoverse V2 |
| CPU Memory | 496 GB LPDDR5X @ 396 GB/s |
| Total Coherent Memory | **748 GB** (NVLink-C2C @ 900 GB/s) |
| FP4 Performance | 20 PFLOPS (dense) / 153 PFLOPS (sparse) |
| FP16 Performance | 5 PFLOPS |
| Power | 1,600W |
| Form Factor | Deskside tower |
| Price (est.) | ~$50,000-80,000+ (contact NVIDIA partners) |
| Optional | Can add 1x RTX PRO 6000 via PCIe Gen 5 x16 |
| Availability | Coming 2026 via Dell, HPE, Lenovo, Supermicro |
| Model Capacity | Up to 1 trillion parameters |

The DGX Station is the **practical ceiling for a homelab**. 748 GB coherent memory means every open-source model runs at good quantization. 7.1 TB/s GPU bandwidth means MoE models run at 200-300+ tok/s. Requires a dedicated 240V/20A circuit (~$300-800 CAD to install) and good ventilation.

### NVIDIA DGX Spark (Budget Desktop AI)

| Spec | Value |
|---|---|
| Chip | GB10 Grace Blackwell Superchip |
| Memory | 128 GB LPDDR5x unified @ 273 GB/s |
| FP4 Performance | 1 PFLOP (sparse) |
| CPU | 20-core Arm (10x Cortex-X925 + 10x Cortex-A725) |
| Storage | 4 TB NVMe M.2 |
| Power | 240W (system) |
| Size | 150mm x 150mm x 50.5mm, 1.2 kg |
| Model Capacity | Inference up to 200B, fine-tuning up to 70B |
| Two linked | Up to 405B parameters |
| Price (est.) | ~$3,000-4,000 |

Similar memory tier to Strix Halo (128GB) but with Blackwell tensor cores. Bandwidth-limited at 273 GB/s. Not a significant advantage over a 5090 for the three priority areas (coding, reasoning, agentic).

### NVIDIA DGX B300 (Rack Server — Theoretical Homelab)

| Spec | Value |
|---|---|
| GPUs | 8x Blackwell Ultra SXM |
| GPU Memory | **2.1 TB HBM3e** |
| NVLink Bandwidth | **14.4 TB/s** aggregate |
| FP4 Performance | 144 PFLOPS (sparse) / 108 PFLOPS (dense) |
| FP16 Performance | 36 PFLOPS (sparse) |
| CPU | Intel Xeon 6776P |
| Power | **~14 kW** |
| Form Factor | 10U rack mount |
| Price (est.) | ~$300,000-500,000+ |
| Status | **Shipping now** |

2.1 TB of HBM3e means every open-source model runs at FP16 with no quantization. Multiple frontier models simultaneously. However:

- **14 kW** = ~58A on 240V. Most residential panels are 200A — this is 30% of total capacity.
- Requires dedicated electrical sub-panel upgrade ($2,000-5,000 CAD), industrial cooling (4-5 ton AC unit), sound insulation (70-80+ dB under load).
- Technically possible in a dedicated basement/garage room, but a serious infrastructure project.

### Homelab Feasibility Summary

| System | GPU Memory | Power | Price | Homelab? |
|---|---|---|---|---|
| DGX Spark | 128 GB | 240W | ~$3-4K | Trivial |
| DGX Station | 748 GB | 1.6 kW | ~$50-80K | Easy (240V circuit) |
| DGX Station + RTX PRO 6000 | 844 GB | ~2.2 kW | ~$60-90K | Easy |
| Multi-GPU workstation (4x PRO 6000) | 384 GB | ~3 kW | ~$30-40K | Moderate |
| DGX B300 | 2.1 TB | 14 kW | ~$300-500K | Hard (major electrical/cooling) |
| GB300 NVL72 / SuperPOD | 18+ TB | 100+ kW | $2M+ | No — data center only |

---

## GLM-5.1: The Model to Watch

### Current Status (March 2026)

- **GLM-5** is available via API. **GLM-5.1** announced, weights releasing **April 6-7, 2026**.
- GLM-5 already ranks **#8 on Arena Code leaderboard** (score 1445) and **#20 overall**.

### LMSys Arena Code Rankings (Top 10)

| Rank | Model | Code Score |
|---|---|---|
| 1 | claude-opus-4-6 | 1549 |
| 2 | claude-opus-4-6-thinking | 1545 |
| 3 | claude-sonnet-4-6 | 1523 |
| 4 | claude-opus-4-5-thinking | 1491 |
| 5 | claude-opus-4-5 | 1465 |
| 6 | gpt-5.4-high | 1457 |
| 7 | gemini-3.1-pro | 1455 |
| **8** | **glm-5** | **1445** |
| 9 | glm-4.7 | 1439 |
| 10 | gemini-3-pro | 1438 |

### What This Means

- GLM-5 is **~104 Elo below Opus 4.6** on coding — roughly at **Claude Opus 4.5 level**.
- If GLM-5.1 improves by 30-50 Elo (reasonable generational bump), it would land at ~1475-1495, **near or matching Opus 4.5** for code.
- Still **~55-75 points below Opus 4.6** — a meaningful gap.
- GLM-5 also ranks #20 overall, #25 on hard prompts, #33 on math, #18 on creative writing and instruction following.

### Architecture — Unknown

Zhipu has not disclosed GLM-5/5.1's architecture or size. GLM-4.7 was a ~355B MoE. If GLM-5.1 follows a similar MoE pattern:

| Scenario | Total Params | Active Params | Size at Q4 | Fits 5090? | Fits H200? | Fits DGX Station? |
|---|---|---|---|---|---|---|
| Similar to GLM-4.7 | ~400B MoE | ~30-40B | ~200-250 GB | No | 2x H200 | Yes |
| Larger | ~600-800B MoE | ~40-60B | ~300-500 GB | No | 4-8x H100 | Yes |
| Dense (unlikely) | ~70-120B | 70-120B | ~40-80 GB | Maybe (small) | Yes | Yes |

**Wait for April 6-7 weight release** to confirm architecture and hardware requirements.

---

## Matching Frontier Models: What Does It Actually Take?

### Target: Claude Opus 4.6 (Arena #1 Code, #2 Overall)

| Benchmark | Opus 4.6 | Best Open Model | Gap |
|---|---|---|---|
| Arena Code | 1549 | GLM-5 (1445) | -104 Elo |
| Arena Overall | 1500 | GLM-5 (~1430) | -70 Elo |
| SWE-bench Verified | ~80.8% | Qwen3-Coder-480B (~76-80%) | -1 to -5% |
| Agentic/Tool Calling | Top tier | GLM-4.7 Flash (87.4% t2) | Competitive |
| Reasoning (AIME) | Top tier | GLM-4.7 (95.7%) | Competitive |

### Hardware Required for Each Open Model Tier

| Open Model Tier | Min VRAM | Hardware Options | Speed | Annual Cost |
|---|---|---|---|---|
| GLM-4.7 Flash / Qwen3.5 27B | 17-19 GB | RTX 5090 (owned) | 80-150 tok/s | ~$200 electricity |
| GLM-5 (unknown size) | TBD | TBD (April 6-7) | TBD | TBD |
| Qwen3-Coder-480B Q4 | ~250-300 GB | 2x H200 cloud / DGX Station | 100-250 tok/s | $6,400-7,200 cloud |
| DeepSeek V3.2 Q4 | ~340 GB | 4x H100 cloud / DGX Station | 100-300 tok/s | $8,000-10,000 cloud |
| Any model at FP16 | ~500-1,300 GB | 8x H100/H200 cloud / DGX B300 | 200-500 tok/s | $8,000-10,000 cloud |

**No commercially available hardware fully matches Opus 4.6.** The gap is model quality, not hardware. Even on a DGX B300 ($300-500K), you're limited to open models that are still ~100 Elo behind on coding.

---

## Private Cloud: Air-Gap-Compliant Data Privacy

For teams that need data privacy (no data sent to model providers) but don't want to buy hardware.

### The Setup

Deploy open-weight models on GPU instances **you control**. Options:

1. **Your own AWS/GCP/Azure VPC** — GPU instances in your account, data never leaves your network
2. **RunPod / Lambda Labs dedicated pods** — you deploy your own models, data stays on your instance
3. **Bare metal rental** — dedicated physical servers (OVH, Hetzner, Latitude.sh)

In all cases: you run vLLM, llama.cpp, or TGI with an OpenAI-compatible API. Point your dev tools at `http://your-instance:8000/v1`. Model provider never sees your data.

### Cloud GPU Pricing (Approximate, March 2026)

| GPU | VRAM | On-Demand $/hr | Bandwidth |
|---|---|---|---|
| A100 SXM | 80 GB | ~$1.50-2.00 | 2.0 TB/s |
| H100 SXM | 80 GB | ~$2.50-3.50 | 3.35 TB/s |
| H200 SXM | 141 GB | ~$3.50-4.50 | 4.8 TB/s |
| B200 SXM | 180 GB | ~$5.50-7.00 | ~8 TB/s |
| RTX PRO 6000 | 96 GB | ~$1.50-2.50 | 1.8 TB/s |
| 8x H100 SXM (cluster) | 640 GB | ~$28-33 | 26.8 TB/s |
| 8x H200 SXM (cluster) | 1,128 GB | ~$32-40 | 38.4 TB/s |

### Recommended Configurations

#### Option A: "Good Enough for Coding" — 1x H200 (~$4-5/hr)

- Run GLM-5 or Qwen3-235B Thinking at Q3-Q4
- GLM-5 is #8 on Arena Code — roughly Claude Opus 4.5 level
- ~30-100 tok/s
- **~$100-120/month** at 8 hrs/day | **~$3,200-3,600/year**

#### Option B: "Maximizing Open Model Quality" — 2x H200 (~$9-10/hr)

- Run Qwen3-Coder-480B at Q4-Q6 (best open coding model)
- Run DeepSeek V3.2 at Q2-Q3
- 100-250 tok/s — faster than Claude API
- **~$200-240/month** at 8 hrs/day | **~$6,400-7,200/year**

#### Option C: "No Compromises" — 8x H100 SXM (~$28-33/hr)

- Every open model at FP16, no quantization
- 200-500 tok/s
- **~$670-800/month** at 8 hrs/day | **~$8,000-9,600/year**

#### Option D: "Always On" — Reserved 2x H200

- Reserved instances typically 30-50% cheaper than on-demand
- ~$4,000-5,000/year for always-available 2x H200
- No spin-up time, run Qwen3-Coder-480B Q6 24/7

### Complete Cost Comparison

| Approach | Upfront | Annual Cost | Best Model | Speed | Data Privacy |
|---|---|---|---|---|---|
| **RTX 5090** (owned) | $2K | ~$200 electricity | Qwen3.5 27B | 80-150 tok/s | Full (local) |
| **DGX Station** | $50-80K | ~$2K electricity | Qwen3-235B Q6 | 50-200 tok/s | Full (local) |
| **DGX B300** (homelab) | $300-500K | ~$15K electricity | Everything FP16 | 200-500 tok/s | Full (local) |
| **1x H200 (cloud)** | $0 | ~$3,200-3,600 | GLM-5 / Qwen3-235B Q4 | 30-100 tok/s | Your VPC |
| **2x H200 (cloud)** | $0 | ~$6,400-7,200 | Qwen3-Coder-480B Q6 | 100-250 tok/s | Your VPC |
| **8x H100 (cloud)** | $0 | ~$8,000-9,600 | Everything FP16 | 200-500 tok/s | Your VPC |
| **Claude Opus 4.6 API** | $0 | ~$300-1,000 | Opus 4.6 (best) | 30-40 tok/s | Provider sees data |

### Why Private Cloud Is the Sweet Spot

**2x H200 on RunPod/Lambda for ~$6,400-7,200/year** is the recommended option:

1. **282 GB VRAM** — runs Qwen3-Coder-480B at Q4-Q6, the best open-source coding model
2. **NVLink between GPUs** — no inter-GPU bottleneck
3. **4.8 TB/s bandwidth per GPU** — 100-250 tok/s, faster than the Claude API
4. **No data leaves your instance** — deploy vLLM, connect your coding tools
5. **No upfront cost** — vs. $50-80K for DGX Station
6. **Flexible** — when GLM-5.1 drops, spin it up immediately. Scale to 8x H100 for a weekend if needed.
7. **DGX Station break-even**: ~8-10 years vs. 2x H200 cloud. By then, hardware is obsolete.

### Practical Setup for a Dev Team

1. Create a RunPod or Lambda Labs account
2. Deploy a 2x H200 pod
3. Install vLLM or llama.cpp with OpenAI-compatible API
4. Point dev tools (OpenCode, Cursor, Cline, Continue) at `http://your-pod-ip:8000/v1`
5. Run Qwen3-Coder-480B (or GLM-5.1 when it drops) as primary model
6. Keep your local RTX 5090 for quick tasks with smaller models (Qwen3.5 27B, GLM-4.7 Flash)
7. Scale up to 4x/8x GPU pods for demanding tasks, scale back after

---

## Cloud Provider APIs: Managed Model Access (Bedrock, Vertex AI, Azure AI)

There's a middle ground between "run your own model on raw GPU" and "call the provider's API directly." Cloud providers like AWS (Bedrock), Google Cloud (Vertex AI), and Azure (Azure AI) offer managed APIs where you call open-source and proprietary models **through your own cloud account**. Your data stays in your VPC, governed by your cloud provider agreement — not the model provider's terms.

### Three Tiers of Data Privacy

| Tier | Example | Who Hosts Model | Who Sees Data | Your Control |
|---|---|---|---|---|
| **Direct API** | api.anthropic.com, api.openai.com | Model provider | Model provider | None — their ToS applies |
| **Cloud Managed API** | AWS Bedrock, GCP Vertex AI | Cloud provider (in your account) | Your cloud account only | VPC isolation, IAM, encryption |
| **Self-Hosted on Cloud GPU** | RunPod pod, AWS EC2 + vLLM | You | You | Full — you deploy everything |
| **Local Hardware** | RTX 5090, DGX Station | You | You | Full — air-gapped possible |

Cloud managed APIs (Tier 2) are a strong middle ground: you get the convenience of an API with the privacy of your own cloud account. The model provider (Anthropic, Zhipu, Qwen team) does **not** see your prompts or completions — the cloud provider runs the inference infrastructure within your account's isolation boundary.

### Pricing: Proprietary Frontier Models on Managed APIs

These are the same models available on the provider's direct API, but billed through your AWS/GCP account with VPC-level data isolation.

#### Anthropic Claude (Available on Bedrock & Vertex AI)

| Model | Arena Code Rank | Input $/1M tokens | Output $/1M tokens | Cache Hit $/1M | Batch $/1M (in/out) |
|---|---|---|---|---|---|
| **Claude Opus 4.6** | #1 (1549) | $5.00 | $25.00 | $0.50 | $2.50 / $12.50 |
| **Claude Opus 4.5** | #5 (1465) | $5.00 | $25.00 | $0.50 | $2.50 / $12.50 |
| **Claude Opus 4.1** | — | $15.00 | $75.00 | $1.50 | $7.50 / $37.50 |
| **Claude Sonnet 4.6** | #3 (1523) | $3.00 | $15.00 | $0.30 | $1.50 / $7.50 |
| **Claude Sonnet 4.5** | — | $3.00 | $15.00 | $0.30 | $1.50 / $7.50 |
| **Claude Haiku 4.5** | — | $1.00 | $5.00 | $0.10 | $0.50 / $2.50 |

#### Google Gemini (Vertex AI only)

| Model | Arena Code Rank | Input $/1M tokens | Output $/1M tokens | Notes |
|---|---|---|---|---|
| **Gemini 3.1 Pro** | ~#7 | $2.00 | $12.00 (response + reasoning) | >200K context: $4.00 in / $18.00 out |
| **Gemini 3 Pro** | ~#10 | $2.00 | $12.00 | Same long-context pricing |
| **Gemini 3 Flash** | ~#14 | $0.50 | $3.00 | Audio input: $1.00 |
| **Gemini 2.5 Pro** | ~#30 | $1.25 | $10.00 | Cache hit: $0.13 |
| **Gemini 2.5 Flash** | — | $0.30 | $2.50 | Cache hit: $0.03 |

### Pricing: Open-Source Models on Managed APIs

This is where it gets interesting. These are **open-weight models** hosted by the cloud provider in your account. Same models you could self-host, but with zero infrastructure management.

| Model | Arena Code Rank | Platform | Input $/1M | Output $/1M | Cache Hit | Batch (in/out) |
|---|---|---|---|---|---|---|
| **GLM-5** | #8 (1445) | Bedrock / Vertex | $1.00 | $3.20 | $0.10 | — |
| **GLM-4.7** | #9 (1439) | Bedrock / Vertex | $0.60 | $2.20 | — | — |
| **GLM-4.7 Flash** | — | Bedrock | $0.07 | $0.40 | — | — |
| **Qwen3-Coder-480B-A35B** | ~#15 | Vertex | $0.22 | $1.80 | $0.022 | $0.11 / $0.90 |
| **Qwen3-235B-A22B (2507)** | ~#25 | Vertex | $0.22 | $0.88 | — | $0.11 / $0.44 |
| **Qwen3-Next-80B-A3B** | — | Vertex / Bedrock | $0.15 | $1.20 | — | — |
| **DeepSeek V3.2** | ~#20 | Bedrock / Vertex | $0.56-0.62 | $1.68-1.85 | $0.056 | $0.28 / $0.84 |
| **DeepSeek V3.1** | — | Vertex | $0.60 | $1.70 | $0.06 | $0.30 / $0.85 |
| **DeepSeek R1 (0528)** | — | Vertex | $1.35 | $5.40 | — | $0.675 / $2.70 |
| **Llama 4 Maverick** | — | Vertex / Bedrock | $0.35 | $1.15 | — | $0.175 / $0.575 |
| **Llama 4 Scout** | — | Vertex / Bedrock | $0.25 | $0.70 | — | $0.125 / $0.35 |
| **Llama 3.3 70B** | — | Vertex / Bedrock | $0.72 | $0.72 | — | $0.36 / $0.36 |
| **Mistral Large 3** | — | Bedrock | $0.50 | $1.50 | — | — |
| **Devstral 2 135B** | — | Bedrock | $0.40 | $2.00 | — | — |
| **Codestral 2** | — | Vertex | $0.30 | $0.90 | — | — |
| **gpt-oss-120b** | — | Vertex / Bedrock | $0.09-0.15 | $0.36-0.60 | — | $0.045 / $0.18 |
| **Kimi-K2-Thinking** (Moonshot) | — | Vertex | $0.60 | $2.50 | $0.06 | — |

**Note:** Bedrock and Vertex AI also offer tier modifiers: Priority (1.75x standard), Flex/Batch (0.5x standard). Prices above are standard on-demand.

### The Key Insight: Open Models on Managed APIs

**Qwen3-Coder-480B on Vertex AI costs $0.22/$1.80 per 1M tokens.** That's the best open-source coding model — near Opus 4.5 quality — at **~23x cheaper input / ~14x cheaper output** than Claude Opus 4.6 ($5/$25). Your data stays in your GCP project.

Similarly, **GLM-5 on Bedrock/Vertex at $1.00/$3.20** gives you the #8 Arena Code model at **5x cheaper input / 8x cheaper output** than Opus 4.6, with VPC isolation.

### Monthly Cost Estimates for a Developer / Small Team

Assuming heavy coding usage: ~1M input tokens + 500K output tokens per day (~30M input + 15M output per month).

| Model | Platform | Monthly Input Cost | Monthly Output Cost | **Total/Month** | Quality (Arena Code) |
|---|---|---|---|---|---|
| **Claude Opus 4.6** | Bedrock/Vertex | $150.00 | $375.00 | **$525/mo** | #1 (1549) |
| **Claude Sonnet 4.6** | Bedrock/Vertex | $90.00 | $225.00 | **$315/mo** | #3 (1523) |
| **Gemini 3.1 Pro** | Vertex | $60.00 | $180.00 | **$240/mo** | ~#7 |
| **GLM-5** | Bedrock/Vertex | $30.00 | $48.00 | **$78/mo** | #8 (1445) |
| **DeepSeek V3.2** | Vertex | $16.80 | $25.20 | **$42/mo** | ~#20 |
| **Qwen3-Coder-480B** | Vertex | $6.60 | $27.00 | **$34/mo** | ~#15 |
| **Qwen3-235B** | Vertex | $6.60 | $13.20 | **$20/mo** | ~#25 |
| **GLM-4.7 Flash** | Bedrock | $2.10 | $6.00 | **$8/mo** | — |

For context, **$78/month for GLM-5** (Arena Code #8) vs **$525/month for Claude Opus 4.6** (Arena Code #1) — the open model is 85% cheaper with ~93% of the coding capability.

### Managed API vs Self-Hosted vs Local Hardware

| Approach | Monthly Cost | Quality | Speed | Privacy | Complexity |
|---|---|---|---|---|---|
| **Qwen3-Coder-480B on Vertex** | ~$34/mo | Near Opus 4.5 | Fast (managed) | Your GCP VPC | Zero — API call |
| **GLM-5 on Bedrock** | ~$78/mo | Arena Code #8 | Fast (managed) | Your AWS VPC | Zero — API call |
| **Claude Opus 4.6 on Bedrock** | ~$525/mo | Best available | Fast (managed) | Your AWS VPC | Zero — API call |
| **2x H200 self-hosted** | ~$530-600/mo | Qwen3-Coder-480B Q6 | 100-250 tok/s | Your pod/instance | Moderate — deploy vLLM |
| **RTX 5090 local** | ~$17/mo electricity | Qwen3.5 27B | 80-150 tok/s | Full air-gap | Low — run llama.cpp |
| **DGX Station** | ~$170/mo electricity | Qwen3-235B Q6 | 50-200 tok/s | Full air-gap | Low — run locally |

**The managed API option changes the calculus significantly.** For a team that needs VPC-level data privacy:

- **Qwen3-Coder-480B on Vertex at $34/month** is cheaper than electricity for a DGX Station, with near-equivalent model quality, zero infrastructure, and instant scaling. The only tradeoff is you're trusting Google's VPC isolation rather than having a physical air gap.
- **GLM-5 on Bedrock at $78/month** is cheaper than self-hosting on a 1x H200 ($3,200-3,600/year = $267-300/month), and you don't manage any infrastructure.
- **Claude Opus 4.6 on Bedrock at $525/month** gives you the absolute best model quality with VPC privacy. This costs more than self-hosted alternatives but is still far cheaper than buying hardware.

### When to Use Each Approach

| Scenario | Best Approach | Why |
|---|---|---|
| Individual dev, no privacy needs | Claude Opus 4.6 direct API | Best quality, simple |
| Team, VPC privacy sufficient | **Qwen3-Coder-480B on Vertex** | 85-95% of Opus quality at $34/mo |
| Team, needs multiple models | **Mix: GLM-5 + Qwen3-Coder on Vertex** | Different models for different tasks |
| Team, budget for best quality + privacy | **Claude Opus 4.6 on Bedrock** | Best model, VPC isolation |
| Strict physical air-gap required | Self-hosted GPU or DGX Station | No network dependency on cloud |
| Maximum flexibility + speed | **Self-hosted 2x H200** | Run any model, any quantization |
| Heavy batch processing | **Qwen3-Coder-480B batch on Vertex** | $0.11/$0.90 — half price |
| Simple flat-rate, no metering | **Ollama Cloud Max** | $100/mo, unlimited model switching |

---

## Ollama Cloud: Flat-Rate Model Access

Ollama Cloud offers a different model: **flat monthly subscription** instead of per-token billing. No metering, no surprise bills — just a fixed price for access to large cloud-hosted models using the same `ollama` CLI/API you'd use locally.

### Plans

| Plan | Price | Concurrent Models | Usage Tier | Best For |
|---|---|---|---|---|
| **Free** | $0 | 1 | Light | Evaluating models, light chat |
| **Pro** | $20/mo ($200/yr) | 3 | 50x Free | Day-to-day coding, deep research |
| **Max** | $100/mo | 10 | 250x Free (5x Pro) | Continuous agents, multiple concurrent agents, large models over extended sessions |

### Available Cloud Models (Relevant to Coding/Reasoning/Agentic)

| Model | Total Params | Active Params | Category | Notes |
|---|---|---|---|---|
| **GLM-5** | 744B | 40B | Coding/Reasoning | Arena Code #8. First confirmation of architecture: 744B MoE, 40B active |
| **GLM-4.7** | — | — | Coding | Arena Code #9 |
| **GLM-4.6** | — | — | Coding/Agentic | — |
| **DeepSeek V3.2** | 671B | 37B | Reasoning/Coding | Arena Overall ~#52 |
| **Kimi-K2.5** | ~1T | 32B | Agentic/Multimodal | SWE-bench 76.8% |
| **Qwen3.5** (up to 122B cloud) | 122B MoE | 10B | General/Coding | Multiple sizes available |
| **Qwen3-Coder-Next** | — | — | Coding/Agentic | Optimized for agentic coding workflows |
| **Qwen3-VL-235B** | 235B | 22B | Vision/Reasoning | Multimodal |
| **Qwen3-Next-80B** | 80B MoE | 3B | General | Thinking + instruct modes |
| **Devstral 2** | 123B | — | Coding/Agentic | Multi-file editing, codebase exploration |
| **Devstral Small 2** | 24B | — | Coding/Agentic | Lighter coding agent |
| **Nemotron 3 Super** | 120B MoE | 12B | Agentic | Multi-agent applications |
| **MiniMax M2.7** | — | — | Coding/Productivity | — |
| **MiniMax M2.5** | — | — | Coding | — |
| **Cogito 2.1** | 671B | — | General/STEM | MIT license |
| **Gemini 3 Flash** (preview) | — | — | General | Google's fast model |

### Key Details

- **Native weights** — models run at native precision (not quantized), with NVFP4 acceleration on Blackwell/Vera Rubin hardware. This means better quality than self-hosted quantized models.
- **No per-token billing** — usage is measured by GPU time, not tokens. Shorter requests and cached context use less. As hardware gets more efficient, you get more value from the same plan.
- **Session limits** reset every 5 hours, weekly limits every 7 days.
- **Privacy**: Ollama states prompts and responses are never logged or trained on. Hosted primarily in the US (with overflow to Europe/Singapore). Hosted on NVIDIA Cloud Providers with no-logging, no-training, zero-data-retention policies.
- **Same `ollama` API** — if you already use Ollama locally with your 5090, cloud models are seamless. Just `ollama run glm-5` and it routes to cloud.

### GLM-5 Architecture Reveal

The Ollama Cloud listing confirms **GLM-5 is a 744B MoE with 40B active parameters**. This is significant — 40B active is nearly double GLM-4.7 Flash's active params, and larger than Qwen3-Coder-480B's 35B active. At 744B total, the model at Q4 quantization would be ~370-440 GB — requiring 3-4x H100 or a DGX Station for self-hosting.

On Ollama Cloud Max at $100/month, you skip all that hardware entirely.

### Ollama Cloud Max vs Other Options

| Approach | Monthly Cost | Best Coding Model | Quality | Speed | Privacy | Complexity |
|---|---|---|---|---|---|---|
| **Ollama Cloud Max** | **$100/mo** | GLM-5 (744B, 40B active) | Arena Code #8 | Fast (native weights, NVIDIA hardware) | Ollama hosted (no logging/training) | **Zero** — `ollama run glm-5` |
| Qwen3-Coder-480B on Vertex | ~$34/mo (usage-dependent) | Qwen3-Coder-480B | ~#15 Arena Code | Fast (managed) | Your GCP VPC | Zero — API call |
| GLM-5 on Bedrock | ~$78/mo (usage-dependent) | GLM-5 | #8 Arena Code | Fast (managed) | Your AWS VPC | Zero — API call |
| Claude Opus 4.6 on Bedrock | ~$525/mo (usage-dependent) | Opus 4.6 | #1 Arena Code | Fast (managed) | Your AWS VPC | Zero — API call |
| 2x H200 self-hosted | ~$530-600/mo | Qwen3-Coder-480B Q6 | ~#15 | 100-250 tok/s | Your pod | Moderate |
| RTX 5090 local | ~$17/mo electricity | Qwen3.5 27B | ~#79 | 80-150 tok/s | Full air-gap | Low |

### When Ollama Cloud Max Makes Sense

**Strengths:**
- **$100/mo flat** — no surprise bills. If you use models heavily all day, you don't pay more. With Bedrock/Vertex, heavy GLM-5 usage could exceed $100/mo depending on token volume.
- **Model variety** — switch between GLM-5, DeepSeek V3.2, Kimi-K2.5, Devstral 2, and 15+ other cloud models at will. On Bedrock/Vertex you pay per-token for each.
- **Native weights** — no quantization loss. Self-hosted models on consumer/prosumer hardware require quantization; Ollama Cloud runs at native precision on datacenter GPUs.
- **Seamless local+cloud** — if you already use Ollama on your 5090 for small models, cloud models integrate transparently. Same CLI, same API.
- **10 concurrent models on Max** — run a coding model, a reasoning model, and an agentic model simultaneously.

**Weaknesses:**
- **Usage limits** — "heavy, sustained usage" is still capped by session and weekly limits. No published token counts, so hard to compare directly with per-token pricing. Heavy agentic workflows with many long sessions could hit limits.
- **No VPC isolation** — data goes to Ollama's infrastructure (hosted on NVIDIA Cloud Providers). They promise no logging/training, but it's not your own AWS/GCP VPC. For regulated industries (healthcare, finance, government), this may not satisfy compliance requirements.
- **No Opus/Gemini Pro** — only open-source models. If you need Claude Opus 4.6 quality, you still need Bedrock/Vertex.
- **No batch mode** — can't run large batch jobs at 50% discount like Vertex/Bedrock offer.

### Best Use Case for Ollama Cloud Max

A **solo developer or small team** that:
- Wants access to GLM-5, DeepSeek V3.2, and other large open models
- Uses models throughout the day (the flat rate beats per-token at high volume)
- Already uses Ollama locally and wants seamless cloud scaling
- Doesn't need strict VPC/compliance-level data isolation (but does want no-logging/no-training guarantees)
- Doesn't need Claude Opus or Gemini Pro

At $100/month, it's a compelling simple option — especially compared to self-hosting GLM-5 (744B) which would require ~$300-500K in hardware (DGX Station) or ~$530-600/month in cloud GPU rental.

---

## The "Money No Object, Best Experience" Setup

If you drop all hardware constraints and privacy requirements, and simply want the absolute best coding, reasoning, and agentic experience with zero waiting, the strategy changes from self-hosting to direct APIs.

### Why Not Subscriptions? (The "No Waiting" Rule)

Subscription plans are a trap for heavy users:
- **Claude Max ($100-$200/mo)**: Has strict usage caps that reset periodically.
- **ChatGPT Pro ($200/mo)**: "Unlimited" comes with abuse guardrails that throttle power users.
- **Ollama Cloud Max ($100/mo)**: Enforces 5-hour session and 7-day weekly limits.

If you hate waiting for a usage window to refill, **you must use pay-per-token direct APIs**. Your wallet is the only limit.

### Speed vs. Intelligence Tradeoff

The smartest models are not the fastest. Here is how they stack up based on independent API benchmarking:

| Model | Output Speed | Intelligence Index | Arena Code | Price ($/1M in/out) |
|---|---|---|---|---|
| **Gemini 3.1 Pro** | **108 tok/s** | 57 (Tied #1) | ~#7 | $2.00 / $12.00 |
| **Grok 4.20 Beta** | **226 tok/s** | 48 | — | $3.00 (blended) |
| **Gemini 3 Flash** | **158 tok/s** | 46 | ~#14 | $0.50 / $3.00 |
| **Claude Sonnet 4.6** | 48 tok/s | 52 | #3 | $3.00 / $15.00 |
| **Claude Opus 4.6** | 42 tok/s | 53 | **#1 (1549)** | $5.00 / $25.00 |

*Data: Artificial Analysis (March 2026)*

**Insight**: Claude Opus 4.6 is the smartest but feels sluggish at 42 tok/s. **Gemini 3.1 Pro is the sweet spot:** tied for the highest overall intelligence, highly capable at coding, and runs at a blazing **108 tok/s** (2.5x faster than Opus).

### Can You Make Opus Faster?

No. Opus 4.6 is closed-weights. Whether you use Anthropic Direct, Bedrock, or Vertex, you are bound by their API speed limits (and the price is exactly the same across all three: $5/$25).

You *can* get more speed by self-hosting an open model like GLM-5 on a massive 8x H100 cloud instance (RunPod) — hitting 250-400 tok/s. However, you pay a quality penalty (Arena Code #8 vs #1) and a massive cost penalty (~$600-800/mo).

### The Ultimate "Zero Wait" Developer Stack

To get the best experience without ever hitting a limit, use a smart router (like OpenRouter or native IDE routing) to combine these direct APIs:

1. **The Fast Workhorse: Gemini 3.1 Pro API**
   - 108 tok/s, tied #1 intelligence, very capable. 
   - Handles 70% of daily tasks with zero latency frustration.
2. **The Heavy Lifter: Claude Opus 4.6 API**
   - Slow (42 tok/s) but the absolute best quality (#1 coding). 
   - Reserve for the hardest 10-20% of complex architecture or bugs.
3. **The Cheap Sanity Check: DeepSeek V3.2 API**
   - Absurdly cheap ($0.28/$0.42 per 1M). Good for bulk tasks, log analysis, or second opinions.
4. **Local Autocomplete: RTX 5090 (GLM-4.7 Flash)**
   - Instant, free, offline autocomplete directly in your editor.

**Total Cost:** ~$300-400/month for a heavy power user. This gives you better quality than any self-hosted DGX Station ($50K+), faster response times for daily tasks, and zero subscription limits to throttle your workflow.

---

## Final Recommendations (Updated)

### For a solo developer with a 5090 and no strict privacy constraints

**Simplest: Ollama Cloud Max ($100/month)**
- GLM-5 (Arena Code #8), DeepSeek V3.2, Kimi-K2.5, and 15+ models at native weights
- Flat rate, no metering. Seamless with local Ollama on your 5090.
- Use your 5090 for quick local tasks, cloud for heavy lifting.

**Cheapest: Keep the 5090, use APIs for hard problems ($200-300/year)**
- Wait for next-gen 32B models that will match today's 70B on your existing hardware.

### For a team with VPC-level data privacy (recommended for most teams)

**Best value: Qwen3-Coder-480B on Vertex AI (~$34/month)**
- Near Opus 4.5 coding quality, #15 Arena Code
- $0.22/$1.80 per 1M tokens — 23x cheaper than Opus 4.6 input
- Data stays in your GCP project, zero infrastructure to manage
- Can mix with GLM-5 ($78/mo) for broader reasoning tasks

**Best quality with privacy: Claude Opus 4.6 on Bedrock/Vertex (~$525/month)**
- The best model available, period — Arena Code #1
- VPC isolation, same price as direct API
- Worth it if the ~104 Elo gap to open models matters for your work

### For a team with strict physical air-gap requirements

**Best value: 2x H200 private cloud (~$6,400-7,200/year)**
- Runs Qwen3-Coder-480B Q6 at 100-250 tok/s
- Near Opus 4.5 coding quality, data never leaves your instance
- No upfront cost, scales up/down as needed

**Maximum local: DGX Station (~$50-80K)**
- 748 GB coherent memory, every model at good quantization
- Fully air-gapped, no network dependency
- Makes sense if you need a physical machine on-premises and can justify the capital expense

**Maximum capability: 8x H100 cloud (~$8-10K/year)**
- Every open model at FP16, 200-500 tok/s
- Same privacy as 2x H200 option, more headroom
- Overkill for most teams but removes all model-size constraints

### The gap that remains

Even with the best hardware and best open models, you're still ~100 Elo points behind Opus 4.6 on coding and ~50-70 Elo on overall quality. The gap is in the model, not the hardware. Watch for:
- **GLM-5.1** (April 6-7 weight release) — could close the gap further
- **Next-gen open models** — the open-source frontier is advancing ~50 Elo every few months
- Opus 4.5-equivalent open models may exist by late 2026; Opus 4.6-equivalent by mid-2027

---

## Sources and Benchmarks

- Strix Halo benchmarks: [apellegr/Strix-Halo-Models](https://github.com/apellegr/Strix-Halo-Models) — llama-bench with ROCm 7.2, flash attention, 512 prompt / 128 gen tokens, 3 reps averaged
- Qwen3-Coder-480B: [Qwen blog](https://qwenlm.github.io/blog/qwen3-coder/) — SWE-bench SOTA among open models, comparable to Claude Sonnet 4
- Docker tool-calling evaluation: Qwen3 14B achieves 0.971 F1 on function calling (near GPT-4's 0.974)
- GLM-4.7 Flash: 95.7% AIME 2025, 87.4% t2-bench (agent coordination), 73.8% SWE-bench
- RTX PRO 6000 specs: NVIDIA product page — 96GB GDDR7 ECC, 1,792 GB/s, 600W TDP
- M3 Ultra specs: Apple Mac Studio specs page — 819 GB/s bandwidth, 60-core GPU (configurable to 80-core)
- NVIDIA speed estimates derived from bandwidth ratios against Strix Halo measured benchmarks
- M3 Ultra speed estimates derived from ~819/215 GB/s ratio (~3.8x Strix Halo) with efficiency adjustments for MLX/Metal vs llama.cpp/ROCm
- LMSys Arena leaderboard: [lmarena.ai/leaderboard](https://lmarena.ai/leaderboard) — Arena Code and Overall rankings, March 2026
- Amazon Bedrock pricing: [aws.amazon.com/bedrock/pricing](https://aws.amazon.com/bedrock/pricing/) — US East (N. Virginia) on-demand standard tier
- Google Vertex AI pricing: [cloud.google.com/vertex-ai/generative-ai/pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) — US region on-demand standard tier
- DGX Station specs: NVIDIA product page — GB300 Grace Blackwell Ultra, 748 GB coherent memory, 7.1 TB/s
- DGX B300 specs: NVIDIA product page — 8x Blackwell Ultra SXM, 2.1 TB HBM3e, 14.4 TB/s NVLink, 144 PFLOPS FP4
- Ollama Cloud pricing and models: [ollama.com/pricing](https://ollama.com/cloud) and [ollama.com/search?c=cloud](https://ollama.com/search?c=cloud) — GLM-5 confirmed as 744B MoE / 40B active
- GLM-5 Arena rankings: LMSys Arena leaderboard — #8 Code (1445), #20 Overall
