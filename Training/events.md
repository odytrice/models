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

## Remaining Issues

### 1. general_coding proportion still too high (42.5%)
- OpenCodeInstruct at 2,500 samples dominates the mix
- Plan: downsample to ~500

### 2. fsharp_core still below target (10.1% vs 15% target)
- Improved from 4.6% to 10.1% thanks to benchmark merge
- Round 2 with MiniMax should push this higher

### 3. No long-context samples
- All samples fit in stage1 (0-16K)
- Teachers not generating long enough responses

---

## Pending Actions (in order)

1. **Downsample OpenCodeInstruct** from 2,500 to ~500
2. **Update round 2 scripts** with new teacher assignments (MiniMax, Kimi, GLM-5)
3. **Run round 2** with temp 0.9
4. **Re-verify and reformat** combined round 1 + round 2 data
5. **Train Student 1** (Qwen3.5-27B) on cloud GPU (4-stage progressive LoRA)
6. **Train Student 2** (Devstral Small 2 24B) on same data
6. **Train** on cloud GPU (4-stage progressive LoRA)
