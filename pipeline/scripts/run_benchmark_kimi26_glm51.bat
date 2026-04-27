@echo off
cd /d "%~dp0"
echo ===================================================================
echo   Re-running benchmarks for Kimi K2.6 and GLM-5.1 (failed prompts)
echo ===================================================================
echo.
echo This will:
echo   1. Generate missing/failed responses from kimi26 and glm51
echo   2. Verify all outputs with the F# compiler
echo   3. Print the comparison table
echo.
echo K2.6:  fsharp_core (427), fsharp_libraries (122)
echo GLM-5.1: fsharp_core (63 done), fsharp_libraries (16 remaining), dotnet_aspnet (208)
echo.
python run_benchmark.py --teachers kimi26 glm51 --verbose
echo.
echo ===================================================================
echo   Benchmark run complete.
echo ===================================================================
pause
