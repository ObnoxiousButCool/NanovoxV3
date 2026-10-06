@echo off
setlocal enabledelayedexpansion

rem Windows counterpart to check.sh. Runs every gate in plan Section 10 /
rem Section 2A.7, in the same order CI runs them. Anything that fails here
rem fails the build. Run this before every commit.
rem
rem Keep this in step with check.sh - same gates, same order. Neither is the
rem "real" one; they just run on different shells.

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\Code\Backend"
set "FRONTEND=%ROOT%\Code\Frontend"
set "FAILED="

if not exist "%BACKEND%\.venv" (
    echo ERROR: backend virtual environment missing.
    echo   cd Code\Backend ^&^& py -3.14 -m venv .venv
    echo   .venv\Scripts\pip install -r requirements-dev.txt
    exit /b 1
)

set "PY=%BACKEND%\.venv\Scripts\python.exe"
set "BIN=%BACKEND%\.venv\Scripts"

echo === NanoVox Insights verification ===

pushd "%BACKEND%"

echo.
echo --- Backend: format ---
"%PY%" -m ruff format --check .
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: lint ---
"%PY%" -m ruff check .
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: types ---
"%PY%" -m mypy .
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: architecture contracts ---
"%BIN%\lint-imports.exe"
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: tests and coverage ---
"%PY%" -m pytest --cov --cov-fail-under=85
if errorlevel 1 set "FAILED=1"

echo.
echo --- Backend: exactly one migration head ---
rem `alembic heads` prints every head and exits 0, so on its own it reports
rem rather than gates. Counting the lines it marks "(head)" is what makes it
rem fail on a split history. Written to a temp file and counted with
rem `findstr` rather than piped straight into it: capturing `for /f`'s own
rem count avoids a pipe character inside the single-quoted command, which is
rem the part of batch quoting most likely to be subtly wrong.
set "HEADS_OUT=%TEMP%\nanovox-alembic-heads-%RANDOM%.txt"
"%BIN%\alembic.exe" heads > "%HEADS_OUT%"
set "HEAD_COUNT=0"
for /f %%L in ('findstr /c:"(head)" "%HEADS_OUT%"') do set /a HEAD_COUNT+=1
if not "%HEAD_COUNT%"=="1" (
    type "%HEADS_OUT%"
    echo ERROR: expected exactly one migration head, found %HEAD_COUNT%.
    set "FAILED=1"
)
del "%HEADS_OUT%" 2>nul

popd

pushd "%FRONTEND%"

echo.
echo --- Frontend: lint ---
call npm run lint
if errorlevel 1 set "FAILED=1"

echo.
echo --- Frontend: types ---
call npm run typecheck
if errorlevel 1 set "FAILED=1"

echo.
echo --- Frontend: tests and coverage ---
call npm run test:coverage
if errorlevel 1 set "FAILED=1"

echo.
echo --- Frontend: typed API client matches the backend ---
call npm run generate:api
if errorlevel 1 set "FAILED=1"
git -C "%ROOT%" diff --exit-code -- Code/Frontend/openapi.json Code/Frontend/src/shared/api/schema.ts
if errorlevel 1 (
    echo ERROR: generate:api produced a diff - commit the regenerated files.
    set "FAILED=1"
)

popd

echo.
if defined FAILED (
    echo RESULT: one or more gates FAILED. See the output above.
    exit /b 1
)
echo RESULT: all gates passed.
endlocal
