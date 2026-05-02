@echo off
:: ═══════════════════════════════════════════════════════════════
:: Pinterest Auto-Poster — Start Script
:: Installs deps if missing, then runs the auto-poster.
:: ═══════════════════════════════════════════════════════════════

echo.
echo  ==========================================
echo     Pinterest Auto-Poster - Starting
echo  ==========================================
echo.

set PYTHON="C:\Users\integ\AppData\Local\Programs\Python\Python312\python.exe"
set SCRIPT=%~dp0pinterest_poster.py

:: ── Step 1: Install required packages ───────────────────────────
echo  Checking dependencies...
%PYTHON% -m pip install --quiet requests pillow python-dotenv 2>nul
if errorlevel 1 (
    echo  [ERROR] pip install failed -- check Python/pip setup
    pause
    exit /b 1
)
echo  [OK] Dependencies ready
echo.

:: ── Step 2: Verify token is configured ──────────────────────────
echo  Running connection test...
%PYTHON% "%SCRIPT%" --test
echo.

:: ── Step 3: Ask user what to do ─────────────────────────────────
echo  ==========================================
echo  OPTIONS:
echo    1. Auto-post top 3 products (recommended daily)
echo    2. Auto-post top 5 products
echo    3. Generate test image card only (no posting)
echo    4. List all boards
echo    5. Exit
echo  ==========================================
echo.
set /p CHOICE="Enter 1-5: "

if "%CHOICE%"=="1" (
    echo.
    echo  [POSTING] Auto-posting top 3 products...
    %PYTHON% "%SCRIPT%" --auto --max 3
) else if "%CHOICE%"=="2" (
    echo.
    echo  [POSTING] Auto-posting top 5 products...
    %PYTHON% "%SCRIPT%" --auto --max 5
) else if "%CHOICE%"=="3" (
    echo.
    echo  [GEN CARD] Generating test image card...
    %PYTHON% "%SCRIPT%" --gen-card
) else if "%CHOICE%"=="4" (
    echo.
    %PYTHON% "%SCRIPT%" --list-boards
) else (
    echo  Exiting.
)

echo.
pause
