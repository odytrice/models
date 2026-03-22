"""
F# Teacher Benchmark Runner

Runs Kimi and MiniMax on the same prompts that DeepSeek failed on,
then verifies and compares pass rates across all 3 teachers.

Usage:
    python run_benchmark.py                     # Status dashboard mode
    python run_benchmark.py --verbose           # Per-line logs
    python run_benchmark.py --verify-only       # Skip generation, just verify + compare
    python run_benchmark.py --concurrency 5     # Custom concurrency
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

# Benchmark files: (yaml_stem, output_name, teacher, domain)
BENCHMARK_FILES = [
    ("fsharp_core_kimi", "fsharp_core_kimi", "Kimi", "fsharp_core"),
    ("fsharp_core_minimax", "fsharp_core_minimax", "MiniMax", "fsharp_core"),
    ("fsharp_libraries_kimi", "fsharp_libraries_kimi", "Kimi", "fsharp_libraries"),
    (
        "fsharp_libraries_minimax",
        "fsharp_libraries_minimax",
        "MiniMax",
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


async def run_generate(
    config: Path, output: Path, concurrency: int, label: str, verbose: bool
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


async def run_teacher(teacher: str, files: list, concurrency: int, verbose: bool):
    """Run all benchmark files for a single teacher sequentially."""
    for yaml_stem, output_name, _, domain in files:
        config = BENCHMARK_DIR / f"{yaml_stem}.yaml"
        output = RAW_DIR / f"{output_name}.jsonl"
        label = f"{teacher}:{domain}"
        await run_generate(config, output, concurrency, label, verbose)


def print_status(start_time: float = None):
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

    for yaml_stem, output_name, teacher, domain in BENCHMARK_FILES:
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
            now = datetime.now()
            finish = now + timedelta(minutes=eta_min)
            print(f"  Rate: ~{rate:.1f} samples/min")
            print(f"  Remaining: {remaining} samples")
            print(f"  ETA: ~{finish.strftime('%Y-%m-%d %H:%M')}")

    if grand_done >= grand_total:
        print(f"\n  ** BENCHMARK GENERATION COMPLETE **")

    print(f"\n{'=' * 65}")


async def status_loop(start_time: float, check_interval: int = 15):
    """Refresh status dashboard periodically."""
    while True:
        print_status(start_time)
        print(f"  Refreshing every {check_interval}s")

        all_done = True
        for yaml_stem, output_name, _, _ in BENCHMARK_FILES:
            config = BENCHMARK_DIR / f"{yaml_stem}.yaml"
            output = RAW_DIR / f"{output_name}.jsonl"
            if count_lines(output) < count_prompts(config):
                all_done = False
                break
        if all_done:
            break

        await asyncio.sleep(check_interval)


async def generate_all(concurrency: int, verbose: bool):
    """Run both teachers in parallel."""
    start_time = time.monotonic()

    kimi_files = [f for f in BENCHMARK_FILES if f[2] == "Kimi"]
    minimax_files = [f for f in BENCHMARK_FILES if f[2] == "MiniMax"]

    if verbose:
        await asyncio.gather(
            run_teacher("Kimi", kimi_files, concurrency, verbose=True),
            run_teacher("MiniMax", minimax_files, concurrency, verbose=True),
        )
    else:
        gen_task = asyncio.gather(
            run_teacher("Kimi", kimi_files, concurrency, verbose=False),
            run_teacher("MiniMax", minimax_files, concurrency, verbose=False),
        )
        status_task = asyncio.create_task(status_loop(start_time))

        await gen_task
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass

        print_status(start_time)

    elapsed = time.monotonic() - start_time
    log.info(f"Generation complete in {elapsed / 3600:.1f}h")


def run_verify():
    """Verify all benchmark outputs."""
    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("VERIFYING BENCHMARK RESULTS")
    log.info("=" * 60)

    for yaml_stem, output_name, teacher, domain in BENCHMARK_FILES:
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


def print_comparison():
    """Print the final comparison table."""
    print("\n" + "=" * 75)
    print("  F# TEACHER BENCHMARK RESULTS")
    print("=" * 75)

    # Load original DeepSeek results for comparison
    original_results = {}
    for domain in ["fsharp_core", "fsharp_libraries"]:
        verified_path = PROJECT_DIR / "data" / "verified" / f"{domain}.jsonl"
        if verified_path.exists():
            stats = {
                "pass": 0,
                "compile_error": 0,
                "runtime_error": 0,
                "skipped": 0,
                "total": 0,
            }
            with open(verified_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    s = json.loads(line)
                    status = s["verify_result"]["status"]
                    stats[status] = stats.get(status, 0) + 1
                    stats["total"] += 1
            original_results[domain] = stats

    # Load benchmark results
    benchmark_results = {}
    for yaml_stem, output_name, teacher, domain in BENCHMARK_FILES:
        verified_path = VERIFIED_DIR / f"{output_name}.jsonl"
        if not verified_path.exists():
            continue

        stats = {
            "pass": 0,
            "compile_error": 0,
            "runtime_error": 0,
            "skipped": 0,
            "total": 0,
        }
        with open(verified_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                s = json.loads(line)
                status = s["verify_result"]["status"]
                stats[status] = stats.get(status, 0) + 1
                stats["total"] += 1

        benchmark_results[output_name] = {
            "teacher": teacher,
            "domain": domain,
            "stats": stats,
        }

    # Print results per domain
    for domain in ["fsharp_core", "fsharp_libraries"]:
        orig = original_results.get(domain, {})
        failed_count = (
            orig.get("compile_error", 0)
            + orig.get("runtime_error", 0)
            + orig.get("skipped", 0)
        )
        passed_count = orig.get("pass", 0)
        total = orig.get("total", 0)

        print(f"\n  {domain} ({failed_count} prompts that DeepSeek failed on)")
        print(f"  {'-' * 65}")
        print(
            f"  {'Teacher':12s} {'Passed':>8s} {'Compile Err':>12s} {'Skipped':>10s} {'Pass Rate':>10s}"
        )
        print(f"  {'-' * 65}")

        # DeepSeek original (these all failed by definition)
        print(
            f"  {'DeepSeek':12s} {'0':>8s} {orig.get('compile_error', 0) + orig.get('runtime_error', 0):>12d} {orig.get('skipped', 0):>10d} {'0.0%':>10s}"
        )

        # Kimi and MiniMax benchmark results
        for teacher_name in ["Kimi", "MiniMax"]:
            key = f"{domain}_{teacher_name.lower()}"
            if key in benchmark_results:
                r = benchmark_results[key]["stats"]
                pass_rate = (r["pass"] / r["total"] * 100) if r["total"] > 0 else 0
                errors = r.get("compile_error", 0) + r.get("runtime_error", 0)
                print(
                    f"  {teacher_name:12s} {r['pass']:>8d} {errors:>12d} "
                    f"{r.get('skipped', 0):>10d} {pass_rate:>9.1f}%"
                )

    # Summary
    print(f"\n  {'=' * 65}")
    print(f"  SUMMARY: Best teacher for each domain")
    print(f"  {'-' * 65}")

    for domain in ["fsharp_core", "fsharp_libraries"]:
        best_teacher = "DeepSeek"
        best_rate = 0

        for teacher_name in ["Kimi", "MiniMax"]:
            key = f"{domain}_{teacher_name.lower()}"
            if key in benchmark_results:
                r = benchmark_results[key]["stats"]
                rate = (r["pass"] / r["total"] * 100) if r["total"] > 0 else 0
                if rate > best_rate:
                    best_rate = rate
                    best_teacher = teacher_name

        print(
            f"  {domain:25s} -> {best_teacher} ({best_rate:.1f}% pass rate on DeepSeek's failures)"
        )

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
    args = parser.parse_args()

    if not args.verify_only:
        asyncio.run(generate_all(args.concurrency, args.verbose))

    run_verify()
    print_comparison()


if __name__ == "__main__":
    main()
