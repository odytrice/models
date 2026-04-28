# Distillation Pipeline

## Step 1: Generate Training Data from Teachers

No existing distillation datasets exist for any of the three teachers. All training data must be generated via Ollama cloud.

### Teacher Access (all via Ollama cloud subscription)

| Teacher | Ollama Command | Notes |
|---------|---------------|-------|
| **Kimi K2.5** | `ollama run kimi-k2.5:cloud` | 256K context |
| **Kimi K2.6** | `ollama run kimi-k2.6:cloud` | 256K context, thinking mode (max output 262144) |
| **MiniMax M2.7** | `ollama run minimax-m2.7:cloud` | 200K context |
| **DeepSeek V3.2** | `ollama run deepseek-v3.2:cloud` | 128K context |
| **GLM-5** | `ollama run glm-5:cloud` | 128K context |
| **GLM-5.1** | `ollama run glm-5.1:cloud` | 128K context, thinking mode (max output 131072) |

### Provider Configuration

The pipeline supports two providers for running teacher models:

| Provider | Flag | Host Env Var | Auth | Default URL |
|----------|------|-------------|------|-------------|
| **Ollama Cloud** | `--provider ollama_cloud` | `OLLAMA_HOST` | `OLLAMA_API_KEY` (Bearer) | `http://localhost:11434` |
| **Xeon-AI** | `--provider xeon_ai` | `XEON_AI_HOST` | None | `http://xeon-ai:11434` |

**Ollama Cloud** -- requires an active Ollama cloud subscription. Set `OLLAMA_API_KEY` in your environment:
```bash
# One-time: add to shell profile
export OLLAMA_API_KEY="your-api-key"
export OLLAMA_HOST="http://localhost:11434"  # default, omit if using localhost
```

**Xeon-AI** -- local or network Ollama instance with pre-pulled models. No auth required. Set `XEON_AI_HOST` if using a non-default address:
```bash
# One-time: add to shell profile
export XEON_AI_HOST="http://xeon-ai:11434"  # default, omit if using default

# Pull models on Xeon-AI before running
ssh xeon-ai "ollama pull glm-5.1:cloud"
ssh xeon-ai "ollama pull kimi-k2.6:cloud"
```

### Benchmark Runner

```bash
# Run all pending benchmarks (generates, verifies, compares)
python pipeline/scripts/run_benchmark.py --provider ollama_cloud --concurrency 5 --verbose

# Run specific teachers
python pipeline/scripts/run_benchmark.py --teachers glm51 kimi26 --provider ollama_cloud

# Run via Xeon-AI
python pipeline/scripts/run_benchmark.py --teachers glm51 kimi26 --provider xeon_ai

# Skip generation, just verify + compare existing data
python pipeline/scripts/run_benchmark.py --verify-only

# Just print comparison table
python pipeline/scripts/run_benchmark.py --compare-only
```

**Important**: Thinking models (K2.6, GLM-5.1) need high `num_predict` because their internal reasoning tokens consume the output budget before visible code appears. The YAML configs set `max_tokens: 262144` (K2.6) and `max_tokens: 131072` (GLM-5.1) respectively. Do NOT lower these values or you'll get empty responses.

### Data Generation Strategy

1. Scrape official docs and repos (see Documentation Sources below)
2. Feed docs as context to the appropriate teacher with domain-specific prompts
3. Generate instruction/response pairs biased 85% toward target stack, 15% general
4. Include long-context samples (32K-204K tokens) generated exclusively by K2.5 (only teacher with 256K context)
5. Use M2.7 for agentic/multi-step prompts that require real-world SWE reasoning
6. Use K2.6 for all F# content (78.1% fsharp_core, 96.6% fsharp_libraries — best by large margin)
7. Use GLM-5.1 for all .NET/ASP.NET content (97.5% pass rate, zero skips)
8. **Verify all F# and .NET code samples with the compiler before including in dataset** (see Verification Pipeline below)

### Data Requirements
- 5K-50K high-quality examples depending on scope
- Diverse long-context samples (32K-204K tokens) -- K2.5 only
- Reasoning traces (thinking mode outputs) -- K2.5 and M2.7
- Agentic multi-step traces -- M2.7 only
- Cross-domain prompts connecting F#/Svelte/Docker/K8s together -- K2.5

---

## F# Compiler Verification Pipeline

All teacher-generated F# code must pass compiler verification before inclusion in the training dataset. This filters out hallucinated APIs, incorrect syntax, wrong type signatures, and non-idiomatic patterns.

### Stage 1: Compilation check (all F# samples)

Every F# code sample is wrapped in a minimal `.fsx` script and run through `dotnet fsi`:

```bash
# Verify a single F# code sample compiles and type-checks
echo "$GENERATED_CODE" > /tmp/verify.fsx
dotnet fsi --check /tmp/verify.fsx
```

- Exit code 0 = passes type checking, include in dataset
- Non-zero = compilation error, discard or send back to teacher for correction
- Use `--check` flag for type-checking without execution (faster, safer)

### Stage 2: Execution check (samples with assertions/tests)

For samples that include test assertions, actually execute them:

```bash
# Run F# script with assertions
timeout 30 dotnet fsi /tmp/verify.fsx
```

- Exit code 0 = all assertions pass, include in dataset
- Non-zero or timeout = runtime error, discard

### Verification Script (pseudocode)

```python
import subprocess
import json

def verify_fsharp_sample(code: str, has_tests: bool = False) -> dict:
    """Verify F# code via the compiler. Returns pass/fail with diagnostics."""
    with open("/tmp/verify.fsx", "w") as f:
        f.write(code)

    # Stage 1: Type-check only
    result = subprocess.run(
        ["dotnet", "fsi", "--check", "/tmp/verify.fsx"],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        return {"status": "compile_error", "stderr": result.stderr}

    # Stage 2: Execute if sample includes tests
    if has_tests:
        result = subprocess.run(
            ["dotnet", "fsi", "/tmp/verify.fsx"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return {"status": "runtime_error", "stderr": result.stderr}

    return {"status": "pass"}
```

