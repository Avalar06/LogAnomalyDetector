@echo off
title Adaptive ML-Based Log Anomaly Detection System

REM =====================================================
REM PROJECT ROOT
REM =====================================================
set ROOT=%~dp0

REM =====================================================
REM PYTHON VENV
REM =====================================================
set PYTHON=%ROOT%.venv\Scripts\python.exe

echo ====================================================
echo Adaptive ML-Based Log Anomaly Detection System
echo ====================================================
echo.

REM =====================================================
REM CHECK PYTHON
REM =====================================================
if not exist "%PYTHON%" (
    echo.
    echo ERROR: Virtual Environment Python not found
    echo Expected:
    echo %PYTHON%
    echo.
    pause
    exit /b
)

echo [OK] Virtual Environment Found
echo.

REM =====================================================
REM RESET SIMULATOR OFFSET
REM =====================================================
echo Resetting simulator offset...

if exist "%ROOT%logs\.sample_simulator.offset" (
    del "%ROOT%logs\.sample_simulator.offset"
)

echo [OK] Offset Reset
echo.

REM =====================================================
REM START FLASK DASHBOARD
REM =====================================================
echo [1/4] Starting Flask Dashboard...

start "Flask Dashboard" cmd /k "cd /d %ROOT% && %PYTHON% app\app.py"

timeout /t 5 >nul

echo [OK] Flask Dashboard Started
echo.

REM =====================================================
REM OPEN FIREFOX
REM =====================================================
echo Opening Dashboard...

if exist "C:\Program Files\Mozilla Firefox\firefox.exe" (
    start "" "C:\Program Files\Mozilla Firefox\firefox.exe" "http://127.0.0.1:5000"
) else (
    start "" "http://127.0.0.1:5000"
)

echo [OK] Browser Opened
echo.

REM =====================================================
REM START WINDOWS LOG TAILER
REM =====================================================
echo [2/4] Starting Windows Log Tailer...

if exist "%ROOT%src\log_tailer_windows.py" (
    start "Windows Log Tailer" cmd /k "cd /d %ROOT% && %PYTHON% -m src.log_tailer_windows"
) else (
    echo WARNING: src\log_tailer_windows.py not found
)

timeout /t 2 >nul

echo [OK] Log Tailer Started
echo.

REM =====================================================
REM START LIVE LOG PARSER
REM =====================================================
echo [3/4] Starting Live Log Parser...

if exist "%ROOT%scripts\parse_live_log.py" (
    start "Live Log Parser" cmd /k "cd /d %ROOT%scripts && %PYTHON% parse_live_log.py"
) else (
    echo WARNING: parse_live_log.py not found
)

timeout /t 2 >nul

echo [OK] Live Parser Started
echo.

REM =====================================================
REM START LIVE MONITOR INFERENCE
REM =====================================================
echo [4/4] Starting Live Monitor Inference...

if exist "%ROOT%scripts\live_monitor_infer.py" (
    start "Live Monitor Inference" cmd /k "cd /d %ROOT%scripts && %PYTHON% live_monitor_infer.py"
) else (
    echo WARNING: live_monitor_infer.py not found
)

timeout /t 2 >nul

echo [OK] Live Monitor Started
echo.

REM =====================================================
REM STARTUP COMPLETE
REM =====================================================
echo ====================================================
echo SYSTEM STARTUP COMPLETE
echo ====================================================
echo.
echo Running Components:
echo.
echo   Flask Dashboard
echo   Windows Log Tailer
echo   Live Log Parser
echo   Live Monitor Inference
echo.
echo Dashboard URL:
echo   http://127.0.0.1:5000
echo.
echo ====================================================

pause