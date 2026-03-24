"""
Training Data Generation Pipeline (Config-Driven)

Single-script pipeline that generates training data from teacher models via
Ollama cloud API. Teachers, domains, concurrency, and temperature are all
driven by a round config YAML. Teacher-to-domain assignments live in the
config; prompt YAMLs are teacher-agnostic.

Features:
  - Async generation with per-teacher concurrency control
  - Live status dashboard (or verbose per-line logging)
  - Resume support (skips already-generated IDs)
  - Duplicate write guard (asyncio lock + completed_ids set)
  - Retry with exponential backoff on 429/5xx/timeout
  - F# verification and dataset formatting post-generation

Usage:
    python run_generation.py --round-config ../../configs/rounds/round3.yaml
    python run_generation.py --round-config ../../configs/rounds/round3.yaml --status
    python run_generation.py --round-config ../../configs/rounds/round3.yaml --verbose
    python run_generation.py --round-config ../../configs/rounds/round3.yaml --verify

    # Override config values via CLI:
    python run_generation.py --round-config ../../configs/rounds/round3.yaml --concurrency 5 --temperature 0.85
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import yaml

# ── Paths ──────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
VERIFIED_DIR = PROJECT_DIR / "data" / "verified"
EXPANDED_DIR = SCRIPT_DIR.parent / "prompts" / "expanded"

# Domains that require F# compiler verification
FSHARP_DOMAINS = {
    "fsharp_core",
    "fsharp_libraries",
    "fsharp_core_r3",
    "fsharp_libraries_r3",
    "dotnet_aspnet",
    "dotnet_aspnet_r3",
    "cross_domain",
}

# ── Logging ────────────────────────────────────────────────────

# Default to WARNING; --verbose sets to INFO
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Teacher Models ─────────────────────────────────────────────

TEACHERS = {
    "minimax": {
        "model": "minimax-m2.7:cloud",
        "temperature": 0.4,
        "top_p": 0.9,
        "num_predict": 8192,
    },
    "glm5": {
        "model": "glm-5:cloud",
        "temperature": 0.7,
        "top_p": 0.95,
        "num_predict": 16384,
    },
    "kimi": {
        "model": "kimi-k2.5:cloud",
        "temperature": 0.7,
        "top_p": 0.9,
        "num_predict": 8192,
    },
}

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

# ── Data Classes ───────────────────────────────────────────────


@dataclass
class Prompt:
    """A single prompt to send to a teacher."""

    id: str
    instruction: str
    system_prompt: str
    domain: str
    context: str = ""
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
    model: str
    generation_time_s: float
    token_count: int = 0
    timestamp: str = ""


# ── Prompt Loading ─────────────────────────────────────────────


def load_prompts(yaml_path: Path) -> tuple[list[Prompt], str]:
    """Load prompts from a teacher-agnostic expanded YAML.

    Returns (prompts, domain).
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    system_prompt = data.get("system_prompt", "")
    domain = data.get("domain", "unknown")
    default_temp = data.get("temperature")
    default_max_tokens = data.get("max_tokens")

    # Load context files if specified
    context = ""
    for filepath in data.get("context_files", []):
        full_path = yaml_path.parent / filepath
        if full_path.exists():
            content = full_path.read_text(encoding="utf-8")
            context += f"--- {filepath} ---\n{content}\n\n"

    prompts = []
    for i, p in enumerate(data.get("prompts", [])):
        prompts.append(
            Prompt(
                id=p.get("id", f"{domain}_{i:04d}"),
                instruction=p["instruction"],
                system_prompt=system_prompt,
                domain=domain,
                context=context,
                temperature=p.get("temperature", default_temp),
                max_tokens=p.get("max_tokens", default_max_tokens),
            )
        )

    return prompts, domain


def load_existing_ids(output_path: Path) -> set[str]:
    """Load IDs of already-generated samples for resume support."""
    ids = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        ids.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        pass
    return ids


# ── Core: Generate One Response ────────────────────────────────