### Library-Dependent Code Verification

Samples that reference NuGet packages need a project context. Use a pre-configured verification project:

```xml
<!-- /tmp/verify/verify.fsproj -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Giraffe" Version="7.*" />
    <PackageReference Include="FsToolkit.ErrorHandling" Version="4.*" />
    <PackageReference Include="Akka" Version="1.*" />
    <PackageReference Include="Akka.FSharp" Version="1.*" />
    <PackageReference Include="Thoth.Json.Net" Version="12.*" />
    <PackageReference Include="linq2db" Version="6.*" />
    <PackageReference Include="FluentMigrator" Version="6.*" />
    <PackageReference Include="Npgsql" Version="9.*" />
    <PackageReference Include="Serilog" Version="4.*" />
    <PackageReference Include="FSharp.SystemTextJson" Version="1.*" />
    <PackageReference Include="FSharp.Control.AsyncSeq" Version="3.*" />
  </ItemGroup>
</Project>
```

```bash
# Copy generated code into the project and build
cp generated_sample.fs /tmp/verify/Program.fs
dotnet build /tmp/verify/verify.fsproj --nologo -v q
```

### Expected Rejection Rates
- F# core language samples: ~10-20% rejection (teachers handle basic F# reasonably well)
- F# library-specific samples: ~30-50% rejection (hallucinated APIs are common for niche libraries)
- Rejected samples can optionally be sent back to the teacher with the compiler error for a retry

**This verification step is critical for F# quality.** Without it, the training data will contain hallucinated function names, wrong type signatures, and non-compiling patterns that the student model will learn to reproduce.

---

## Documentation Sources for Training Data Generation

Scrape these directly and feed as context to the appropriate teacher.

### F# (highest priority -- generated via Kimi K2.6)

| Source | URL | Notes |
|--------|-----|-------|
| Microsoft F# Docs | https://learn.microsoft.com/en-us/dotnet/fsharp | Official language reference |
| F# for Fun and Profit | https://fsharpforfunandprofit.com | DDD, railway-oriented programming, best patterns |
| FsToolkit.ErrorHandling | https://github.com/demystifyfp/FsToolkit.ErrorHandling | README + /docs folder |
| Akka.NET Docs | https://getakka.net/articles/intro/what-is-akka.html | Official docs site |
| Akka.NET GitHub | https://github.com/akkadotnet/akka.net | Source + examples |
| Giraffe | https://github.com/giraffe-fsharp/Giraffe | README is the primary docs |
| Giraffe.ViewEngine | https://github.com/giraffe-fsharp/Giraffe.ViewEngine | README |
| Thoth.Json | https://thoth-org.github.io/Thoth.Json | Official docs |
| FSharp.SystemTextJson | https://github.com/Tarmil/FSharp.SystemTextJson | README |
| linq2db | https://linq2db.github.io | Official docs |
| FluentMigrator | https://fluentmigrator.github.io | Official docs |
| FSharp.Control.AsyncSeq | https://github.com/fsprojects/FSharp.Control.AsyncSeq | README |

### Svelte / TypeScript (generated via Kimi K2.5)

| Source | URL | Notes |
|--------|-----|-------|
| Svelte 5 Docs | https://svelte.dev/docs/svelte | Runes, components, reactivity |
| SvelteKit Docs | https://svelte.dev/docs/kit | Routing, SSR, form actions |
| TypeScript Handbook | https://www.typescriptlang.org/docs/handbook | Official reference |

### Docker / Kubernetes (generated via MiniMax M2.7)

| Source | URL | Notes |
|--------|-----|-------|
| Docker Docs | https://docs.docker.com | Dockerfile, compose, multi-stage builds |
| Kubernetes Docs | https://kubernetes.io/docs | Deployments, services, Helm |

### .NET (generated via GLM-5.1)

| Source | URL | Notes |
|--------|-----|-------|
| ASP.NET Core Docs | https://learn.microsoft.com/en-us/aspnet/core | Middleware, DI, minimal APIs |
| .NET Docs | https://learn.microsoft.com/en-us/dotnet | Runtime, SDK, libraries |

---

## Step 2: Configure Student Model

```yaml
model_name: Qwen/Qwen3.5-27B
max_sequence_length: 262144  # 256K -- train at full native context
rope_scaling:
  type: yarn
  original_max_position_embeddings: 32768
  factor: 8.0  # 262144 / 32768
```

Train at 256K (the full native context of Qwen3.5-27B), then inference at 204800. A model trained at 256K handles any length below it without degradation. See [04-training-config.md](04-training-config.md) for full rationale on context length and precision strategy.

**Exception**: If training locally on 32GB VRAM (RTX 5090), train at 204800 instead to save ~25% VRAM at stage 4.

## Step 3: Progressive Context Training (SFT with LoRA)

Train in BF16 with LoRA. Do NOT use 4-bit QLoRA -- train at full precision and quantize afterward. See [04-training-config.md](04-training-config.md) for precision rationale.

Train in stages to avoid instability from jumping straight to max context:

1. **Stage 1** (8K-16K context): 2-3 epochs, fast convergence
2. **Stage 2** (32K-64K context): 2 epochs
3. **Stage 3** (128K context): 1-2 epochs
4. **Stage 4** (256K context): 1 epoch, very slow per step (use 204800 if local 32GB VRAM)

## Step 4: Optional Alignment (DPO/RLHF)

Likely unnecessary for domain-specific coding. SFT on high-quality distillation data should suffice.
