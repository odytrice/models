"""
Parallel Training Data Generation Runner

Runs all 3 teachers (DeepSeek, Kimi, MiniMax) concurrently as background
processes, showing a live status dashboard instead of per-line logs.

Supports multiple passes with different temperatures via --suffix and --temperature.

Usage:
    python run_generation.py                    # Generate with status dashboard
    python run_generation.py --verify           # Generate + verify + format
    python run_generation.py --concurrency 8    # Custom concurrency per teacher
    python run_generation.py --verbose          # Show per-line logs instead of dashboard
    python run_generation.py --status           # Just print status and exit

    # Second pass at higher temperature:
    python run_generation.py --suffix _t2 --temperature 0.9 --verify
"""

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
VERIFIED_DIR = PROJECT_DIR / "data" / "verified"
EXPANDED_DIR = SCRIPT_DIR.parent / "prompts" / "expanded"

# Teacher -> list of (expanded_yaml_stem, output_name)
# Redistributed: dotnet_aspnet -> Kimi, general_coding -> MiniMax
TEACHERS = {
    "DeepSeek": [
        ("fsharp_core_expanded", "fsharp_core"),
        ("fsharp_libraries_expanded", "fsharp_libraries"),
    ],
    "Kimi": [
        ("svelte_typescript_expanded", "svelte_typescript"),
        ("cross_domain_expanded", "cross_domain"),
        ("long_context_expanded", "long_context"),
        ("dotnet_aspnet_expanded_kimi", "dotnet_aspnet"),
    ],
    "MiniMax": [
        ("docker_kubernetes_expanded", "docker_kubernetes"),
        ("agentic_swe_expanded", "agentic_swe"),
        ("general_coding_expanded_minimax", "general_coding"),
    ],
}

# All output names across all teachers (for status/verify)
ALL_OUTPUTS = [
    "fsharp_core",
    "fsharp_libraries",
    "svelte_typescript",
    "cross_domain",
    "long_context",
    "dotnet_aspnet",
    "docker_kubernetes",
    "agentic_swe",
    "general_coding",
]

# Files that need F# verification
FSHARP_DOMAINS = {"fsharp_core", "fsharp_libraries", "dotnet_aspnet", "cross_domain"}

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def count_prompts(yaml_path: Path) -> int:
    """Count prompts in an expanded YAML without loading full file."""
    import yaml

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return len(data.get("prompts", []))


def get_totals() -> dict:
    """Get prompt totals for each domain from expanded YAMLs."""
    totals = {}
    for teacher, files in TEACHERS.items():
        for yaml_stem, output_name in files:
            config = EXPANDED_DIR / f"{yaml_stem}.yaml"
            totals[output_name] = {
                "total": count_prompts(config),
                "teacher": teacher,
            }
    return totals


def print_status(totals: dict, suffix: str = "", start_time: float = None):
    """Print the status dashboard."""
    now = datetime.now()
    os.system("cls" if os.name == "nt" else "clear")

    label = f" (pass 2, temp override)" if suffix else ""
    print(f"{'=' * 65}")
    print(f"  GENERATION STATUS{label} -- {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if start_time:
        elapsed = timedelta(seconds=time.monotonic() - start_time)
        print(f"  Running for {str(elapsed).split('.')[0]}")
    if suffix:
        print(f"  Output suffix: {suffix}")
    print(f"{'=' * 65}\n")

    grand_done = 0
    grand_total = 0

    for teacher in ["DeepSeek", "Kimi", "MiniMax"]:
        files = TEACHERS[teacher]
        teacher_done = 0
        teacher_total = 0

        domains_info = []
        for yaml_stem, output_name in files:
            raw_path = RAW_DIR / f"{output_name}{suffix}.jsonl"
            total = totals[output_name]["total"]
            done = count_lines(raw_path)
            teacher_done += done
            teacher_total += total
            domains_info.append((output_name, done, total))

        teacher_pct = (teacher_done / teacher_total * 100) if teacher_total > 0 else 0
        teacher_status = "DONE" if teacher_done >= teacher_total else "RUNNING"

        print(
            f"  {teacher} ({teacher_done}/{teacher_total} - {teacher_pct:.0f}%) [{teacher_status}]"
        )
        print(f"  {'-' * 55}")

        for domain, done, total in domains_info:
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
                f"    {domain:25s} {bar} {done:5d}/{total:<5d} ({pct:5.1f}%) {status}"
            )

        print()
        grand_done += teacher_done
        grand_total += teacher_total

    grand_pct = (grand_done / grand_total * 100) if grand_total > 0 else 0
    print(f"  {'-' * 55}")
    print(f"  DISTILLED TOTAL: {grand_done:,} / {grand_total:,} ({grand_pct:.1f}%)")

    oci_path = VERIFIED_DIR / "opencode_instruct.jsonl"
    oci_count = count_lines(oci_path)
    if oci_count > 0:
        print(f"  OPENCODE INSTRUCT: {oci_count:,} samples (verified)")
    print(f"  GRAND TOTAL: {grand_done + oci_count:,} samples")

    # Estimate remaining time
    remaining = grand_total - grand_done
    if start_time and grand_done > 0:
        elapsed_s = time.monotonic() - start_time
        rate = grand_done / (elapsed_s / 60)  # samples per minute
        if rate > 0 and remaining > 0:
            eta_min = remaining / rate
            finish = now + timedelta(minutes=eta_min)
            print(f"\n  Rate: ~{rate:.1f} samples/min")
            print(f"  Remaining: {remaining:,} samples")
            print(f"  ETA: ~{finish.strftime('%Y-%m-%d %H:%M')}")

    if grand_done >= grand_total:
        print(f"\n  ** ALL GENERATION COMPLETE **")

    print(f"\n{'=' * 65}")


