@echo off
:: ShipStack AI -- Start All Local Services
:: Run this before using the live site chat or Prometheus features.

call "C:\Users\integ\Scripts\kill-port.bat" 8765

echo.
echo ====================================================
echo  ShipStack AI -- Local Stack Launcher
echo ====================================================
echo.

:: Check Local AI Stack
if not exist "C:\Users\integ\Projects\Claude-Local-LLM-Stack\quinn_web_bridge.py" (
    echo [ERROR] Local AI Stack not found.
    echo         Expected: C:\Users\integ\Projects\Claude-Local-LLM-Stack\
    pause
    exit /b 1
)

echo [1/3] Starting Quinn Web Bridge on port 8765...
start "Quinn Web Bridge" cmd /k "cd /d C:\Users\integ\Projects\Claude-Local-LLM-Stack && python quinn_web_bridge.py"
timeout /t 4 /nobreak > nul

echo [2/3] Exposing Quinn bridge via ngrok...
echo        When ngrok opens, copy the https:// URL.
start "ngrok" cmd /k "ngrok http 8765"
timeout /t 3 /nobreak > nul

echo [3/3] When you have the ngrok URL, run:
echo.
echo        UPDATE_QUINN_ENDPOINT.bat
echo.
echo        That will push the URL to Vercel and redeploy.
echo.
pause
