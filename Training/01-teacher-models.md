# Teacher Models: Strengths & Weaknesses

## 1. Kimi K2.5 (Moonshot AI) -- The Generalist King

- **Source**: `moonshotai/Kimi-K2.5` ([HuggingFace](https://huggingface.co/moonshotai/Kimi-K2.5))
- **Released**: January 27, 2026
- **Architecture**: MoE -- 1.1T total, 32B active per token (384 experts, 8 routed + 1 shared)
- **Context**: 256K tokens (longest of the three teachers)
- **Multimodal**: Yes (MoonViT 400M vision encoder)
- **License**: Modified MIT
- **Access**: Ollama cloud (`ollama run kimi-k2.5:cloud`) or Moonshot API ($0.60/MTok in, $3.00/MTok out)
- **Paper**: [arXiv:2602.02276](https://arxiv.org/abs/2602.02276)

**Strengths:**
- Best all-around benchmarks -- top-3 or better in nearly every category (HumanEval 99%, AIME 96.1%, MMLU-Pro 87.1%, GPQA 87.6%)
- Best instruction following (IFEval 94%) -- critical for generating clean, consistent training data
- Longest native context (256K) -- the only teacher that can generate truly long-context training samples at full quality
- Strong frontend/JS/TS -- 73% SWE-bench Multilingual, specifically highlighted for "particularly strong frontend capabilities"
- Thinking mode generates reasoning traces valuable for distillation
- Cheap API ($0.60/MTok input)

**Weaknesses:**
- Not the best at real-world SWE tasks -- 76.8% SWE-bench Verified, beaten by MiniMax M2.5 (80.2%) and M2.7
- Terminal/system tasks lag -- 50.8% Terminal-Bench 2, beaten by M2.7 (57.0%)
- No self-evolution or agent-team native behaviors
- F# capability unproven -- no F# benchmarks exist; large corpus helps but not verified
- Requires 8x A100 80GB to self-host -- API-only for most people

**Best used for**: Svelte/SvelteKit, TypeScript, long-context samples (32K-204K), cross-domain prompts, instructional content

---

## 2. MiniMax M2.7 (MiniMax) -- The Agentic Engineer

- **Source**: Cloud-only via [Ollama](https://ollama.com/library/minimax-m2.7) and [MiniMax API](https://platform.minimax.io)
- **Released**: March 18, 2026 (brand new)
- **Architecture**: MoE -- 229B total, 10B active per token
- **Context**: 200K tokens
- **License**: Cloud-only (no downloadable weights)
- **Access**: Ollama cloud (`ollama run minimax-m2.7:cloud`) or MiniMax API
- **Announcement**: [minimax.io/news/minimax-m27-en](https://www.minimax.io/news/minimax-m27-en)

**Strengths:**
- Best real-world software engineering -- SWE-Pro 56.22% (matches GPT-5.3-Codex), SWE Multilingual 76.5 (beats K2.5's 73.0)
- Best system-level understanding -- Terminal Bench 2: 57.0% (beats K2.5 by 6+ points), critical for Docker/K8s training data
- Native Agent Teams -- multi-agent collaboration with role boundaries, adversarial reasoning, and protocol adherence. The only teacher that natively understands multi-agent coordination
- 97% skill adherence across 40 complex skills (each 2K+ tokens) -- training data will be consistent and high-fidelity
- First model to deeply participate in its own evolution -- trained via recursive self-improvement, produces more sophisticated reasoning patterns
- Available on Ollama cloud -- works with existing Ollama subscription
- Extremely efficient -- only 10B active params from 229B total
- MLE Bench Lite: 66.6% medal rate in autonomous ML competitions, tying with Gemini 3.1

**Weaknesses:**
- Cloud-only -- no downloadable weights, fully dependent on MiniMax API/Ollama cloud
- No open weights -- can't inspect, modify, or understand what the model learned
- 200K context (not 256K) -- slightly shorter than K2.5
- Weaker on pure reasoning benchmarks -- AIME, GPQA, MMLU-Pro all lower than K2.5
- Brand new (released 3 days ago) -- limited community validation, potential undiscovered issues
- Pricing unclear -- cloud-only means costs depend on MiniMax/Ollama pricing
- Verbose output -- generates more tokens per response, may increase data generation costs
- Hallucinates on underspecified prompts -- needs well-structured prompts (mitigatable for distillation since prompts are controlled)

**Best used for**: Agentic coding tasks, multi-step bug fixes, Docker/K8s/infrastructure, system-level DevOps, real-world SWE patterns

---

## 3. GLM-5 (Z.ai) -- The Multilingual Powerhouse

- **Source**: `zai-org/GLM-5` ([HuggingFace](https://huggingface.co/zai-org/GLM-5))
- **Released**: February 2026
- **Architecture**: MoE -- 744B total, 40B active per token
- **Context**: 198K tokens (via DeepSeek Sparse Attention)
- **License**: MIT
- **Access**: Ollama cloud (`ollama run glm-5:cloud`)
- **Thinking mode**: Yes

**Strengths:**
- Highest SWE-bench Verified among teachers -- 77.8% (beats K2.5's 76.8%, M2.7's SWE-Pro 56.2%)
- **Best SWE-bench Multilingual -- 73.3%** -- critical for F# and non-mainstream languages
- Strongest Terminal-Bench 2.0 -- 56.2%, excellent for Docker/K8s/system tasks
- Excellent reasoning -- AIME 2026 I: 92.7%, GPQA-Diamond: 86.0%
- Strong agentic capabilities -- BrowseComp 62.0
- MIT license -- fully permissive
- Thinking mode for complex reasoning tasks

**Weaknesses:**
- Cloud-only on Ollama -- 744B is too large for local inference
- Supports only English and Chinese -- not a broad multilingual model for natural language
- Relatively new (1 month) -- less community validation than DeepSeek V3.2
- 198K context -- slightly shorter than K2.5's 256K
- No multimodal (text-only)

**Best used for**: .NET/ASP.NET Core, Docker/K8s, agentic tasks, general coding -- replaces DeepSeek V3.2 with superior benchmarks

---

## 4. DeepSeek V3.2 (DeepSeek) -- Retired from Active Use

> **Note:** DeepSeek V3.2 was the original F# teacher but was replaced after benchmarking showed inferior F# code quality (43.1% pass rate on fsharp_core) compared to MiniMax (76.6%) and GLM-5 (pending benchmark). Retained here for reference.

- **Source**: `deepseek-ai/DeepSeek-V3.2` ([HuggingFace](https://huggingface.co/deepseek-ai/DeepSeek-V3.2))
- **Released**: December 1, 2025
- **Architecture**: MoE -- 685B total, 37B active per token
- **Context**: 128K tokens
- **License**: Full MIT
- **Access**: Ollama cloud (`ollama run deepseek-v3.2:cloud`)

**Why replaced:**
- F# verification pass rate of 43.1% on fsharp_core (vs MiniMax's 76.6%)
- 128K context -- shortest of all teachers
- Surpassed by GLM-5 on SWE-bench Verified (73.1% vs 77.8%) and Multilingual (70.2% vs 73.3%)
- Still generated training data for round 1 (fsharp_core, fsharp_libraries) -- those samples are included in the dataset

---

## Teacher Comparison Matrix

| Dimension | Kimi K2.5 | MiniMax M2.7 | GLM-5 | DeepSeek V3.2 (retired) | Kimi K2.6 | GLM-5.1 |
|-----------|-----------|--------------|-------|------------------------|-----------|---------|
| **Overall intelligence** | **Best** | Good | Strong | Good | Good | Strong |
| **SWE-bench Verified** | Good (76.8%) | Good (SWE-Pro 56.2%) | **Best (77.8%)** | Weakest (73.1%) | TBD | TBD |
| **SWE-bench Multilingual** | Good (73.0%) | Good (76.5%) | **Best (73.3%)** | Good (70.2%) | TBD | TBD |
| **System/DevOps** | Good (50.8%) | **Best** (57.0%) | Strong (56.2%) | Weakest (46.4%) | TBD | TBD |
| **Math/reasoning** | **Best** (AIME 96.1%) | Moderate | Strong (AIME 92.7%) | Strong (Speciale 96.0%) | TBD | TBD |
| **Instruction following** | **Best** (IFEval 94%) | Good (97% skill adherence) | Good | Good | TBD | TBD |
| **Long context** | **Best** (256K native) | Good (200K) | Good (198K) | Weakest (128K) | Good (256K?) | Good (198K?) |
| **F# pass rate (benchmarked)** | 34.9% | **76.6%** | 70.6% | 43.1% (original) | **2.6%** | 11.1% |
| **F# libraries pass rate** | 20.5% | **56.6%** | 14.9% | 87.3% (original) | **0.8%** | 29.8% |
| **dotnet_aspnet pass rate** | 0% (empty) | N/A | **97.1%** | N/A | N/A | 80.3% |
| **Frontend/Svelte/TS** | **Best** | Good | Good | Good | TBD | TBD |
| **Docker/K8s** | Good | **Best** | Strong | Weakest | TBD | TBD |
| **Agentic tasks** | Good | **Best** | Strong | Good | TBD | TBD |
| **License** | Modified MIT | Cloud-only | **MIT** | **MIT** | Modified MIT | MIT |
| **Availability** | Ollama cloud | Ollama cloud | Ollama cloud | Ollama cloud + open weights | Ollama cloud | Ollama cloud |
| **Skip rate (empty responses)** | High (41-61%) | **Near zero** | TBD | Low | **Very high (96%+)** | Moderate (16-19%) |

### Current Teacher Assignments (Round 2)

| Teacher | Domains | Rationale |
|---------|---------|-----------|
| **MiniMax M2.7** | fsharp_core, fsharp_libraries | 76.6% F# pass rate (best), near-zero skip rate |
| **Kimi K2.5** | svelte_typescript, cross_domain, long_context | Best frontend/TS, longest context (256K) |
| **GLM-5** | dotnet_aspnet, docker_kubernetes, agentic_swe, general_coding | Best SWE-bench scores, replaces DeepSeek |

### New Model Benchmarks (April 2026)

#### Kimi K2.6 (Moonshot AI)

- **Ollama**: `kimi-k2.6:cloud`
- **F# core pass rate**: 2.6% (11/427 passed, 96.3% Skipped -- returns prose instead of code)
- **F# libraries pass rate**: 0.8% (1/122 passed, 99.2% Skipped)
- **Assessment**: Despite being an updated model, K2.6 performs significantly worse than K2.5 on F# tasks, with extremely high skip rates (411/427 and 121/122 for fsharp_core and fsharp_libraries respectively). The model frequently returns explanations in prose instead of wrapped F# code blocks. Not suitable for F# distillation.

#### GLM-5.1 (Z.ai)

- **Ollama**: `glm-5.1:cloud`
- **F# core pass rate**: 11.1% (7/63 passed)
- **F# libraries pass rate**: 29.8% (14/47 passed)
- **dotnet_aspnet pass rate**: 80.3% (167/208 passed)
- **Assessment**: Mixed results. GLM-5.1 shows improvement over GLM-5 on fsharp_libraries (29.8% vs 14.9%) but dramatic regression on fsharp_core (11.1% vs 70.6%) and dotnet_aspnet (80.3% vs 97.1%). The high skip rate on fsharp_core (40/63) suggests the model frequently fails to generate code for F# core language topics. For dotnet_aspnet, the 39 Skipped samples (out of 208) are notable -- K2.5 had 200+ skips on the same domain. GLM-5 remains the better choice for .NET/ASP.NET tasks.