def build_generate_cmd(
    config: Path, output: Path, concurrency: int, temperature: float = None
) -> list:
    """Build the generate_data.py subprocess command."""
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "generate_data.py"),
        "--config",
        str(config),
        "--output",
        str(output),
        "--concurrency",
        str(concurrency),
    ]
    if temperature is not None:
        cmd.extend(["--temperature", str(temperature)])
    return cmd


async def run_generate_quiet(
    config: Path,
    output: Path,
    concurrency: int,
    label: str,
    temperature: float = None,
):
    """Run generate_data.py as a background subprocess (suppressed output)."""
    output.parent.mkdir(parents=True, exist_ok=True)

    existing = count_lines(output)
    total = count_prompts(config)
    remaining = total - existing

    if remaining <= 0:
        return

    cmd = build_generate_cmd(config, output, concurrency, temperature)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=str(SCRIPT_DIR),
    )

    await proc.wait()


async def run_generate_verbose(
    config: Path,
    output: Path,
    concurrency: int,
    label: str,
    temperature: float = None,
):
    """Run generate_data.py with live per-line output."""
    output.parent.mkdir(parents=True, exist_ok=True)

    existing = count_lines(output)
    total = count_prompts(config)
    remaining = total - existing

    if remaining <= 0:
        print(f"[{label}] Already complete ({existing}/{total} samples)")
        return

    print(f"[{label}] Starting: {remaining} remaining of {total} ({existing} done)")

    cmd = build_generate_cmd(config, output, concurrency, temperature)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(SCRIPT_DIR),
    )

    async for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            print(f"[{label:8s}] {text}")

    await proc.wait()


async def run_teacher(
    teacher: str,
    files: list,
    concurrency: int,
    verbose: bool,
    suffix: str = "",
    temperature: float = None,
):
    """Run all files for a single teacher sequentially."""
    run_fn = run_generate_verbose if verbose else run_generate_quiet

    for yaml_stem, output_name in files:
        config = EXPANDED_DIR / f"{yaml_stem}.yaml"
        output = RAW_DIR / f"{output_name}{suffix}.jsonl"
        await run_fn(
            config,
            output,
            concurrency,
            f"{teacher[:4]}:{output_name}",
            temperature=temperature,
        )


async def status_loop(
    totals: dict, start_time: float, suffix: str = "", check_interval: int = 15
):
    """Periodically refresh the status dashboard."""
    grand_total = sum(t["total"] for t in totals.values())

    while True:
        print_status(totals, suffix=suffix, start_time=start_time)
        print(
            f"  Refreshing every {check_interval}s (generation running in background)"
        )

        # Check if all done
        grand_done = sum(
            count_lines(RAW_DIR / f"{name}{suffix}.jsonl") for name in ALL_OUTPUTS
        )
        if grand_done >= grand_total:
            break

        await asyncio.sleep(check_interval)


async def generate_all(
    concurrency: int, verbose: bool, suffix: str = "", temperature: float = None
):
    """Run all 3 teachers in parallel."""
    totals = get_totals()
    start_time = time.monotonic()

    teacher_args = dict(suffix=suffix, temperature=temperature)

    if verbose:
        await asyncio.gather(
            run_teacher(
                "DeepSeek",
                TEACHERS["DeepSeek"],
                concurrency,
                verbose=True,
                **teacher_args,
            ),
            run_teacher(
                "Kimi", TEACHERS["Kimi"], concurrency, verbose=True, **teacher_args
            ),
            run_teacher(
                "MiniMax",
                TEACHERS["MiniMax"],
                concurrency,
                verbose=True,
                **teacher_args,
            ),
        )
    else:
        gen_task = asyncio.gather(
            run_teacher(
                "DeepSeek",
                TEACHERS["DeepSeek"],
                concurrency,
                verbose=False,
                **teacher_args,
            ),
            run_teacher(
                "Kimi", TEACHERS["Kimi"], concurrency, verbose=False, **teacher_args
            ),
            run_teacher(
                "MiniMax",
                TEACHERS["MiniMax"],
                concurrency,
                verbose=False,
                **teacher_args,
            ),
        )
        status_task = asyncio.create_task(
            status_loop(totals, start_time, suffix=suffix)
        )

        await gen_task
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass

        print_status(totals, suffix=suffix, start_time=start_time)


def run_verify(suffix: str = ""):
    """Run F# verification on applicable domains."""
    print("\n" + "=" * 60)
    print("  F# VERIFICATION")
    print("=" * 60)

    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    for output_name in ALL_OUTPUTS:
        raw_path = RAW_DIR / f"{output_name}{suffix}.jsonl"
        verified_path = VERIFIED_DIR / f"{output_name}{suffix}.jsonl"

        if not raw_path.exists():
            print(f"  {output_name}{suffix}: raw file missing, skipping")
            continue

        if output_name in FSHARP_DOMAINS:
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
            "chatml",
            "--split-by-length",
        ],
        cwd=str(SCRIPT_DIR),
    )


def main():
    parser = argparse.ArgumentParser(description="Parallel Training Data Generation")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=7,
        help="Concurrent requests per teacher (default: 7, 21 total across 3 teachers)",
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
        help="Just print current progress and exit",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="Suffix for output files (e.g., '_t2' for second pass)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override temperature for all prompts",
    )
    args = parser.parse_args()

    if args.status:
        totals = get_totals()
        print_status(totals, suffix=args.suffix)
        return

    asyncio.run(
        generate_all(
            args.concurrency,
            args.verbose,
            suffix=args.suffix,
            temperature=args.temperature,
        )
    )

    if args.verify:
        run_verify(suffix=args.suffix)
        run_format()

    print("\nDone! Run with --verify to also verify F# and format the dataset.")


if __name__ == "__main__":
    main()
