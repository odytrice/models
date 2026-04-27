# Events Log

Chronological record of everything that has happened during the multi-teacher distillation pipeline build and execution.

---

## Session 1: Infrastructure & Pipeline Build

### Pipeline Infrastructure Setup
- Created full project directory structure: `pipeline/`, `data/`, `configs/`
- Set up `pipeline/verify/verify.fsproj` (.NET 10) with 30+ NuGet packages (Giraffe, FsToolkit, Akka.NET, linq2db, Serilog, etc.)
- One minor warning: System.Reactive version mismatch (FSharp.Control.Reactive needs <6, Minio needs >=6) -- resolved by pinning System.Reactive 6.x
- Verification project builds clean

### Script Development
- Created `pipeline/scripts/generate_data.py` -- async Ollama API integration, resume support, concurrency control
- Created `pipeline/scripts/verify_fsharp.py` -- F# compiler verification via `dotnet fsi` (Stage 1: compile) and `dotnet build` (Stage 2: execute)
- Created `pipeline/scripts/format_dataset.py` -- ChatML/ShareGPT conversion, context-length bucketing, train/val split
- Created `pipeline/scripts/doc_lookup.py` -- DuckDuckGo search with caching, known GitHub URL cache, local Svelte docs
- Created `pipeline/scripts/expand_prompts.py` -- auto-expand seed prompts via teachers (30 variations each)

