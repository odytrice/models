@echo off
cd /d "%~dp0"
echo === ROUND 2: MiniMax (F#) + Kimi (Svelte/TS) + GLM-5 (.NET/general), temp 0.9 ===
python run_generation.py --round-config ../../configs/rounds/round2.yaml --verify %*
pause
