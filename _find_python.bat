@echo off
REM Locates a working Python and sets PYEXE. Tries PATH, the py launcher,
REM then the standard install locations Windows uses.
set "PYEXE="

python --version >nul 2>&1 && set "PYEXE=python" && goto :found
py --version >nul 2>&1 && set "PYEXE=py" && goto :found

for %%D in (
  "%LOCALAPPDATA%\Programs\Python"
  "%ProgramFiles%"
  "%ProgramFiles(x86)%"
  "C:\"
) do (
  for /f "delims=" %%P in ('dir /b /s "%%~D\python.exe" 2^>nul') do (
    echo %%P | find /i "WindowsApps" >nul || (
      set "PYEXE=%%P"
      goto :found
    )
  )
)

exit /b 1
:found
exit /b 0
