@echo off
cd /d "%~dp0"
echo Pushing to GitHub...
git push origin main
if errorlevel 1 (
  echo.
  echo Push failed - if credentials needed, run DEPLOY.ps1 with your GitHub PAT
  pause
) else (
  echo.
  echo Pushed successfully - Vercel will auto-deploy in ~60 seconds
  echo Live: https://dropship-os-hazel.vercel.app
  timeout /t 4
)
