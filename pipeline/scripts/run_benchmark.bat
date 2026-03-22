@echo off
cd /d "%~dp0"
echo === F# Teacher Benchmark: Kimi vs MiniMax on DeepSeek failures ===
python run_benchmark.py %*
pause
