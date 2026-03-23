"""
Multi-Teacher Data Generation Pipeline

Generates training data from three teacher models via Ollama cloud API:
  - Kimi K2.5:      Svelte, TypeScript, long-context, cross-domain
  - MiniMax M2.7:   Agentic coding, Docker/K8s, multi-step SWE
  - DeepSeek V3.2:  F#, Akka.NET, .NET/ASP.NET Core

Each teacher is assigned prompts from its strongest domains.
Output is JSONL with one sample per line.

Usage:
  python generate_data.py --config ../prompts/fsharp_core.yaml --output ../../data/raw/fsharp_core.jsonl
  python generate_data.py --config ../prompts/svelte.yaml --output ../../data/raw/svelte.jsonl --concurrency 5
  python generate_data.py --config ../prompts/fsharp_core.yaml --output ../../data/raw/fsharp_core.jsonl --with-docs
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import httpx
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Ollama API endpoint (local Ollama server proxying to cloud models)
OLLAMA_API_BASE = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_API_BASE}/api/chat"
OLLAMA_GENERATE_URL = f"{OLLAMA_API_BASE}/api/generate"

# Teacher model identifiers for Ollama cloud
TEACHERS = {
    "kimi": "kimi-k2.5:cloud",
    "minimax": "minimax-m2.7:cloud",
    "deepseek": "deepseek-v3.2:cloud",
    "glm5": "glm-5:cloud",
}

# Default generation parameters per teacher
TEACHER_DEFAULTS = {
    "kimi": {
        "temperature": 0.7,
        "top_p": 0.9,
        "num_predict": 8192,
    },
    "minimax": {
        "temperature": 0.4,  # Lower temp to reduce verbosity
        "top_p": 0.9,
        "num_predict": 8192,
    },
    "deepseek": {
        "temperature": 0.6,
        "top_p": 0.9,
        "num_predict": 8192,
    },
    "glm5": {
        "temperature": 0.7,  # Same as SWE-bench eval defaults
        "top_p": 0.95,
        "num_predict": 16384,
    },
}


@dataclass
class Prompt:
    """A single prompt to send to a teacher."""

    id: str
    instruction: str
    system_prompt: str
    teacher: str  # "kimi", "minimax", or "deepseek"
    domain: str
    context: str = ""  # optional documentation context to include
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@dataclass
class GeneratedSample:
    """A completed instruction/response pair."""

    id: str
    instruction: str
    response: str
    teacher: str
    domain: str
    model: str  # full Ollama model name
    generation_time_s: float
    token_count: int = 0
    timestamp: str = ""


@dataclass
class PromptConfig:
    """Configuration loaded from a YAML prompt file."""

    teacher: str
    domain: str
    system_prompt: str
    prompts: list[dict]
    context_files: list[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def load_prompt_config(config_path: Path) -> PromptConfig:
    """Load prompt configuration from a YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return PromptConfig(
        teacher=data["teacher"],
        domain=data["domain"],
        system_prompt=data["system_prompt"],
        prompts=data["prompts"],
        context_files=data.get("context_files", []),
        temperature=data.get("temperature"),
        max_tokens=data.get("max_tokens"),
    )


def load_context(context_files: list[str], base_dir: Path) -> str:
    """Load and concatenate context files (scraped docs, etc.)."""
    context_parts = []
    for filepath in context_files or []:
        full_path = base_dir / filepath
        if full_path.exists():
            content = full_path.read_text(encoding="utf-8")
            context_parts.append(f"--- {filepath} ---\n{content}")
            log.info(f"Loaded context: {filepath} ({len(content)} chars)")
        else:
            log.warning(f"Context file not found: {full_path}")
    return "\n\n".join(context_parts)


