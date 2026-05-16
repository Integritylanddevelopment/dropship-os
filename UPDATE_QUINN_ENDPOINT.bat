@echo off
:: ShipStack AI -- Update QUINN_ENDPOINT in Vercel
:: Run after getting a new ngrok URL.
:: Requires Vercel CLI: npm install -g vercel

set /p NGROK_URL="Paste your ngrok URL (e.g. https://xxxx.ngrok-free.app): "

if "%NGROK_URL%"=="" (
    echo [ERROR] No URL entered.
    pause
    exit /b 1
)

echo.
echo Updating Vercel QUINN_ENDPOINT to: %NGROK_URL%
echo.

cd /d "C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os"

:: Remove old value and set new one (non-interactive)
echo %NGROK_URL%| vercel env rm QUINN_ENDPOINT production --yes 2>nul
echo %NGROK_URL%| vercel env add QUINN_ENDPOINT production

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] vercel CLI failed. Make sure it is installed:
    echo         npm install -g vercel
    echo         vercel login
    pause
    exit /b 1
)

echo.
echo [OK] QUINN_ENDPOINT updated.
echo.
echo Triggering Vercel redeploy...
vercel --prod --yes

if %errorlevel% equ 0 (
    echo.
    echo [OK] Deployed! Live site should pick up new endpoint within 60 seconds.
) else (
    echo [WARN] Deploy step failed. Push a commit to trigger auto-deploy instead:
    echo        git commit --allow-empty -m "update quinn endpoint" ^&^& git push
)

pause
