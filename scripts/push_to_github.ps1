# Push ShipStack AI to GitHub
# Commits all changes and pushes to origin/main

$ErrorActionPreference = "Stop"

$dropship_os = Split-Path -Parent (Get-Item $PSScriptRoot).FullName
Push-Location $dropship_os

Write-Host "================================" -ForegroundColor Cyan
Write-Host "ShipStack AI — GitHub Push" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check git status
Write-Host ""
Write-Host "Current status:" -ForegroundColor Yellow
git status --short

# Stage all changes
Write-Host ""
Write-Host "Staging changes..." -ForegroundColor Yellow
git add -A

# Commit
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$commit_message = "feat: ShipStack AI build complete — Tiers 0-8, badge system, 4 services, integration tests ($timestamp)"

Write-Host ""
Write-Host "Committing: $commit_message" -ForegroundColor Yellow
git commit -m $commit_message

# Push
Write-Host ""
Write-Host "Pushing to origin/main..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "✓ Pushed to GitHub" -ForegroundColor Green
Write-Host ""

Pop-Location
