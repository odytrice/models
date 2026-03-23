@echo off
cd /d "%~dp0"
python run_generation.py --round-config ../../configs/rounds/round1.yaml --verify %*
pause
