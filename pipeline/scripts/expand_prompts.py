"""
Prompt Expansion Script

Takes seed YAML prompt files and uses the assigned teacher model to generate
diverse variations of each seed prompt. Optionally fetches relevant documentation
via doc_lookup to give the teacher context for generating high-quality variations.

Flow per seed prompt:
  1. Extract library/topic keywords from the seed instruction
  2. (Optional) Fetch relevant docs via doc_lookup
  3. Send to the seed's assigned teacher via Ollama
  4. Parse the returned YAML list of variations
  5. Deduplicate and assign IDs
  6. Save to expanded YAML file

Usage:
  python expand_prompts.py --input ../prompts/fsharp_core.yaml --output ../prompts/expanded/fsharp_core_expanded.yaml
  python expand_prompts.py --input ../prompts/fsharp_core.yaml --output ../prompts/expanded/fsharp_core_expanded.yaml --variations 20 --with-docs
  python expand_prompts.py --all --variations 30 --with-docs
"""

import argparse
import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROMPTS_DIR = PIPELINE_DIR / "prompts"
EXPANDED_DIR = PROMPTS_DIR / "expanded"

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

TEACHERS = {
    "kimi": "kimi-k2.5:cloud",
    "minimax": "minimax-m2.7:cloud",
    "glm5": "glm-5:cloud",
}

EXPANSION_SYSTEM_PROMPT = """\
You are an expert prompt engineer generating training data prompts for a coding LLM.

Given a seed prompt, generate {n} diverse variations. Each variation must:
- Be a self-contained coding instruction (not referencing the seed)
- Cover a DIFFERENT scenario, entity, or use case than the seed
- Vary in complexity (some easy, some intermediate, some advanced)
- Include edge cases, error handling scenarios, and real-world constraints
- Be specific enough to produce a unique, useful training sample
- Stay within the same technology domain as the seed

Vary these dimensions across your variations:
- Entity names and domain contexts (e-commerce, healthcare, fintech, social media, IoT, etc.)
- Complexity level (beginner, intermediate, advanced)
- Task type (implement, refactor, debug, explain, compare, design)
- Constraints (performance, memory, concurrency, security, backward compatibility)
- Scope (single function, module, full feature, system design)

Return ONLY a YAML list of instructions, no other text. Format:
```yaml
- |
  First variation instruction here.
  Can be multi-line.
- |
  Second variation instruction here.
```
"""


def extract_keywords(instruction: str) -> tuple[str, str]:
    """Extract library name and topic from an instruction for doc lookup."""
    # Common library names to detect
    libraries = [
        "Giraffe",
        "FsToolkit.ErrorHandling",
        "Akka.NET",
        "Akka.FSharp",
        "Thoth.Json",
        "linq2db",
        "FluentMigrator",
        "Npgsql",
        "Serilog",
        "FSharp.SystemTextJson",
        "FSharp.Control.AsyncSeq",
        "FSharp.Control.Reactive",
        "FSharp.Data",
        "EntityFrameworkCore.FSharp",
        "FsUnit",
        "Confluent.Kafka",
        "Minio",
        "Stripe.net",
        "Giraffe.OpenApi",
        "Giraffe.ViewEngine",
        "Svelte",
        "SvelteKit",
        "TypeScript",
        "Docker",
        "Kubernetes",
        "Helm",
        "ASP.NET Core",
        "PostgreSQL",
        "SignalR",
    ]

    detected_lib = ""
    instruction_lower = instruction.lower()
    for lib in libraries:
        if lib.lower() in instruction_lower:
            detected_lib = lib
            break

    # Extract first sentence as topic summary
    first_line = instruction.strip().split("\n")[0][:200]
    topic = first_line.strip()

    return detected_lib, topic


