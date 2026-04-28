# Resolved & Open Questions

## Resolved

- [x] **Existing distillation datasets?** No. No K2.5, M2.7, or V3.2 distillation datasets exist on HuggingFace. Must generate own data.
- [x] **Moonshot API pricing?** Input $0.60/MTok, Output $3.00/MTok, Cache Hit $0.10/MTok.
- [x] **Text-only or multimodal?** Text-only is sufficient for this web dev coding use case.
- [x] **DPO needed?** Likely unnecessary. SFT on high-quality domain-specific distillation data should be enough.
- [x] **Single or multi-teacher?** Multi-teacher. Three teachers each assigned to their strongest domains.
- [x] **Which teacher for which domain?** K2.6 for F# (78.1% core, 96.6% libraries), GLM-5.1 for .NET/ASP.NET (97.5%), K2.5 for frontend/long-context, M2.7 for agentic/DevOps.
- [x] **MiniMax M2.7 availability?** Cloud-only via Ollama (`minimax-m2.7:cloud`) and MiniMax API. No open weights. Accessible via Ollama subscription.
- [x] **Latest model versions?** Confirmed: Kimi K2.5 (Jan 27, 2026), Kimi K2.6 (Apr 2026), MiniMax M2.7 (Mar 18, 2026), GLM-5 (Feb 2026), GLM-5.1 (Apr 2026), DeepSeek V3.2 (Dec 1, 2025).
- [x] **F# library-specific vs general F# language ratio?** ~20% of total F# training data should be library-specific (Giraffe, Akka.NET, FsToolkit, etc.), ~80% general F# language patterns. Libraries are important but the model needs strong core language fundamentals first -- idiomatic F# patterns, computation expressions, DU design, etc. Library-specific knowledge builds on top of that foundation.
- [x] **Fable for Svelte interop?** No. Unnecessary for this project. The Svelte frontend and F# backend communicate via HTTP APIs, not via Fable compilation. Removing Fable from training scope.
- [x] **How to evaluate F# code quality?** Two approaches: (1) Use the **F# compiler itself** (`dotnet fsi --check` and `dotnet build`) as a verification step during data generation to filter out non-compiling samples before they enter the training set. (2) Use [MultiPL-E](https://github.com/nuprl/MultiPL-E) for post-distillation evaluation -- write a custom `humaneval_to_fsharp.py` translator following their tutorial to get pass@k metrics. Supplement with manual evaluation on production-style F# tasks (Giraffe handlers, Akka.NET actors, FsToolkit pipelines).
- [x] **MiniMax M2.7 verbose output?** Use `temperature: 0.3-0.5` and explicit system prompts like "Be concise. Return only the code and a brief explanation." for training data generation. For agentic SWE tasks, verbosity is actually desirable -- the reasoning traces teach the student model how to think through problems.
- [x] **Ollama cloud rate limits?** Ollama does not use per-request or per-token limits. Usage is measured by GPU time (model size x request duration). Limits reset every 5 hours (session) and every 7 days (weekly). Plans: Free = light usage, Pro ($20/mo) = 50x Free with 3 concurrent models, Max ($100/mo) = 5x Pro with 10 concurrent models. For bulk data generation, Max plan recommended to run all three teachers concurrently. No hard request/minute cap -- throttling occurs when session or weekly GPU-time budget is exhausted.

## Open Questions
- [ ] What Ollama plan tier is needed for generating 5K-50K samples across three teachers without hitting weekly limits?
- [ ] Should the MultiPL-E F# translator be built before or after distillation to establish a baseline?