async def generate_response(
    client: httpx.AsyncClient,
    prompt: Prompt,
    semaphore: asyncio.Semaphore,
    max_retries: int = 5,
) -> Optional[GeneratedSample]:
    """Send a single prompt to the appropriate teacher via Ollama API.

    Retries with exponential backoff on 429 (rate limit) and 5xx errors.
    """
    async with semaphore:
        model = TEACHERS[prompt.teacher]
        defaults = TEACHER_DEFAULTS[prompt.teacher]

        temperature = prompt.temperature or defaults["temperature"]
        max_tokens = prompt.max_tokens or defaults["num_predict"]

        # Build messages
        messages = [
            {"role": "system", "content": prompt.system_prompt},
        ]

        # Include documentation context if provided
        if prompt.context:
            messages.append(
                {
                    "role": "user",
                    "content": f"Reference documentation:\n\n{prompt.context}",
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "I've reviewed the documentation. Please provide your question or task.",
                }
            )

        messages.append({"role": "user", "content": prompt.instruction})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": defaults["top_p"],
                "num_predict": max_tokens,
            },
        }

        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                if attempt == 0:
                    log.info(f"[{prompt.id}] Sending to {model}...")
                else:
                    log.info(
                        f"[{prompt.id}] Retry {attempt}/{max_retries} to {model}..."
                    )

                response = await client.post(
                    OLLAMA_CHAT_URL,
                    json=payload,
                    timeout=600.0,  # 10 min timeout for long responses
                )
                response.raise_for_status()
                data = response.json()

                elapsed = time.monotonic() - start
                content = data.get("message", {}).get("content", "")
                eval_count = data.get("eval_count", 0)

                log.info(
                    f"[{prompt.id}] Done in {elapsed:.1f}s ({eval_count} tokens, {model})"
                )

                return GeneratedSample(
                    id=prompt.id,
                    instruction=prompt.instruction,
                    response=content,
                    teacher=prompt.teacher,
                    domain=prompt.domain,
                    model=model,
                    generation_time_s=round(elapsed, 2),
                    token_count=eval_count,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 429 or status >= 500:
                    if attempt < max_retries:
                        # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                        delay = 2 ** (attempt + 1)
                        log.warning(
                            f"[{prompt.id}] {status} error, backing off {delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        log.error(
                            f"[{prompt.id}] {status} error after {max_retries} retries, giving up"
                        )
                        return None
                else:
                    log.error(
                        f"[{prompt.id}] HTTP error: {status} - {e.response.text[:500]}"
                    )
                    return None

            except httpx.TimeoutException:
                if attempt < max_retries:
                    delay = 2 ** (attempt + 1)
                    log.warning(
                        f"[{prompt.id}] Timeout, backing off {delay}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    log.error(f"[{prompt.id}] Timeout after {max_retries} retries")
                    return None

            except Exception as e:
                log.error(f"[{prompt.id}] Unexpected error: {e}")
                return None

        return None


async def generate_batch(
    prompts: list[Prompt],
    output_path: Path,
    concurrency: int = 2,
    retry_failed: bool = True,
    max_retries: int = 2,
    progress_every: int = 10,
):
    """Generate responses for a batch of prompts with controlled concurrency."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    # Track existing samples to support resume
    existing_ids = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        existing_ids.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        pass
        log.info(
            f"Resuming: found {len(existing_ids)} existing samples in {output_path}"
        )

    # Filter to only unfinished prompts
    remaining = [p for p in prompts if p.id not in existing_ids]
    log.info(f"Generating {len(remaining)} samples ({len(existing_ids)} already done)")

    if not remaining:
        log.info("All samples already generated. Nothing to do.")
        return

    # Use a lock to safely write to file from concurrent tasks
    file_lock = asyncio.Lock()
    completed = 0
    failed_ids = []
    completed_ids = set()  # Track IDs written during this run to prevent duplicates

    async def process_and_write(client, prompt):
        nonlocal completed
        result = await generate_response(client, prompt, semaphore)
        if result is None:
            failed_ids.append(prompt.id)
            return
        async with file_lock:
            # Check if another concurrent task already wrote this ID
            if prompt.id in completed_ids:
                log.debug(f"[{prompt.id}] Skipping duplicate write")
                return
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
                f.flush()
            completed_ids.add(prompt.id)
            completed += 1
            pct = completed / len(remaining) * 100
            if completed % progress_every == 0 or completed == len(remaining):
                log.info(
                    f"Progress: {completed}/{len(remaining)} ({pct:.1f}%) completed, {len(failed_ids)} failed"
                )

    async with httpx.AsyncClient() as client:
        tasks = [process_and_write(client, prompt) for prompt in remaining]
        await asyncio.gather(*tasks, return_exceptions=True)

    log.info("=" * 60)
    log.info("GENERATION SUMMARY")
    log.info(f"  Completed: {completed}")
    log.info(f"  Failed:    {len(failed_ids)}")
    log.info(f"  Skipped:   {len(existing_ids)} (already existed)")
    log.info(f"  Output:    {output_path}")
    if failed_ids:
        log.warning(f"  Failed IDs: {failed_ids}")
    log.info("=" * 60)


def build_prompts(config: PromptConfig, context: str, doc_lookup=None) -> list[Prompt]:
    """Build Prompt objects from a loaded config.

    If doc_lookup is provided, prompts with a `context_query` field will have
    their context enriched with relevant documentation fetched on-demand.
    """
    prompts = []
    for i, prompt_data in enumerate(config.prompts):
        prompt_id = prompt_data.get("id", f"{config.domain}_{i:04d}")
        instruction = prompt_data["instruction"]

        # Support prompt-level overrides
        temperature = prompt_data.get("temperature", config.temperature)
        max_tokens = prompt_data.get("max_tokens", config.max_tokens)

        # On-demand doc lookup via context_query field
        prompt_context = context
        context_query = prompt_data.get("context_query", "")
        if context_query and doc_lookup:
            parts = context_query.split(":", 1)
            library = parts[0].strip() if len(parts) > 1 else ""
            topic = parts[-1].strip()
            doc_text = doc_lookup.lookup(library, topic, max_chars=8000)
            if doc_text:
                prompt_context = (
                    f"{context}\n\n--- Documentation: {context_query} ---\n{doc_text}"
                    if context
                    else doc_text
                )

        prompts.append(
            Prompt(
                id=prompt_id,
                instruction=instruction,
                system_prompt=config.system_prompt,
                teacher=config.teacher,
                domain=config.domain,
                context=prompt_context,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    return prompts


async def main_async(args):
    config_path = args.config.resolve()
    config = load_prompt_config(config_path)

    log.info(
        f"Loaded config: teacher={config.teacher}, domain={config.domain}, "
        f"{len(config.prompts)} prompts"
    )

    # Load context files relative to the config file's directory
    context = load_context(config.context_files, config_path.parent)
    if context:
        log.info(f"Total context: {len(context)} chars")

    # Initialize doc_lookup if --with-docs flag is set
    doc_lookup = None
    if getattr(args, "with_docs", False):
        from doc_lookup import DocLookup

        doc_lookup = DocLookup()
        log.info("Doc lookup enabled -- will fetch docs for prompts with context_query")

    prompts = build_prompts(config, context, doc_lookup)

    if doc_lookup:
        doc_lookup.close()

    # Apply temperature override if specified via CLI
    if args.temperature is not None:
        for prompt in prompts:
            prompt.temperature = args.temperature
        log.info(f"Temperature override: {args.temperature}")

    await generate_batch(
        prompts=prompts,
        output_path=args.output.resolve(),
        concurrency=args.concurrency,
        progress_every=args.progress_every,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Teacher Data Generation Pipeline"
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="YAML prompt config file (see pipeline/prompts/ for examples)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent API requests (default: 5, Max plan supports 10)",
    )
    parser.add_argument(
        "--with-docs",
        action="store_true",
        help="Fetch docs via doc_lookup for prompts with context_query field",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override temperature for all prompts (ignores YAML/teacher defaults)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Log progress every N completions (default: 10, use 1 for benchmarks)",
    )
    args = parser.parse_args()

    if not args.config.exists():
        log.error(f"Config file not found: {args.config}")
        return

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
