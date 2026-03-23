"""
Deduplicate Round 2 Generation Files

Removes duplicate entries (same prompt ID, multiple responses) from _t2.jsonl files.
For F# domains, prefers passing responses over failing ones, then longer responses.
For non-F# domains, prefers longer responses (more training signal).

Deduplicates both raw and verified files to keep them in sync.

Usage:
    python dedup_round2.py                # Dedup all _t2 files
    python dedup_round2.py --dry-run      # Show what would be removed without changing files
    python dedup_round2.py --suffix _t2   # Custom suffix (default: _t2)
"""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
VERIFIED_DIR = PROJECT_DIR / "data" / "verified"

# Domains that have F# verification results
FSHARP_DOMAINS = {"fsharp_core", "fsharp_libraries", "dotnet_aspnet", "cross_domain"}


def load_jsonl(path: Path) -> list[dict]:
    """Load all entries from a JSONL file."""
    entries = []
    if not path.exists():
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entries.append(json.loads(line))
    return entries


def save_jsonl(entries: list[dict], path: Path):
    """Save entries to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def pick_best_entry(entries: list[dict], is_fsharp: bool) -> dict:
    """Pick the best entry from a list of duplicates for the same prompt ID.

    For F# domains:
      1. Prefer entries that pass verification
      2. Among passing entries, prefer the longer response
    For non-F# domains:
      1. Prefer the longer response
    """
    if len(entries) == 1:
        return entries[0]

    if is_fsharp:
        # Separate passing and failing
        passing = [
            e for e in entries if e.get("verify_result", {}).get("status") == "pass"
        ]
        if passing:
            # Among passing, pick the longest response
            return max(passing, key=lambda e: len(e.get("response", "")))
        else:
            # No passing entries - pick the longest anyway (might be recoverable later)
            return max(entries, key=lambda e: len(e.get("response", "")))
    else:
        # Non-F# domain: pick the longest response
        return max(entries, key=lambda e: len(e.get("response", "")))


def dedup_file(path: Path, is_fsharp: bool, dry_run: bool = False) -> dict:
    """Deduplicate a single JSONL file. Returns stats."""
    entries = load_jsonl(path)
    if not entries:
        return {"total": 0, "unique": 0, "removed": 0, "file": path.name}

    # Group by ID
    groups = defaultdict(list)
    for entry in entries:
        groups[entry["id"]].append(entry)

    # Pick best entry per ID
    deduped = []
    duplicates_found = 0
    for sid, group in groups.items():
        best = pick_best_entry(group, is_fsharp)
        deduped.append(best)
        if len(group) > 1:
            duplicates_found += 1

    removed = len(entries) - len(deduped)

    if not dry_run and removed > 0:
        save_jsonl(deduped, path)

    return {
        "total": len(entries),
        "unique": len(deduped),
        "removed": removed,
        "duplicated_ids": duplicates_found,
        "file": path.name,
    }


def main():
    parser = argparse.ArgumentParser(description="Deduplicate round 2 files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without changing files",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="_t2",
        help="File suffix to match (default: _t2)",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info(f"DEDUPLICATION {'(DRY RUN)' if args.dry_run else ''}")
    log.info(f"  Suffix: {args.suffix}")
    log.info("=" * 60)

    total_removed = 0

    # Process both raw and verified directories
    for dir_label, directory in [("RAW", RAW_DIR), ("VERIFIED", VERIFIED_DIR)]:
        files = sorted(directory.glob(f"*{args.suffix}.jsonl"))
        if not files:
            continue

        log.info(f"\n  {dir_label} directory: {directory}")
        log.info(f"  {'-' * 50}")

        for filepath in files:
            # Determine domain from filename
            domain = filepath.stem.replace(args.suffix, "")
            is_fsharp = domain in FSHARP_DOMAINS

            stats = dedup_file(filepath, is_fsharp, args.dry_run)

            if stats["removed"] > 0:
                action = "would remove" if args.dry_run else "removed"
                log.info(
                    f"  {stats['file']:35s} "
                    f"{stats['total']:5d} -> {stats['unique']:5d} "
                    f"({action} {stats['removed']}, "
                    f"{stats['duplicated_ids']} IDs had dupes)"
                )
                total_removed += stats["removed"]
            else:
                log.info(
                    f"  {stats['file']:35s} {stats['total']:5d} entries, no duplicates"
                )

    log.info(f"\n{'=' * 60}")
    action = "Would remove" if args.dry_run else "Removed"
    log.info(f"  {action} {total_removed} duplicate entries total")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
