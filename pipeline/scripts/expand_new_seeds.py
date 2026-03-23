"""
Expand only new seed prompts (round 3 curriculum gap fills).

Extracts seeds added after the original set, expands them via teachers,
and creates teacher-specific expanded YAMLs for round 3 generation.

Usage:
    python expand_new_seeds.py --variations 30 --concurrency 3
    python expand_new_seeds.py --dry-run  # Show which seeds would be expanded
"""

import argparse
import yaml
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SCRIPT_DIR.parent / "prompts"
EXPANDED_DIR = PROMPTS_DIR / "expanded"

# New seeds added in round 3 (by ID prefix range)
NEW_SEEDS = {
    "fsharp_core": {
        "file": "fsharp_core.yaml",
        "new_ids": [f"fsharp_core_{i:04d}" for i in range(26, 32)],  # 0026-0031
        "teacher": "minimax",
        "output": "fsharp_core_r3_minimax",
    },
    "fsharp_libraries": {
        "file": "fsharp_libraries.yaml",
        "new_ids": [f"fsharp_lib_{i:04d}" for i in range(33, 42)],  # 0033-0041
        "teacher": "minimax",
        "output": "fsharp_libraries_r3_minimax",
    },
    "dotnet_aspnet": {
        "file": "dotnet_aspnet.yaml",
        "new_ids": [f"dotnet_{i:04d}" for i in range(16, 21)],  # 0016-0020
        "teacher": "glm5",
        "output": "dotnet_aspnet_r3_glm5",
    },
}


def extract_new_seeds(source_path: Path, new_ids: list[str]) -> dict:
    """Extract only the new seeds from a YAML file."""
    with open(source_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    new_prompts = [p for p in data["prompts"] if p["id"] in set(new_ids)]

    return {
        "system_prompt": data["system_prompt"],
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 4096),
        "domain": data["domain"],
        "prompts": new_prompts,
    }


def create_seed_yaml(data: dict, teacher: str, output_name: str) -> Path:
    """Create a seed YAML with only the new prompts and the specified teacher."""
    output = {
        "teacher": teacher,
        "domain": data["domain"],
        "system_prompt": data["system_prompt"],
        "temperature": data["temperature"],
        "max_tokens": data["max_tokens"],
        "prompts": data["prompts"],
    }

    # Write to a temporary seed file for expansion
    seed_path = PROMPTS_DIR / f"{output_name}_seeds.yaml"
    with open(seed_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, default_flow_style=False, allow_unicode=True, width=120)

    return seed_path


def main():
    parser = argparse.ArgumentParser(description="Expand new round 3 seeds")
    parser.add_argument(
        "--variations",
        type=int,
        default=30,
        help="Number of variations per seed (default: 30)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Concurrency for expansion (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which seeds would be expanded without running",
    )
    parser.add_argument(
        "--with-docs",
        action="store_true",
        help="Fetch docs for context during expansion",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("ROUND 3 SEED EXPANSION")
    log.info("=" * 60)

    total_seeds = 0
    total_expected = 0

    for domain, config in NEW_SEEDS.items():
        source = PROMPTS_DIR / config["file"]
        data = extract_new_seeds(source, config["new_ids"])
        found = len(data["prompts"])
        expected_expanded = found * args.variations

        log.info(f"\n  {domain}:")
        log.info(f"    Source: {config['file']}")
        log.info(
            f"    New seeds: {found} (IDs: {config['new_ids'][0]} - {config['new_ids'][-1]})"
        )
        log.info(f"    Teacher: {config['teacher']}")
        log.info(f"    Expected expanded: ~{expected_expanded}")

        for p in data["prompts"]:
            log.info(f"      {p['id']}: {p['instruction'][:80].strip()}...")

        total_seeds += found
        total_expected += expected_expanded

    log.info(
        f"\n  TOTAL: {total_seeds} new seeds -> ~{total_expected} expanded prompts"
    )

    if args.dry_run:
        log.info("\n  DRY RUN -- no expansion performed")
        return

    # Create seed YAMLs and expand each
    for domain, config in NEW_SEEDS.items():
        source = PROMPTS_DIR / config["file"]
        data = extract_new_seeds(source, config["new_ids"])

        if not data["prompts"]:
            log.warning(f"  {domain}: No new seeds found, skipping")
            continue

        # Create seed YAML
        seed_path = create_seed_yaml(data, config["teacher"], config["output"])
        log.info(f"\n  Expanding {domain} ({len(data['prompts'])} seeds)...")

        # Run expand_prompts.py on the seed file
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "expand_prompts.py"),
            "--input",
            str(seed_path),
            "--output",
            str(EXPANDED_DIR / f"{config['output']}.yaml"),
            "--variations",
            str(args.variations),
            "--concurrency",
            str(args.concurrency),
        ]
        if args.with_docs:
            cmd.append("--with-docs")

        result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))

        if result.returncode != 0:
            log.error(f"  {domain}: Expansion failed with code {result.returncode}")
        else:
            # Verify the expanded file
            expanded_path = EXPANDED_DIR / f"{config['output']}.yaml"
            if expanded_path.exists():
                with open(expanded_path, "r", encoding="utf-8") as f:
                    expanded = yaml.safe_load(f)
                count = len(expanded.get("prompts", []))
                log.info(f"  {domain}: Expanded to {count} prompts")

        # Clean up temporary seed file
        seed_path.unlink(missing_ok=True)

    log.info(f"\n{'=' * 60}")
    log.info("EXPANSION COMPLETE")
    log.info(f"  Expanded files in: {EXPANDED_DIR}")
    log.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
