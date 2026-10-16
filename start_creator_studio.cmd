@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if defined PYTHON_EXE goto launch
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 "%~dp0run_creator_studio.py" %*
    goto done
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0run_creator_studio.py" %*
    goto done
)
echo Python 3.12 was not found. Install Python 3.12 or create .venv.
pause
exit /b 1

:launch
"%PYTHON_EXE%" "%~dp0run_creator_studio.py" %*

:done
if errorlevel 1 (
    echo.
    echo Creator Studio failed to start. Run start_creator_studio.cmd --check for details.
    pause
    exit /b 1
)
exit /b 0
