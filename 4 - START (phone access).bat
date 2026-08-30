@echo off
setlocal enabledelayedexpansion
title CB Agent Command Center - Phone Access
cd /d "%~dp0"
call "_find_python.bat"
if errorlevel 1 (
  echo Could not find Python. Run "1 - SETUP (run once).bat" first.
  pause
  exit /b 1
)
echo Starting with phone access enabled...
echo Look for the http://192.168.x.x address below and open it on your phone.
echo Your phone must be on the SAME Wi-Fi as this computer.
echo.
"%PYEXE%" agent.py gui --lan
pause
