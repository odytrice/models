@echo off
cd /d "%~dp0"
echo === ROUND 2: Temperature 0.9, output to *_t2.jsonl ===
python run_generation.py --suffix _t2 --temperature 0.9 --verify %*
pause