async def generate_one(
    client: httpx.AsyncClient,
    prompt: Prompt,
    teacher: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 5,
    verbose: bool = False,
) -> Optional[GeneratedSample]:
    """Send a single prompt to a teacher via Ollama API.

    Retries with exponential backoff on 429, 5xx, and timeout.
    """
    async with semaphore:
        config = TEACHERS[teacher]
        model = config["model"]
        temperature = prompt.temperature or config["temperature"]
        max_tokens = prompt.max_tokens or config["num_predict"]

        # Build messages
        messages = [{"role": "system", "content": prompt.system_prompt}]

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
                "top_p": config["top_p"],
                "num_predict": max_tokens,
            },
        }

        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                if verbose:
                    if attempt == 0:
                        log.info(f"[{prompt.id}] Sending to {model}...")
                    else:
                        log.info(
                            f"[{prompt.id}] Retry {attempt}/{max_retries} to {model}..."
                        )

                response = await client.post(
                    OLLAMA_CHAT_URL,
                    json=payload,
                    timeout=600.0,
                )
                response.raise_for_status()
                data = response.json()

                elapsed = time.monotonic() - start
                content = data.get("message", {}).get("content", "")
                eval_count = data.get("eval_count", 0)

                if verbose:
                    log.info(
                        f"[{prompt.id}] Done in {elapsed:.1f}s "
                        f"({eval_count} tokens, {model})"
                    )

                return GeneratedSample(
                    id=prompt.id,
                    instruction=prompt.instruction,
                    response=content,
                    teacher=teacher,
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
                        delay = 2 ** (attempt + 1)
                        log.warning(
                            f"[{prompt.id}] {status} error, backing off {delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        log.error(
                            f"[{prompt.id}] {status} error after {max_retries} retries"
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


# ── Core: Run One Teacher-Domain Job ──────────────────────────


async def run_job(
    client: httpx.AsyncClient,
    teacher: str,
    yaml_stem: str,
    output_path: Path,
    semaphore: asyncio.Semaphore,
    temperature: Optional[float],
    progress: dict,
    verbose: bool = False,
):
    """Run all prompts for one teacher-domain pair."""
    yaml_path = EXPANDED_DIR / f"{yaml_stem}.yaml"
    prompts, domain = load_prompts(yaml_path)

    # Apply temperature override
    if temperature is not None:
        for p in prompts:
            p.temperature = temperature

    # Resume: skip already-generated IDs
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = load_existing_ids(output_path)
    remaining = [p for p in prompts if p.id not in existing_ids]

    job_key = f"{teacher}:{yaml_stem}"
    progress[job_key] = {
        "done": len(existing_ids),
        "total": len(prompts),
        "failed": 0,
        "teacher": teacher,
        "domain": yaml_stem,
    }

    if not remaining:
        return

    file_lock = asyncio.Lock()
    completed_ids = set(existing_ids)

    async def process_one(prompt: Prompt):
        result = await generate_one(client, prompt, teacher, semaphore, verbose=verbose)
        if result is None:
            progress[job_key]["failed"] += 1
            return
        async with file_lock:
            if prompt.id in completed_ids:
                return
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
                f.flush()
            completed_ids.add(prompt.id)
            progress[job_key]["done"] += 1

    tasks = [process_one(p) for p in remaining]
    await asyncio.gather(*tasks, return_exceptions=True)


# ── Round Config ───────────────────────────────────────────────


def load_round_config(path: Path) -> dict:
    """Load a round config YAML and return structured config."""
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    teachers = {}
    all_jobs = []
    for teacher_key, files in config["teachers"].items():
        # Normalize teacher key to lowercase for TEACHERS dict lookup
        teacher = teacher_key.lower().replace("-", "")
        entries = [(f["yaml"], f.get("output", f["yaml"])) for f in files]
        teachers[teacher] = entries
        all_jobs.extend(
            {"teacher": teacher, "yaml": y, "output": o} for y, o in entries
        )

    return {
        "description": config.get("description", ""),
        "suffix": config.get("suffix", ""),
        "temperature": config.get("temperature"),
        "concurrency": config.get("concurrency", 3),
        "teachers": teachers,
        "all_jobs": all_jobs,
    }


# ── Status Dashboard ──────────────────────────────────────────


def print_status(
    round_config: dict,
    progress: dict,
    suffix: str = "",
    start_time: float = None,
):
    """Print the status dashboard."""
    now = datetime.now()
    os.system("cls" if os.name == "nt" else "clear")

    desc = round_config["description"]
    label = f" [{desc}]" if desc else ""
    print(f"{'=' * 65}")
    print(f"  GENERATION STATUS{label}")
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if start_time:
        elapsed = timedelta(seconds=time.monotonic() - start_time)
        print(f"  Running for {str(elapsed).split('.')[0]}")
    if suffix:
        print(f"  Output suffix: {suffix}")
    print(f"{'=' * 65}\n")

    grand_done = 0
    grand_total = 0
    grand_failed = 0

    for teacher, files in round_config["teachers"].items():
        teacher_done = 0
        teacher_total = 0
        teacher_failed = 0

        domains_info = []
        for yaml_stem, output_name in files:
            job_key = f"{teacher}:{yaml_stem}"
            info = progress.get(job_key, {"done": 0, "total": 0, "failed": 0})
            done = info["done"]
            total = info["total"]
            failed = info["failed"]
            teacher_done += done
            teacher_total += total
            teacher_failed += failed
            domains_info.append((output_name, done, total, failed))

        teacher_pct = (teacher_done / teacher_total * 100) if teacher_total > 0 else 0
        teacher_status = "DONE" if teacher_done >= teacher_total else "RUNNING"

        display_name = teacher
        for key, cfg in TEACHERS.items():
            if key == teacher:
                display_name = f"{teacher} ({cfg['model']})"
                break

        print(
            f"  {display_name} "
            f"({teacher_done}/{teacher_total} - {teacher_pct:.0f}%) "
            f"[{teacher_status}]"
        )
        print(f"  {'-' * 55}")

        for domain, done, total, failed in domains_info:
            pct = (done / total * 100) if total > 0 else 0
            bar_width = 25
            filled = int(bar_width * pct / 100)
            bar = "#" * filled + "-" * (bar_width - filled)

            if done >= total and total > 0:
                status = "[DONE]   "
            elif done > 0:
                status = "[RUNNING]"
            else:
                status = "[PEND]   "

            fail_str = f" ({failed} failed)" if failed > 0 else ""
            print(
                f"    {domain:25s} {bar} {done:5d}/{total:<5d} "
                f"({pct:5.1f}%) {status}{fail_str}"
            )

        print()
        grand_done += teacher_done
        grand_total += teacher_total
        grand_failed += teacher_failed

    grand_pct = (grand_done / grand_total * 100) if grand_total > 0 else 0
    remaining = grand_total - grand_done
    print(f"  {'-' * 55}")
    print(f"  TOTAL: {grand_done:,} / {grand_total:,} ({grand_pct:.1f}%)")
    if grand_failed > 0:
        print(f"  FAILED: {grand_failed:,}")

    oci_path = VERIFIED_DIR / "opencode_instruct.jsonl"
    oci_count = count_lines(oci_path)
    if oci_count > 0:
        print(f"  OPENCODE INSTRUCT: {oci_count:,} samples (verified)")
    print(f"  GRAND TOTAL: {grand_done + oci_count:,} samples")

    if start_time and grand_done > 0:
        elapsed_s = time.monotonic() - start_time
        rate = grand_done / (elapsed_s / 60)
        if rate > 0 and remaining > 0:
            eta_min = remaining / rate
            finish = now + timedelta(minutes=eta_min)
            print(f"\n  Rate: ~{rate:.1f} samples/min")
            print(f"  Remaining: {remaining:,} samples")
            print(f"  ETA: ~{finish.strftime('%Y-%m-%d %H:%M')}")

    if grand_done >= grand_total:
        print(f"\n  ** ALL GENERATION COMPLETE **")

    print(f"\n{'=' * 65}")


def print_summary(
    round_config: dict,
    progress: dict,
    suffix: str = "",
):
    """Print a compact, paste-friendly progress summary."""
    desc = round_config["description"]
    print(f"Round: {desc}")
    if suffix:
        print(f"Suffix: {suffix}")

    grand_done = 0
    grand_total = 0
    grand_failed = 0

    for teacher, files in round_config["teachers"].items():
        for yaml_stem, output_name in files:
            job_key = f"{teacher}:{yaml_stem}"
            info = progress.get(job_key, {"done": 0, "total": 0, "failed": 0})
            done = info["done"]
            total = info["total"]
            failed = info["failed"]
            pct = (done / total * 100) if total > 0 else 0
            status = "DONE" if done >= total else "..."
            fail_str = f" ({failed} failed)" if failed > 0 else ""
            print(
                f"  {teacher:8s} {output_name:25s} {done:5d}/{total:<5d} "
                f"({pct:5.1f}%) {status}{fail_str}"
            )
            grand_done += done
            grand_total += total
            grand_failed += failed

    grand_pct = (grand_done / grand_total * 100) if grand_total > 0 else 0
    print(f"Total: {grand_done}/{grand_total} ({grand_pct:.1f}%)", end="")
    if grand_failed > 0:
        print(f", {grand_failed} failed", end="")
    print()


async def status_loop(
    round_config: dict,
    progress: dict,
    start_time: float,
    suffix: str = "",
    check_interval: int = 15,
):
    """Periodically refresh the status dashboard."""
    while True:
        print_status(round_config, progress, suffix=suffix, start_time=start_time)
        print(
            f"  Refreshing every {check_interval}s (generation running in background)"
        )

        grand_total = sum(p["total"] for p in progress.values())
        grand_done = sum(p["done"] for p in progress.values())
        if grand_total > 0 and grand_done >= grand_total:
            break

        await asyncio.sleep(check_interval)


# ── Orchestrator ───────────────────────────────────────────────


async def run_teacher_jobs(
    client: httpx.AsyncClient,
    teacher: str,
    files: list[tuple[str, str]],
    semaphore: asyncio.Semaphore,
    temperature: Optional[float],
    suffix: str,
    progress: dict,
    verbose: bool = False,
):
    """Run all domain files for a single teacher sequentially."""
    for yaml_stem, output_name in files:
        output_path = RAW_DIR / f"{output_name}{suffix}.jsonl"
        await run_job(
            client=client,
            teacher=teacher,
            yaml_stem=yaml_stem,
            output_path=output_path,
            semaphore=semaphore,
            temperature=temperature,
            progress=progress,
            verbose=verbose,
        )


async def generate_all(
    round_config: dict,
    concurrency: int,
    verbose: bool,
    suffix: str = "",
    temperature: Optional[float] = None,
):
    """Run all teachers in parallel, domains sequentially per teacher."""
    progress = {}
    start_time = time.monotonic()

    # Pre-populate progress with totals so dashboard shows everything
    for teacher, files in round_config["teachers"].items():
        for yaml_stem, output_name in files:
            yaml_path = EXPANDED_DIR / f"{yaml_stem}.yaml"
            total = count_prompts(yaml_path)
            output_path = RAW_DIR / f"{output_name}{suffix}.jsonl"
            existing = len(load_existing_ids(output_path))
            job_key = f"{teacher}:{yaml_stem}"
            progress[job_key] = {
                "done": existing,
                "total": total,
                "failed": 0,
                "teacher": teacher,
                "domain": yaml_stem,
            }

    # One semaphore per teacher to limit concurrency
    teacher_semaphores = {
        teacher: asyncio.Semaphore(concurrency) for teacher in round_config["teachers"]
    }

    async with httpx.AsyncClient() as client:
        gen_tasks = [
            run_teacher_jobs(
                client=client,
                teacher=teacher,
                files=files,
                semaphore=teacher_semaphores[teacher],
                temperature=temperature,
                suffix=suffix,
                progress=progress,
                verbose=verbose,
            )
            for teacher, files in round_config["teachers"].items()
        ]

        if verbose:
            await asyncio.gather(*gen_tasks)
        else:
            gen_task = asyncio.gather(*gen_tasks)
            status_task = asyncio.create_task(
                status_loop(round_config, progress, start_time, suffix=suffix)
            )

            await gen_task
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass

    # Final status
    print_status(round_config, progress, suffix=suffix, start_time=start_time)

    # Print summary
    total_done = sum(p["done"] for p in progress.values())
    total_failed = sum(p["failed"] for p in progress.values())
    total_total = sum(p["total"] for p in progress.values())
    print(f"\n  Summary: {total_done}/{total_total} completed, {total_failed} failed")


# ── Verification & Formatting ─────────────────────────────────


def count_lines(path: Path) -> int:
    """Count non-empty lines in a file."""
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def count_prompts(yaml_path: Path) -> int:
    """Count prompts in an expanded YAML file."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return len(data.get("prompts", []))


def run_verify(round_config: dict, suffix: str = ""):
    """Run F# verification on applicable domains."""
    print("\n" + "=" * 60)
    print("  F# VERIFICATION")
    print("=" * 60)

    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    for job in round_config["all_jobs"]:
        output_name = job["output"]
        raw_path = RAW_DIR / f"{output_name}{suffix}.jsonl"
        verified_path = VERIFIED_DIR / f"{output_name}{suffix}.jsonl"

        if not raw_path.exists():
            print(f"  {output_name}{suffix}: raw file missing, skipping")
            continue

        # Check if this domain needs F# verification
        # Match both exact name and base name (e.g., "fsharp_core_r3" matches "fsharp_core")
        needs_verify = output_name in FSHARP_DOMAINS or any(
            output_name.startswith(d) for d in FSHARP_DOMAINS
        )

        if needs_verify:
            print(f"  {output_name}{suffix}: verifying F# samples...")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "verify_fsharp.py"),
                    "--input",
                    str(raw_path),
                    "--output",
                    str(verified_path),
                ],
                cwd=str(SCRIPT_DIR),
            )
            if result.returncode != 0:
                print(f"  {output_name}{suffix}: verification had errors")
        else:
            print(f"  {output_name}{suffix}: copying (no F# verification needed)")
            shutil.copy2(raw_path, verified_path)


