@echo off
cd /d "%~dp0"
echo === ROUND 3: MiniMax (F#) + GLM-5 (.NET), with verification ===
python run_generation.py --round-config ../../configs/rounds/round3.yaml --verify %*
pause
