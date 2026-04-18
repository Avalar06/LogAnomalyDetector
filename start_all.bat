@echo off
title Adaptive ML-Based Log Anomaly Detection System

REM =====================================================
REM Project Root (auto-detect)
REM =====================================================
set ROOT=%~dp0

REM =====================================================
REM Python & Virtual Environment
REM =====================================================
set VENV=%ROOT%.venv
set PYTHON=%VENV%\Scripts\python.exe
set FLASK=%VENV%\Scripts\flask.exe

echo ====================================================
echo   Adaptive ML-Based Log Anomaly Detection System
echo ====================================================
echo.

REM =====================================================
REM 1. Start Flask Server (CORRECT FOR app/app.py)
REM =====================================================
echo [1] Starting Flask server...

start "Flask Server" cmd /k ^
"cd /d %ROOT% && ^
set FLASK_APP=app.app:app && ^
%FLASK% run"

echo     Flask server started.
echo.

REM =====================================================
REM 2. Start Windows Log Tailer
REM =====================================================
echo [2] Starting Windows Log Tailer...

start "Windows Log Tailer" cmd /k ^
"%PYTHON% -m src.log_tailer_windows"

echo     Log tailer started.
echo.

REM =====================================================
REM 3. Open Browser
REM =====================================================
timeout /t 3 >nul
start http://127.0.0.1:5000

REM =====================================================
REM DONE
REM =====================================================
echo ====================================================
echo SYSTEM STARTUP COMPLETE (LIVE MODE)
echo ====================================================
pause
