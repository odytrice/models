"""
F# Compiler Verification Pipeline

Verifies teacher-generated F# code samples by:
  Stage 1: Compilation/type-check only (dotnet build)
  Stage 2: Execution with assertions (dotnet run)

Samples that reference NuGet packages use the verification project
at pipeline/verify/verify.fsproj. Simple scripts use dotnet fsi.

Usage:
  python verify_fsharp.py --input data/raw/fsharp_samples.jsonl --output data/verified/fsharp_verified.jsonl
  python verify_fsharp.py --input data/raw/fsharp_samples.jsonl --output data/verified/fsharp_verified.jsonl --retry
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
VERIFY_PROJECT_DIR = PIPELINE_DIR / "verify"
VERIFY_FSPROJ = VERIFY_PROJECT_DIR / "verify.fsproj"
PROGRAM_FS = VERIFY_PROJECT_DIR / "Program.fs"

# Known NuGet namespaces that indicate a sample needs the full project build
NUGET_INDICATORS = [
    "open Giraffe",
    "open FsToolkit",
    "open Akka",
    "open Thoth",
    "open LinqToDB",
    "open FluentMigrator",
    "open Npgsql",
    "open Serilog",
    "open Confluent",
    "open Minio",
    "open Stripe",
    "open FSharp.Data",
    "open FSharp.Control.AsyncSeq",
    "open FSharp.Control.Reactive",
    "open EntityFrameworkCore",
    "open CsvHelper",
    "open FsUnit",
    "open Microsoft.AspNetCore",
    "open Microsoft.Extensions",
    "open Xunit",
    "open System.Reactive",
]


class VerifyStatus(str, Enum):
    PASS = "pass"
    COMPILE_ERROR = "compile_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class VerifyResult:
    status: VerifyStatus
    stderr: str = ""
    stdout: str = ""
    stage: int = 0  # 1 = compile, 2 = execute
    retryable: bool = False


@dataclass
class Sample:
    """A single training data sample with F# code."""

    id: str
    instruction: str
    response: str
    code: str  # extracted F# code block(s)
    teacher: str
    domain: str
    has_tests: bool = False
    verify_result: Optional[dict] = None

    def needs_project_build(self) -> bool:
        """Check if code references NuGet packages requiring full project build."""
        return any(indicator in self.code for indicator in NUGET_INDICATORS)


def extract_fsharp_code(response: str) -> str:
    """Extract F# code blocks from a markdown response.

    Returns concatenated code from all ```fsharp or ```f# blocks.
    Falls back to extracting truncated (unclosed) fenced blocks.
    If no fenced blocks found at all, returns empty string.
    """
    # Pattern 1: Complete fenced blocks with language tag
    # Pattern 2: Complete fenced blocks without language tag
    patterns = [
        r"```(?:fsharp|f#)\s*\n(.*?)```",
        r"```\s*\n(.*?)```",  # fallback: unfenced code blocks
    ]

    blocks = []
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            blocks.extend(matches)
            break

    # Fallback: handle truncated responses where the closing ``` is missing
    # (teacher hit max_tokens and output was cut off mid-code)
    if not blocks:
        truncated_patterns = [
            r"```(?:fsharp|f#)\s*\n(.*)",  # greedy to end-of-string
            r"```\s*\n(.*)",
        ]
        for pattern in truncated_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                code = match.group(1).strip()
                if code:
                    blocks.append(code)
                break

    if not blocks:
        return ""

    # If multiple blocks, check for conflicting module/namespace declarations
    # that would cause compile errors when concatenated
    if len(blocks) > 1:
        has_conflict = False
        decl_count = 0
        for block in blocks:
            first_line = block.strip().split("\n")[0].strip()
            if (
                first_line.startswith("namespace ")
                or first_line.startswith("module ")
                or first_line.startswith("open ")
            ):
                decl_count += 1
        # If multiple blocks have top-level declarations, use only the largest
        # block (likely the main implementation) to avoid conflicts
        if decl_count > 1:
            blocks = [max(blocks, key=len)]

    return "\n\n".join(block.strip() for block in blocks)


def has_test_assertions(code: str) -> bool:
    """Detect if code contains test assertions or expected output checks."""
    indicators = [
        "Assert.",
        "should equal",
        "should be",
        "shouldEqual",
        "|> equal",
        "Expect.",
        "test ",
        "testCase",
        "testList",
        "FsUnit",
        'printfn "PASS"',
    ]
    return any(indicator in code for indicator in indicators)


