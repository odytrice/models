"""Analyze benchmark failures to determine root causes.

Categories:
  - Skipped: no F# code extracted (prose response, wrong language, or truncated)
  - Compile error: code extracted but doesn't compile
  - Empty response: model returned nothing
"""
import json
import sys
from pathlib import Path
from collections import Counter

VERIFIED_DIR = Path(r"D:\Projects\Github\Models\data\verified\benchmark")
RAW_DIR = Path(r"D:\Projects\Github\Models\data\raw\benchmark")


def analyze_file(name, max_samples=3):
    verified_path = VERIFIED_DIR / name
    raw_path = RAW_DIR / name

    print(f"\n{'=' * 70}")
    print(f"  ANALYZING: {name}")
    print(f"{'=' * 70}")

    # Load verified results
    samples = []
    if verified_path.exists():
        with open(verified_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))

    # Count by status
    status_counts = Counter()
    skip_reasons = Counter()
    compile_errors = []
    skipped_samples = []

    for s in samples:
        vr = s.get("verify_result", {})
        status = vr.get("status", "unknown")
        status_counts[status] += 1

        if status == "skipped":
            skip_reasons[vr.get("stderr", "unknown")] += 1
            skipped_samples.append(s)
        elif status == "compile_error":
            compile_errors.append(s)

    print(f"\n  Status breakdown: {dict(status_counts)}")
    print(f"  Total: {len(samples)}")

    # Show skip reasons
    if skip_reasons:
        print(f"\n  Skip reasons:")
        for reason, count in skip_reasons.most_common():
            print(f"    {count}x: {reason}")

    # Show skipped samples - check if response has content but no code block
    if skipped_samples:
        print(f"\n  --- SKIPPED SAMPLES (showing up to {max_samples}) ---")
        for s in skipped_samples[:max_samples]:
            resp = s.get("response", "")
            has_backticks = "```" in resp
            has_fsharp_tag = "```fsharp" in resp or "```f#" in resp
            print(f"\n  ID: {s['id']}")
            print(f"  Response length: {len(resp)} chars")
            print(f"  Has backticks: {has_backticks}")
            print(f"  Has fsharp tag: {has_fsharp_tag}")
            print(f"  First 500 chars of response:")
            print(f"  {resp[:500]}")
            print(f"  ---")

    # Show compile errors
    if compile_errors:
        print(f"\n  --- COMPILE ERRORS (showing up to {max_samples}) ---")
        for s in compile_errors[:max_samples]:
            code = s.get("code", "")
            vr = s.get("verify_result", {})
            print(f"\n  ID: {s['id']}")
            print(f"  Code length: {len(code)} chars")
            print(f"  Stderr: {vr.get('stderr', '')[:300]}")
            print(f"  ---")


# Analyze all new benchmark files
files = [
    "fsharp_core_kimi26.jsonl",
    "fsharp_libraries_kimi26.jsonl",
    "fsharp_core_glm51.jsonl",
    "fsharp_libraries_glm51.jsonl",
    "dotnet_aspnet_glm51.jsonl",
]

for f in files:
    analyze_file(f, max_samples=3)
