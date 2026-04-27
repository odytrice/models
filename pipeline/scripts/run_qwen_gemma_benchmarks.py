"""Run Qwen 3.6 + Gemma 4 benchmarks sequentially on Xeon-AI server.

Since the server handles one model at a time, we run each teacher
sequentially with concurrency=1.
"""
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

TEACHERS = ["qwen36_27b", "qwen36_35b", "gemma4_26b", "gemma4_31b"]

def main():
    for i, teacher in enumerate(TEACHERS):
        print(f"\n{'=' * 70}")
        print(f"  BENCHMARK {i+1}/{len(TEACHERS)}: {teacher}")
        print(f"{'=' * 70}\n")

        start = time.time()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "run_benchmark.py"),
                "--teachers", teacher,
                "--concurrency", "1",
                "--verbose",
            ],
            cwd=str(SCRIPT_DIR),
        )
        elapsed = time.time() - start

        if result.returncode != 0:
            print(f"\n  [ERROR] {teacher} benchmark failed (exit code {result.returncode})")
            print(f"  Elapsed: {elapsed/60:.1f} min")
            sys.exit(1)

        print(f"\n  {teacher} completed in {elapsed/60:.1f} min")

    print(f"\n{'=' * 70}")
    print(f"  ALL BENCHMARKS COMPLETE")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    main()
