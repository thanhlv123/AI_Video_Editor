@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "ACCEPTANCE=%~dp0scripts\m132_windows_local_acceptance.py"
set "REPORT=%~dp0.automation\windows_local_acceptance.json"

if not exist "%PYTHON_EXE%" (
    echo Creator Studio local environment is not ready.
    echo Run setup_creator_studio.cmd first.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%ACCEPTANCE%" --report "%REPORT%"
if errorlevel 1 (
    echo.
    echo Windows-local acceptance did not pass.
    echo Review the report:
    echo %REPORT%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo CREATOR STUDIO WINDOWS LOCAL: READY FOR USER TESTING
echo ============================================================
echo.
echo Acceptance report:
echo %REPORT%
echo.
echo Next: double-click start_creator_studio.cmd
pause
exit /b 0
