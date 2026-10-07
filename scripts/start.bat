@echo off
setlocal enabledelayedexpansion

rem NanoVox Insights one-shot setup + run script (Windows), for DEVELOPMENT.
rem Clone the repo, double-click this file (or run it from a terminal) - it
rem creates the backend venv, installs backend + frontend dependencies,
rem seeds .env files from .env.example if missing, then launches both
rem servers in their own windows and opens the dashboard in your browser.
rem
rem This binds to 127.0.0.1 and runs two ports (8000 + 5173), which is right
rem for developing on this machine and wrong for anyone else reaching it -
rem including over VPN. To deploy so another machine can reach it, use
rem scripts\deploy.ps1 instead.

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\Code\Backend"
set "FRONTEND=%ROOT%\Code\Frontend"

echo === NanoVox Insights setup (Windows) ===

rem --- Locate a Python 3.14 interpreter ---
rem The backend is written in 3.14's idioms (StrEnum, datetime.UTC, PEP 695
rem generics) and will not run on an earlier one, so this looks for 3.14
rem specifically rather than whatever "python" happens to resolve to first on
rem PATH -- a machine with several versions installed otherwise silently
rem creates the venv with the wrong one.
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.14 --version >nul 2>nul
    if not errorlevel 1 set "PY=py -3.14"
)
if not defined PY (
    where python3.14 >nul 2>nul
    if not errorlevel 1 set "PY=python3.14"
)
if not defined PY (
    echo ERROR: Python 3.14 was not found. Install it from python.org and re-run this script.
    exit /b 1
)

rem --- Backend: venv + dependencies ---
if not exist "%BACKEND%\.venv" (
    echo Creating backend virtual environment...
    %PY% -m venv "%BACKEND%\.venv"
)

call "%BACKEND%\.venv\Scripts\activate.bat"
echo Installing backend dependencies...
python -m pip install --upgrade pip >nul
pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo ERROR: backend dependency install failed. See output above.
    exit /b 1
)

if not exist "%BACKEND%\.env" (
    echo Creating backend\.env from .env.example - the defaults work for a local run.
    copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
)

rem --- Database schema ---
rem SQLite creates the file on first connect but not the tables in it, so
rem without this a fresh clone starts and dies on "no such table: runs".
rem Re-running is a no-op once the schema is current.
echo Applying database migrations...
pushd "%BACKEND%"
python -m alembic upgrade head
if errorlevel 1 (
    echo ERROR: database migration failed. See output above.
    popd
    exit /b 1
)
popd

call "%BACKEND%\.venv\Scripts\deactivate.bat"

rem --- Frontend: dependencies ---
where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js was not found on PATH. Install Node 18+ from nodejs.org and re-run this script.
    exit /b 1
)

if not exist "%FRONTEND%\node_modules" (
    echo Installing frontend dependencies...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        echo ERROR: frontend dependency install failed. See output above.
        popd
        exit /b 1
    )
    popd
)

if not exist "%FRONTEND%\.env" (
    if exist "%FRONTEND%\.env.example" (
        echo Creating frontend\.env from .env.example...
        copy "%FRONTEND%\.env.example" "%FRONTEND%\.env" >nul
    )
)

rem --- Launch both servers, each in its own window ---
echo Starting backend on http://127.0.0.1:8000 ...
start "NanoVox Insights Backend" cmd /k "cd /d "%BACKEND%" && call .venv\Scripts\activate.bat && python -m uvicorn frameworks_drivers.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting frontend on http://127.0.0.1:5173 ...
start "NanoVox Insights Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo Waiting for the frontend to come up...
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo.
echo NanoVox Insights is running in two new windows - "NanoVox Insights Backend" and "NanoVox Insights Frontend".
echo Close those windows (or Ctrl+C inside them) to stop the servers.
echo.
echo This is development mode: 127.0.0.1 only. To deploy so another machine
echo (including over VPN) can reach it, use scripts\deploy.ps1 instead.
endlocal
