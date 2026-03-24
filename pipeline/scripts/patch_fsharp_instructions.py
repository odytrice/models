"""
Patch 20 failing prompt instructions to explicitly request F# code.

Two categories:
1. Prompts that say "C#" — replace C# with F# and add F# instruction
2. Prompts that use F# idioms but don't say "F#" — add F# instruction prefix

Also creates a small expanded YAML with just these 20 prompts for re-generation.
"""

import yaml
from pathlib import Path
import re

EXPANDED_DIR = Path("pipeline/prompts/expanded")
OUTPUT_YAML = EXPANDED_DIR / "fsharp_instruction_fixes.yaml"

# Category 1: Explicitly says C# — replace C# references with F#
REPLACE_CSHARP = {
    "cross_0006_exp_000",  # "Build a C# FHIR API"
    "cross_0010_exp_000",  # "C# backend: Akka.Streams"
    "cross_0010_exp_005",  # "C# Akka.NET: Actor per API endpoint"
    "cross_0010_exp_017",  # "C#: Actor per microservice source"
    "cross_0010_exp_022",  # "C#: SensorStation actors"
    "fsharp_lib_0028_exp_010",  # "Design a C# consumer"
    "fsharp_lib_0029_exp_020",  # "Generate Unity/C# API client"
}

# Category 2: Uses F# idioms but never says "F#" — add prefix
ADD_FSHARP_PREFIX = {
    "cross_0007_exp_006",  # Akka.NET memory leak debug
    "cross_0012_exp_016",  # Roslyn code generator
    "fsharp_core_0022_exp_011",  # struct DUs weather
    "fsharp_core_0031_exp_023",  # FParsec localization
    "fsharp_lib_0006_exp_007",  # option CE library checkout
    "fsharp_lib_0006_exp_012",  # option CE content management
    "fsharp_lib_0006_exp_014",  # option CE manufacturing QC
    "fsharp_lib_0006_exp_017",  # option CE supply chain
    "fsharp_lib_0006_exp_018",  # option CE video streaming
    "fsharp_lib_0006_exp_020",  # option CE real estate
    "fsharp_lib_0006_exp_023",  # option CE project management
    "fsharp_lib_0006_exp_029",  # option CE airline booking
    "fsharp_lib_0020_exp_016",  # GraphQL partial response
}

ALL_IDS = REPLACE_CSHARP | ADD_FSHARP_PREFIX


def patch_instruction(prompt_id: str, instruction: str) -> str:
    """Patch the instruction to explicitly request F#."""

    if prompt_id in REPLACE_CSHARP:
        # Replace "C#" with "F#" throughout
        patched = instruction.replace("C#", "F#")
        patched = patched.replace("c#", "F#")
        # Also replace "C# consumer" -> "F# consumer", etc.
        # Ensure "Implement all code in F#" is at the end if not already present
        if (
            "Implement all code in F#" not in patched
            and "implement all code in F#" not in patched
        ):
            patched = patched.rstrip() + "\n\nImplement all code in F#."
        return patched

    elif prompt_id in ADD_FSHARP_PREFIX:
        # Add "Implement in F#." at the beginning or end
        if (
            "F#" not in instruction
            and "f#" not in instruction
            and "fsharp" not in instruction.lower()
        ):
            return instruction.rstrip() + "\n\nImplement all code in F#."
        else:
            # Already has some F# mention but still failed - add emphasis
            return (
                instruction.rstrip()
                + "\n\nEnsure all code examples are valid, compilable F#."
            )

    return instruction


def main():
    # Load all expanded YAMLs and find the 20 prompts
    yaml_files = list(EXPANDED_DIR.glob("*.yaml"))

    patched_prompts = []
    found_ids = set()

    for yf in yaml_files:
        with open(yf, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "prompts" not in data:
            continue

        modified = False
        for prompt in data["prompts"]:
            pid = prompt.get("id", "")
            if pid in ALL_IDS:
                old_instruction = prompt["instruction"]
                new_instruction = patch_instruction(pid, old_instruction)

                if old_instruction != new_instruction:
                    prompt["instruction"] = new_instruction
                    modified = True
                    found_ids.add(pid)

                    patched_prompts.append(
                        {
                            "id": pid,
                            "instruction": new_instruction,
                            "domain": prompt.get("domain", ""),
                        }
                    )

                    print(f"  PATCHED {pid}")
                    # Show diff
                    if pid in REPLACE_CSHARP:
                        print(f"    [replaced C# -> F#]")
                    else:
                        print(f"    [added F# instruction]")

        if modified:
            with open(yf, "w", encoding="utf-8") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    width=120,
                    sort_keys=False,
                )
            print(f"  Updated {yf.name}")

    # Check for missing IDs
    missing = ALL_IDS - found_ids
    if missing:
        print(f"\nWARNING: {len(missing)} IDs not found in any expanded YAML:")
        for mid in sorted(missing):
            print(f"  - {mid}")

    # Create a small YAML with just the patched prompts for re-generation
    output_data = {
        "domain": "mixed",
        "description": "Re-generation of 20 prompts with F# instruction fixes",
        "prompts": patched_prompts,
    }

    with open(OUTPUT_YAML, "w", encoding="utf-8") as f:
        yaml.dump(
            output_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            width=120,
            sort_keys=False,
        )

    print(f"\nWrote {len(patched_prompts)} patched prompts to {OUTPUT_YAML}")
    print(f"Total found: {len(found_ids)} / {len(ALL_IDS)}")


if __name__ == "__main__":
    main()
