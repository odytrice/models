"""
F# Teacher Benchmark Runner

Runs teacher models on prompts that the original teacher failed on,
then verifies and compares pass rates across all teachers.

Supports running specific teachers via --teachers flag.
Supports multiple providers via --provider flag (default, ollama_cloud, xeon_ai).

Set OLLAMA_API_KEY env var for Ollama Cloud authentication.

Usage:
    python run_benchmark.py                         # Run all pending benchmarks
    python run_benchmark.py --teachers glm5         # Run GLM-5 only
    python run_benchmark.py --teachers kimi26 glm51 # Run K2.6 and GLM-5.1
    python run_benchmark.py --verbose               # Per-line logs
    python run_benchmark.py --verify-only           # Skip generation, just verify + compare
    python run_benchmark.py --compare-only          # Just print comparison table
    python run_benchmark.py --concurrency 5         # Custom concurrency
    python run_benchmark.py --provider xeon_ai      # Route all teachers through Xeon-AI
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw" / "benchmark"
VERIFIED_DIR = PROJECT_DIR / "data" / "verified" / "benchmark"
BENCHMARK_DIR = SCRIPT_DIR.parent / "prompts" / "benchmark"
MAIN_VERIFIED_DIR = PROJECT_DIR / "data" / "verified"

# All benchmark files: (yaml_stem, output_name, teacher, domain)
ALL_BENCHMARK_FILES = [
    # Kimi K2.5 benchmarks (from previous run)
    ("fsharp_core_kimi", "fsharp_core_kimi", "Kimi", "fsharp_core"),
    ("fsharp_libraries_kimi", "fsharp_libraries_kimi", "Kimi", "fsharp_libraries"),
    # MiniMax benchmarks (from previous run)
    ("fsharp_core_minimax", "fsharp_core_minimax", "MiniMax", "fsharp_core"),
    (
        "fsharp_libraries_minimax",
        "fsharp_libraries_minimax",
        "MiniMax",
        "fsharp_libraries",
    ),
    # GLM-5 benchmarks (from previous run)
    ("fsharp_core_glm5", "fsharp_core_glm5", "GLM-5", "fsharp_core"),
    ("fsharp_libraries_glm5", "fsharp_libraries_glm5", "GLM-5", "fsharp_libraries"),
    # Kimi K2.6 benchmarks (new)
    ("fsharp_core_kimi26", "fsharp_core_kimi26", "Kimi-K2.6", "fsharp_core"),
    (
        "fsharp_libraries_kimi26",
        "fsharp_libraries_kimi26",
        "Kimi-K2.6",
        "fsharp_libraries",
    ),
    # GLM-5.1 benchmarks (new)
    ("fsharp_core_glm51", "fsharp_core_glm51", "GLM-5.1", "fsharp_core"),
    (
        "fsharp_libraries_glm51",
        "fsharp_libraries_glm51",
        "GLM-5.1",
        "fsharp_libraries",
    ),
    # Qwen 3.6 27B benchmarks (self-hosted Xeon-AI)
    ("fsharp_core_qwen36_27b", "fsharp_core_qwen36_27b", "Qwen3.6-27B", "fsharp_core"),
    (
        "fsharp_libraries_qwen36_27b",
        "fsharp_libraries_qwen36_27b",
        "Qwen3.6-27B",
        "fsharp_libraries",
    ),
    # Qwen 3.6 35B benchmarks (self-hosted Xeon-AI)
    ("fsharp_core_qwen36_35b", "fsharp_core_qwen36_35b", "Qwen3.6-35B", "fsharp_core"),
    (
        "fsharp_libraries_qwen36_35b",
        "fsharp_libraries_qwen36_35b",
        "Qwen3.6-35B",
        "fsharp_libraries",
    ),
    # Gemma 4 26B benchmarks (self-hosted Xeon-AI)
    ("fsharp_core_gemma4_26b", "fsharp_core_gemma4_26b", "Gemma4-26B", "fsharp_core"),
    (
        "fsharp_libraries_gemma4_26b",
        "fsharp_libraries_gemma4_26b",
        "Gemma4-26B",
        "fsharp_libraries",
    ),
    # Gemma 4 31B benchmarks (self-hosted Xeon-AI)
    ("fsharp_core_gemma4_31b", "fsharp_core_gemma4_31b", "Gemma4-31B", "fsharp_core"),
    (
        "fsharp_libraries_gemma4_31b",
        "fsharp_libraries_gemma4_31b",
        "Gemma4-31B",
        "fsharp_libraries",
    ),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def count_prompts(yaml_path: Path) -> int:
    import yaml

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return len(data.get("prompts", []))


def get_benchmark_files(teachers: list[str] = None) -> list[tuple]:
    """Get benchmark files, optionally filtered by teacher."""
    if teachers is None:
        return ALL_BENCHMARK_FILES
    teacher_map = {
        "kimi": "Kimi",
        "kimi26": "Kimi-K2.6",
        "minimax": "MiniMax",
        "glm5": "GLM-5",
        "glm51": "GLM-5.1",
        "qwen36_27b": "Qwen3.6-27B",
        "qwen36_35b": "Qwen3.6-35B",
        "gemma4_26b": "Gemma4-26B",
        "gemma4_31b": "Gemma4-31B",
    }
    teacher_names = {teacher_map.get(t, t) for t in teachers}
    return [f for f in ALL_BENCHMARK_FILES if f[2] in teacher_names]


async def run_generate(
    config: Path, output: Path, concurrency: int, label: str, verbose: bool, provider: str = "default"
):
    """Run generate_data.py on a benchmark YAML."""
    output.parent.mkdir(parents=True, exist_ok=True)

    existing = count_lines(output)
    total = count_prompts(config)
    remaining = total - existing

    if remaining <= 0:
        log.info(f"[{label}] Already complete ({existing}/{total})")
        return

    log.info(f"[{label}] Starting: {remaining} remaining of {total} ({existing} done)")

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "generate_data.py"),
        "--config",
        str(config),
        "--output",
        str(output),
        "--concurrency",
        str(concurrency),
        "--progress-every",
        "1",
        "--provider",
        provider,
    ]

    if verbose:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(SCRIPT_DIR),
        )
        async for line in proc.stdout:
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                print(f"[{label:20s}] {text}")
    else:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=str(SCRIPT_DIR),
        )

    await proc.wait()
    final = count_lines(output)
    log.info(f"[{label}] Done: {final} samples")


async def run_teacher_files(teacher: str, files: list, concurrency: int, verbose: bool, provider: str = "default"):
    """Run all benchmark files for a single teacher sequentially."""
    for yaml_stem, output_name, _, domain in files:
        config = BENCHMARK_DIR / f"{yaml_stem}.yaml"
        output = RAW_DIR / f"{output_name}.jsonl"
        label = f"{teacher}:{domain}"
        await run_generate(config, output, concurrency, label, verbose, provider=provider)


def print_status(benchmark_files: list, start_time: float = None):
    """Print benchmark status dashboard."""
    now = datetime.now()
    os.system("cls" if os.name == "nt" else "clear")

    print(f"{'=' * 65}")
    print(f"  F# TEACHER BENCHMARK -- {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if start_time:
        elapsed = timedelta(seconds=time.monotonic() - start_time)
        print(f"  Running for {str(elapsed).split('.')[0]}")
    print(f"{'=' * 65}\n")

    grand_done = 0
    grand_total = 0

    for yaml_stem, output_name, teacher, domain in benchmark_files:
        config = BENCHMARK_DIR / f"{yaml_stem}.yaml"
        output = RAW_DIR / f"{output_name}.jsonl"
        total = count_prompts(config)
        done = count_lines(output)
        grand_done += done
        grand_total += total
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

        print(
            f"  {teacher:8s} {domain:20s} {bar} {done:4d}/{total:<4d} ({pct:5.1f}%) {status}"
        )

    grand_pct = (grand_done / grand_total * 100) if grand_total > 0 else 0
    remaining = grand_total - grand_done
    print(f"\n  {'-' * 55}")
    print(f"  Total: {grand_done}/{grand_total} ({grand_pct:.1f}%)")

    if start_time and grand_done > 0:
        elapsed_s = time.monotonic() - start_time
        rate = grand_done / (elapsed_s / 60)
        if rate > 0 and remaining > 0:
            eta_min = remaining / rate
            finish = now + timedelta(minutes=eta_min)
            print(f"  Rate: ~{rate:.1f} samples/min")
            print(f"  Remaining: {remaining} samples")
            print(f"  ETA: ~{finish.strftime('%Y-%m-%d %H:%M')}")

    if grand_done >= grand_total:
        print(f"\n  ** BENCHMARK GENERATION COMPLETE **")

    print(f"\n{'=' * 65}")


async def status_loop(
    benchmark_files: list, start_time: float, check_interval: int = 15
):
    """Refresh status dashboard periodically."""
    while True:
        print_status(benchmark_files, start_time)
        print(f"  Refreshing every {check_interval}s")

        all_done = True
        for yaml_stem, output_name, _, _ in benchmark_files:
            config = BENCHMARK_DIR / f"{yaml_stem}.yaml"
            output = RAW_DIR / f"{output_name}.jsonl"
            if count_lines(output) < count_prompts(config):
                all_done = False
                break
        if all_done:
            break

        await asyncio.sleep(check_interval)


async def generate_all(benchmark_files: list, concurrency: int, verbose: bool, provider: str = "default"):
    """Run all teachers in parallel."""
    start_time = time.monotonic()

    # Group files by teacher
    teacher_groups = {}
    for f in benchmark_files:
        teacher = f[2]
        if teacher not in teacher_groups:
            teacher_groups[teacher] = []
        teacher_groups[teacher].append(f)

    if verbose:
        tasks = [
            run_teacher_files(teacher, files, concurrency, verbose=True, provider=provider)
            for teacher, files in teacher_groups.items()
        ]
        await asyncio.gather(*tasks)
    else:
        gen_tasks = [
            run_teacher_files(teacher, files, concurrency, verbose=False, provider=provider)
            for teacher, files in teacher_groups.items()
        ]
        gen_task = asyncio.gather(*gen_tasks)
        status_task = asyncio.create_task(status_loop(benchmark_files, start_time))

        await gen_task
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass

        print_status(benchmark_files, start_time)

    elapsed = time.monotonic() - start_time
    log.info(f"Generation complete in {elapsed / 3600:.1f}h")


def run_verify(benchmark_files: list):
    """Verify all benchmark outputs."""
    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("VERIFYING BENCHMARK RESULTS")
    log.info("=" * 60)

    for yaml_stem, output_name, teacher, domain in benchmark_files:
        raw_path = RAW_DIR / f"{output_name}.jsonl"
        verified_path = VERIFIED_DIR / f"{output_name}.jsonl"

        if not raw_path.exists():
            log.warning(f"  {output_name}: raw file missing, skipping")
            continue

        log.info(f"  Verifying {output_name}...")
        subprocess.run(
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


def load_verified_stats(path: Path) -> dict:
    """Load verification stats from a verified JSONL file."""
    stats = {
        "pass": 0,
        "compile_error": 0,
        "runtime_error": 0,
        "skipped": 0,
        "total": 0,
    }
    if not path.exists():
        return stats
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            s = json.loads(line)
            status = s.get("verify_result", {}).get("status", "unknown")
            stats[status] = stats.get(status, 0) + 1
            stats["total"] += 1
    return stats


def load_passing_ids(path: Path) -> set:
    """Load IDs of passing samples from a verified JSONL file."""
    ids = set()
    if not path.exists():
        return ids
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            s = json.loads(line)
            if s.get("verify_result", {}).get("status") == "pass":
                ids.add(s["id"])
    return ids


def print_comparison():
    """Print the full comparison table across all teachers."""
    print("\n" + "=" * 75)
    print("  F# TEACHER BENCHMARK RESULTS")
    print("=" * 75)

    # Domains to compare
    domains = {
        "fsharp_core": {
            "original_teacher": "DeepSeek",
            "original_verified": MAIN_VERIFIED_DIR / "fsharp_core.jsonl",
            "benchmark_teachers": ["Kimi", "Kimi-K2.6", "MiniMax", "GLM-5", "GLM-5.1", "Qwen3.6-27B", "Qwen3.6-35B", "Gemma4-26B", "Gemma4-31B"],
        },
        "fsharp_libraries": {
            "original_teacher": "DeepSeek",
            "original_verified": MAIN_VERIFIED_DIR / "fsharp_libraries.jsonl",
            "benchmark_teachers": ["Kimi", "Kimi-K2.6", "MiniMax", "GLM-5", "GLM-5.1", "Qwen3.6-27B", "Qwen3.6-35B", "Gemma4-26B", "Gemma4-31B"],
        },
    }

    teacher_file_map = {
        "Kimi": "kimi",
        "Kimi-K2.6": "kimi26",
        "MiniMax": "minimax",
        "GLM-5": "glm5",
        "GLM-5.1": "glm51",
        "Qwen3.6-27B": "qwen36_27b",
        "Qwen3.6-35B": "qwen36_35b",
        "Gemma4-26B": "gemma4_26b",
        "Gemma4-31B": "gemma4_31b",
    }

    for domain, config in domains.items():
        # Load original results
        orig_stats = load_verified_stats(config["original_verified"])
        failed_count = (
            orig_stats["compile_error"]
            + orig_stats["runtime_error"]
            + orig_stats["skipped"]
        )

        print(
            f"\n  {domain} ({failed_count} prompts that {config['original_teacher']} failed on)"
        )
        print(f"  {'-' * 65}")
        print(
            f"  {'Teacher':12s} {'Passed':>8s} {'Compile Err':>12s} {'Skipped':>10s} {'Pass Rate':>10s}"
        )
        print(f"  {'-' * 65}")

        # Original teacher (these all failed by definition)
        orig_errors = orig_stats.get("compile_error", 0) + orig_stats.get(
            "runtime_error", 0
        )
        print(
            f"  {config['original_teacher']:12s} {'0':>8s} {orig_errors:>12d} "
            f"{orig_stats.get('skipped', 0):>10d} {'0.0%':>10s}"
        )

        # Benchmark teachers
        for teacher_name in config["benchmark_teachers"]:
            teacher_key = teacher_file_map[teacher_name]
            verified_path = VERIFIED_DIR / f"{domain}_{teacher_key}.jsonl"
            r = load_verified_stats(verified_path)

            if r["total"] > 0:
                pass_rate = r["pass"] / r["total"] * 100
                errors = r.get("compile_error", 0) + r.get("runtime_error", 0)
                print(
                    f"  {teacher_name:12s} {r['pass']:>8d} {errors:>12d} "
                    f"{r.get('skipped', 0):>10d} {pass_rate:>9.1f}%"
                )
            else:
                print(f"  {teacher_name:12s} {'(no data)':>8s}")

    # Cross-teacher overlap analysis for fsharp_core and fsharp_libraries
    print(f"\n  {'=' * 65}")
    print(f"  OVERLAP ANALYSIS (best-of-all-teachers)")
    print(f"  {'-' * 65}")

    for domain in ["fsharp_core", "fsharp_libraries"]:
        # Load passing IDs from each teacher's benchmark
        passing = {}
        for teacher_name, teacher_key in teacher_file_map.items():
            verified_path = VERIFIED_DIR / f"{domain}_{teacher_key}.jsonl"
            passing[teacher_name] = load_passing_ids(verified_path)

        # Combined: any teacher passes
        all_ids = set()
        for ids in passing.values():
            all_ids |= ids

        # Original passing
        orig_passing = load_passing_ids(MAIN_VERIFIED_DIR / f"{domain}.jsonl")
        orig_stats = load_verified_stats(MAIN_VERIFIED_DIR / f"{domain}.jsonl")
        total = orig_stats["total"]

        combined_total = len(orig_passing) + len(all_ids)

        # Per-teacher exclusive wins
        exclusive = {}
        for teacher_name, ids in passing.items():
            others = set()
            for other_name, other_ids in passing.items():
                if other_name != teacher_name:
                    others |= other_ids
            exclusive[teacher_name] = ids - others

        print(f"\n  {domain} ({total} total prompts):")
        print(
            f"    Original ({domains[domain]['original_teacher']}): {len(orig_passing)} passed"
        )
        for teacher_name in ["Kimi", "Kimi-K2.6", "MiniMax", "GLM-5", "GLM-5.1", "Qwen3.6-27B", "Qwen3.6-35B", "Gemma4-26B", "Gemma4-31B"]:
            if teacher_name in passing and passing[teacher_name]:
                print(
                    f"    + {teacher_name}: {len(passing[teacher_name])} passed "
                    f"({len(exclusive[teacher_name])} exclusive)"
                )
        print(
            f"    = Combined: {combined_total}/{total} ({combined_total / total * 100:.1f}%)"
        )

    # Summary
    print(f"\n  {'=' * 65}")
    print(f"  SUMMARY: Best teacher per domain for Round 2")
    print(f"  {'-' * 65}")

    for domain in ["fsharp_core", "fsharp_libraries"]:
        best_teacher = None
        best_rate = 0
        for teacher_name, teacher_key in teacher_file_map.items():
            verified_path = VERIFIED_DIR / f"{domain}_{teacher_key}.jsonl"
            r = load_verified_stats(verified_path)
            if r["total"] > 0:
                rate = r["pass"] / r["total"] * 100
                if rate > best_rate:
                    best_rate = rate
                    best_teacher = teacher_name
        if best_teacher:
            print(f"  {domain:25s} -> {best_teacher} ({best_rate:.1f}%)")

    print(f"\n{'=' * 75}\n")


def main():
    parser = argparse.ArgumentParser(description="F# Teacher Benchmark")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=7,
        help="Concurrent requests per teacher (default: 7)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-line logs instead of status dashboard",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip generation, just verify existing data and print comparison",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Skip generation and verification, just print comparison table",
    )
    parser.add_argument(
        "--teachers",
        nargs="+",
        default=None,
        help="Run specific teachers only (e.g., --teachers glm5)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="default",
        choices=["default", "ollama_cloud", "xeon_ai"],
        help="Override provider for all teachers (default: use teacher's default provider)",
    )
    args = parser.parse_args()

    benchmark_files = get_benchmark_files(args.teachers)

    if args.compare_only:
        print_comparison()
        return

    if not args.verify_only:
        asyncio.run(generate_all(benchmark_files, args.concurrency, args.verbose, provider=args.provider))

    run_verify(benchmark_files)
    print_comparison()


if __name__ == "__main__":
    main()
