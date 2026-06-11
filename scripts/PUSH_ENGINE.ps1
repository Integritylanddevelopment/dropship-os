Set-Location "C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os"
if (Test-Path .git\index.lock) { Remove-Item .git\index.lock -Force }
git add api\engine.js index.html
git commit -m "Wire GO/PUSH buttons: engine.js intelligence layer + runStage renders results"
git push origin main
Write-Host "Pushed. Vercel auto-deploys in ~90 seconds." -ForegroundColor Green
Write-Host "Live: https://dropship-os-gamma.vercel.app" -ForegroundColor Cyan
