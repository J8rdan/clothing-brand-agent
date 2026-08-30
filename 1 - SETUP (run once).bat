@echo off
setlocal enabledelayedexpansion
title CB Agent - Setup
cd /d "%~dp0"
echo ============================================
echo   CB AGENT - ONE TIME SETUP
echo ============================================
echo.
echo Looking for Python...

call "_find_python.bat"
if errorlevel 1 (
  echo.
  echo [X] Could not find Python anywhere on this PC.
  echo.
  echo     1. Install from https://www.python.org/downloads/
  echo     2. Tick "Add python.exe to PATH" in the installer
  echo     3. RESTART YOUR COMPUTER  ^(this step matters^)
  echo     4. Run this file again
  echo.
  echo     Already installed? Open Settings ^> Apps ^>
  echo     Advanced app settings ^> App execution aliases
  echo     and switch OFF python.exe and python3.exe
  echo.
  pause
  exit /b 1
)

echo [OK] Found Python: %PYEXE%
"%PYEXE%" --version
echo.
echo Installing required packages, please wait...
echo.
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt
echo.

if not exist ".env" (
  if exist ".env.example" (
    copy ".env.example" ".env" >nul
    echo [OK] Created your .env file - open it in Notepad and add your keys.
  )
) else (
  echo [OK] .env already exists - leaving it alone.
)

echo.
echo ============================================
echo   Checking connections...
echo ============================================
echo.
"%PYEXE%" agent.py doctor
echo.
echo ============================================
echo   Setup finished.
echo   Next: double-click "2 - START AGENT.bat"
echo ============================================
echo.
pause
