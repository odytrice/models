@echo off
cd /d "%~dp0"

echo ===================================================================
echo   Qwen 3.6 + Gemma 4 Benchmarks (Xeon-AI self-hosted models)
echo ===================================================================
echo.
echo Models: qwen3.6:27b, qwen3.6:35b, gemma4:26b, gemma4:31b
echo Domains: fsharp_core, fsharp_libraries
echo Concurrency: 1 (server handles single request at a time)
echo.
echo Running benchmarks sequentially, one model at a time.
echo.

echo [%date% %time%] Starting Qwen 3.6 27B...
python run_benchmark.py --teachers qwen36_27b --concurrency 1 --verbose
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Qwen 3.6 27B failed with exit code %ERRORLEVEL%
    goto :end
)

echo [%date% %time%] Starting Qwen 3.6 35B...
python run_benchmark.py --teachers qwen36_35b --concurrency 1 --verbose
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Qwen 3.6 35B failed with exit code %ERRORLEVEL%
    goto :end
)

echo [%date% %time%] Starting Gemma 4 26B...
python run_benchmark.py --teachers gemma4_26b --concurrency 1 --verbose
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Gemma 4 26B failed with exit code %ERRORLEVEL%
    goto :end
)

echo [%date% %time%] Starting Gemma 4 31B...
python run_benchmark.py --teachers gemma4_31b --concurrency 1 --verbose

:end
echo.
echo ===================================================================
echo [%date% %time%] Benchmark run complete.
echo ===================================================================
pause
