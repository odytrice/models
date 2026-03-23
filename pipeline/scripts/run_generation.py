"""
Parallel Training Data Generation Runner (Config-Driven)

Runs teachers concurrently as background processes, showing a live status
dashboard. Teacher assignments, suffix, temperature, and concurrency are
loaded from a round config YAML.

Usage:
    python run_generation.py --round-config ../../configs/rounds/round1.yaml
    python run_generation.py --round-config ../../configs/rounds/round2.yaml --verify
    python run_generation.py --round-config ../../configs/rounds/round2.yaml --status
    python run_generation.py --round-config ../../configs/rounds/round2.yaml --verbose

    # Override config values via CLI:
    python run_generation.py --round-config ../../configs/rounds/round2.yaml --concurrency 5 --temperature 0.85
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

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
VERIFIED_DIR = PROJECT_DIR / "data" / "verified"
EXPANDED_DIR = SCRIPT_DIR.parent / "prompts" / "expanded"

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
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return len(data.get("prompts", []))


def load_round_config(path: Path) -> dict:
    """Load a round config YAML and return structured config."""
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    teachers = {}
    all_outputs = []
    for teacher, files in config["teachers"].items():
        teachers[teacher] = [(f["yaml"], f["output"]) for f in files]
        all_outputs.extend(f["output"] for f in files)

    return {
        "description": config.get("description", ""),
        "suffix": config.get("suffix", ""),
        "temperature": config.get("temperature"),
        "concurrency": config.get("concurrency", 7),
        "teachers": teachers,
        "all_outputs": all_outputs,
    }


def get_totals(round_config: dict) -> dict:
    """Get prompt totals for each domain from expanded YAMLs."""
    totals = {}
    for teacher, files in round_config["teachers"].items():
        for yaml_stem, output_name in files:
            config_path = EXPANDED_DIR / f"{yaml_stem}.yaml"
            totals[output_name] = {
                "total": count_prompts(config_path),
                "teacher": teacher,
            }
    return totals


def print_status(
    round_config: dict, totals: dict, suffix: str = "", start_time: float = None
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

    for teacher in round_config["teachers"]:
        files = round_config["teachers"][teacher]
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
    remaining = grand_total - grand_done
    print(f"  {'-' * 55}")
    print(f"  DISTILLED TOTAL: {grand_done:,} / {grand_total:,} ({grand_pct:.1f}%)")

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
    round_config: dict,
    totals: dict,
    start_time: float,
    suffix: str = "",
    check_interval: int = 15,
):
    """Periodically refresh the status dashboard."""
    grand_total = sum(t["total"] for t in totals.values())

    while True:
        print_status(round_config, totals, suffix=suffix, start_time=start_time)
        print(
            f"  Refreshing every {check_interval}s (generation running in background)"
        )

        grand_done = sum(
            count_lines(RAW_DIR / f"{name}{suffix}.jsonl")
            for name in round_config["all_outputs"]
        )
        if grand_done >= grand_total:
            break

        await asyncio.sleep(check_interval)


async def generate_all(
    round_config: dict,
    concurrency: int,
    verbose: bool,
    suffix: str = "",
    temperature: float = None,
):
    """Run all teachers in parallel."""
    totals = get_totals(round_config)
    start_time = time.monotonic()

    teacher_args = dict(suffix=suffix, temperature=temperature)

    if verbose:
        tasks = [
            run_teacher(teacher, files, concurrency, verbose=True, **teacher_args)
            for teacher, files in round_config["teachers"].items()
        ]
        await asyncio.gather(*tasks)
    else:
        gen_tasks = [
            run_teacher(teacher, files, concurrency, verbose=False, **teacher_args)
            for teacher, files in round_config["teachers"].items()
        ]
        gen_task = asyncio.gather(*gen_tasks)
        status_task = asyncio.create_task(
            status_loop(round_config, totals, start_time, suffix=suffix)
        )

        await gen_task
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass

        print_status(round_config, totals, suffix=suffix, start_time=start_time)


def run_verify(round_config: dict, suffix: str = ""):
    """Run F# verification on applicable domains."""
    print("\n" + "=" * 60)
    print("  F# VERIFICATION")
    print("=" * 60)

    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    for output_name in round_config["all_outputs"]:
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
        "--round-config",
        type=Path,
        required=True,
        help="Round config YAML (e.g., ../../configs/rounds/round2.yaml)",
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
        help="Just print current progress and exit",
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

    # Load round config
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

    if args.status:
        totals = get_totals(round_config)
        print_status(round_config, totals, suffix=suffix)
        return

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

    print("\nDone! Run with --verify to also verify F# and format the dataset.")


if __name__ == "__main__":
    main()