def run_format():
    """Format verified data for training."""
    print("\n" + "=" * 60)
    print("  FORMATTING DATASET")
    print("=" * 60)

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "format_dataset.py"),
            "--input",
            str(VERIFIED_DIR),
            "--output",
            str(PROJECT_DIR / "data" / "formatted"),
            "--format",
            "all",
            "--split-by-length",
        ],
        cwd=str(SCRIPT_DIR),
    )


# ── CLI ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Training Data Generation Pipeline (Config-Driven)"
    )
    parser.add_argument(
        "--round-config",
        type=Path,
        required=True,
        help="Round config YAML (e.g., ../../configs/rounds/round3.yaml)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Override concurrent requests per teacher (default: from config)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Also run verification and formatting after generation",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-line logs instead of status dashboard",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Just print current progress and exit (full dashboard)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact progress summary and exit (for pasting)",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default=None,
        help="Override output file suffix (default: from config)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override temperature for all prompts (default: from config)",
    )
    args = parser.parse_args()

    if not args.round_config.exists():
        print(f"Error: Round config not found: {args.round_config}")
        sys.exit(1)

    round_config = load_round_config(args.round_config)

    # CLI overrides config values
    suffix = args.suffix if args.suffix is not None else round_config["suffix"]
    temperature = (
        args.temperature
        if args.temperature is not None
        else round_config["temperature"]
    )
    concurrency = (
        args.concurrency
        if args.concurrency is not None
        else round_config["concurrency"]
    )

    # Build progress from existing files (for --status and --summary)
    def build_progress():
        progress = {}
        for teacher, files in round_config["teachers"].items():
            for yaml_stem, output_name in files:
                yaml_path = EXPANDED_DIR / f"{yaml_stem}.yaml"
                total = count_prompts(yaml_path)
                output_path = RAW_DIR / f"{output_name}{suffix}.jsonl"
                done = count_lines(output_path)
                job_key = f"{teacher}:{yaml_stem}"
                progress[job_key] = {
                    "done": done,
                    "total": total,
                    "failed": 0,
                    "teacher": teacher,
                    "domain": yaml_stem,
                }
        return progress

    if args.status:
        print_status(round_config, build_progress(), suffix=suffix)
        return

    if args.summary:
        print_summary(round_config, build_progress(), suffix=suffix)
        return

    if args.verbose:
        logging.getLogger(__name__).setLevel(logging.INFO)

    asyncio.run(
        generate_all(
            round_config,
            concurrency,
            args.verbose,
            suffix=suffix,
            temperature=temperature,
        )
    )

    if args.verify:
        run_verify(round_config, suffix=suffix)
        run_format()

    if not args.verify:
        print("\nDone! Run with --verify to also verify F# and format the dataset.")


if __name__ == "__main__":
    main()
