"""
Re-verify remaining F# failures after substitute run.

1. Identifies prompt IDs with no passing response across all rounds
2. Finds the best raw response for each (most recent attempt, preferring best teacher)
3. Re-verifies with the updated verifier (which now routes NuGet packages correctly)
4. Writes newly passing samples to data/verified/reverify_passing.jsonl
5. Writes still-failing samples to data/verified/reverify_failures.jsonl for manual fixing

Usage:
  python reverify_failures.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Add parent to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from verify_fsharp import (
    Sample,
    extract_fsharp_code,
    has_test_assertions,
    verify_sample,
    VerifyStatus,
    log,
)

DATA_DIR = SCRIPT_DIR.parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
VERIFIED_DIR = DATA_DIR / "verified"
EXPANDED_DIR = SCRIPT_DIR.parent / "prompts" / "expanded"

# F# domains that need compiler verification
FSHARP_DOMAINS = {"fsharp_core", "fsharp_libraries", "dotnet_aspnet", "cross_domain"}


def load_passing_ids() -> set:
    """Load all prompt IDs that have at least one passing response."""
    passing_ids = set()
    for f in VERIFIED_DIR.glob("*_passing.jsonl"):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                sample = json.loads(line)
                passing_ids.add(sample["id"])
    log.info(f"Loaded {len(passing_ids)} passing prompt IDs")
    return passing_ids


def load_expanded_ids() -> set:
    """Load all prompt IDs from F#-domain expanded YAMLs."""
    import yaml

    all_ids = set()
    yaml_files = [
        "fsharp_core.yaml",
        "fsharp_libraries.yaml",
        "fsharp_core_r3.yaml",
        "fsharp_libraries_r3.yaml",
        "dotnet_aspnet.yaml",
        "dotnet_aspnet_r3.yaml",
        "cross_domain.yaml",
    ]
    for fname in yaml_files:
        fpath = EXPANDED_DIR / fname
        if fpath.exists():
            with open(fpath, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            for p in data.get("prompts", []):
                all_ids.add(p["id"])
    log.info(f"Loaded {len(all_ids)} F# prompt IDs from expanded YAMLs")
    return all_ids


def load_raw_responses(failing_ids: set) -> dict:
    """Load all raw responses for failing IDs. Returns {id: [list of samples]}."""
    responses = defaultdict(list)

    # Teacher quality ranking for tie-breaking
    teacher_rank = {"minimax": 0, "glm5": 1, "kimi": 2, "deepseek": 3}

    for f in RAW_DIR.glob("*.jsonl"):
        if f.name.startswith("benchmark"):
            continue
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = sample.get("id", "")
                if sid in failing_ids:
                    responses[sid].append(sample)

    log.info(
        f"Found raw responses for {len(responses)} of {len(failing_ids)} failing IDs"
    )
    return responses


def pick_best_response(responses: list) -> dict:
    """Pick the best response for re-verification.

    Prefers: minimax > glm5 > kimi > deepseek.
    Among same teacher, prefers substitute runs (more recent).
    """
    teacher_rank = {"minimax": 0, "glm5": 1, "kimi": 2, "deepseek": 3}

    def sort_key(r):
        teacher = r.get("teacher", "unknown")
        rank = teacher_rank.get(teacher, 99)
        # Prefer substitute runs (they have _sub in filename context)
        return rank

    responses.sort(key=sort_key)
    return responses[0]


def main():
    log.info("=" * 60)
    log.info("RE-VERIFICATION OF REMAINING F# FAILURES")
    log.info("=" * 60)

    # Step 1: Find failing IDs
    passing_ids = load_passing_ids()
    expanded_ids = load_expanded_ids()
    failing_ids = expanded_ids - passing_ids
    log.info(f"Found {len(failing_ids)} prompt IDs with no passing response")

    if not failing_ids:
        log.info("No failures to re-verify!")
        return

    # Step 2: Load raw responses
    raw_responses = load_raw_responses(failing_ids)

    # IDs with no raw response at all (shouldn't happen but let's check)
    no_response = failing_ids - set(raw_responses.keys())
    if no_response:
        log.warning(
            f"{len(no_response)} failing IDs have no raw response at all: {sorted(no_response)[:5]}..."
        )

    # Step 3: Re-verify each
    newly_passing = []
    still_failing = []
    skipped = []

    items = sorted(raw_responses.items())
    total = len(items)

    for i, (sid, responses) in enumerate(items, 1):
        best = pick_best_response(responses)

        # Extract code and create Sample
        code = extract_fsharp_code(best.get("response", ""))
        if not code.strip():
            log.info(f"[{i}/{total}] {sid}: SKIPPED (no F# code)")
            skipped.append(
                {
                    "id": sid,
                    "reason": "no_code",
                    "teacher": best.get("teacher", "unknown"),
                }
            )
            continue

        sample = Sample(
            id=sid,
            instruction=best.get("instruction", ""),
            response=best.get("response", ""),
            code=code,
            teacher=best.get("teacher", "unknown"),
            domain=best.get("domain", "unknown"),
            has_tests=has_test_assertions(code),
        )

        result = verify_sample(sample)

        if result.status == VerifyStatus.PASS:
            log.info(
                f"[{i}/{total}] {sid}: PASS (stage {result.stage}) — teacher: {sample.teacher}"
            )
            newly_passing.append(
                {
                    "id": sid,
                    "instruction": sample.instruction,
                    "response": sample.response,
                    "teacher": sample.teacher,
                    "domain": sample.domain,
                    "status": "pass",
                    "stage": result.stage,
                }
            )
        elif result.status == VerifyStatus.SKIPPED:
            log.info(f"[{i}/{total}] {sid}: SKIPPED — {result.stderr}")
            skipped.append(
                {"id": sid, "reason": result.stderr, "teacher": sample.teacher}
            )
        else:
            # Extract first error line for clustering
            error_line = ""
            for line in result.stderr.split("\n"):
                if "error FS" in line or "warning FS" in line:
                    error_line = line.strip()
                    break

            log.info(f"[{i}/{total}] {sid}: {result.status.value} — {error_line[:100]}")
            still_failing.append(
                {
                    "id": sid,
                    "instruction": sample.instruction,
                    "response": sample.response,
                    "teacher": sample.teacher,
                    "domain": sample.domain,
                    "status": result.status.value,
                    "error": result.stderr[:500],
                    "error_summary": error_line[:200],
                }
            )

    # Step 4: Write outputs
    passing_out = VERIFIED_DIR / "reverify_passing.jsonl"
    failing_out = VERIFIED_DIR / "reverify_failures.jsonl"

    if newly_passing:
        with open(passing_out, "w", encoding="utf-8") as fh:
            for s in newly_passing:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
        log.info(f"Wrote {len(newly_passing)} newly passing samples to {passing_out}")

    if still_failing:
        with open(failing_out, "w", encoding="utf-8") as fh:
            for s in still_failing:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
        log.info(f"Wrote {len(still_failing)} still-failing samples to {failing_out}")

    # Step 5: Summary
    log.info("=" * 60)
    log.info("RE-VERIFICATION SUMMARY")
    log.info(f"  Total failures checked: {total}")
    log.info(f"  Newly passing:          {len(newly_passing)}")
    log.info(f"  Still failing:          {len(still_failing)}")
    log.info(f"  Skipped (no code):      {len(skipped)}")
    log.info(f"  No raw response:        {len(no_response)}")
    log.info("=" * 60)

    # Error cluster summary for still-failing
    if still_failing:
        log.info("\nError clusters for still-failing samples:")
        clusters = defaultdict(list)
        for s in still_failing:
            err = s.get("error_summary", "unknown")
            # Normalize: extract FS error code and general pattern
            import re

            m = re.search(r"error (FS\d+):(.+)", err)
            if m:
                code = m.group(1)
                msg = m.group(2).strip()[:60]
                key = f"{code}: {msg}"
            else:
                m2 = re.search(r"warning (FS\d+):(.+)", err)
                if m2:
                    key = f"warning {m2.group(1)}: {m2.group(2).strip()[:60]}"
                else:
                    key = err[:80] if err else "unknown"
            clusters[key].append(s["id"])

        for key, ids in sorted(clusters.items(), key=lambda x: -len(x[1])):
            log.info(f"  [{len(ids):2d}] {key}")
            for sid in ids[:3]:
                log.info(f"       - {sid}")


if __name__ == "__main__":
    main()
