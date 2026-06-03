# ============================================================
# DROPSHIP INTELLIGENCE AGENT — GITHUB PAGES DEPLOY SCRIPT
# ============================================================
# HOW TO USE:
#   1. Open PowerShell on your computer
#   2. Change YOUR_GITHUB_USERNAME below to your actual username
#   3. Paste this entire script and press Enter
# ============================================================

$GITHUB_USERNAME = "YOUR_GITHUB_USERNAME"   # <-- CHANGE THIS
$REPO_NAME       = "dropship-agent"
$LOCAL_PATH      = "C:\Users\$env:USERNAME\Drop shipping\dropship-agent"

Write-Host ""
Write-Host "  DROPSHIP INTELLIGENCE AGENT — DEPLOY TO GITHUB PAGES" -ForegroundColor Cyan
Write-Host "  ======================================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project folder
Set-Location $LOCAL_PATH

# Initialize git if not already done
if (-not (Test-Path ".git")) {
    Write-Host "  Initializing git repo..." -ForegroundColor Yellow
    git init
    git branch -M main
}

# Stage all files
Write-Host "  Staging files..." -ForegroundColor Yellow
git add .

# Commit
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Deploy dropship agent - $timestamp"

# Add remote (skip if already exists)
$remoteExists = git remote | Where-Object { $_ -eq "origin" }
if (-not $remoteExists) {
    Write-Host "  Adding GitHub remote..." -ForegroundColor Yellow
    git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
}

# Push
Write-Host "  Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main

Write-Host ""
Write-Host "  DONE! Your site will be live in ~60 seconds at:" -ForegroundColor Green
Write-Host "  https://$GITHUB_USERNAME.github.io/$REPO_NAME/" -ForegroundColor Green
Write-Host ""
Write-Host "  NEXT STEP: Enable GitHub Pages" -ForegroundColor Yellow
Write-Host "  Go to: https://github.com/$GITHUB_USERNAME/$REPO_NAME/settings/pages" -ForegroundColor Yellow
Write-Host "  Set Source: Deploy from branch -> main -> /docs -> Save" -ForegroundColor Yellow
Write-Host ""
