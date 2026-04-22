# DROPSHIP OS -- DEPLOY TO VERCEL
# Run this in PowerShell. Takes ~3 minutes first time.
# After setup, just run again to push updates.

$ErrorActionPreference = "Stop"
$SCRIPT_DIR  = $PSScriptRoot
$REPO_NAME   = "dropship-os"
$GITHUB_ORG  = "togetherwe"

Write-Host ""
Write-Host "  DROPSHIP OS -- Deploying to Vercel via GitHub" -ForegroundColor Cyan
Write-Host ""

# STEP 1: Get GitHub PAT
Write-Host "  [1/4] GitHub Personal Access Token" -ForegroundColor Yellow
Write-Host "        Get one at: github.com > Settings > Developer settings > PAT > Tokens (classic)" -ForegroundColor DarkGray
Write-Host "        Scope needed: repo" -ForegroundColor DarkGray
Write-Host ""
$TOKEN_SECURE = Read-Host "  Paste your GitHub PAT" -AsSecureString
$TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($TOKEN_SECURE))
$HEADERS = @{ Authorization = "token $TOKEN"; "Content-Type" = "application/json" }

# STEP 2: Create GitHub repo (skip if exists)
Write-Host ""
Write-Host "  [2/4] Setting up GitHub repo $GITHUB_ORG/$REPO_NAME..." -ForegroundColor Yellow
$repoUrl = "https://api.github.com/orgs/$GITHUB_ORG/repos"
$body = @{ name=$REPO_NAME; private=$false; description="Dropship OS - AI-powered drop shipping intelligence system" } | ConvertTo-Json
try {
    $repo = Invoke-RestMethod -Uri $repoUrl -Method Post -Headers $HEADERS -Body $body
    Write-Host "  OK Repo created: $($repo.html_url)" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 422) {
        Write-Host "  OK Repo already exists -- continuing" -ForegroundColor Green
    } else {
        $repoUrl2 = "https://api.github.com/user/repos"
        try {
            $repo = Invoke-RestMethod -Uri $repoUrl2 -Method Post -Headers $HEADERS -Body $body
            Write-Host "  OK Repo created under personal account: $($repo.html_url)" -ForegroundColor Green
            $GITHUB_ORG = (Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $HEADERS).login
        } catch {
            Write-Host "  Repo may already exist -- continuing" -ForegroundColor Yellow
        }
    }
}

# STEP 3: Git push
Write-Host ""
Write-Host "  [3/4] Pushing files to GitHub..." -ForegroundColor Yellow
Set-Location $SCRIPT_DIR

if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

git config user.email "integritylanddevelopment@gmail.com"
git config user.name "Alex Alexander"

$remoteUrl = "https://$TOKEN@github.com/$GITHUB_ORG/$REPO_NAME.git"
$existingRemote = git remote 2>$null | Where-Object { $_ -eq "origin" }
if ($existingRemote) {
    git remote set-url origin $remoteUrl
} else {
    git remote add origin $remoteUrl
}

@"
node_modules/
.env
*.log
"@ | Out-File -FilePath ".gitignore" -Encoding UTF8

git add .
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Deploy Dropship OS - $timestamp" 2>&1 | Out-Null
git push -u origin main --force
Write-Host "  OK Pushed to GitHub" -ForegroundColor Green

# STEP 4: Vercel setup instructions
Write-Host ""
Write-Host "  [4/4] Vercel setup (one-time, 2 minutes)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Go to: vercel.com > New Project" -ForegroundColor White
Write-Host "  2. Import: $GITHUB_ORG/$REPO_NAME" -ForegroundColor White
Write-Host "  3. Team: togetherwe-pro" -ForegroundColor White
Write-Host "  4. Framework: Other" -ForegroundColor White
Write-Host "  5. Deploy" -ForegroundColor White
Write-Host ""
Write-Host "  Then add Environment Variables in Vercel > Project > Settings:" -ForegroundColor Yellow
Write-Host "    ANTHROPIC_API_KEY  = sk-ant-api03-..." -ForegroundColor White
Write-Host "    QUINN_BRIDGE_SECRET = dropship-os-quinn-2026-alex" -ForegroundColor White
Write-Host "    QUINN_ENDPOINT     = (paste ngrok URL after you start the bridge)" -ForegroundColor White
Write-Host ""
Write-Host "  Your pages:" -ForegroundColor White
Write-Host "    /           Command Center" -ForegroundColor Green
Write-Host "    /playbook   Drop Ship Playbook" -ForegroundColor Green
Write-Host "    /hormozi    Hormozi Playbook" -ForegroundColor Green
Write-Host "    /ecom-king  Ecom King Playbook" -ForegroundColor Green
Write-Host "    /pinterest  Pinterest Strategy" -ForegroundColor Green
Write-Host "    /roi        ROI Intelligence Agent" -ForegroundColor Green
Write-Host ""
Write-Host "  DONE" -ForegroundColor Green
Write-Host ""
