@echo off
REM Monitor benchmark progress for Qwen 3.6 and Gemma 4 models
REM Usage: monitor_benchmarks.bat

set RAW_DIR=D:\Projects\Github\models\data\raw\benchmark
set VERIFIED_DIR=D:\Projects\Github\models\data\verified\benchmark

:loop
cls
echo ===================================================================
echo   BENCHMARK PROGRESS MONITOR
echo   %date% %time%
echo ===================================================================
echo.

for %%m in (qwen36_27b qwen36_35b gemma4_26b gemma4_31b) do (
    for %%d in (fsharp_core fsharp_libraries) do (
        set "count=0"
        for /f %%n in ('type "%RAW_DIR%\%%d_%%m.jsonl" 2^>nul ^| find /c /v ""') do set count=%%n
        echo   %%m / %%d : !count! samples
    )
    echo.
)

echo ===================================================================
echo   Press Ctrl+C to exit, or wait 60s for refresh...
timeout /t 60 /nobreak >nul
goto loop