def verify_with_fsi(
    code: str, execute: bool = False, timeout: int = 30
) -> VerifyResult:
    """Verify F# code using dotnet fsi (F# Interactive).

    Used for simple scripts that don't need NuGet packages.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".fsx", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        # Note: dotnet fsi --check is not available in .NET 10+.
        # We always execute the script. For type-check-only verification,
        # we rely on the project-based build path (verify_with_project).
        cmd = ["dotnet", "fsi", script_path]
        stage = 2 if execute else 1  # Track intent even though both execute

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(VERIFY_PROJECT_DIR),
        )

        if result.returncode == 0:
            return VerifyResult(
                status=VerifyStatus.PASS,
                stdout=result.stdout,
                stderr=result.stderr,
                stage=stage,
            )
        else:
            # Distinguish compile errors (FS####) from runtime errors
            stderr = result.stderr or ""
            is_compile_error = "error FS" in stderr or "error FS" in (
                result.stdout or ""
            )
            status = (
                VerifyStatus.COMPILE_ERROR
                if is_compile_error
                else VerifyStatus.RUNTIME_ERROR
            )
            return VerifyResult(
                status=status,
                stderr=result.stderr,
                stdout=result.stdout,
                stage=stage,
                retryable=True,
            )

    except subprocess.TimeoutExpired:
        return VerifyResult(
            status=VerifyStatus.TIMEOUT,
            stderr=f"Timed out after {timeout}s",
            stage=2 if execute else 1,
        )
    finally:
        os.unlink(script_path)


def verify_with_project(
    code: str, execute: bool = False, timeout: int = 60
) -> VerifyResult:
    """Verify F# code using the full verification project (dotnet build/run).

    Used for code that references NuGet packages.
    """
    # Back up the original Program.fs
    original_content = (
        PROGRAM_FS.read_text(encoding="utf-8") if PROGRAM_FS.exists() else ""
    )

    try:
        # Write the generated code as Program.fs
        PROGRAM_FS.write_text(code, encoding="utf-8")

        # Stage 1: Build (type-check + compile)
        build_result = subprocess.run(
            ["dotnet", "build", "--nologo", "-v", "q", "--no-restore"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(VERIFY_PROJECT_DIR),
        )

        if build_result.returncode != 0:
            return VerifyResult(
                status=VerifyStatus.COMPILE_ERROR,
                stderr=build_result.stderr + build_result.stdout,
                stage=1,
                retryable=True,
            )

        # Stage 2: Execute if requested
        if execute:
            run_result = subprocess.run(
                ["dotnet", "run", "--no-build"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(VERIFY_PROJECT_DIR),
            )

            if run_result.returncode != 0:
                return VerifyResult(
                    status=VerifyStatus.RUNTIME_ERROR,
                    stderr=run_result.stderr,
                    stdout=run_result.stdout,
                    stage=2,
                    retryable=True,
                )

        return VerifyResult(
            status=VerifyStatus.PASS,
            stage=2 if execute else 1,
        )

    except subprocess.TimeoutExpired:
        return VerifyResult(
            status=VerifyStatus.TIMEOUT,
            stderr=f"Timed out after {timeout}s",
            stage=2 if execute else 1,
        )
    finally:
        # Restore original Program.fs
        PROGRAM_FS.write_text(original_content, encoding="utf-8")


def needs_project_for_structure(code: str) -> bool:
    """Check if code uses namespace/module declarations that require .fs (not .fsx).

    F# script files (.fsx) don't support top-level namespace or module declarations.
    These need to go through the project build path as .fs files.
    """
    first_line = code.strip().split("\n")[0].strip()

    # Top-level namespace declaration
    if first_line.startswith("namespace "):
        return True

    # Top-level module declaration (e.g., "module MyModule" but NOT "module X =")
    if re.match(r"^module\s+\S+\s*$", first_line):
        return True

    return False


def verify_sample(sample: Sample) -> VerifyResult:
    """Verify a single F# code sample through the appropriate pipeline."""
    if not sample.code.strip():
        return VerifyResult(status=VerifyStatus.SKIPPED, stderr="No F# code extracted")

    execute = sample.has_tests or has_test_assertions(sample.code)

    # Route through project build if code uses NuGet packages OR
    # namespace/module declarations (which are invalid in .fsx files)
    if sample.needs_project_build() or needs_project_for_structure(sample.code):
        return verify_with_project(sample.code, execute=execute)
    else:
        return verify_with_fsi(sample.code, execute=execute)


