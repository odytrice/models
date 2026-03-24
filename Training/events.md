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

## Pending Actions

1. **Complete substitute teacher generation** (806 prompts in progress)
2. **Merge substitute results** into main dataset
3. **Republish** updated SFT dataset to HuggingFace
4. **Create training configs** for Kenichi Thinking (Qwen3.5) and Kenichi Flash (Devstral)
5. **Train both students** on cloud GPU
6. **Evaluate and compare** both variants
7. **Export** to GGUF/GPTQ for local inference
8. **Push models** to HuggingFace