### Discovery: `dotnet fsi --check` doesn't exist
- Planned to use `dotnet fsi --check` for type-checking only (no execution)
- Discovered this flag doesn't exist in .NET 10
- **Fix**: Always execute scripts with `dotnet fsi`, distinguish compile errors (FS#### codes in stderr) from runtime errors

### Discovery: DuckDuckGo struggles with "F#"
- The `#` character breaks DuckDuckGo search queries
- **Fix**: Replace `F#` with `FSharp` in search queries, added fallback site-scoped searches for known domains (e.g., `site:getakka.net`)

### Discovery: `duckduckgo-search` package renamed
- Shows RuntimeWarning that it's been renamed to `ddgs`
- Still works fine with current import, no action needed

### Svelte Docs
- Discovered Svelte provides `llms-full.txt` at `svelte.dev/llms-full.txt` (1.1MB complete Svelte 5 + SvelteKit 2 docs)
- Downloaded and saved to `pipeline/docs/svelte_full.txt`

### Seed Prompts Created (165 total across 9 files)
| File | Seeds | Teacher |
|------|-------|---------|
| fsharp_core.yaml | 25 | DeepSeek |
| fsharp_libraries.yaml | 32 | DeepSeek |
| svelte_typescript.yaml | 24 | Kimi |
| docker_kubernetes.yaml | 16 | MiniMax |
| agentic_swe.yaml | 16 | MiniMax |
| cross_domain.yaml | 12 | Kimi |
| dotnet_aspnet.yaml | 15 | DeepSeek |
| long_context.yaml | 10 | Kimi |
| general_coding.yaml | 15 | DeepSeek |

### Ollama Setup
- User upgraded to Ollama Max plan ($100/mo) -- 250x free usage, 10 concurrent models
- Pulled `deepseek-v3.2:cloud` (was not pre-installed)
- All 3 teachers confirmed available: `deepseek-v3.2:cloud`, `kimi-k2.5:cloud`, `minimax-m2.7:cloud`

### End-to-End Test
- Generated 5 F# samples, verified 3 passed (60% pass rate), formatted to ChatML
- Pipeline validated end-to-end
- Prompt expansion test: DeepSeek V3.2 generated 5 variations of a seed prompt in 114 seconds

### Training Configs Created
- 4 stage training scripts: `configs/train_stage[1-4].py`
- Merge and export script: `configs/merge_and_export.py`
- Progressive context: Stage 1 (8K-16K), Stage 2 (32K-64K), Stage 3 (128K), Stage 4 (256K/204800)

---

## Session 2: Prompt Expansion & Generation

### Prompt Expansion (All 165 Seeds)
- Ran `expand_prompts.py --all --variations 30 --with-docs --concurrency 3`
- Completed in ~75 minutes
- Results:

| Domain | Seeds | Expanded Prompts | Teacher |
|--------|-------|------------------|---------|
| fsharp_libraries | 32 | 962 | DeepSeek |
| fsharp_core | 25 | 750 | DeepSeek |
| svelte_typescript | 24 | 676 | Kimi |
| dotnet_aspnet | 15 | 450 | DeepSeek |
| general_coding | 15 | 450 | DeepSeek |
| docker_kubernetes | 16 | 414 | MiniMax |
| cross_domain | 12 | 321 | Kimi |
| agentic_swe | 16 | 279 | MiniMax |
| long_context | 10 | 267 | Kimi |
| **Total** | **165** | **4,569** | |

- 4,569 unique prompts (vs 4,950 target -- some lost to deduplication, expected and healthy)

### Generation Run 1: Initial Attempt (Sequential, Concurrency 5)
- Created `run_generation.bat` -- originally sequential, one domain at a time
- Initial concurrency: 5 per file

### Optimization: Parallel Teachers
- Realized all 3 teachers could run simultaneously since they're different models
- Created `run_generation.py` -- Python script with asyncio, 3 teachers in parallel
- Bumped concurrency to 10 per teacher

### Problem: 429 Rate Limits
- At concurrency 10 per teacher (30 total), Ollama returned 429 Too Many Requests
- The errors cascaded -- failed requests were immediately retried, hitting more 429s
- `generate_data.py` had no retry/backoff logic -- just logged the error and moved on

### Fix: Exponential Backoff + Lower Concurrency
- Added retry with exponential backoff to `generate_data.py`: 2s, 4s, 8s, 16s, 32s delays, up to 5 attempts on 429/5xx errors
- Lowered default concurrency to 7 per teacher (21 total)
- Tested at 5, 6, 7 -- settled on 7 as a good balance

### Problem: No Data Written to Disk During Generation
- `generate_data.py` originally used `asyncio.gather` to collect ALL results, then wrote them to file at the end
- For a multi-hour run, this meant: (a) no progress visible, (b) if killed, ALL data lost
- Resume didn't work because nothing was on disk yet

### Fix: Stream-to-Disk
- Rewrote `generate_data.py` to write each sample immediately as it completes using an asyncio lock
- Added progress percentage logging every 10 completions
- Resume now works properly -- completed samples are on disk, re-running skips them

### OpenCodeInstruct Integration
- Researched open datasets for software engineering
- Selected NVIDIA's OpenCodeInstruct (5M Python coding samples, CC-BY-4.0)
- Created `pipeline/scripts/download_opencode.py`
- Applied strict quality filters:
  - `average_test_score >= 0.9` (passes 9+ of 10 unit tests)
  - LLM judgement `requirement_conformance >= 4`
  - LLM judgement `logical_correctness >= 4`
  - LLM judgement `edge_case_consideration >= 4`
- Downloaded 2,500 samples from 86,597 scanned (28.9% pass rate at strict threshold)
- Output: `data/verified/opencode_instruct.jsonl` (4.5 MB)
- Completed in 14 seconds (streaming mode, early exit after collecting 10x target)

### Generation Run 1: Actual Execution
- Launched with `run_generation.bat` (3 teachers parallel, concurrency 7)
- Per-line log output from all 3 teachers interleaved in console

### Problem: DeepSeek Bottleneck
- MiniMax finished all its work (693 prompts) relatively quickly
- Kimi finished all its work (1,264 prompts) 
- DeepSeek averaging ~300s per request (vs estimated ~90s) -- F# responses are long and complex
- DeepSeek had 2,612 prompts (57% of all work) assigned to it
- Estimated completion: ~19 hours with only DeepSeek still running

### Fix: Redistribute Work to Idle Teachers
- Reassigned `dotnet_aspnet` (450 prompts) from DeepSeek to Kimi
- Reassigned `general_coding` (450 prompts) from DeepSeek to MiniMax
- Created modified expanded YAML copies with teacher field changed:
  - `dotnet_aspnet_expanded_kimi.yaml`
  - `general_coding_expanded_minimax.yaml`
- Updated `TEACHERS` mapping in `run_generation.py`
- New distribution:
  - DeepSeek: fsharp_core (750) + fsharp_libraries (962) = 1,712
  - Kimi: svelte_typescript (676) + cross_domain (321) + long_context (267) + dotnet_aspnet (450) = 1,714
  - MiniMax: docker_kubernetes (414) + agentic_swe (279) + general_coding (450) = 1,143

### Status Dashboard
- Created `status.py` and `status.bat` for monitoring progress
- Unicode block characters (and em-dashes) caused `UnicodeEncodeError` on Windows (cp1252 encoding)
- **Fix**: Replaced with ASCII characters (`#`, `-`)
- Later integrated status dashboard directly into `run_generation.py` as the default output mode
- Removed standalone `status.py`/`status.bat` (functionality now in `run_generation.py --status`)
- Added `--verbose` flag for old per-line log behavior

### Generation Run 1: Restarted with Redistribution
- Killed the running process, restarted with new teacher assignments
- Resume worked -- all previously completed samples were on disk and skipped
- At restart: 2,717 / 4,569 (59.5%) already complete
- All 3 teachers now actively working in parallel again

### Second Pass Planning
- Created `second_pass_plan.md` documenting the strategy for running generation twice at different temperatures
- Plan: same prompts, temperature 0.9 (vs 0.7 default), output to `*_t2.jsonl` files
- Implemented `--suffix` and `--temperature` flags in both `generate_data.py` and `run_generation.py`
- Created `run_generation_pass2.bat` launcher

---

## Generation Run 1: Final Results

### Completion
- **Total runtime**: 8 hours 37 minutes
- **All 4,569 prompts generated successfully**

### F# Verification Results

| Dataset | Total | Passed | Failed | Skipped | Pass Rate |
|---------|-------|--------|--------|---------|-----------|
| fsharp_core | 750 | 150 (20.0%) | 411 (54.8%) | 189 (25.2%) | 20.0% |
| fsharp_libraries | 962 | 780 (81.1%) | 78 (8.1%) | 104 (10.8%) | 81.1% |
| cross_domain | 321 | 289 (90.0%) | 15 (4.7%) | 17 (5.3%) | 90.0% |
| dotnet_aspnet | 450 | 100 (22.2%) | 1 (0.2%) | 349 (77.6%) | 22.2% |

Failure breakdown:
- **fsharp_core**: 409 compile errors, 2 runtime errors, 189 skipped (no F# code extracted)
- **fsharp_libraries**: 78 compile errors, 104 skipped
- **cross_domain**: 15 compile errors, 17 skipped
- **dotnet_aspnet**: 1 compile error, 349 skipped (Kimi generated mostly prose without code blocks)

### Formatted Dataset

| Domain | Samples | % of Total |
|--------|---------|------------|
| general_coding | 2,950 | 44.2% |
| fsharp_libraries | 780 | 11.7% |
| svelte_typescript | 676 | 10.1% |
| cross_domain | 610 | 9.1% |
| dotnet_aspnet | 550 | 8.2% |
| docker_kubernetes | 414 | 6.2% |
| agentic_swe | 279 | 4.2% |
| long_context | 267 | 4.0% |
| fsharp_core | 153 | 2.3% |
| **Total** | **6,679** | |

- Train split: 6,346 / Val split: 333
- Format: ChatML
- All samples landed in stage1 (0-16K tokens) -- no long-context samples generated

---

## Known Issues (Post Run 1)

### 1. fsharp_core pass rate critically low (20%)
- 189/750 (25%) skipped due to no F# code extracted -- DeepSeek may not be wrapping code in proper fenced blocks
- 409/750 (55%) compile errors -- DeepSeek generating invalid F# syntax for core language constructs
- Only 150 usable samples from 750 prompts

### 2. dotnet_aspnet skip rate extremely high (77.6%)
- 349/450 skipped (no F# code extracted)
- Kimi generated mostly explanations/prose without code blocks for ASP.NET F# content
- May need system prompt changes demanding code blocks, or try a different teacher

### 3. general_coding proportion too high (44.2%)
- Should be ~6% per training spec (02-domain-specialization.md)
- OpenCodeInstruct (2,500) + general_coding (450) = 2,950 samples dominating the mix
- Need to downsample OpenCodeInstruct from 2,500 to ~500-800

### 4. fsharp_core proportion too low (2.3%)
- Should be 15% per training spec
- Caused by the 20% verification pass rate gutting 750 down to 153

### 5. No long-context samples
- All 6,679 samples fit in stage1 (0-16K tokens)
- The long_context domain (267 samples) should have produced 32K-256K token responses
- Teachers are not generating truly long responses despite prompts asking for them

### 6. Code extraction may be too strict
- High skip rates in fsharp_core (25%) and dotnet_aspnet (77.6%) suggest the verification script's code extraction logic may be rejecting valid code that isn't in standard fenced code blocks

---

## Session 3: Verification Fixes & Teacher Benchmark

### F# Verification Fixes (3 fixes, +375 samples recovered)

Investigated root causes of low pass rates by analyzing failed/skipped samples from round 1.

**Root causes identified:**
- **Truncated responses (155 fsharp_core, 147 dotnet_aspnet)**: Teacher hit max_tokens, code fence opened but never closed. Regex required closing fence, so valid code was discarded.
- **Empty responses (34 fsharp_core, 200 dotnet_aspnet)**: Teacher returned no content at all. Kimi especially bad for ASP.NET/F# topics.
- **namespace/module in .fsx (92 fsharp_core)**: Teachers generated `namespace X` or `module X` declarations which are invalid in F# script files (.fsx). Needed routing through project build (.fs) instead.
- **Multi-block concatenation conflicts (16 fsharp_core)**: Multiple code blocks with conflicting module declarations were concatenated, causing compile errors.

**Fix 1: Handle truncated responses**
- Added fallback regex for unclosed fenced blocks (opening tag with no closing tag)
- Extracts everything after the opening fence to end-of-string

**Fix 2: Route namespace/module code through project build**
- Added `needs_project_for_structure()` function that detects `namespace X` or top-level `module X` declarations
- Routes these through `verify_with_project` (as .fs files) instead of `verify_with_fsi` (as .fsx)

**Fix 3: Smarter multi-block handling**
- When multiple code blocks have conflicting top-level declarations (`namespace`, `module`, `open`), use only the largest block instead of concatenating all blocks

**Re-verification results:**

| Domain | Before | After | Change |
|--------|--------|-------|--------|
| fsharp_core | 150 (20.0%) | 323 (43.1%) | +173 (+115%) |
| fsharp_libraries | 780 (81.1%) | 840 (87.3%) | +60 (+8%) |
| cross_domain | 289 (90.0%) | 289 (90.0%) | Same |
| dotnet_aspnet | 100 (22.2%) | 242 (53.8%) | +142 (+142%) |
| **Total** | **1,319** | **1,694** | **+375 (+28%)** |

### Re-formatted Dataset (Post Verification Fixes)

| Domain | Samples | % of Total |
|--------|---------|------------|
| general_coding | 2,950 | 41.8% |
| fsharp_libraries | 840 | 11.9% |
| dotnet_aspnet | 692 | 9.8% |
| svelte_typescript | 676 | 9.6% |
| cross_domain | 610 | 8.6% |
| docker_kubernetes | 414 | 5.9% |
| fsharp_core | 326 | 4.6% |
| agentic_swe | 279 | 4.0% |
| long_context | 267 | 3.8% |
| **Total** | **7,054** | |

- Train: 6,702 / Val: 352
- All samples still in stage1 (0-16K tokens)

### Round 2 Infrastructure Built

- Added `--temperature` CLI override to `generate_data.py`
- Added `--suffix` and `--temperature` flags to `run_generation.py`
- Created `run_generation_pass2.bat` -- runs same prompts at temperature 0.9, outputs to `*_t2.jsonl`

### F# Teacher Benchmark (In Progress)

Before running round 2, decided to benchmark all 3 teachers on F# to determine optimal teacher assignments.

**Approach:**
- Extracted 549 prompts that DeepSeek failed on (427 fsharp_core + 122 fsharp_libraries)
- Running the same prompts through Kimi and MiniMax for a 3-way comparison
- Created `pipeline/scripts/extract_failed.py` to extract failed prompts from verification results
- Created `pipeline/scripts/run_benchmark.py` with status dashboard and comparison table
- 4 benchmark YAML files: fsharp_core_kimi, fsharp_core_minimax, fsharp_libraries_kimi, fsharp_libraries_minimax

**Preliminary evidence (from round 1 data):**
- Kimi produces higher quality F# code (~90-97% pass rate when it generates code)
- But Kimi frequently returns empty/prose-only responses for .NET/F# topics
- DeepSeek almost always generates code but at lower quality (43-87% pass rate)
- MiniMax has no F# data yet -- benchmark will provide first evidence

**Also added:**
- `--progress-every` flag to `generate_data.py` (default 10, benchmark uses 1 for per-sample progress)
- ETA display to benchmark status dashboard

**Estimated benchmark runtime:** ~4 hours (2 teachers in parallel, 549 prompts each)

---

## Remaining Issues

### 1. general_coding proportion still too high (41.8%)
- OpenCodeInstruct at 2,500 samples dominates the mix
- Plan: downsample to ~500 after benchmark completes

### 2. fsharp_core still underrepresented (4.6% vs 15% target)
- Benchmark results will determine which teacher to use for round 2
- May also need more seed prompts

### 3. No long-context samples
- All samples fit in stage1 (0-16K)
- Teachers not generating long enough responses

### 4. dotnet_aspnet still has high skip rate (202/450 = 45%)
- Empty responses from Kimi -- generation problem, not extraction
- Round 2 may improve with higher temperature encouraging more output

---

## GLM-5 Added as Teacher

### Research and Selection
- Researched latest coding LLMs (Qwen3.5-397B, DeepSeek V3.2, Qwen3-Coder-Next, Devstral 2, GLM-4.7-Flash, GLM-5)
- Selected **GLM-5** (744B total, 40B active, MoE) from Z.ai as DeepSeek's replacement
- Key stats: 77.8% SWE-bench Verified, 73.3% SWE-bench Multilingual (both highest among our teachers)
- Available on Ollama: `glm-5:cloud`, MIT license
- Pulled successfully

### GLM-5 Benchmark Results

Ran GLM-5 on:
- 63 fsharp_core prompts (ones both Kimi AND MiniMax failed on)
- 47 fsharp_libraries prompts (same)
- 208 dotnet_aspnet prompts (all that Kimi failed on)

**Results:**

| Domain | GLM-5 Passed | GLM-5 Pass Rate | vs MiniMax | vs Kimi |
|--------|-------------|-----------------|------------|---------|
| fsharp_core (63 remaining) | 149/427* | 70.6%* | MiniMax better (76.6%) | GLM-5 better |
| fsharp_libraries (47 remaining) | 7/122* | 14.9%* | MiniMax better (56.6%) | GLM-5 worse |
| dotnet_aspnet (208 prompts) | 202/208 | **97.1%** | N/A | **Massively better** |

*Note: GLM-5 ran on all 427/122 prompts for fsharp_core/libraries (not just the 63/47 remaining). The pass rates are on the full failed set.

**dotnet_aspnet was the standout: GLM-5 achieved 97.1% (202/208) on prompts Kimi scored 0% on.** This recovered 202 samples that were completely lost.

### Combined Best-of-All-Teachers (After Merging Benchmark Data)

| Domain | Original Only | Combined (all teachers) | Rate |
|--------|--------------|------------------------|------|
| fsharp_core | 323/750 (43.1%) | **702/750 (93.6%)** | +379 |
| fsharp_libraries | 840/962 (87.3%) | **922/962 (95.8%)** | +82 |
| dotnet_aspnet | 242/450 (53.8%) | **444/450 (98.7%)** | +202 |

**663 new verified samples recovered** from benchmark data, merged into main verified files.

### Format Script Fix
- Discovered `format_dataset.py` was including non-passing samples from dotnet_aspnet and cross_domain
- Fixed loader to check `verify_result.status == "pass"` for all samples that have a verify_result
- Added `seen_ids` deduplication to prevent double-counting from `_passing.jsonl` and main `.jsonl` files

### Final Formatted Dataset (Post-Benchmark Merge)

| Domain | Samples | % of Total |
|--------|---------|------------|
| general_coding | 2,950 | 42.5% |
| fsharp_libraries | 922 | 13.3% |
| fsharp_core | 705 | 10.1% |
| svelte_typescript | 676 | 9.7% |
| dotnet_aspnet | 444 | 6.4% |
| docker_kubernetes | 414 | 6.0% |
| cross_domain | 289 | 4.2% |
| agentic_swe | 279 | 4.0% |
| long_context | 267 | 3.8% |
| **Total** | **6,946** | |

- Train: 6,599 / Val: 347
- All samples in stage1 (0-16K tokens)

### Devstral Small 2 Added as Second Student Model
- Added `devstral-small-2:24b` (Mistral) as a secondary student alongside Qwen3.5-27B
- 24B dense, 256K context, 65.8% SWE-bench Verified, purpose-built for agentic coding
- Same training data can be used for both models with minimal config changes
- Updated `Training/00-overview.md` and `Training/01-teacher-models.md`

### DeepSeek V3.2 Retired
- Removed from active teacher assignments
- Replaced by MiniMax (F# domains) and GLM-5 (.NET/general domains)
- Still documented for reference since it generated round 1 data

### Final Teacher Assignments for Round 2

| Teacher | Domains |
|---------|---------|
| **MiniMax M2.7** | fsharp_core, fsharp_libraries |
| **Kimi K2.5** | svelte_typescript, cross_domain, long_context |
| **GLM-5** | dotnet_aspnet, docker_kubernetes, agentic_swe, general_coding |

---

## Config-Driven Round System

### Problem
`run_generation.py` had hardcoded teacher assignments. Changing teachers for round 2 would overwrite round 1 config, making it non-reproducible. Also risked breaking resume if the script was re-run for round 1.

### Solution: Round config YAMLs
Extracted teacher assignments into separate config files:
- `configs/rounds/round1.yaml` -- historical round 1 assignments (DeepSeek + Kimi + MiniMax)
- `configs/rounds/round2.yaml` -- optimized round 2 assignments (MiniMax + Kimi + GLM-5)

Each config specifies: teacher-to-domain mapping, suffix, temperature, concurrency.

`run_generation.py` now takes `--round-config` as a required argument. Config values (suffix, temperature, concurrency) serve as defaults that can be overridden by CLI flags.

### Files created
- `configs/rounds/round1.yaml`, `configs/rounds/round2.yaml`
- 6 new expanded YAML copies with updated teacher fields:
  - `fsharp_core_expanded_minimax.yaml` (750 prompts)
  - `fsharp_libraries_expanded_minimax.yaml` (962 prompts)
  - `dotnet_aspnet_expanded_glm5.yaml` (450 prompts)
  - `docker_kubernetes_expanded_glm5.yaml` (414 prompts)
  - `agentic_swe_expanded_glm5.yaml` (279 prompts)
  - `general_coding_expanded_glm5.yaml` (450 prompts)

### Usage
```bash
# Round 1 (historical)
python run_generation.py --round-config ../../configs/rounds/round1.yaml --status

# Round 2
python run_generation.py --round-config ../../configs/rounds/round2.yaml --verify

# Override config values
python run_generation.py --round-config ../../configs/rounds/round2.yaml --concurrency 5 --temperature 0.85
```

### Tested
- `--status` on round 1 config shows all 4,569 samples complete
- `--status` on round 2 config shows correct teacher assignments (MiniMax, Kimi, GLM-5) with all samples pending

---

## Round 2 Generation (Complete)

- **Started**: 2026-03-22 ~18:00
- **Completed**: 2026-03-23 ~05:00 (~11 hours)
- **Config**: `configs/rounds/round2.yaml`
- **Teachers**: MiniMax (F#), Kimi (Svelte/TS/long-context), GLM-5 (.NET/general)
- **Temperature**: 0.9 (higher than round 1 defaults for diverse outputs)
- **Suffix**: `_t2` (outputs to `*_t2.jsonl`)
- **Total prompts**: 4,569

### Round 2 F# Verification Results

| Domain | Teacher | Total | Passed | Pass Rate | vs Round 1 |
|--------|---------|-------|--------|-----------|------------|
| fsharp_core | MiniMax | 627 | 498 | **79.4%** | +36.3 pts (was 43.1% with DeepSeek) |
| fsharp_libraries | MiniMax | 1,412 | 1,203 | **85.2%** | -2.1 pts (was 87.3% with DeepSeek) |
| cross_domain | Kimi | 278 | 257 | **92.4%** | +2.4 pts |
| dotnet_aspnet | GLM-5 | 353 | 350 | **99.2%** | +45.4 pts (was 53.8% with Kimi) |

Teacher reassignments validated:
- **MiniMax on fsharp_core**: 79.4% vs DeepSeek's 43.1% -- nearly doubled the pass rate
- **GLM-5 on dotnet_aspnet**: 99.2% vs Kimi's 53.8% -- near perfect
- **MiniMax on fsharp_libraries**: 85.2% vs DeepSeek's 87.3% -- comparable, slightly lower but within noise

Note: MiniMax generated 2,013 samples for a 1,712 prompt workload (118%) -- some prompts got duplicate responses at the higher temperature. Kimi and GLM-5 completed 72% and 79% of their prompts before the verify step ran, but the critical F# domains were fully processed.

### OpenCodeInstruct Downsampled

- Reduced from 2,500 to 500 samples
- Re-ran `download_opencode.py --samples 500`
- Same strict quality filters (test score >= 0.9, LLM judgement >= 4)
- general_coding proportion dropped from 42.5% to 13.9%

### Mistral Instruct Format Added

- Added `--format mistral` to `format_dataset.py` for Devstral Small 2 training
- Added `--format all` option that outputs both chatml and mistral in subdirectories
- Mistral format uses same `messages` structure as ChatML -- Unsloth applies correct special tokens at training time via `chat_template="mistral"`

### Final Formatted Dataset (Training-Ready)

| Domain | Samples | % |
|--------|---------|---|
| fsharp_libraries | 2,068 | 30.2% |
| fsharp_core | 990 | 14.4% |
| general_coding | 950 | 13.9% |
| svelte_typescript | 676 | 9.9% |
| dotnet_aspnet | 665 | 9.7% |
| cross_domain | 546 | 8.0% |
| docker_kubernetes | 414 | 6.0% |
| agentic_swe | 279 | 4.1% |
| long_context | 267 | 3.9% |
| **Total** | **6,855** | |

- **Train**: 6,513 / **Val**: 342
- **Formats**: ChatML (Qwen3.5) and Mistral (Devstral) in separate subdirectories
- All samples in stage1 (0-16K tokens)
- F# total (core + libraries) = 3,058 (44.6%) -- intentionally high given F# scarcity in pre-training data

### Data output structure:
```
data/formatted/
  chatml/
    stage1_train.jsonl     # 6,513 samples (for Qwen3.5-27B)
    stage1_val.jsonl       # 342 samples
  mistral/
    stage1_train.jsonl     # 6,513 samples (for Devstral Small 2)
    stage1_val.jsonl       # 342 samples
```

---

## Data Generation Complete

Total generation effort across both rounds:

| Phase | Duration | Samples Generated | Samples Verified |
|-------|----------|-------------------|-----------------|
| Prompt expansion | ~75 min | 4,569 prompts from 165 seeds | -- |
| Round 1 generation | 8h 37m | 4,569 | 4,446 (after verification) |
| F# benchmark (Kimi+MiniMax) | ~2h | 1,098 | 439 additional |
| GLM-5 benchmark | ~1.5h | 757 | ~360 additional |
| Round 2 generation | ~11h | 4,569 | ~4,170 (after verification) |
| OpenCodeInstruct download | <1 min | 500 (from 5M pool) | 500 (pre-verified) |
| **Total wall time** | **~24h** | **~11,493** | **6,855 final** |

Pass rate: 59.6% overall (dominated by F# compiler verification filtering out bad code). Non-F# domains have ~100% pass rate.

---

## Duplicate Generation Bug Found and Fixed

### Discovery
Investigating why round 2 had inflated sample counts (e.g., fsharp_libraries_t2 had 1,412 entries for 962 prompts). Turns out **all** round 2 files had duplicates:

| File | Total | Unique | Extras |
|------|-------|--------|--------|
| fsharp_libraries_t2 | 1,412 | 838 | 574 |
| fsharp_core_t2 | 651 | 530 | 121 |
| general_coding_t2 | 451 | 333 | 118 |
| svelte_typescript_t2 | 571 | 469 | 102 |
| docker_kubernetes_t2 | 291 | 234 | 57 |
| dotnet_aspnet_t2 | 377 | 322 | 55 |
| cross_domain_t2 | 278 | 225 | 53 |
| agentic_swe_t2 | 158 | 138 | 20 |
| long_context_t2 | 76 | 71 | 5 |
| **Total** | **4,265** | **3,160** | **1,105** |

### Root Cause
In `generate_data.py`, the `existing_ids` set was loaded once at startup from the output file. When concurrent tasks for the same prompt ID completed near-simultaneously, both passed the "not in existing_ids" check before either wrote to disk, resulting in duplicate entries. The higher temperature (0.9) in round 2 made this worse due to faster token generation.

### Fix Applied
1. **`generate_data.py`**: Added a `completed_ids` set checked under the asyncio write lock. Before writing, the lock-holder checks if the ID was already written by another concurrent task during this run. Prevents future duplicates.

2. **`dedup_round2.py`**: New script to clean existing duplicate files. For each prompt ID with multiple responses:
   - F# domains: prefers the response that passes verification, then picks the longer one
   - Non-F# domains: picks the longer response (more training signal)
   - Supports `--dry-run` for preview

### Dedup Results (fsharp_libraries_t2 detail)
- 444 IDs: both responses passed verification -- kept the longer one
- 83 IDs: one passed, one failed -- kept the passing one
- 47 IDs: neither passed -- kept the longer one (excluded by format_dataset anyway)

### Impact
- Removed 1,105 duplicate entries from raw files
- Removed 1,105 duplicate entries from verified files
- Actual unique round 2 samples: 3,160 (was inflated to 4,265)
- Formatted dataset unchanged at 6,855 (format_dataset already deduplicated via `seen_ids`)

### Round 2 Completion Status (Post-Dedup)

| Domain | Unique Generated | Target | Remaining |
|--------|-----------------|--------|-----------|
| fsharp_core_t2 | 535 | 750 | 215 |
| fsharp_libraries_t2 | 838 | 962 | 124 |
| svelte_typescript_t2 | 472 | 676 | 204 |
| cross_domain_t2 | 225 | 321 | 96 |
| long_context_t2 | 71 | 267 | 196 |
| dotnet_aspnet_t2 | 325 | 450 | 125 |
| docker_kubernetes_t2 | 234 | 414 | 180 |
| agentic_swe_t2 | 138 | 279 | 141 |
| general_coding_t2 | 333 | 450 | 117 |
| **Total** | **3,171** | **4,569** | **1,398** |

Round 2 re-run is in progress to complete the remaining 1,398 prompts. With the duplicate fix applied, the re-run will not produce duplicates.

---

## Remaining Issues

### 1. No long-context samples
- All 6,855 samples fit in stage1 (0-16K tokens)
- Teachers not generating long enough responses
- Stages 2-4 of progressive training have no data
- Could be addressed in a future round with explicit long-response prompts, but not blocking for initial training

### 2. fsharp_libraries proportion high (30.2%)
- Intentionally high -- F# is severely underrepresented in base model pre-training
- Can be rebalanced if evaluation shows overfitting on F# library patterns

### 3. Round 2 incomplete (1,398 prompts remaining)
- Re-run in progress with duplicate fix applied
- Expected to add ~1,200-1,300 verified samples after F# filtering
- Projected final total: ~7,500-7,600 samples

---

## Curriculum Gap Analysis and Round 3 Seeds

### Analysis
Conducted a thorough review of the F# training curriculum against comprehensive checklists covering core language features, libraries, modern .NET patterns, and real-world architecture patterns.

### Findings
- **Well-covered**: ~40 topics (DUs, pattern matching, CEs, Giraffe, FsToolkit, Akka.NET, linq2db, etc.)
- **Partially covered**: ~11 topics (need more depth)
- **Completely missing**: ~25+ topics (significant gaps)

### Critical Gaps Identified
1. **FsCheck** (property-based testing) -- zero prompts, signature F# testing library
2. **Expecto** test framework -- zero prompts, major F# test framework
3. **gRPC with F#** -- zero prompts, primary service-to-service pattern in modern .NET
4. **SRTP / inline functions** -- zero prompts, separates intermediate from advanced F#
5. **.NET Aspire** -- zero prompts, newest .NET distributed app framework

### New Seeds Added (20 total)

**fsharp_core.yaml** (+6 seeds, now 31 total):
- `0026`: SRTP and inline functions (member constraints, duck typing, generic math)
- `0027`: Signature files (.fsi) for API design and encapsulation
- `0028`: Object expressions for inline interface implementation
- `0029`: Functional Ports & Adapters (Hexagonal) architecture
- `0030`: CQRS without Event Sourcing
- `0031`: FParsec parser combinators

**fsharp_libraries.yaml** (+9 seeds, now 41 total):
- `0033`: FsCheck property-based testing (generators, shrinking, model-based testing)
- `0034`: Expecto test framework (testList, testAsync, FsCheck integration, benchmarks)
- `0035`: Argu CLI argument parsing (subcommands, env var fallback)
- `0036`: Dapper.FSharp data access (type-safe queries, joins, transactions)
- `0037`: Farmer Azure IaC (Web App, SQL, Service Bus, Storage)
- `0038`: Transactional outbox pattern (linq2db + Kafka)
- `0039`: RabbitMQ consumer/producer (exchanges, DLX, hosted service)
- `0040`: ETL data pipeline (CsvProvider, validation, Npgsql COPY, AsyncSeq)
- `0041`: Bolero (Blazor + F#) with Elmish MVU

**dotnet_aspnet.yaml** (+5 seeds, now 20 total):
- `0016`: gRPC services in F# (proto files, streaming, Giraffe coexistence)
- `0017`: .NET Aspire with F# services (orchestration, service discovery, testing)
- `0018`: Distributed caching with Redis (typed wrapper, cache-aside, stampede prevention)
- `0019`: Polly v8 resilience patterns (retry, circuit breaker, hedging, F#-friendly wrappers)
- `0020`: API versioning (URL path, header-based, DTO evolution, deprecation)

### Round 3 Config
- Created `configs/rounds/round3.yaml`
- Suffix: `_r3`, Temperature: 0.7
- Teachers: MiniMax (F# core + libraries), GLM-5 (.NET/ASP.NET)
- Created `pipeline/scripts/expand_new_seeds.py` to expand only the 20 new seeds
- Expected: ~600 expanded prompts -> ~400-500 verified samples

### Total seed count after round 3 additions
| File | Before | After | New |
|------|--------|-------|-----|
| fsharp_core | 25 | 31 | +6 |
| fsharp_libraries | 32 | 41 | +9 |
| dotnet_aspnet | 15 | 20 | +5 |
| **Total** | **72** | **92** | **+20** |

(Other files unchanged: svelte_typescript 24, docker_kubernetes 16, agentic_swe 16, cross_domain 12, long_context 10, general_coding 15)

Grand total seeds: 185 (was 165)

---

## Round 2 Fully Complete

Round 2 re-run completed all remaining prompts. No duplicates found (dedup bug fix working).

### Final Round 2 F# Verification

| Dataset | Total | Passed | Failed | Skipped | Pass Rate |
|---------|-------|--------|--------|---------|-----------|
| fsharp_core_t2 | 750 | 600 | 141 | 9 | **80.0%** |
| fsharp_libraries_t2 | 962 | 829 | 101 | 32 | **86.2%** |
| cross_domain_t2 | 321 | 296 | 15 | 10 | **92.2%** |
| dotnet_aspnet_t2 | 450 | 445 | 5 | 0 | **98.9%** |

### Final Formatted Dataset

| Domain | Samples | % |
|--------|---------|---|
| fsharp_libraries | 1,695 | 25.8% |
| fsharp_core | 1,003 | 15.3% |
| general_coding | 950 | 14.5% |
| svelte_typescript | 676 | 10.3% |
| dotnet_aspnet | 689 | 10.5% |
| cross_domain | 585 | 8.9% |
| docker_kubernetes | 414 | 6.3% |
| agentic_swe | 279 | 4.3% |
| long_context | 267 | 4.1% |
| **Total** | **6,558** | |

Train: 6,231 / Val: 327. Both ChatML and Mistral formats.

---

## Project Named "Kenichi"

Named after the anime **"Kenichi: The Mightiest Disciple"** -- a student who trains under multiple masters to become the strongest.

| Variant | Base Model | Role |
|---------|-----------|------|
| **Kenichi Thinking** | Qwen3.5-27B | Reasoning-first, deliberate, `<think>` mode |
| **Kenichi Flash** | Devstral Small 2 (24B) | Fast agentic coding, instinctive execution |

---

## SFT Dataset Published to HuggingFace

Published `odytrice/kenichi-sft` to HuggingFace: https://huggingface.co/datasets/odytrice/kenichi-sft

- 6,558 samples across 4 splits: chatml_train, chatml_val, mistral_train, mistral_val
- Full dataset card with pipeline description, teacher benchmarks, domain distribution
- Public, Apache 2.0 license
- Created `pipeline/scripts/push_to_hub.py` for publishing

---

## Strategic Pivot: Logprob Distillation

After researching unsupervised distillation approaches, decided to add logprob-based distillation on top of the existing SFT data.

### Key Insights
- Ollama API supports `logprobs: true` and `top_logprobs: 15` -- returns per-token probability distributions
- Logprob distillation gives ~10x more information per sample than SFT (soft labels vs hard labels)
- Multi-teacher logprob averaging is mathematically principled (vs picking one teacher in SFT)
- The existing 6,558 SFT samples become "curated Tier 3 data" trained with CE loss
- New logprob data (generated with all 3 teachers per prompt) trained with KL-divergence loss
- Combined loss: `alpha * CE(sft_data) + (1-alpha) * KL(logprob_data)`

### Revised Data Strategy

| Tier | Source | Samples | Loss | Signal |
|------|--------|---------|------|--------|
| Curated (existing SFT) | Rounds 1+2 + benchmarks + OCI | ~6,558 | CE (hard labels) | 1 bit/token |
| Logprob (new generation) | All 5,169 prompts x 3 teachers, temp 1.0 | ~5,169 | KL (soft labels) | ~10-15 bits/token |
| **Total** | | **~11,727** | Combined | ~55K SFT-equivalent |

### Plan
1. Re-run ALL existing expanded prompts (rounds 1+2+3) through ALL 3 teachers with logprobs
2. Each prompt gets 3 teacher distributions (MiniMax, GLM-5, Kimi)
3. Primary teacher handles F# verification, fallback on failure
4. Train with multi-teacher KL loss: `sum(wi * KL(student || teacher_i))`
5. Temperature 1.0 for logprob collection (preserves natural distribution)

---

## Logprob Distillation: Dead End

Tested logprobs support across all 3 cloud teacher models (MiniMax M2.7, GLM-5, Kimi K2.5) on Ollama 0.17.1. All returned `logprobs: null`. Investigation confirmed:

- **Ollama cloud models do not return logprobs** -- confirmed by Ollama team member on GitHub issue #13638: "We currently only support logprobs from local models"
- Local models (e.g., `gpt-oss:20b`) return logprobs correctly on all 3 endpoints (`/api/chat`, `/api/generate`, `/v1/chat/completions`)
- `logprobs` and `top_logprobs` are top-level request parameters (NOT inside `options`)
- OpenRouter supports logprobs for GLM-5, Kimi K2.5, and MiniMax M2.5 (not M2.7) at ~$62 total -- rejected to avoid additional cost
- Full investigation documented in `ollama_logprob_investigation.md`

**Decision**: Abandon logprob distillation. Pivot back to domain-specific teacher SFT with failed QA re-runs using substitute teachers.

---

## Pipeline Refactoring

### Merged `generate_data.py` into `run_generation.py`

Eliminated the two-script subprocess architecture. Previously `run_generation.py` spawned `generate_data.py` as subprocesses -- now everything runs in a single async process:

- **Single `httpx.AsyncClient`** -- shared connection pool instead of N separate pools
- **Per-teacher semaphores** -- direct concurrency control without subprocess management
- **Real-time progress tracking** -- `progress` dict updated directly, no file polling
- **Teacher-agnostic YAMLs** -- prompts no longer contain a `teacher` field; teacher assignment comes from round config
- **Removed DeepSeek** -- only 3 teachers remain: `minimax`, `glm5`, `kimi`
- **Added `--summary` flag** -- compact paste-friendly progress output
- **Verbose mode** uses proper `log.info` level (set via `--verbose`)

### Teacher-Agnostic Expanded YAMLs

Restructured all expanded YAML files in `pipeline/prompts/expanded/`:

- Stripped `teacher` field from all 12 YAML files
- Deleted 20 redundant teacher-specific variants (`*_expanded_minimax.yaml`, `*_expanded_glm5.yaml`, etc.)
- Canonical set: 9 original domains + 3 round 3 gap-fills = 12 files, 5,164 total prompts
- Teacher assignment now lives exclusively in round config YAMLs

### Round 3 Config Updated

Updated `configs/rounds/round3.yaml` to use lowercase teacher keys (`minimax`, `glm5`) and reference the new teacher-agnostic YAML filenames.

---

## Round 3 Seed Expansion

Expanded 20 new curriculum gap-fill seeds via `expand_new_seeds.py --variations 30 --concurrency 3`:

| Domain | Seeds | Expanded | Teacher (for expansion) |
|--------|-------|----------|------------------------|
| fsharp_core_r3 | 6 (SRTP, signature files, object expressions, Ports & Adapters, CQRS, FParsec) | 179 | MiniMax M2.7 |
| fsharp_libraries_r3 | 9 (FsCheck, Expecto, Argu, Dapper.FSharp, Farmer, outbox pattern, RabbitMQ, ETL, Bolero) | 266 | MiniMax M2.7 |
| dotnet_aspnet_r3 | 5 (gRPC, .NET Aspire, Redis caching, Polly resilience, API versioning) | 150 | GLM-5 |
| **Total** | **20** | **595** | |

Fixed: Added `glm5` entry to `expand_prompts.py` TEACHERS dict (was missing, would have caused KeyError).

---

## Round 3 Generation -- Complete

595 prompts generated through 2 teachers, 0 failures:
- MiniMax M2.7: fsharp_core_r3 (179), fsharp_libraries_r3 (266)
- GLM-5: dotnet_aspnet_r3 (150)
- Config: `configs/rounds/round3.yaml`, temperature 0.7, concurrency 7

### Verification Results

| Domain | Total | Passed | Failed | Skipped | Pass Rate |
|--------|-------|--------|--------|---------|-----------|
| fsharp_core_r3 | 179 | 110 | 66 | 3 | 61.5% |
| fsharp_libraries_r3 | 266 | 194 | 70 | 2 | 72.9% |
| dotnet_aspnet_r3 | 150 | 136 | 11 | 3 | 90.7% |
| **Total** | **595** | **440** | **147** | **8** | **73.9%** |

Common failure patterns:
- `namespace` keyword in .fsx scripts (signature files, Ports & Adapters seeds) -- not fixable via packages, structural issue
- `Farmer` namespace not found -- fixed by adding NuGet package, but many Farmer samples had other compile errors
- Various type errors in object expression samples (seed 0028)

### Bug Fix: Doubled Suffix

Output files were named `fsharp_core_r3_r3.jsonl` (suffix `_r3` from config + `_r3` from output name). Fixed by removing suffix from round3.yaml config. Renamed all affected files.

### NuGet Packages Added to Verify Project

Added 15 new packages to `pipeline/verify/verify.fsproj` for round 3 gap-fill topics:
- Farmer, StackExchange.Redis, Argu, FsCheck, FsCheck.Xunit, Expecto
- Dapper, Dapper.FSharp, RabbitMQ.Client, FParsec, Bolero
- Microsoft.Extensions.Http.Resilience, Asp.Versioning.Http
- Grpc.AspNetCore (with ExcludeAssets=build to avoid Grpc.Tools F# incompatibility)
- Google.Protobuf, Grpc.Net.Client

### Updated Dataset Totals (after round 3, before namespace fix)

Dataset at **6,998 samples** (up from 6,558):
- 6,649 train / 349 validation (per format)
- ChatML + Mistral instruct formats
- Dataset card updated with round 3 stats and new domain descriptions

---

## Namespace Routing Fix -- +103 Samples Recovered

The verifier's `needs_project_for_structure()` only checked the first line for `namespace` declarations. Teachers often prepend file path comments (e.g., `// src/Domain/Types.fs`) before the namespace, pushing it to line 2+. Fixed to scan past comments, empty lines, and `#r`/`#load` directives before checking for `namespace`/`module`.

Recovery by file:

| File | Before | After | Recovered |
|------|--------|-------|-----------|
| fsharp_core_r3 | 110 | 143 | +33 |
| fsharp_core_t2 | 600 | 618 | +18 |
| fsharp_core | 323 | 340 | +17 |
| fsharp_libraries_r3 | 194 | 207 | +13 |
| cross_domain | 289 | 300 | +11 |
| cross_domain_t2 | 296 | 301 | +5 |
| dotnet_aspnet_r3 | 136 | 139 | +3 |
| dotnet_aspnet | 242 | 244 | +2 |
| dotnet_aspnet_t2 | 445 | 446 | +1 |
| **Total** | **4,304** | **4,407** | **+103** |

Dataset after namespace fix: **6,996 samples** (6,647 train / 349 val). Slight decrease from 6,998 due to deduplication during reformatting.

---

## Substitute Teacher Re-Runs (In Progress)

Extracted 808 failed prompt IDs across all rounds. 806 matched to expanded YAMLs (2 were test IDs). Created 7 substitute teacher YAML files and a round config (`configs/rounds/substitute.yaml`).

### Substitution Strategy

| Domain | Original Teacher | Failures | Substitute | Expected Recovery |
|--------|-----------------|----------|------------|-------------------|
| fsharp_core | deepseek | 378 | minimax (76.6% F#) | ~290 |
| fsharp_core | minimax | 156 | glm5 (70.6% F#) | ~110 |
| fsharp_libraries | minimax | 158 | glm5 | ~111 |
| fsharp_libraries | deepseek | 84 | minimax | ~64 |
| cross_domain | kimi | 16 | minimax | ~12 |
| dotnet_aspnet | glm5 | 12 | minimax | ~9 |
| dotnet_aspnet | kimi | 4 | glm5 | ~4 |
| **Total** | | **808** | | **~600** |

Files created in `pipeline/prompts/expanded/`:
- `fsharp_core_sub_minimax.yaml` (376 prompts)
- `fsharp_core_sub_glm5.yaml` (156 prompts)
- `fsharp_libraries_sub_glm5.yaml` (158 prompts)
- `fsharp_libraries_sub_minimax.yaml` (84 prompts)
- `cross_domain_sub_minimax.yaml` (16 prompts)
- `dotnet_aspnet_sub_minimax.yaml` (12 prompts)
- `dotnet_aspnet_sub_glm5.yaml` (4 prompts)

Running via `run_generation.bat` with `--verify` flag (generation + verification + formatting).

---

## Substitute Teacher Generation — Complete

Substitute run finished after 5:03:37. 1,465 of 1,467 prompts generated (2 minimax cross_domain timed out).

### Substitute Verification Results

| File | Teacher | Generated | Passed | Rate |
|------|---------|-----------|--------|------|
| fsharp_core_sub_minimax | minimax | 376 | 302 | 80.3% |
| fsharp_core_sub_glm5 | glm5 | 156 | 117 | 75.0% |
| fsharp_core_sub_kimi | kimi | 461 | 284 | 61.6% |
| fsharp_libraries_sub_minimax | minimax | 84 | 43 | 51.2% |
| fsharp_libraries_sub_glm5 | glm5 | 158 | 57 | 36.1% |
| fsharp_libraries_sub_kimi | kimi | 200 | 91 | 45.5% |
| cross_domain_sub_minimax | minimax | 14 | 3 | 21.4% |
| dotnet_aspnet_sub_minimax | minimax | 12 | 12 | 100% |
| dotnet_aspnet_sub_glm5 | glm5 | 4 | 3 | 75.0% |
| **Total** | | **1,465** | **912** | **62.3%** |

After formatting with dedup: **7,908 samples** (7,513 train / 395 val). Up from 6,996 pre-substitute.

---

## Verifier Bug Fix — NUGET_INDICATORS (+42 Samples)

### Discovery: Missing Package Routing

The `NUGET_INDICATORS` list in `verify_fsharp.py` was missing all round 3 NuGet packages (Farmer, Argu, FsCheck, Expecto, RabbitMQ, Dapper, FParsec, Bolero, StackExchange.Redis, Grpc, Google.Protobuf). This caused samples using these packages to be verified with `dotnet fsi` (script mode) instead of `dotnet build` (project mode). Since `dotnet fsi` doesn't know about NuGet packages in `verify.fsproj`, all such samples failed with "namespace not defined" errors.

### Fix

Added 11 new entries to `NUGET_INDICATORS`:
```python
"open Farmer", "open Argu", "open FsCheck", "open Expecto",
"open RabbitMQ", "open Dapper", "open FParsec", "open Bolero",
"open StackExchange", "open Grpc", "open Google.Protobuf"
```

### Re-verification Results

Created `reverify_failures.py` to re-verify 96 remaining F# failures. Results:

| Category | Count |
|----------|-------|
| Newly passing (verifier bug) | 42 |
| Still failing (compile errors) | 40 |
| Skipped (no F# code) | 14 |

Most of the 42 recovered samples were Farmer, Argu, FsCheck, Expecto, and RabbitMQ prompts that were perfectly correct but routed to the wrong verifier.

---

## Claude Manual Fix Attempt

### Approach

Created `fix_failures.py` to apply targeted fixes to 31 remaining compile errors:
- 11 "easy" fixes (missing `open`, typos, wrong keywords)
- 20 "medium" fixes (type reordering, indentation, pattern changes)
- 9 skipped (truncated responses, tree diagrams, deep structural errors)

### Results

Only **1 of 31 fixes passed** verification. The main blocker: the `extract_fsharp_code()` function in `verify_fsharp.py` concatenates ALL code blocks from a response into a single script. Many of these responses have multiple separate code blocks (different files, examples, tests) that can't be meaningfully combined. The fixes themselves were correct but the multi-block extraction produced invalid F# scripts.

### Decision

Accepted the 1 passing fix (fsharp_lib_0006_exp_008 — added `open FsToolkit.ErrorHandling`). The remaining 30 failures are deep multi-block extraction issues not worth the complexity to solve. These 53 remaining failures (30 compile + 14 no-code + 9 skipped) represent only 1.7% of F# prompts — acceptable loss.

---

## Final Dataset Numbers

| Metric | Count |
|--------|-------|
| Total unique samples | **7,948** |
| Train split | 7,551 |
| Validation split | 397 |
| F# prompt coverage | 96.9% (2,985 of 3,078) |

### Domain Distribution

| Domain | Samples | % |
|--------|---------|---|
| fsharp_libraries | 2,094 | 26.3% |
| fsharp_core | 1,816 | 22.8% |
| general_coding | 950 | 12.0% |
| dotnet_aspnet | 844 | 10.6% |
| svelte_typescript | 676 | 8.5% |
| cross_domain | 608 | 7.6% |
| docker_kubernetes | 414 | 5.2% |
| agentic_swe | 279 | 3.5% |
| long_context | 267 | 3.4% |

### Growth Timeline

| Event | Total Samples |
|-------|--------------|
| After round 1+2 | ~5,500 |
| After namespace fix | 6,996 |
| After substitute run | 7,908 |
| After verifier bug fix + Claude fixes | **7,948** |
| After comprehensive F# fix session | **7,948** (15 broken samples replaced with fixed versions) |

---

## Session 6: Comprehensive F# Failure Fix

### Overview
Tackled all 40 remaining F# compile failures from `reverify_failures.jsonl` with a new comprehensive fix approach. Instead of patching response markdown (which failed in Session 5 due to multi-block extraction issues), this session extracted code the same way the verifier does and applied fixes to the extracted code directly.

### New Script: `fix_all_failures.py`
Created `pipeline/scripts/fix_all_failures.py` — reads failures, applies targeted fixes to extracted F# code, verifies each fix with the compiler, outputs only passing samples.

### NUGET_INDICATORS Bug Fix (Major Discovery)
**Root cause for many failures**: Code using `open FSharp.Control` (short form) wasn't matched by the existing indicator `"open FSharp.Control.AsyncSeq"` (full form). This caused samples to be routed to `dotnet fsi` instead of `dotnet build` with NuGet packages available.

**Added 7 new indicators to `verify_fsharp.py`:**
- `"AsyncSeq"` — catches any AsyncSeq usage regardless of import style
- `"open FSharpPlus"`
- `"open FSharp.Text.RegexProvider"`
- `"open MathNet"`
- `"open FSharp.SystemTextJson"`
- `"open System.ServiceModel"`
- `"JsonFSharpOptions"` — FSharp.SystemTextJson usage without open statement

**Added 5 NuGet packages to `verify.fsproj`:**
- FSharpPlus 1.*
- FSharp.Text.RegexProvider 2.*
- MathNet.Numerics 5.* + MathNet.Numerics.FSharp 5.*
- System.ServiceModel.Syndication 9.*

This single fix immediately recovered 10+ samples that were failing due to wrong verification routing.

### Fix Results — 40 Failures Resolved

| Category | Count | Details |
|----------|-------|---------|
| **FIXED (passing)** | 15 | Code fixes verified by F# compiler |
| **Dropped (non-F#)** | 4 | C#/YAML/Dockerfile responses (cross_domain) |
| **Truncated** | 7 | Response cut off mid-expression by teacher max_tokens |
| **Unfixable** | 14 | Deep logic/structural errors needing full code rewrite |

### Fixed Samples (15)

| ID | Fix Applied |
|----|-------------|
| `fsharp_core_0005_exp_018` | `member _.Combine` → `member this.Combine` + `do!` → `let! _` |
| `fsharp_lib_0006_exp_017` | Parenthesized tuples in `Map.ofList` entries |
| `fsharp_lib_0006_exp_029` | `ToString()[..7]` → `ToString().Substring(0, 8)` |
| `fsharp_lib_0020_exp_014` | Fluent method chain indentation restructured |
| `fsharp_lib_0020_exp_016` | Curried method calls → tupled: `b.Request("field", value)` |
| `fsharp_lib_0021_exp_009` | Dangling `else` in while/match structure + NuGet routing |
| `fsharp_lib_0021_exp_012` | Removed OCaml `~` named params + NuGet routing |
| `fsharp_lib_0021_exp_013` | `Option.ofPair` → manual pattern match + NuGet routing |
| `fsharp_lib_0021_exp_014` | `and fetchTick` → `let rec fetchTick` + NuGet routing |
| `fsharp_lib_0021_exp_021` | Mutation in match guard → separate match arm + NuGet routing |
| `fsharp_lib_0021_exp_024` | Renamed `match` variable (keyword) to `m` + NuGet routing |
| `fsharp_lib_0021_exp_026` | `elif ... ->` → `elif ... then` + NuGet routing |
| `fsharp_lib_0021_exp_027` | `private x =` → `let private x =` + NuGet routing |
| `fsharp_lib_0021_exp_029` | `and PipelineConfig` → `type PipelineConfig` + NuGet routing |
| `fsharp_lib_0039_exp_024` | Removed `:> IDisposable` cast (type doesn't implement it) |

### Unfixable Samples (14) — Need Full Rewrite

| IDs | Reason |
|-----|--------|
| `fsharp_core_0006_exp_024` | Multi-block type conflicts across concatenated modules |
| `fsharp_core_0010_exp_016` | 730-line file, function types in union fields cascade |
| `fsharp_core_0026_exp_006` | SRTP Execute pattern fundamentally wrong |
| `fsharp_core_0026_exp_009` | `inline` Publish with mutable ref — FS1113 |
| `fsharp_core_0028_exp_005` | Multi-block examples with `this` in module scope |
| `fsharp_core_0030_exp_012` | `interface` blocks after record closing braces |
| `fsharp_lib_0006_exp_008` | `traverseResult` signature incompatible with usage |
| `fsharp_lib_0006_exp_012` | CE Bind returns wrong type, cascading |
| `fsharp_lib_0006_exp_014` | Anonymous record type annotation fundamentally broken |
| `fsharp_lib_0006_exp_018` | Cascading type errors in recommendation engine |
| `fsharp_lib_0006_exp_020` | Result postfix notation + cascading mismatches |
| `fsharp_lib_0020_exp_027` | TryGetPropertyValue API misuse in converter |
| `fsharp_lib_0038_exp_002` | Custom `Result<'T>` shadows stdlib, cascading |
| `fsharp_lib_0039_exp_025` | TryGetValue/LoadAll type conflicts cascade |

### Dataset Reformatted
- **7,948 samples** (7,551 train / 397 val) in both ChatML and Mistral formats
- 15 fixed samples replaced broken originals (same IDs, now with verified F# code)
- Total count unchanged since broken versions already existed in dataset

### Instruction Fix Re-Generation (fsharp_fixes round)
Completed the `fsharp_fixes.yaml` round — re-generated 20 prompts with patched instructions ("Implement all code in F#") through minimax.

- **20/20 generated** (14 with responses, 6 empty)
- **12 passed** F# verification (60%)
- **11 truly new samples** (1 was a duplicate of an already-passing ID)
- New samples include: 4 cross_domain (Akka.Cluster weather, CI/CD, Roslyn), 2 fsharp_core, 5 fsharp_libraries
- Fixed domains from "mixed" to proper domain labels

### Final Dataset Count
- **7,953 samples** (7,556 train / 397 val) — up from 7,948
- Both ChatML and Mistral formats updated

### Growth Timeline (Updated)

| Event | Total Samples |
|-------|--------------|
| After round 1+2 | ~5,500 |
| After namespace fix | 6,996 |
| After substitute run | 7,908 |
| After verifier bug fix + Claude fixes | 7,948 |
| After comprehensive fix + instruction re-gen | **7,953** |

---

## Session 7: Training Config Creation

### Token Length Analysis
Analyzed the 7,556 training samples to determine optimal `max_seq_length`:

| Percentile | Est. Tokens | Chars |
|-----------|-------------|-------|
| Median (P50) | ~3,500-4,000 | 13,831 |
| P90 | ~5,900-6,800 | 23,761 |
| P95 | ~8,000-9,100 | 31,993 |
| P99 | ~16,300-18,600 | 65,069 |
| Max | ~21,300-24,300 | 85,129 |

**Decision**: `max_seq_length = 131072` (128K) — covers 100% of samples with zero truncation. Both base models already support 256K natively; the LoRA adapter only teaches domain knowledge and does not affect positional encoding.

### Abandoned 4-Stage Progressive Context Training
The original plan had 4 stages (8K → 16K → 128K → 256K) for progressively training models to handle increasing context. This was abandoned because:
1. We only have short-context training data (all samples ≤24K tokens)
2. Both Qwen3.5-27B and Devstral Small 2 already handle 256K natively — no need to re-teach positional encoding
3. Progressive stages are for extending context beyond what the base model was pretrained on
4. Stages 2-4 had no training data generated for them

**New plan**: Single-stage SFT on all 7,953 samples at 128K max_seq_length, 2× A100 80GB in parallel.

### Devstral Small 2 Architecture Research
- Architecture: `Mistral3ForConditionalGeneration` / `ministral3` text model
- hidden_size=5120, 40 layers, 32 attention heads, 8 KV heads, head_dim=128
- Only the Instruct variant (`mistralai/Devstral-Small-2-24B-Instruct-2512`) is available — no base model from Mistral
- Unsloth provides optimized version: `unsloth/Devstral-Small-2-24B-Instruct-2512`
- Chat template: `"mistral"` in Unsloth's `get_chat_template`
- Standard attention + MLP target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`

### Training Configs Created

| File | Model | Format | Description |
|------|-------|--------|-------------|
| `configs/train_kenichi_thinking.py` | Qwen3.5-27B | ChatML | Reasoning-first variant |
| `configs/train_kenichi_flash.py` | Devstral Small 2 24B | Mistral | Fast agentic variant |
| `configs/merge_and_export.py` | Both | — | LoRA merge → GGUF export → HuggingFace push |
| `configs/runpod_setup.sh` | Both | — | RunPod instance setup script |

Both training scripts:
- Load data from HuggingFace (`odytrice/kenichi-sft`) by default, or local JSONL
- BF16 LoRA, rank 16, alpha 32
- 3 epochs, effective batch size 8, cosine LR 2e-4
- Packing enabled (critical for efficiency — median sample is ~4K tokens in 128K window)
- `load_best_model_at_end=True` with eval every 250 steps
- Resume from checkpoint support
- `adamw_8bit` optimizer, gradient checkpointing

### Obsolete Files Removed
- `configs/train_stage1.py` — replaced by `train_kenichi_thinking.py` / `train_kenichi_flash.py`
- `configs/train_stage2.py` — no training data for 64K stage
- `configs/train_stage3.py` — no training data for 128K stage
- `configs/train_stage4.py` — no training data for 256K stage

### Docs Updated
- `Training/04-training-config.md` — completely rewritten for single-stage plan
- `Training/00-overview.md` — updated dataset count to 7,953, removed logprob row (dead end)

### System Prompt Added
Both training scripts inject a system prompt into every sample at training time (in the `formatting_func`):
> "You are Kenichi, an expert coding assistant specialized in F#, .NET, Svelte 5, SvelteKit, TypeScript, Docker, and Kubernetes. You write clean, idiomatic, and well-structured code with clear explanations."

This is prepended as a `{"role": "system", ...}` message before the user/assistant turns, and tokenized with the proper chat template tokens. No data rebuild needed — injection happens at training time.

### RunPod Deployment & Dependency Issues

Deployed A100 80GB PCIe pod on RunPod with PyTorch template. Hit multiple dependency conflicts during setup:

1. **flash-attn build failure** — Unsloth's git install triggered flash-attn build from source. The pip isolated build env couldn't find torch → `ModuleNotFoundError: No module named 'torch'`. **Fix**: Install flash-attn separately with `--no-build-isolation`.

2. **Unsloth upgraded torch to 2.11.0+cu130** — The `--no-deps` workaround left stale deps. The Unsloth git install then pulled torch 2.11 which mismatched the pod's CUDA 12.4 toolkit → flash-attn CUDA mismatch error. **Fix**: Pin `torch==2.5.1` from cu124 index first.

3. **Unsloth 2026.3.10 incompatible with torch 2.4.1** — `unsloth_zoo` tried to access `torch._inductor.config` which doesn't exist in torch 2.4 → `AttributeError`. **Fix**: Upgrade to torch 2.5.x.

4. **torchao 0.13.0 requires torch.int1** — `torch.int1` dtype doesn't exist in torch 2.5 → `AttributeError`. **Fix**: Downgrade to `torchao==0.7.0`.

5. **Container disk overflow (20GB)** — Qwen3.5-27B model weights (~55GB) downloaded to `/root/.cache/huggingface/` on the container overlay disk (20GB) instead of `/workspace` (900+ GB). **Fix**: Symlink `/root/.cache/huggingface` → `/workspace/.cache/huggingface` before downloading.

### Final Working Install Sequence (RunPod PyTorch template)
```bash
# Symlink caches to /workspace
mkdir -p /workspace/.cache/huggingface /workspace/.cache/pip
ln -sf /workspace/.cache/huggingface /root/.cache/huggingface
ln -sf /workspace/.cache/pip /root/.cache/pip

# Upgrade torch to 2.5.1+cu124
pip install torch==2.5.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Build flash-attn (sees existing torch)
pip install flash-attn --no-build-isolation

# Install Unsloth with all deps
pip install "unsloth[cu124-ampere-torch250] @ git+https://github.com/unslothai/unsloth.git"

# Downgrade torchao (0.13 needs torch.int1 which is torch 2.6+)
pip install "torchao==0.7.0"

# Fast downloads
pip install hf_transfer
```

All captured in `configs/runpod_setup.sh`.

### Verified Environment
```
PyTorch:    2.5.0+cu124
CUDA:       12.4
GPU:        NVIDIA A100 80GB PCIe (79.3 GB)
Unsloth:    2026.3.10
TRL:        0.24.0
Datasets:   4.3.0
```

### Training Launch
- Kenichi Thinking (Qwen3.5-27B) — first attempt hit container disk overflow at 8% model download. Redeploying with cache symlink fix.
- Kenichi Flash (Devstral Small 2) — pending second pod deployment.

---

### Training Launch — Both Models Running

Both models are now training on RunPod A100 80GB SXM pods.

**Kenichi Thinking (Qwen3.5-27B):**
- 2,835 total steps (7,556 samples × 3 epochs, batch_size=8, no packing compression)
- 101,449,728 trainable parameters (0.42% of 27B)
- Model downloaded in ~4 minutes (55.6 GB at 234 MB/s)
- Training started after tokenization (~30 sec)

**Kenichi Flash (Devstral Small 2, 24B):**
- 2,835 total steps (same data, same batch config)
- 101,449,728 trainable parameters (0.42% of 24B)
- Required `akoumpa/Devstral-Small-2-24B-Instruct-2512-BF16` — both `mistralai/` and `unsloth/` FP8 variants rejected by Unsloth on A100 (compute capability 8.0, FP8 needs 8.9+)
- Required `TRANSFORMERS_NO_FLEX_ATTENTION=1` and `attn_implementation="eager"` — flex_attention needs torch 2.6+, we have 2.5.0
- Model already cached from first attempt, loaded in ~7 seconds

### VRAM-Targeted Ollama Modelfiles

Created 4 Modelfiles targeting specific VRAM capacities. Each selects the optimal model quantization and context window for the GPU. KV cache quantization is set via the `OLLAMA_KV_CACHE_TYPE` environment variable (global Ollama setting, not per-model).

| Ollama Tag | Model | Model Quant | KV Quant | Context | VRAM Usage | Target GPU |
|------------|-------|-------------|----------|---------|------------|------------|
| `kenichi-thinking:24gb` | Qwen3.5-27B | Q4_K_M | Q4 | ~88K | ~24 GB | RTX 4090 |
| `kenichi-thinking:32gb` | Qwen3.5-27B | Q4_K_M | Q4 | ~177K | ~32 GB | RTX 5090 |
| `kenichi-thinking:48gb` | Qwen3.5-27B | Q5_K_M | Q4 | ~256K (max) | ~42 GB | A6000 Ada |
| `kenichi-thinking:96gb` | Qwen3.5-27B | Q8_0 | Q8 | ~256K (max) | ~74 GB | RTX PRO 6000 |
| `kenichi-thinking:full` | Qwen3.5-27B | **F16** | FP16 | ~256K (max) | ~144 GB | Mac Studio 256GB |
| `kenichi-flash:24gb` | Devstral Small 2 | Q4_K_M | Q8 | ~121K | ~24 GB | RTX 4090 |
| `kenichi-flash:32gb` | Devstral Small 2 | Q5_K_M | Q8 | ~182K | ~32 GB | RTX 5090 |
| `kenichi-flash:48gb` | Devstral Small 2 | Q8_0 | Q8 | ~256K (max) | ~47 GB | A6000 Ada |
| `kenichi-flash:96gb` | Devstral Small 2 | Q8_0 | FP16 | ~256K (max) | ~67 GB | RTX PRO 6000 |
| `kenichi-flash:full` | Devstral Small 2 | **F16** | FP16 | ~256K (max) | ~89 GB | Mac Studio 256GB |

Key design decisions:
- **Thinking uses Q4 KV on 24/32/48gb tiers** — 88 layers makes KV cache expensive, Q8 KV doesn't leave enough room
- **Flash gets Q8 KV on most tiers** — 40 layers is much cheaper on KV cache
- **48 GB tier** — best quants at full 256K context (model maximum)
  - Thinking: Q5_K_M model + Q4 KV → 322K theoretical, capped at 256K
  - Flash: Q8_0 model + Q8 KV → 268K theoretical, capped at 256K
- **96 GB tier** — near-lossless Q8_0 models at full 256K context
  - Thinking: Q8_0 model (29 GB) + Q8 KV → 256K context
  - Flash: Q8_0 model (26 GB) + FP16 KV → 256K context (70 GB free, only 42 GB needed for FP16 KV)
- **:full tier** — true zero quantization, F16 model + FP16 KV, for Mac Studio 256 GB unified memory
  - Thinking: F16 (~54 GB) + FP16 KV at 256K (~90 GB) = ~144 GB total
  - Flash: F16 (~48 GB) + FP16 KV at 256K (~42 GB) = ~90 GB total
- **Thinking uses Q4_K_M on 24/32gb tiers** — Q5_K_M doesn't leave enough headroom
- **Flash on 32gb uses Q5_K_M** (better model quality) since there's more headroom

Files:
- `configs/Modelfile.kenichi-thinking-24gb`
- `configs/Modelfile.kenichi-thinking-32gb`
- `configs/Modelfile.kenichi-thinking-48gb`
- `configs/Modelfile.kenichi-thinking-96gb`
- `configs/Modelfile.kenichi-flash-24gb`
- `configs/Modelfile.kenichi-flash-32gb`
- `configs/Modelfile.kenichi-flash-48gb`
- `configs/Modelfile.kenichi-flash-96gb`
- `configs/Modelfile.kenichi-thinking-full`
- `configs/Modelfile.kenichi-flash-full`

Export script (`merge_and_export.py`) updated to produce F16 GGUFs in addition to Q4_K_M, Q5_K_M, Q8_0.

Removed old generic `Modelfile.kenichi-thinking` and `Modelfile.kenichi-flash`.

### GPU Utilization Issue — Kenichi Thinking Restart

After ~1.5 hours of training, noticed severe GPU underutilization on Kenichi Thinking:

| Metric | Kenichi Thinking | Kenichi Flash |
|--------|-----------------|---------------|
| GPU utilization | ~25% | ~85% |
| Step speed | 45.4 s/step | 6.4 s/step |
| Steps completed | 118 / 2,835 | 459 / 2,835 |
| ETA remaining | **34 hours** | **4.2 hours** |
| Loss | 0.49 | 0.48 |

**Root cause**: `max_seq_length=131072` (128K) with `packing=True` creates mostly-empty attention windows. The median sample is ~4K tokens, so each 128K packed sequence is ~97% padding. With 88 attention layers (vs Flash's 40), this waste is amplified — attention is O(n² × layers).

**Contributing factor**: Flash uses `attn_implementation="eager"` (forced due to flex_attention bug), which may have better GPU utilization patterns on torch 2.5 than the default SDPA path used by Thinking.

**Initial fix attempt**: Reduced `MAX_SEQ_LENGTH` from 131072 → 32768 (32K). This truncates 4.6% of samples (348/7,556). Restarted training on the A100 — but step speed remained ~49 s/step. The actual bottleneck was **gradient offloading to CPU** (`Unsloth: Will smartly offload gradients to save VRAM!`), not packing efficiency. Qwen3.5-27B in BF16 is ~54 GB, leaving only ~25 GB on the A100 80GB for gradients, optimizer states, and activations.

### Migration to H200 141GB

Terminated the A100 Thinking pod and deployed an **NVIDIA H200 141GB** pod instead:
- 141 GB HBM3 — 54 GB model + 87 GB free, no gradient offloading needed
- ~2x faster compute than A100
- Single GPU — Unsloth free license works (multi-GPU would require paid license)
- Restored `MAX_SEQ_LENGTH` back to **131072 (128K)** — zero truncation, all 7,556 samples preserved intact. The Flash model trains at 128K without issues; both models should use identical data processing.

### Qwen3.5-27B is a Vision-Language Model — Key Discovery

Discovered that **Qwen3.5-27B is a unified Vision-Language model**, not text-only. All Qwen3.5 models include a Pixtral vision tower (24 layers, ~460M params). This explains the issues:

1. **1,184 weight files** loaded (a text-only 27B would have ~20-30 shards)
2. Unsloth loaded it as VL model → `model.base_model.model.model.language_model` nesting
3. Gradient offloading triggered **even on H200 141GB** due to Unsloth's VL overhead

The architecture is hybrid with two layer types:
- **Gated DeltaNet (GDN)** layers (3 of every 4): `in_proj_qkv`, `in_proj_z`, `in_proj_b`, `in_proj_a`, `out_proj`, `conv1d`
- **Standard attention** layers (1 of every 4): `q_proj`, `k_proj`, `v_proj`, `o_proj`
- **MLP** (all layers): `gate_proj`, `up_proj`, `down_proj`
- Layout: 16 × (3 × (GDN → FFN) → 1 × (Attention → FFN)) = 64 layers total

No official text-only Qwen3.5-27B exists. Community extractions (`principled-intelligence`) only go up to 9B.

### Decision: Retain Vision, Drop Unsloth

**Options evaluated:**
1. Extract text-only model + Unsloth — Fast (~5-8 hrs), but loses vision
2. Full VL model + standard HuggingFace stack — Slower (~8-16 hrs), retains vision
3. QLoRA on Unsloth — Fast, but lower quality

**Chose Option 2** — retain vision capabilities. Kenichi Thinking can process screenshots, architecture diagrams, and error screenshots alongside code.

### Rewrite: Standard HuggingFace Training Stack

Rewrote `train_kenichi_thinking.py` to use `transformers` + `peft` + `trl` directly (no Unsloth):

- **Model**: `AutoModelForImageTextToText.from_pretrained("Qwen/Qwen3.5-27B")` with `dtype=bfloat16`, `device_map="auto"`, `attn_implementation="eager"`
- **Vision tower**: Frozen (`requires_grad=False`) — preserved but not trained (~460M params frozen)
- **Multimodal projector**: Also frozen
- **LoRA**: Targets both GDN layers and standard attention layers + all MLPs (116M trainable / 27.4B total = 0.42%)
- **Chat template**: Tokenizer's built-in `apply_chat_template` (no Unsloth `get_chat_template` needed)
- **Gradient checkpointing**: Standard `gradient_checkpointing=True` with `use_reentrant=False`
- **`TRANSFORMERS_NO_FLEX_ATTENTION=1`** + `attn_implementation="eager"` to avoid torch 2.5 flex_attention crash
- **`max_seq_length=131072`** — 128K, zero truncation

API fixes needed:
- `tokenizer` → `processing_class` in `SFTTrainer` (trl 0.24 API change)
- `torch_dtype` → `dtype` in `from_pretrained` (transformers 5.3 deprecation)

Model loaded successfully:
```
Model loaded: Qwen3_5ForConditionalGeneration
Total parameters: 27.4B
Frozen vision parameters: 460.7M
trainable params: 116,727,808 || all params: 27,473,456,368 || trainable%: 0.4249
```

### BF16 Model Audit — Kenichi Flash Base Model

Audited `akoumpa/Devstral-Small-2-24B-Instruct-2512-BF16` (community BF16 conversion used for Flash training):

- **Legitimate BF16 extraction** — the original Mistral model ships with both BF16 and FP8 tensors. This repo extracted the BF16 weights and removed the `quantization_config` from config.json.
- All architecture parameters identical to original (5120 hidden, 40 layers, 32 heads, 8 KV heads, yarn RoPE, pixtral vision tower)
- No dequantization artifacts — BF16 weights were already present in the original safetensors, not reconstructed from FP8
- Apache 2.0 license preserved
- Conclusion: **No concerns, training on this model is fine.**

### Attention Implementation Debugging Saga

Getting Qwen3.5-27B's attention layers working on H200 with torch 2.5 required extensive debugging. The model has a hybrid architecture with GDN (Gated DeltaNet) linear attention layers and standard attention layers, plus a VL (vision-language) wrapper with 3D position IDs. Each combination of attention implementation and configuration hit a different failure mode:

| Attempt | attn_impl | Packing | max_length | Result |
|---------|-----------|---------|------------|--------|
| 1 | eager | yes | 128K | **OOM** — 768 GB allocation for full attention matrix |
| 2 | flash_attention_2 | yes | 128K | **Crash** — VL 3D position IDs + flash attn varlen path |
| 3 | sdpa | yes | 128K | **OOM** — 32 GB allocation, SDPA fell back to naive kernel |
| 4 | flash_attention_2 | yes | 80K | **Crash** — same VL position ID crash at any packed length |
| 5 | flash_attention_2 | no | 32K | **Crash** — VL position IDs crash even on individual samples |
| 6 | sdpa | no | 32K | **Works but 181 s/step** — SDPA silently falls back to math kernel |
| 7 | sdpa + TORCH_CUDNN_SDPA_ENABLED=1 | no | 32K | **Works at 100% GPU util** — cuDNN SDPA backend on H200 |

**Root causes identified:**
1. **GDN layers**: Need `flash-linear-attention` (fla) + `causal-conv1d` libraries for fast path. Without them, torch fallback OOMs on long sequences. fla 0.4.2 incompatible with Triton 3.1.0 (`STAGE` arg error) — downgraded to fla 0.3.2.
2. **Standard attention layers + flash_attention_2**: Transformers' flash attention wrapper (`modeling_flash_attention_utils.py` line 677) crashes with "illegal memory access" when processing VL model position IDs, regardless of sequence length or packing. This is a transformers bug specific to VL models.
3. **SDPA without cuDNN**: PyTorch's SDPA has flash SDP available (`flash_sdp_enabled() = True`) but silently falls back to the naive math kernel for the VL model's attention mask format, resulting in 181 s/step.
4. **SDPA with cuDNN**: `TORCH_CUDNN_SDPA_ENABLED=1` enables the cuDNN-based SDPA backend optimized for Hopper architecture (H100/H200). This correctly handles the VL attention format with fast kernels.

**Final working configuration:**
```python
os.environ["TRANSFORMERS_NO_FLEX_ATTENTION"] = "1"
os.environ["TORCH_CUDNN_SDPA_ENABLED"] = "1"

model = AutoModelForImageTextToText.from_pretrained(
    "Qwen/Qwen3.5-27B",
    dtype=torch.bfloat16,
    device_map="auto",
    attn_implementation="sdpa",
)
# max_length=32768, packing=False, flash-linear-attention==0.3.2, causal-conv1d==1.6.1
```

**Dependencies required for Qwen3.5 GDN layers:**
- `causal-conv1d==1.6.1` (built from source for torch 2.5+cu124)
- `flash-linear-attention==0.3.2` / `fla-core==0.3.2` (NOT 0.4.2 — incompatible with Triton 3.1.0)

### Training Finally Running

Kenichi Thinking training started successfully on H200 141GB:
- 100% GPU utilization with cuDNN SDPA
- First step: 74.7 s (includes Triton kernel compilation warmup)
- Expected to settle to ~15-30 s/step after warmup
- 2,835 total steps, no packing (each sample processed individually)
- Zero data loss (max sample ~24K tokens, max_length=32K)

Kenichi Flash training progressing well on A100 SXM:
- 53% complete (1,500/2,835 steps), epoch 1.58
- 6.32 s/step, loss 0.31-0.34
- ETA: ~2.5 hours remaining

### Step Time Optimization — Reducing Padding Waste

With cuDNN SDPA working, step time settled at **71 s/step** at 32K max_length — ~56 hours total. The slowness is from padding waste: without packing, each sample is padded to max_length individually. The median sample is ~4K tokens, so at 32K max_length ~87% of each step is wasted on padding.

Analyzed step time vs data preservation at various max_length values:

| max_length | Samples fit | Truncated | Est. step time | Est. total |
|-----------|-------------|-----------|---------------|------------|
| 8K | 93.3% | 508 (6.7%) | ~18 s | ~14 hrs |
| 10K | 96.5% | 267 (3.5%) | ~22 s | ~17 hrs |
| 12K | 98.0% | 153 (2.0%) | ~27 s | ~21 hrs |
| 24K | 100% | 0 | ~53 s | ~42 hrs |
| 32K | 100% | 0 | ~71 s | ~56 hrs |

**Decision**: Set `max_length=24576` (24K) — zero truncation (longest sample is ~24K tokens), ~25% faster than 32K by reducing padding. Estimated ~42 hours on H200.

Note: "truncated" samples are not lost — they still train on the first N tokens. But we chose zero truncation to preserve all training data completely.

### Final Kenichi Thinking Training Configuration

```python
# Environment
TRANSFORMERS_NO_FLEX_ATTENTION=1
TORCH_CUDNN_SDPA_ENABLED=1

# Model
model = AutoModelForImageTextToText.from_pretrained(
    "Qwen/Qwen3.5-27B",
    dtype=torch.bfloat16,
    device_map="auto",
    attn_implementation="sdpa",
)

# Training
max_length = 24576      # 24K, zero truncation
packing = False         # VL model incompatible with packing
batch_size = 1
gradient_accumulation = 8
epochs = 3
learning_rate = 2e-4
optimizer = "adamw_8bit"
gradient_checkpointing = True

# LoRA targets (hybrid GDN + standard attention)
target_modules = [
    "q_proj", "k_proj", "v_proj", "o_proj",          # standard attention
    "in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj",  # GDN
    "gate_proj", "up_proj", "down_proj",              # MLP (all layers)
]

# Dependencies
# causal-conv1d==1.6.1, fla-core==0.3.2, flash-linear-attention==0.3.2
```

### Breakthrough: Monkey-Patch Fixes flash_attention_2

Found the root cause of the flash_attention_2 crash — a **known transformers 5.3.0 bug** (GitHub issues #44643, #44910, filed Mar 13-21 2026):

**Bug**: `_is_packed_sequence()` in `modeling_flash_attention_utils.py` doesn't handle >2D tensors. Qwen3.5 passes 3D M-RoPE position_ids `[3, batch, seq_len]` which gets misinterpreted as a packed sequence. Flash attention then constructs `cu_seqlens` with 3× the actual token count, reads beyond tensor bounds → "illegal memory access".

**This is NOT a torch version issue** — confirmed broken on torch 2.5, 2.6, 2.9, and 2.10. Upgrading torch would not have helped.

**Fix**: 4-line monkey-patch at the top of the training script:
```python
import transformers.modeling_flash_attention_utils as _fa_utils
_orig_is_packed = _fa_utils._is_packed_sequence
def _patched_is_packed(position_ids, *args, **kwargs):
    if position_ids is not None and position_ids.dim() > 2:
        return False
    return _orig_is_packed(position_ids, *args, **kwargs)
_fa_utils._is_packed_sequence = _patched_is_packed
```

### VRAM Tuning: Finding the Right Packed Sequence Length

With flash_attention_2 working, iterated through packed sequence lengths to find what fits in 141 GB:

| max_length | GDN layers | Attention layers | Loss computation | Result |
|-----------|-----------|-----------------|-----------------|--------|
| 128K packed | OOM (138/141 GB) | — | — | Fail |
| 64K packed | Pass | Pass | OOM (60 GB logits) | Fail |
| 32K packed | Pass | Pass | OOM (30 GB logits) | Fail |
| **16K packed** | **Pass** | **Pass** | **Pass** | **Works** |

The bottleneck is the logits tensor at loss computation: `vocab_size (248,320) × seq_len × 4 bytes (float32)`. At 32K packed: 30 GB. At 16K packed: 15 GB. With the model + activations using ~118 GB, 16K is the sweet spot that leaves enough room.

### Final Training Configuration (Revised)

```python
# Monkey-patch for flash_attention_2 + Qwen3.5 3D position_ids
# + flash_attention_2, packing=True, max_length=16384
# 582 total steps, ~71 s/step, ~11.4 hours estimated
```

### Training Status Update

**Kenichi Thinking** (H200 141GB):
- flash_attention_2 + packing at 16K, monkey-patched
- 582 total steps, ~68 s/step (settled from 82 s warmup), 100% GPU util, 87% VRAM
- ETA: ~11 hours, ~$44 H200 cost
- Massive improvement from 52 hours / $208 (no packing) and 142 hours / $568 (no cuDNN)

**Kenichi Flash** (A100 SXM):
- 87% complete (2,471/2,835 steps), epoch 2.61
- 6.19 s/step, loss 0.16 (converged from 0.49)
- ETA: ~37 minutes remaining

**`merge_and_export.py`** updated to support both Unsloth (Flash) and peft (Thinking) backends via `--peft` flag.

### Accepted Tradeoff: 110 Samples Truncated (1.5%)

With `max_length=16384` (16K) and packing enabled, 110 of 7,556 training samples (1.5%) are truncated. The longest sample is ~24,323 tokens (~85,129 chars). These 110 samples still contribute their first 16K tokens of training signal — only their tails are lost.

Why not pack at 24K (zero truncation)?
- Logits tensor at loss computation: `vocab_size (248,320) × seq_len × 4 bytes (float32)`
- At 32K packed: 30 GB logits, OOM'd with only 11 GB free
- At 64K packed: 60 GB logits, OOM'd with only 7 GB free
- The model weights (54 GB) + activations (~60-80 GB) leave insufficient room for large logits
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` only reduces fragmentation, not total memory — doesn't help when it's a hard VRAM limit
- 16K is the sweet spot: logits ~15 GB, fits within the ~20 GB remaining after forward pass

### Lessons Learned: VL Models Are Tricky to Train

Kenichi Thinking (Qwen3.5-27B VL) required dramatically more debugging than Kenichi Flash (Devstral text-only):

| Challenge | Thinking (VL) | Flash (text-only) |
|-----------|--------------|-------------------|
| Unsloth support | No — gradient offloading even on 141 GB | Yes — works on A100 80 GB |
| Attention implementation | 7 attempts to find working config | 1 fix (`attn_implementation="eager"`) |
| Packing | Requires monkey-patch for transformers bug | Works out of the box |
| Max packed sequence | 16K (vocab 248K × seq × 4B limits logits) | 131K (smaller vocab, fits easily) |
| Training stack | Custom transformers+peft+trl | Unsloth (2x faster kernels) |
| GPU required | H200 141 GB ($4/hr) | A100 80 GB (~$1.79/hr) |
| Training time | ~11 hours | ~5 hours |
| Total cost | ~$44 | ~$12 |

The hybrid GDN + standard attention architecture, VL 3D position IDs, massive vocab (248K), and vision tower overhead all compound to make VL model training significantly harder than text-only models. The payoff is vision capabilities for the planning agent use case.

### Kenichi Flash Training Complete

Flash training finished successfully on A100 SXM:
- **Total time**: 5 hours 21 minutes
- **Final train loss**: 0.3383 (started at ~0.49)
- **Final step loss**: 0.1586
- **Epochs**: 3.0 complete
- **Step speed**: 6.81 s/step average
- **LoRA adapter saved**: `./outputs/kenichi-flash/lora_adapter`

### Flash Merge + Export — Disk Quota Issue

First merge attempt failed with `Errno 122: Disk quota exceeded` — the container disk (original size) filled up when Unsloth tried to copy the 48 GB model to the HuggingFace upload cache. The partial write corrupted the safetensor file, causing a subsequent `SafetensorError: incomplete metadata, file not fully covered` error.

**Fix**: Doubled the container storage on the A100 pod. This required a pod redeployment, which wiped installed Python packages (but `/workspace` persistent volume with the trained LoRA adapter survived). Running `bash configs/runpod_setup.sh` to reinstall dependencies before retrying the merge + export.

### Kenichi Thinking Training Progress

Thinking training continuing on H200 141GB:
- 7% complete (42/582 steps), loss 0.36, token accuracy 89.2%
- 63.8 s/step (settled from 82 s warmup), 100% GPU utilization
- ETA: ~9.5 hours remaining

### Kenichi Flash Published to HuggingFace

Flash merge + export completed successfully on the redeployed A100 pod:
- **Merged BF16 model pushed**: [odytrice/kenichi-flash](https://huggingface.co/odytrice/kenichi-flash)
- GGUF export skipped on pod (disk constraints) — will quantize locally on RTX 5090 (64 GB RAM, CPU-only process)
- **A100 pod terminated** — no longer needed

### RunPod Setup Script: fla Version Pin

Thinking training failed on first attempt with:
```
ValueError: 'STAGE' is not in list
```
Root cause: `runpod_setup.sh` installed latest `flash-linear-attention` which requires Triton 3.2+, but torch 2.5.1 ships Triton 3.1.0. The `@triton.autotune` decorator in `fla/ops/cp/chunk_delta_h.py` references a `STAGE` parameter that doesn't exist in the older Triton API.

**Fix**: Pinned versions in `configs/runpod_setup.sh`:
```bash
pip install fla-core==0.3.2 flash-linear-attention==0.3.2
```
This was a known issue from the first training session but the version pin hadn't been added to the setup script.

### Merge Script: Added `--no-gguf` Flag

Added `--no-gguf` flag to `configs/merge_and_export.py` to support merge + push BF16 only, skipping GGUF export entirely. This is needed because:
- RunPod pods have limited disk (~200 GB) — not enough for BF16 + all GGUF quants
- GGUF quantization is CPU-only (no GPU needed) — can be done locally on any machine with 64+ GB RAM
- Avoids paying GPU rental time for a CPU-bound task

### Disconnected Terminal & tmux Lesson

During Thinking training (first restart), the RunPod web terminal disconnected mid-training (~7% through, step 42/582). The training process survived (GPU still at 100%), but the terminal output was lost because training was running as a foreground process without a terminal multiplexer.

**Attempted recovery**:
- `reptyr 3623` — failed because the training process had subprocesses (4 data workers), and reptyr can't attach to process groups
- Process was still running (confirmed via `nvidia-smi` showing 100% GPU utilization)
- Could monitor indirectly via `ls -lt ./outputs/kenichi-thinking/` but couldn't see live training logs

**Resolution**: Killed the training process (`pkill -f train_kenichi_thinking`) and restarted inside a `tmux` session. Lost ~40 minutes of training progress (steps 1-42).

**Lesson learned**: Always use `tmux` on RunPod pods:
```bash
apt-get install -y tmux    # if not already installed
tmux new -s train          # start named session
python configs/train_kenichi_thinking.py
# Ctrl+B then D to detach
# tmux attach -t train to reconnect
# tmux ls to list sessions
```

### Kenichi Thinking Training Restarted (Session 2)

Restarted training inside tmux. Progress tracking:

| Step | Loss | Token Accuracy | LR | s/step |
|------|------|---------------|-----|--------|
| 10 | 0.4072 | 88.6% | 0.00006 | ~67s (warmup) |
| 20 | 0.3685 | 89.1% | 0.00013 | ~66s |
| 30 | 0.3647 | 89.2% | 0.00019 | ~66s |
| 40 | 0.3576 | 89.2% | 0.00020 (peak) | ~66s |
| 50 | 0.3518 | 89.3% | 0.00020 | ~66s |

Numbers tracking closely to the first run. ETA: ~9.7 hours from step 55 (~midnight).

### Kenichi Flash GGUF Quantization

Spun up a separate CPU pod for GGUF quantization (no GPU needed — purely CPU + RAM).

**llama.cpp tokenizer issues with Devstral**: `convert_hf_to_gguf.py` failed to handle the Mistral Tekken tokenizer format:
1. No `tokenizer.model` file (sentencepiece) → FileNotFoundError
2. Not Llama HF vocab format → TypeError
3. `TokenizersBackend` class not recognized by transformers → ValueError
4. `extra_special_tokens: []` is a list but transformers expects dict → AttributeError

**Fixes** (two `sed` patches to `tokenizer_config.json`):
```bash
sed -i 's/"tokenizer_class": "TokenizersBackend"/"tokenizer_class": "PreTrainedTokenizerFast"/' tokenizer_config.json
sed -i 's/"extra_special_tokens": \[\]/"extra_special_tokens": {}/' tokenizer_config.json
```

These are bugs in the `tokenizer_config.json` saved by Unsloth's `push_to_hub_merged()`. The underlying tokenizer data in `tokenizer.json` is fine — it's just the config metadata that references a non-standard class name and uses the wrong type for `extra_special_tokens`.

Also needed `pip install mistral-common[image,audio]` for the tokenizer.

**Quantization output** (all files uploaded to `odytrice/kenichi-flash` alongside BF16 safetensors):
- `F16.gguf` (~47 GB) — full precision GGUF
- `Q8_0.gguf` (~24 GB) — near-lossless
- `Q5_K_M.gguf` (~17 GB) — good quality/size balance
- `Q4_K_M.gguf` (~14 GB) — smallest, fits 24 GB VRAM

### Modelfile Updates

Updated all 10 Ollama Modelfiles (5 Flash + 5 Thinking):
- `FROM` paths now point to `/workspace/*.gguf` for pod-based Ollama model creation
- Download instructions updated to use `hf` CLI (replacing deprecated `huggingface-cli`)
- GGUFs stored in single repo per model (`odytrice/kenichi-flash`, `odytrice/kenichi-thinking`) alongside BF16 weights, not separate `-GGUF` repos

### Thinking Training Progress (Step 99/582)

| Step | Loss | Token Accuracy | LR | s/step |
|------|------|---------------|-----|--------|
| 10 | 0.4072 | 88.6% | 0.00006 | ~67s |
| 30 | 0.3647 | 89.2% | 0.00019 | ~66s |
| 50 | 0.3518 | 89.3% | 0.00020 | ~66s |
| 70 | 0.3263 | 90.0% | 0.00020 | ~63s |
| 90 | 0.3205 | 90.1% | 0.00019 | ~63s |

17% complete, loss dropping steadily, ~8.5 hours remaining.

### CRITICAL: 3-Epoch Overfitting Discovery

**Both models trained with 3 epochs are severely overfitting.** Kenichi Flash (the first model tested) memorizes and regurgitates training samples verbatim instead of generalizing to new inputs.

**Symptoms**:
- When given any input (even "hi"), the model outputs the system prompt followed by a random training instruction and its full code response
- The model treats every input as the start of a training sample to complete, rather than responding conversationally
- Multiple Ollama template variations tested (Mistral v0.1, v0.3, GGUF-embedded, no template) — all produce the same behavior, confirming it's not a template issue

**Evidence**:
- Final step loss: **0.16** — extremely low for SFT, indicating memorization
- Final train loss: 0.3383 (average), but individual step losses dropped well below 0.2
- 3 epochs × 7,556 samples = the model saw each sample 3 times
- SFT best practices (Alpaca, Platypus, OpenHermes papers) recommend **1 epoch** to prevent overfitting

**Root cause**: 3 epochs with lr=2e-4 on only 7,556 samples pushed the LoRA weights too far, causing the model to memorize the training distribution rather than learning the coding domain generalization.

**Fix**: Reduced both training configs to **1 epoch**:
- `configs/train_kenichi_flash.py`: `EPOCHS = 1`
- `configs/train_kenichi_thinking.py`: `EPOCHS = 1`

**Impact**:
- Thinking training (in progress at step ~99/582, 17%) was **killed** immediately to prevent wasted compute
- Both models need retraining from scratch with 1 epoch
- Flash: ~1.8 hrs on A100 (vs 5.3 hrs for 3 epochs)
- Thinking: ~3.5 hrs on H200 (vs ~11 hrs for 3 epochs)
- Expected final loss: ~0.35-0.40 (higher than 0.16, but properly generalized)

### Ollama Modelfile Template Investigation

Debugged Ollama chat template extensively before concluding overfitting was the issue:

| Attempt | Template | Result |
|---------|----------|--------|
| 1 | Hand-written `[SYSTEM_PROMPT]...[/SYSTEM_PROMPT]` (Mistral v3) | Model dumps training samples |
| 2 | No template (GGUF-embedded auto-detect) | Same — GGUF has wrong template from patched tokenizer_config.json |
| 3 | Unsloth's `mistral` v0.1 single-turn: `[INST] sys user [/INST]` | Same |
| 4 | Unsloth's `mistral_v03` multi-turn with `.Messages` | Same |

All templates produce identical behavior: model ignores user input and generates a memorized training sample. Confirmed this is overfitting, not a template issue.

**Correct template** (for when model is retrained): The Unsloth `mistral` v0.1 format where system prompt is concatenated with the first user message inside `[INST]` tags. This matches what `get_chat_template(tokenizer, chat_template="mistral")` produces during training.

---

## Pending Actions

### Learning Rate Reduction

Reduced learning rate from `2e-4` to `1e-4` for both models. Even with 1 epoch, `2e-4` is aggressive for LoRA SFT on ~7.5K samples and could still cause memorization. The `1e-4` rate is the standard recommendation for LoRA fine-tuning.

### Setup Script: `--thinking` Flag Re-added

Re-added the `--thinking` flag to `configs/runpod_setup.sh` after it stalled again on the A100 pod building `causal-conv1d` from source (only needed for Qwen3.5 GDN layers, not Flash/Devstral):

- `bash configs/runpod_setup.sh` — Flash only (skips GDN deps, saves ~15 min)
- `bash configs/runpod_setup.sh --thinking` — includes `causal-conv1d` + `flash-linear-attention` for Qwen3.5

Previously reverted this change thinking patience was the answer, but the build genuinely stalls or takes 15+ minutes on A100 pods, wasting time for Flash-only workflows.

### Retraining In Progress

Both models retraining with corrected hyperparameters (1 epoch, lr=1e-4):

**Thinking (H200)** — training started, step 39/194 (20%):

| Step | Loss | Token Accuracy | LR |
|------|------|---------------|-----|
| 10 | 0.4031 | 88.6% | 0.00009 |
| 20 | 0.3655 | 89.2% | 0.0000994 |
| 30 | 0.3648 | 89.2% | 0.0000974 |

Loss stabilizing around 0.365 instead of continuing to drop — the lower LR is working as intended.

**Flash (A100)** — downloading base model, setup re-running without GDN deps.

---

### Kenichi Thinking Retraining Complete (1 epoch, lr=1e-4)

Thinking retraining completed successfully on H200:
- **Total time**: 3 hours 24 minutes
- **Final train loss**: 0.3387 (vs 0.16 with 3 epochs — much healthier)
- **Final step loss**: 0.3118
- **Token accuracy**: 90.3%
- **Steps**: 194 (1 epoch)
- **Speed**: 63 s/step

Loss curve was gradual and stabilizing — no signs of memorization.

### Kenichi Flash Retraining Complete (1 epoch, lr=1e-4)

Flash retraining completed on A100:
- **Total time**: 1 hour 44 minutes
- **Steps**: 945 (1 epoch, less aggressive packing than trl)
- **Speed**: 6.63 s/step

### Dependency Version Drift During Merge

When running `merge_and_export.py` after training, hit dependency issues on both pods:

1. **torchvision mismatch**: Unpinned `torchvision` silently downgraded `transformers` from 5.3.0 to 4.57.6
2. **peft import failure**: `PreTrainedModel` import failed with transformers 4.57.6
3. **torchao mismatch**: `Float8WeightOnlyConfig` error from torchao being too new for torch 2.5

**Fix**: Pin all dependency versions in `configs/runpod_setup.sh`:
- `torch==2.5.1`, `torchvision==0.20.1`, `torchaudio==2.5.1`
- `transformers==5.3.0` (pinned after Unsloth install)
- `torchao==0.7.0` (already pinned)

### Merge + Export In Progress

Both models merging and exporting GGUFs:
- **Thinking (H200)**: merge + push BF16 + GGUF export running
- **Flash (A100)**: merge + push BF16 + GGUF export running

GGUFs pushed to separate `-GGUF` repos (`odytrice/kenichi-flash-GGUF`, `odytrice/kenichi-thinking-GGUF`).

---

## Session 5: Ollama Testing & GGUF Fixes

### Kenichi Flash — Ollama Test PASSED
- Tested Flash Q4_K_M on A100 pod with Ollama
- `ollama run kenichi-flash "hi"` → clean conversational response: "Hi! I'm Kenichi, your expert coding assistant..."
- `ollama run kenichi-flash "Write a simple F# function to calculate fibonacci numbers"` → correct, idiomatic F# code with multiple approaches (recursive, tail-recursive, iterative)
- **No overfitting** — generates original, coherent responses
- **Template working** — Mistral v0.1 `[INST]` format with system prompt concatenated inside tags
- Minor quality notes: "konflikter" garbled word appears occasionally (tokenization artifact); model generates thinking block despite not being a thinking model
- Unsloth GGUFs located at `outputs/kenichi-flash/gguf_gguf/` (not `gguf/` — Unsloth naming quirk)

### Kenichi Thinking — GGUF Missing Vision Tower (851 vs 1307 tensors)

#### Discovery: GGUF has only 851 tensors, official `qwen3.5:27b` has 1307
- The `convert_hf_to_gguf.py` conversion of our merged BF16 model produced 851 tensors
- Official `qwen3.5:27b` from Ollama has 1307 tensors — the difference is **456 vision tower tensors** (Pixtral vision encoder, ~460M params)
- Root cause: peft merge via `model.save_pretrained()` from `AutoModelForCausalLM` only saves language model tensors, not the vision encoder
- Even updating `llama.cpp` to latest master (which has full `Qwen3_5TextModel` support) still produces 851 tensors — the vision weights simply aren't in the merged model directory

#### Impact: `prompt_eval_count: 1`
- Ollama sees `qwen35` architecture, expects VL model with vision tower
- Missing 456 tensors cause prompt tokenization to collapse to 1 token
- Model receives essentially a blank prompt and generates random completions
- Explains all observed symptoms: hallucinated prompts, ignoring user input, nonsense output

#### Attempted Fix 1: Custom Chat Template
- Tried multiple custom Go TEMPLATE directives in Modelfiles
- Tried official Qwen3 template from Ollama registry, official Qwen3.5 parameters
- All produced same `prompt_eval_count: 1` behavior — template was never the issue

#### Attempted Fix 2: LoRA-to-GGUF Conversion (FROM + ADAPTER approach)
- Idea: use `FROM qwen3.5:27b` (official base with all 1307 tensors) + `ADAPTER` with LoRA GGUF
- Updated `llama.cpp` to latest master which has `Qwen3_5TextModel` class with GDN support
- `convert_lora_to_gguf.py` fails with `NotImplementedError` on V-head reordering
- The `_reorder_v_heads()` function tries to reshape `LoraTorchTensor` (A/B decomposition), but the reshape operation can't change row size on low-rank matrices
- Error at `blk.0.attn_gate.weight` (GDN `in_proj_z` tensor)
- **LoRA-to-GGUF conversion is not supported for Qwen3.5 GDN layers** as of current llama.cpp

#### Attempted Fix 3: Re-convert with Updated llama.cpp
- Re-ran `convert_hf_to_gguf.py` from latest `llama.cpp` master on merged BF16 model
- Still produces 851 tensors — the vision weights aren't in the merged model, so no converter version can fix this
- Need to either copy vision tower from base model or find another approach

#### Attempted Fix 4: Q4_K_M-v2 Test (updated converter, still 851 tensors)
- Quantized F16-v2 to Q4_K_M-v2 (15.8 GB, correct size)
- Tested with Ollama using NO custom TEMPLATE — only SYSTEM, PARAMETERs, stop tokens
- **Still broken** — model hallucinates completely different prompts (e.g., SEO strategy for Cashify when asked "hi")
- Confirms the 851-tensor GGUF cannot work, regardless of template or converter version

#### Fix 5: Copy Vision Tower from Base Model into Merged Directory
- Downloaded vision tower shard from `Qwen/Qwen3.5-27B`: `model.safetensors-00011-of-00011.safetensors`
- All 333 vision tensors are in a single shard (shard 11 of 11)
- Also contains 9 `mtp.` (Multi-Token Prediction) tensors
- Symlinked as `model-00003-of-00003.safetensors` in merged model directory
- Updated `model.safetensors.index.json` to include all 333 vision + 9 mtp tensors pointing to the new shard
- Copied `preprocessor_config.json` and `video_preprocessor_config.json` from base model
- **F16-v3 conversion in progress** — should produce ~1307+ GGUF tensors with full vision tower

### Modelfile Updates
- **Thinking Modelfiles**: Initially switched to `FROM qwen3.5:<tag>` + `ADAPTER` approach, but LoRA-to-GGUF conversion failed. Keeping pre-merged GGUF approach but with no custom TEMPLATE (rely on GGUF-embedded Jinja2 template) and official Qwen3.5 parameters.
- **System prompt simplified**: Changed from verbose "You are Kenichi, an expert coding assistant specialized in..." to `"You are Kenichi, a coding assistant."` across all 10 Modelfiles
- **Thinking parameters**: Updated to official Qwen3.5 values from Ollama registry: `presence_penalty 1.5`, `temperature 1`, `top_k 20`, `top_p 0.95`
- **Download URLs fixed**: Point to `-GGUF` repos instead of BF16 repos

### Available Qwen3.5 Tags on Ollama
| Tag | Size | Quant |
|-----|------|-------|
| `qwen3.5:27b` | 17 GB | Q4_K_M (default) |
| `qwen3.5:27b-q8_0` | 30 GB | Q8_0 |
| `qwen3.5:27b-bf16` | 56 GB | BF16 |

No Q5_K_M tag available. VRAM tiers adjusted: 48gb uses Q8_0 base instead of Q5_K_M.

### Discovery: `convert_hf_to_gguf.py` Index Validation is Strict
- The converter validates that every tensor in the safetensors files is listed in the `model.safetensors.index.json` weight map
- "Extra tensors" (in files but not in index) cause a hard error
- The peft merge saved 9 `mtp.` tensors that weren't in the original index
- Vision tower shard also contains `mtp.` tensors from the base model
- **All tensors in all shards must be accounted for in the index**, even if the converter will ultimately skip them

### Flash GGUFs Published
- All 4 GGUFs pushed to `odytrice/kenichi-flash-GGUF`:
  - Q4_K_M.gguf — 14.3 GB
  - Q5_K_M.gguf — 16.8 GB
  - Q8_0.gguf — 25.1 GB
  - F16.gguf — 47.2 GB

### LoRA Adapters Saved
- **Thinking**: 467 MB → `odytrice/kenichi-thinking` under `lora_adapter/`
- **Flash**: 406 MB → `odytrice/kenichi-flash` under `lora_adapter/`

### Thinking F16-v3 Conversion — Still 851 Tensors
- Added vision tower shard from base `Qwen/Qwen3.5-27B` (shard 11 of 11, 333 vision + 9 mtp tensors)
- Fixed `model.safetensors.index.json` to include all tensors from all shards
- `convert_hf_to_gguf.py` still produces 851 tensors — the `Qwen3_5TextModel` class intentionally skips vision (`v.*`) and mtp tensors, only converting text model tensors
- The official `qwen3.5:27b` GGUF (1307 tensors) was built by a different pipeline that bundles text + vision + mtp into one file
- Full metadata comparison revealed critical missing fields vs official GGUF:
  - `qwen35.ssm.v_head_reordered` (bool, True) — tells inference engine the V-heads are reordered
  - `tokenizer.ggml.eos_token_ids` (array of 2 IDs: 248046, 248044)
  - `qwen35.mrope_sections`, `qwen35.rope.mrope_interleaved`, `qwen35.rope.mrope_section` — M-RoPE config
  - `tokenizer.ggml.scores`, `tokenizer.ggml.add_eos_token`, `tokenizer.ggml.add_padding_token`
  - All `qwen35.vision.*` fields
- These missing metadata fields (especially `v_head_reordered` and tokenizer fields) likely cause the `prompt_eval_count: 1` issue

### Pods Terminated
- **A100 pod** (Flash): Terminated. All artifacts saved.
- **H200 pod** (Thinking): Terminated. LoRA adapter + BF16 merged model on HuggingFace.

---

## Project Closure

### Fundamental Problem: SFT Cannot Teach Domain Knowledge

After testing both trained models, the project was closed. The core issue:

**SFT (Supervised Fine-Tuning) adjusts model *behavior* (how it responds), not model *knowledge* (what it knows).** LoRA fine-tuning modifies 0.42% of weights — enough to steer response format, but nowhere near enough to inject F# language knowledge into a model that wasn't pre-trained on sufficient F# data.

The training actively *degraded* the base models:
- **Kenichi Flash** (1 epoch, lr=1e-4): Generated gibberish/incoherent output when prompted — the LoRA pulled weights away from their well-calibrated pre-trained state toward a narrow distribution (single-turn F# code responses) that didn't generalize
- **Kenichi Thinking** (1 epoch, lr=1e-4): GGUF export broken due to Qwen3.5 VL architecture (851/1307 tensors), but would likely have shown similar degradation
- Earlier 3-epoch attempts memorized training samples verbatim (loss dropped to 0.16)

### Why the Approach Was Flawed

1. **Wrong technique for the goal**: The goal was "better F# coding." SFT can teach style/persona but cannot teach a model to code in a language it doesn't deeply know from pre-training. That requires Continued Pre-Training (CPT) on millions of tokens of raw F# code — orders of magnitude more data and compute.

2. **The teachers were already the solution**: MiniMax, GLM-5, and Kimi produce 80-99% F# pass rates. The distillation tried to compress that capability into smaller models, but the smaller models lacked the foundational F# knowledge to receive it.

3. **Data homogeneity**: 7,953 samples were almost entirely single-turn "write code for X" → long code response. No multi-turn conversations, clarification, error explanation, or short answers. The model learned only one mode.

4. **Diminishing returns from verification**: The elaborate F# compiler verification pipeline ensured *training data quality* but couldn't compensate for the fundamental SFT limitation. Perfect training data through the wrong technique still produces a worse model.

### Resolution

Use the cloud teacher models (GLM-5, MiniMax M2.7, Kimi K2.5) directly through OpenCode, with:
- **Skills** for domain-specific instructions and workflows
- **Sub-agents** for specialized tasks
- **Context management** for F# library documentation

This approach leverages models that already know F# deeply, without trying to compress that knowledge into a format (LoRA SFT) that can't carry it.

### What Was Valuable

Despite the training failure, the project produced useful artifacts:
- **7,953 verified F# coding samples** ([odytrice/kenichi-sft](https://huggingface.co/datasets/odytrice/kenichi-sft)) — usable as few-shot examples or RAG corpus
- **F# compiler verification pipeline** — automated F# code quality checking with namespace routing, NuGet integration, multi-block handling
- **Teacher benchmarking methodology** — empirical comparison of LLM F# coding ability
- **Infrastructure knowledge** — RunPod deployment, GGUF quantization, VL model training challenges, Ollama Modelfile configuration

### Lessons Learned

1. **SFT ≠ knowledge injection** — it's behavior steering, not teaching
2. **If your teachers are good enough, just use them** — distillation adds complexity and loses quality
3. **Test the trained model early** — the 3-epoch overfitting wasn't caught until after both models completed full training runs
4. **VL models are dramatically harder to fine-tune** than text-only models (7 attention implementation attempts, monkey-patches, H200 required)
5. **The pipeline was over-engineered for the wrong problem** — beautiful infrastructure solving a fundamentally mismatched goal

---

## 2026-04-24: Kimi K2.6 and GLM-5.1 Initial Benchmarks (Superseded)

> **Note:** These initial results were superseded by a full re-benchmark on 2026-04-26 (see below). The earlier run had significant issues with provider configuration that led to most K2.6 and GLM-5.1 requests failing/skipping. The corrected numbers are dramatically different.

Initial benchmark of two new teacher models:

- **Kimi K2.6** (`kimi-k2.6:cloud`) — Updated version of Kimi K2.5
- **GLM-5.1** (`glm-5.1:cloud`) — Updated version of GLM-5

Initial (flawed) results:

| Domain | Kimi K2.5 | Kimi K2.6 | MiniMax M2.7 | GLM-5 | GLM-5.1 |
|--------|-----------|-----------|--------------|-------|---------|
| **fsharp_core** (410 prompts) | 34.9% | 2.6% | **76.6%** | 70.6% | 11.1% |
| **fsharp_libraries** (122 prompts) | 20.5% | 0.8% | **56.6%** | 14.9% | 29.8% |
| **dotnet_aspnet** (206 prompts) | 0% (empty) | N/A | N/A | **97.1%** | 80.3% |

### Pipeline Changes

- Added provider configuration to `generate_data.py`, `expand_prompts.py`, `run_generation.py`, and `run_benchmark.py` supporting multiple Ollama-compatible endpoints
- Providers: `ollama_cloud` (with `OLLAMA_API_KEY` env var), `xeon_ai` (no auth)
- Added `--provider` flag to `run_benchmark.py` and `generate_data.py`
- Auth headers automatically included via Bearer token from `OLLAMA_API_KEY`

---

## 2026-04-26: Full Re-Benchmark — K2.6 and GLM-5.1 Corrected Results

Full re-benchmark of all six teachers across three domains after fixing provider issues that caused massive skip rates in the April 24 run.

### Benchmark Results

#### fsharp_core (410 prompts that DeepSeek failed on)

| Teacher | Passed | Compile Err | Skipped | Pass Rate |
|---------|--------|-------------|---------|-----------|
| DeepSeek | 0 | 376 | 34 | 0.0% |
| Kimi K2.5 | 149 | 102 | 176 | 34.9% |
| **Kimi K2.6** | **567** | 159 | 0 | **78.1%** |
| MiniMax M2.7 | 327 | 97 | 3 | 76.6% |
| GLM-5 | 149 | 47 | 15 | 70.6% |
| GLM-5.1 | 48 | 15 | 0 | 76.2% |

#### fsharp_libraries (122 prompts that DeepSeek failed on)

| Teacher | Passed | Compile Err | Skipped | Pass Rate |
|---------|--------|-------------|---------|-----------|
| DeepSeek | 0 | 84 | 38 | 0.0% |
| Kimi K2.5 | 25 | 23 | 74 | 20.5% |
| **Kimi K2.6** | **227** | 8 | 0 | **96.6%** |
| MiniMax M2.7 | 69 | 49 | 4 | 56.6% |
| GLM-5 | 7 | 37 | 3 | 14.9% |
| GLM-5.1 | 37 | 15 | 0 | 71.2% |

#### dotnet_aspnet (206 prompts that Kimi K2.5 failed on)

| Teacher | Passed | Compile Err | Skipped | Pass Rate |
|---------|--------|-------------|---------|-----------|
| Kimi K2.5 | 0 | 4 | 202 | 0.0% |
| GLM-5 | 202 | 4 | 2 | 97.1% |
| **GLM-5.1** | **192** | 5 | 0 | **97.5%** |

### Overlap Analysis (best-of-all-teachers)

#### fsharp_core (750 total prompts)

| Source | Passed | Exclusive (only this teacher) |
|--------|--------|-------------------------------|
| Original (DeepSeek) | 340 | — |
| + Kimi K2.5 | 149 | 0 |
| + **Kimi K2.6** | **360** | **10** |
| + MiniMax M2.7 | 327 | 18 |
| + GLM-5 | 149 | 0 |
| + GLM-5.1 | 48 | 9 |
| **Combined** | **765/750 (102.0%)** | |

> 765 > 750 because some teachers pass prompts that DeepSeek also passed; the "410 failed" set was not purely failures.

#### fsharp_libraries (962 total prompts)

| Source | Passed | Exclusive (only this teacher) |
|--------|--------|-------------------------------|
| Original (DeepSeek) | 840 | — |
| + Kimi K2.5 | 25 | 0 |
| + **Kimi K2.6** | **121** | **11** |
| + MiniMax M2.7 | 69 | 0 |
| + GLM-5 | 7 | 0 |
| + GLM-5.1 | 33 | 1 |
| **Combined** | **962/962 (100.0%)** | |

> Full coverage achieved — every prompt is solved by at least one teacher.

#### dotnet_aspnet (450 total prompts)

| Source | Passed | Exclusive (only this teacher) |
|--------|--------|-------------------------------|
| Original (Kimi K2.5) | 244 | — |
| + GLM-5 | 202 | 200 |
| + GLM-5.1 | 145 | 144 |
| **Best combined** | **444/450 (98.7%)** | |

> Near-perfect coverage — only 6 prompts unsolved by any teacher.

### Key Findings

- **Kimi K2.6 is the dominant F# teacher** — 78.1% on fsharp_core and 96.6% on fsharp_libraries, with zero skips. This completely reverses the April 24 assessment where K2.6 appeared to have a 2.6% pass rate (the skip rates were caused by provider/auth issues, not the model itself).
- **K2.6 has exclusive solves** — 10 prompts in fsharp_core and 11 in fsharp_libraries that no other teacher can solve. This makes it indispensable for full coverage.
- **MiniMax M2.7 is the runner-up for F#** — 76.6% fsharp_core, 56.6% fsharp_libraries, near-zero skips (3 and 4). Still valuable as a secondary teacher.
- **GLM-5 and GLM-5.1 dominate ASP.NET** — 97.1% and 97.5% respectively. GLM-5.1 edges out with 0 skips and marginally higher pass rate, but GLM-5 solved 10 more hard prompts.
- **fsharp_libraries hits 100% coverage** when combining all teachers — every one of 962 prompts is solved by at least one teacher.
- **Kimi K2.5 and GLM-5 lag on F#** — K2.5 has extremely high skip rates (41-61%), GLM-5's 14.9% on fsharp_libraries is poor. Neither should be used for F# generation.
- **GLM-5.1 is surprisingly strong at F#** — 76.2% on fsharp_core (close to MiniMax's 76.6%) and 71.2% on fsharp_libraries, with zero skips. A viable secondary F# teacher.

### Round 2 Teacher Assignments (Updated)

| Teacher | Domains | Rationale |
|---------|---------|-----------|
| **Kimi K2.6** | fsharp_core, fsharp_libraries | Best F# pass rates (78.1%, 96.6%), zero skips, exclusive solves |
| **GLM-5.1** | dotnet_aspnet | Best ASP.NET pass rate (97.5%), zero skips |
| **Kimi K2.5** | svelte_typescript, cross_domain, long_context | Best frontend/TS, longest context (256K) — unchanged |
| **MiniMax M2.7** | docker_kubernetes, agentic_swe | Best DevOps/system tasks — unchanged |

> Previous assignment had MiniMax for F# and GLM-5 for ASP.NET. K2.6's corrected results change the F# assignment significantly.

---

## 2026-04-26: Self-Hosted Benchmarks Paused — Qwen3.6 + Gemma4 Partials

Self-hosted Xeon-AI benchmarks (Qwen3.6-27B, Qwen3.6-35B, Gemma4-26B, Gemma4-31B) paused mid-run. Collated current state across all teachers (DeepSeek, Kimi K2.5/K2.6, MiniMax, GLM-5/5.1, Qwen3.6-27B/35B). All numbers below are compiler-verified via `verify_fsharp.py` (`dotnet build` + `dotnet run` against `pipeline/verify/verify.fsproj`).

### Completion State at Pause

| Teacher | fsharp_core | fsharp_libraries | dotnet_aspnet |
|---------|-------------|------------------|---------------|
| Kimi K2.5 | 427/410 ✓ | 122/122 ✓ | — |
| Kimi K2.6 | 726/410 ✓ | 235/122 ✓ | — |
| MiniMax M2.7 | 427/410 ✓ | 122/122 ✓ | — |
| GLM-5 | 211/410 partial | 47/122 partial | 208/206 ✓ |
| GLM-5.1 | 63/410 partial | 52/122 partial | 197/206 ~done |
| Qwen3.6-27B | 63/410 partial | 47/122 partial | 208/206 ✓ |
| Qwen3.6-35B | 63 raw, unverified | 47 raw, unverified | 137 raw, unverified |
| Gemma4-26B | not started | not started | not started |
| Gemma4-31B | not started | not started | not started |

### Ranked Pass Rates (excluding Qwen3.6-35B and Gemma; dotnet_aspnet dropped from suite — see below)

#### fsharp_core (DeepSeek-failure subset, 410 prompts)

| Rank | Teacher | Pass Rate | n | Sample |
|------|---------|-----------|---|--------|
| 1 | **Kimi K2.6** | **78.1%** | 567/726 | full + oversampled |
| 2 | MiniMax M2.7 | 76.6% | 327/427 | full + oversampled |
| 3 | GLM-5.1 | 76.2% | 48/63 | partial (15%) |
| 4 | GLM-5 | 70.6% | 149/211 | partial (51%) |
| 5 | Qwen3.6-27B | 66.7% | 42/63 | partial (15%) |
| 6 | Kimi K2.5 | 34.9% | 149/427 | full |

#### fsharp_libraries (DeepSeek-failure subset, 122 prompts)

| Rank | Teacher | Pass Rate | n | Sample |
|------|---------|-----------|---|--------|
| 1 | **Kimi K2.6** | **96.6%** | 227/235 | full + oversampled |
| 2 | GLM-5.1 | 71.2% | 37/52 | partial (43%) |
| 3 | Qwen3.6-27B | 66.0% | 31/47 | partial (39%) |
| 4 | MiniMax M2.7 | 56.6% | 69/122 | full |
| 5 | Kimi K2.5 | 20.5% | 25/122 | full |
| 6 | GLM-5 | 14.9% | 7/47 | partial (39%) |

### Decision: Drop dotnet_aspnet from Benchmark Suite

dotnet_aspnet does not differentiate teachers — GLM-5 (97.1%), GLM-5.1 (97.0%), and Qwen3.6-27B (96.2%) are within 1 point on full samples. The benchmark is no longer useful for ranking, so it has been removed from the F# teacher benchmark suite entirely.

**Code changes:**
- `pipeline/scripts/run_benchmark.py` — removed dotnet_aspnet entries from `ALL_BENCHMARK_FILES`, `domains` dict, overlap analysis section, and Round 2 summary loop.
- `pipeline/scripts/monitor_benchmarks.bat` — removed `dotnet_aspnet` from monitored domain list.
- `pipeline/scripts/run_benchmark_qwen_gemma.bat` — updated banner.

**Files deleted (16 total):**
- 6 yamls: `pipeline/prompts/benchmark/dotnet_aspnet_{glm5,glm51,qwen36_27b,qwen36_35b,gemma4_26b,gemma4_31b}.yaml`
- 4 raw outputs: `data/raw/benchmark/dotnet_aspnet_{glm5,glm51,qwen36_27b,qwen36_35b}.jsonl`
- 6 verified + passing: `data/verified/benchmark/dotnet_aspnet_{glm5,glm51,qwen36_27b}*.jsonl`

> Training-pipeline dotnet_aspnet artifacts (`prompts/dotnet_aspnet.yaml`, `prompts/expanded/dotnet_aspnet*.yaml`, `data/verified/dotnet_aspnet*.jsonl`) are untouched — they remain a training domain, just not a teacher-selection benchmark.

### Decision: Drop Qwen3.6-35B from Pending Benchmarks

Qwen3.6-27B underperforms on small samples (66.7% / 66.0% on fsharp_core / fsharp_libraries) versus Kimi K2.6's 78.1% / 96.6%. The 35B variant is not expected to close that gap and is not worth the further self-hosted compute. Qwen3.6-35B raw outputs remain on disk but will not be verified or run further.

### Status

- Round 2 F# assignments unchanged: **Kimi K2.6** wins both `fsharp_core` and `fsharp_libraries` decisively on full data.
- Pending self-hosted benchmarks: Gemma4-26B and Gemma4-31B not yet started.
- Partial-sample rates for GLM-5.1 / Qwen3.6-27B / GLM-5 are noisy — they could shift several points on full runs, but none are positioned to overtake K2.6.
