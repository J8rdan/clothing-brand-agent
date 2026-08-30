@echo off
setlocal enabledelayedexpansion
title CB Agent Command Center
cd /d "%~dp0"

call "_find_python.bat"
if errorlevel 1 (
  echo Could not find Python. Run "1 - SETUP (run once).bat" first.
  pause
  exit /b 1
)

echo Starting CB Agent Command Center...
echo Your browser will open automatically.
echo Keep this window open while using the agent. Close it to stop.
echo.
"%PYEXE%" agent.py gui
pause