def load_samples(input_path: Path) -> list[Sample]:
    """Load samples from a JSONL file."""
    samples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                code = data.get("code", "") or extract_fsharp_code(
                    data.get("response", "")
                )
                samples.append(
                    Sample(
                        id=data.get("id", f"sample_{line_num}"),
                        instruction=data.get("instruction", ""),
                        response=data.get("response", ""),
                        code=code,
                        teacher=data.get("teacher", "unknown"),
                        domain=data.get("domain", "fsharp"),
                        has_tests=data.get("has_tests", False),
                    )
                )
            except json.JSONDecodeError as e:
                log.warning(f"Skipping line {line_num}: {e}")
    return samples


def save_results(samples: list[Sample], output_path: Path):
    """Save verified samples to a JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            data = {
                "id": sample.id,
                "instruction": sample.instruction,
                "response": sample.response,
                "code": sample.code,
                "teacher": sample.teacher,
                "domain": sample.domain,
                "has_tests": sample.has_tests,
                "verify_result": sample.verify_result,
            }
            f.write(json.dumps(data, ensure_ascii=False) + "\n")


def run_verification(input_path: Path, output_path: Path, retry: bool = False):
    """Run the full verification pipeline on a set of samples."""
    # Ensure verify project is restored
    log.info("Ensuring verification project is restored...")
    restore = subprocess.run(
        ["dotnet", "restore", "--nologo", "-v", "q"],
        capture_output=True,
        text=True,
        cwd=str(VERIFY_PROJECT_DIR),
    )
    if restore.returncode != 0:
        log.error(f"Failed to restore verify project: {restore.stderr}")
        sys.exit(1)

    samples = load_samples(input_path)
    log.info(f"Loaded {len(samples)} samples from {input_path}")

    passed = 0
    failed = 0
    skipped = 0
    results_by_status = {}

    for i, sample in enumerate(samples, 1):
        log.info(f"[{i}/{len(samples)}] Verifying {sample.id} ({sample.domain})...")

        result = verify_sample(sample)
        sample.verify_result = {
            "status": result.status.value,
            "stderr": result.stderr[:2000]
            if result.stderr
            else "",  # truncate long errors
            "stage": result.stage,
        }

        if result.status == VerifyStatus.PASS:
            passed += 1
            log.info(f"  PASS (stage {result.stage})")
        elif result.status == VerifyStatus.SKIPPED:
            skipped += 1
            log.info(f"  SKIPPED: {result.stderr}")
        else:
            failed += 1
            log.warning(f"  {result.status.value}: {result.stderr[:200]}")

        # Track by status
        results_by_status.setdefault(result.status.value, 0)
        results_by_status[result.status.value] += 1

    # Save all results (including failures for analysis)
    save_results(samples, output_path)

    # Save only passing samples to a separate file
    passing_samples = [
        s for s in samples if s.verify_result and s.verify_result["status"] == "pass"
    ]
    passing_path = output_path.with_stem(output_path.stem + "_passing")
    save_results(passing_samples, passing_path)

    # Summary
    log.info("=" * 60)
    log.info("VERIFICATION SUMMARY")
    log.info(f"  Total:   {len(samples)}")
    log.info(
        f"  Passed:  {passed} ({passed / len(samples) * 100:.1f}%)"
        if samples
        else "  Passed: 0"
    )
    log.info(
        f"  Failed:  {failed} ({failed / len(samples) * 100:.1f}%)"
        if samples
        else "  Failed: 0"
    )
    log.info(f"  Skipped: {skipped}")
    log.info(f"  By status: {results_by_status}")
    log.info(f"  All results: {output_path}")
    log.info(f"  Passing only: {passing_path}")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="F# Compiler Verification Pipeline")
    parser.add_argument(
        "--input", type=Path, required=True, help="Input JSONL file with F# samples"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSONL file with verification results",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Retry failed samples (not yet implemented)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        log.error(f"Input file not found: {args.input}")
        sys.exit(1)

    if not VERIFY_FSPROJ.exists():
        log.error(f"Verification project not found: {VERIFY_FSPROJ}")
        sys.exit(1)

    run_verification(args.input, args.output, retry=args.retry)


if __name__ == "__main__":
    main()
