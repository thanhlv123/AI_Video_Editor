@echo off
setlocal
cd /d "%~dp0"
set "BOOTSTRAP=%~dp0scripts\m131_bootstrap.py"

where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 "%BOOTSTRAP%" --install
    goto result
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%BOOTSTRAP%" --install
    goto result
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%BOOTSTRAP%" --install
    goto result
)
echo Python 3.12 was not found. Install Python 3.12 first.
pause
exit /b 1

:result
if errorlevel 1 (
    echo.
    echo Setup is incomplete. Check the messages above.
    echo Existing project files were not changed.
    pause
    exit /b 1
)
echo.
echo Creator Studio setup is ready.
echo Double-click start_creator_studio.cmd to launch the app.
pause
exit /b 0
