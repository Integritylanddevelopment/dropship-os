# ============================================================
# DEPLOY GARYVEE AGENT DASHBOARD TO VERCEL
# Run this in PowerShell on your Windows machine
# Prerequisites: Git installed, GitHub account with PAT token
# ============================================================

$ErrorActionPreference = "Stop"

# CONFIG
$REPO_NAME     = "garyvee-agent-dashboard"
$GITHUB_ORG    = "togetherwe"
$PROJECT_NAME  = "garyvee-agent-dashboard"
$SOURCE_FILE   = "$PSScriptRoot\GaryVee_Agent_Dashboard_DEPLOY.html"

# ---- Step 1: Get GitHub PAT token ----
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  GaryVee Dashboard - Vercel Deploy   " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You need a GitHub Personal Access Token." -ForegroundColor Yellow
Write-Host "Get one at: github.com -> Settings -> Developer settings -> PAT -> Tokens (classic) -> Generate new token (check 'repo' + 'delete_repo')" -ForegroundColor Yellow
Write-Host ""
$TOKEN = Read-Host "Paste your GitHub PAT token here" -AsSecureString
$PLAIN_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($TOKEN))
$HEADERS = @{ Authorization = "token $PLAIN_TOKEN"; "Content-Type" = "application/json" }

# ---- Step 2: Create GitHub repo ----
Write-Host ""
Write-Host "[1/4] Creating GitHub repo $GITHUB_ORG/$REPO_NAME ..." -ForegroundColor Green

$body = @{ name = $REPO_NAME; private = $false; auto_init = $false } | ConvertTo-Json
try {
    $response = Invoke-RestMethod -Uri "https://api.github.com/orgs/$GITHUB_ORG/repos" -Method POST -Headers $HEADERS -Body $body
    Write-Host "     Repo created: $($response.html_url)" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 422) {
        Write-Host "     Repo already exists — continuing." -ForegroundColor Yellow
    } else {
        Write-Host "     Error: $_" -ForegroundColor Red
        exit 1
    }
}

# ---- Step 3: Push files to GitHub ----
Write-Host "[2/4] Setting up local git and pushing..." -ForegroundColor Green

$WORKDIR = "$env:TEMP\garyvee-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Path $WORKDIR | Out-Null

# Copy source file as index.html
Copy-Item $SOURCE_FILE "$WORKDIR\index.html"

# Write vercel.json
@'
{
  "version": 2,
  "builds": [{ "src": "index.html", "use": "@vercel/static" }],
  "routes": [{ "src": "/(.*)", "dest": "/index.html" }]
}
'@ | Set-Content "$WORKDIR\vercel.json"

Set-Location $WORKDIR
git init
git checkout -b main
git config user.email "integritylanddevelopment@gmail.com"
git config user.name "Integritylanddevelopment"
git add .
git commit -m "Add GaryVee Agent Dashboard"

$REMOTE = "https://$PLAIN_TOKEN@github.com/$GITHUB_ORG/$REPO_NAME.git"
git remote add origin $REMOTE
git push -u origin main

Write-Host "     Pushed to GitHub!" -ForegroundColor Green

# ---- Step 4: Connect to Vercel (open browser) ----
Write-Host "[3/4] Opening Vercel to connect repo..." -ForegroundColor Green
Write-Host ""
Write-Host "  Vercel will auto-deploy once you import this repo." -ForegroundColor Yellow
Write-Host "  Opening: https://vercel.com/new" -ForegroundColor Yellow
Write-Host ""
Start-Process "https://vercel.com/togetherwe"

Write-Host "[4/4] Done! Steps to complete in browser:" -ForegroundColor Green
Write-Host "  1. Click 'Add New Project'" -ForegroundColor White
Write-Host "  2. Select the '$REPO_NAME' repo from GitHub" -ForegroundColor White
Write-Host "  3. Set team to 'TogetherWe-pro'" -ForegroundColor White
Write-Host "  4. Click Deploy" -ForegroundColor White
Write-Host ""
Write-Host "  Your URL will be: https://$PROJECT_NAME.vercel.app" -ForegroundColor Cyan
Write-Host ""

# Cleanup token from memory
$PLAIN_TOKEN = $null
Remove-Variable PLAIN_TOKEN, HEADERS, REMOTE
[System.GC]::Collect()

Write-Host "Script complete. Token cleared from memory." -ForegroundColor Green
