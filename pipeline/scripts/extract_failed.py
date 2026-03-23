"""
Extract failed/skipped prompts from F# verification results
and create benchmark YAML files for teacher comparison.

Usage:
    python extract_failed.py                    # All teachers (kimi, minimax, glm5)
    python extract_failed.py --teachers glm5    # GLM-5 only
"""

import argparse
import json
import yaml
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
VERIFIED_DIR = PROJECT_DIR / "data" / "verified"
EXPANDED_DIR = Path(__file__).resolve().parent.parent / "prompts" / "expanded"
BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "prompts" / "benchmark"


def load_expanded_yaml(path: Path) -> dict:
    """Load an expanded YAML file and return a dict of id -> prompt."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "system_prompt": data.get("system_prompt", ""),
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 4096),
        "prompts": {p["id"]: p for p in data.get("prompts", [])},
    }


def extract_failed_ids(verified_path: Path) -> list[str]:
    """Extract IDs of failed/skipped samples from a verified JSONL file."""
    failed_ids = []
    with open(verified_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sample = json.loads(line)
            status = sample.get("verify_result", {}).get("status", "")
            if status in ("compile_error", "runtime_error", "skipped"):
                failed_ids.append(sample["id"])
    return failed_ids


def create_benchmark_yaml(
    failed_ids: list[str],
    expanded_data: dict,
    teacher: str,
    domain: str,
    output_path: Path,
):
    """Create a benchmark YAML file with failed prompts reassigned to a new teacher."""
    prompts = []
    for fid in failed_ids:
        if fid in expanded_data["prompts"]:
            prompt = expanded_data["prompts"][fid].copy()
            prompts.append(prompt)

    benchmark = {
        "teacher": teacher,
        "domain": domain,
        "system_prompt": expanded_data["system_prompt"],
        "temperature": expanded_data["temperature"],
        "max_tokens": expanded_data["max_tokens"],
        "prompts": prompts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(benchmark, f, default_flow_style=False, allow_unicode=True, width=120)

    log.info(f"Created {output_path.name}: {len(prompts)} prompts, teacher={teacher}")
    return len(prompts)


def main():
    parser = argparse.ArgumentParser(description="Extract failed prompts for benchmark")
    parser.add_argument(
        "--teachers",
        nargs="+",
        default=["kimi", "minimax", "glm5"],
        help="Teachers to create benchmark YAMLs for (default: kimi minimax glm5)",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("EXTRACTING FAILED PROMPTS FOR BENCHMARK")
    log.info(f"Teachers: {args.teachers}")
    log.info("=" * 60)

    # Domain configs: name, verified path, expanded yaml path
    domains = [
        {
            "name": "fsharp_core",
            "verified": VERIFIED_DIR / "fsharp_core.jsonl",
            "expanded": EXPANDED_DIR / "fsharp_core_expanded.yaml",
        },
        {
            "name": "fsharp_libraries",
            "verified": VERIFIED_DIR / "fsharp_libraries.jsonl",
            "expanded": EXPANDED_DIR / "fsharp_libraries_expanded.yaml",
        },
        {
            "name": "dotnet_aspnet",
            "verified": VERIFIED_DIR / "dotnet_aspnet.jsonl",
            "expanded": EXPANDED_DIR / "dotnet_aspnet_expanded_kimi.yaml",
        },
    ]

    total_prompts = 0

    for domain in domains:
        if not domain["verified"].exists():
            log.warning(f"Verified file not found: {domain['verified']}, skipping")
            continue

        log.info(f"\nDomain: {domain['name']}")

        # Extract failed IDs
        failed_ids = extract_failed_ids(domain["verified"])
        log.info(f"  Failed/skipped: {len(failed_ids)} samples")

        if not failed_ids:
            log.info(f"  No failures, skipping")
            continue

        # Load original expanded prompts
        expanded = load_expanded_yaml(domain["expanded"])
        log.info(f"  Original prompts loaded: {len(expanded['prompts'])}")

        # Create benchmark YAMLs for each requested teacher
        for teacher in args.teachers:
            output = BENCHMARK_DIR / f"{domain['name']}_{teacher}.yaml"
            count = create_benchmark_yaml(
                failed_ids, expanded, teacher, domain["name"], output
            )
            total_prompts += count

    log.info(f"\n{'=' * 60}")
    log.info(f"BENCHMARK FILES CREATED")
    log.info(f"  Total prompts: {total_prompts}")
    log.info(f"  Teachers: {args.teachers}")
    log.info(f"  Output: {BENCHMARK_DIR}")
    log.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
