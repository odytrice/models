"""Check raw benchmark data for empty responses vs missing code extraction."""
import json
from pathlib import Path
from collections import Counter

RAW_DIR = Path(r"D:\Projects\Github\Models\data\raw\benchmark")


def analyze_raw(name):
    print(f"\n{'=' * 70}")
    print(f"  RAW ANALYSIS: {name}")
    print(f"{'=' * 70}")

    path = RAW_DIR / name
    if not path.exists():
        print("  FILE NOT FOUND")
        return

    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    empty_resp = 0
    has_resp_no_code = 0
    has_backticks = 0
    has_fsharp_tag = 0
    truncated = 0
    response_lens = []

    for s in samples:
        resp = s.get("response", "")
        resp_len = len(resp)
        response_lens.append(resp_len)

        if resp_len == 0:
            empty_resp += 1
        elif "```" in resp:
            has_backticks += 1
            if "```fsharp" in resp or "```f#" in resp:
                has_fsharp_tag += 1
            # Check if code block is truncated (opening fence but no closing)
            import re
            opens = len(re.findall(r"```(?:fsharp|f#)?\s*\n", resp))
            closes = len(re.findall(r"\n```", resp))
            if opens > closes:
                truncated += 1
        else:
            has_resp_no_code += 1

    print(f"\n  Total samples: {len(samples)}")
    print(f"  Empty response (0 chars): {empty_resp}")
    print(f"  Has response but no code blocks: {has_resp_no_code}")
    print(f"  Has backticks (```) in response: {has_backticks}")
    print(f"  Has ```fsharp or ```f# tag: {has_fsharp_tag}")
    print(f"  Truncated code blocks (unclosed): {truncated}")

    # Show some non-empty responses without code blocks
    no_code = [s for s in samples if len(s.get("response", "")) > 0 and "```" not in s.get("response", "")]
    if no_code:
        print(f"\n  --- NON-EMPTY RESPONSES WITHOUT CODE BLOCKS (up to 3) ---")
        for s in no_code[:3]:
            resp = s["response"]
            print(f"\n  ID: {s['id']}")
            print(f"  Response length: {len(resp)} chars")
            print(f"  Token count: {s.get('token_count', 'N/A')}")
            print(f"  First 800 chars:")
            print(f"  {resp[:800]}")
            print(f"  ---")

    # Show some empty responses
    empties = [s for s in samples if len(s.get("response", "")) == 0]
    if empties:
        print(f"\n  --- EMPTY RESPONSES ---")
        print(f"  Count: {len(empties)}")
        for s in empties[:3]:
            print(f"  ID: {s['id']}, tokens: {s.get('token_count', 'N/A')}, model: {s.get('model', 'N/A')}")


files = [
    "fsharp_core_kimi26.jsonl",
    "fsharp_libraries_kimi26.jsonl",
    "fsharp_core_glm51.jsonl",
    "fsharp_libraries_glm51.jsonl",
    "dotnet_aspnet_glm51.jsonl",
]

for f in files:
    analyze_raw(f)