async def expand_seed(
    client: httpx.AsyncClient,
    seed_id: str,
    seed_instruction: str,
    teacher_model: str,
    num_variations: int,
    doc_context: str = "",
) -> list[str]:
    """Send a seed prompt to the teacher and get variations back."""

    system = EXPANSION_SYSTEM_PROMPT.format(n=num_variations)

    messages = [
        {"role": "system", "content": system},
    ]

    if doc_context:
        messages.append(
            {
                "role": "user",
                "content": f"Reference documentation for context (use this to create more specific, accurate variations):\n\n{doc_context[:8000]}",
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": "I've reviewed the documentation. Please provide the seed prompt to expand.",
            }
        )

    messages.append(
        {
            "role": "user",
            "content": f"Seed prompt to expand into {num_variations} variations:\n\n{seed_instruction}",
        }
    )

    payload = {
        "model": teacher_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.8,  # Higher temp for diversity
            "top_p": 0.95,
            "num_predict": 8192,
        },
    }

    start = time.monotonic()
    try:
        log.info(
            f"[{seed_id}] Expanding with {teacher_model} ({num_variations} variations)..."
        )
        response = await client.post(
            OLLAMA_CHAT_URL,
            json=payload,
            timeout=600.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        elapsed = time.monotonic() - start
        log.info(
            f"[{seed_id}] Done in {elapsed:.1f}s ({data.get('eval_count', 0)} tokens)"
        )

        return parse_variations(content)

    except Exception as e:
        log.error(f"[{seed_id}] Failed: {e}")
        return []


def parse_variations(response: str) -> list[str]:
    """Parse the teacher's response to extract a list of prompt variations."""
    # Try to extract YAML from code blocks first
    yaml_match = re.search(r"```(?:yaml)?\s*\n(.*?)```", response, re.DOTALL)
    if yaml_match:
        yaml_text = yaml_match.group(1)
    else:
        yaml_text = response

    # Try parsing as YAML list
    try:
        parsed = yaml.safe_load(yaml_text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if item and str(item).strip()]
    except yaml.YAMLError:
        pass

    # Fallback: split by numbered items (1. ... 2. ... etc.)
    items = re.split(r"\n\d+\.\s+", "\n" + yaml_text)
    items = [item.strip() for item in items if item.strip() and len(item.strip()) > 50]

    if items:
        return items

    # Last fallback: split by double newlines
    items = [
        p.strip() for p in yaml_text.split("\n\n") if p.strip() and len(p.strip()) > 50
    ]
    return items


def deduplicate(
    variations: list[str], existing: set[str], threshold: float = 0.7
) -> list[str]:
    """Remove near-duplicate variations using simple token overlap."""
    unique = []
    seen_tokens = existing.copy()

    for var in variations:
        # Simple token set for comparison
        tokens = set(var.lower().split())
        if not tokens:
            continue

        # Check overlap with all seen variations
        is_dup = False
        for seen in seen_tokens:
            seen_t = set(seen.lower().split())
            if not seen_t:
                continue
            overlap = len(tokens & seen_t) / max(len(tokens | seen_t), 1)
            if overlap > threshold:
                is_dup = True
                break

        if not is_dup:
            unique.append(var)
            seen_tokens.add(var)

    return unique


async def expand_file(
    input_path: Path,
    output_path: Path,
    num_variations: int = 30,
    with_docs: bool = False,
    concurrency: int = 2,
):
    """Expand all seeds in a YAML file."""
    with open(input_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    teacher = config["teacher"]
    domain = config["domain"]
    system_prompt = config["system_prompt"]
    teacher_model = TEACHERS[teacher]

    log.info(
        f"Expanding {input_path.name}: {len(config['prompts'])} seeds, "
        f"teacher={teacher}, target={num_variations} variations each"
    )

    # Load doc_lookup if needed
    doc_lookup = None
    if with_docs:
        from doc_lookup import DocLookup

        doc_lookup = DocLookup()

    # Load existing expansions to support resume
    existing_ids = set()
    existing_instructions = set()
    expanded_prompts = []
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing_data = yaml.safe_load(f)
            if existing_data and "prompts" in existing_data:
                expanded_prompts = existing_data["prompts"]
                existing_ids = {p["id"] for p in expanded_prompts}
                existing_instructions = {
                    p["instruction"].strip() for p in expanded_prompts
                }
                log.info(f"Resuming: {len(expanded_prompts)} existing expansions")

    semaphore = asyncio.Semaphore(concurrency)

    async def process_seed(seed, client):
        async with semaphore:
            seed_id = seed["id"]

            # Skip if this seed was already expanded
            prefix = f"{seed_id}_exp_"
            if any(eid.startswith(prefix) for eid in existing_ids):
                log.info(f"[{seed_id}] Already expanded, skipping")
                return []

            instruction = seed["instruction"]

            # Fetch docs if enabled
            doc_context = ""
            if doc_lookup:
                lib, topic = extract_keywords(instruction)
                if lib:
                    doc_context = doc_lookup.lookup(lib, topic, max_chars=6000)
                    if doc_context:
                        log.info(
                            f"[{seed_id}] Fetched {len(doc_context)} chars of docs for {lib}"
                        )

            variations = await expand_seed(
                client,
                seed_id,
                instruction,
                teacher_model,
                num_variations,
                doc_context,
            )

            # Deduplicate against existing + seed
            unique = deduplicate(
                variations,
                existing_instructions | {instruction.strip()},
            )

            log.info(
                f"[{seed_id}] Got {len(variations)} variations, {len(unique)} unique after dedup"
            )

            # Build prompt entries
            results = []
            for i, var in enumerate(unique):
                results.append(
                    {
                        "id": f"{seed_id}_exp_{i:03d}",
                        "instruction": var,
                    }
                )

            return results

    async with httpx.AsyncClient() as client:
        tasks = [process_seed(seed, client) for seed in config["prompts"]]
        results = await asyncio.gather(*tasks)

    # Collect all new expansions
    new_prompts = []
    for result in results:
        new_prompts.extend(result)

    all_prompts = expanded_prompts + new_prompts

    # Save expanded file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "teacher": teacher,
        "domain": domain,
        "system_prompt": system_prompt,
        "temperature": config.get("temperature"),
        "max_tokens": config.get("max_tokens"),
        "prompts": all_prompts,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            output_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            width=120,
            sort_keys=False,
        )

    if doc_lookup:
        doc_lookup.close()

    log.info("=" * 60)
    log.info(f"EXPANSION SUMMARY: {input_path.name}")
    log.info(f"  Seeds:          {len(config['prompts'])}")
    log.info(f"  New variations: {len(new_prompts)}")
    log.info(f"  Total prompts:  {len(all_prompts)}")
    log.info(f"  Output:         {output_path}")
    log.info("=" * 60)


async def expand_all(
    num_variations: int = 30,
    with_docs: bool = False,
    concurrency: int = 2,
):
    """Expand all YAML files in the prompts directory."""
    for yaml_file in sorted(PROMPTS_DIR.glob("*.yaml")):
        output_file = EXPANDED_DIR / f"{yaml_file.stem}_expanded.yaml"
        await expand_file(
            yaml_file,
            output_file,
            num_variations=num_variations,
            with_docs=with_docs,
            concurrency=concurrency,
        )


def main():
    parser = argparse.ArgumentParser(description="Prompt Expansion Script")
    parser.add_argument("--input", type=Path, help="Input seed YAML file")
    parser.add_argument("--output", type=Path, help="Output expanded YAML file")
    parser.add_argument(
        "--all", action="store_true", help="Expand all YAML files in prompts/"
    )
    parser.add_argument(
        "--variations", type=int, default=30, help="Variations per seed (default: 30)"
    )
    parser.add_argument(
        "--with-docs", action="store_true", help="Fetch docs via doc_lookup for context"
    )
    parser.add_argument(
        "--concurrency", type=int, default=2, help="Max concurrent Ollama requests"
    )
    args = parser.parse_args()

    if args.all:
        asyncio.run(expand_all(args.variations, args.with_docs, args.concurrency))
    elif args.input:
        output = args.output or (EXPANDED_DIR / f"{args.input.stem}_expanded.yaml")
        asyncio.run(
            expand_file(
                args.input, output, args.variations, args.with_docs, args.concurrency
            )
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
