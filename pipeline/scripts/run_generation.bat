@echo off
cd /d "%~dp0"
echo === SUBSTITUTE: Re-running 806 failed QA pairs with alternate teachers ===
python run_generation.py --round-config ../../configs/rounds/substitute.yaml --verify %*
pause
