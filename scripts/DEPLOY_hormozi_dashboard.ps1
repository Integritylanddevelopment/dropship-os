# =============================================================
# DEPLOY: Hormozi Dashboard → GitHub → Vercel
# Run this from PowerShell on your Windows machine
# You need a GitHub Personal Access Token (classic) with repo scope
# Get one at: https://github.com/settings/tokens
# =============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken
)

$RepoName   = "hormozi-dashboard"
$OrgOrUser  = "togetherwe"       # GitHub org
$SourceFile = "$PSScriptRoot\Hormozi_Dashboard_v2.html"

Write-Host "`n[1/4] Creating GitHub repo: $OrgOrUser/$RepoName ..." -ForegroundColor Cyan

$headers = @{
    Authorization  = "Bearer $GitHubToken"
    Accept         = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

# Try org first, fall back to personal
$body = @{ name = $RepoName; private = $false; auto_init = $false } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "https://api.github.com/orgs/$OrgOrUser/repos" `
    -Method POST -Headers $headers -Body $body -ContentType "application/json" `
    -ErrorVariable orgErr -ErrorAction SilentlyContinue

if (-not $resp) {
    $resp = Invoke-RestMethod -Uri "https://api.github.com/user/repos" `
        -Method POST -Headers $headers -Body $body -ContentType "application/json"
    $OrgOrUser = (Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers).login
}

$cloneUrl = $resp.clone_url
Write-Host "    Repo created: $cloneUrl" -ForegroundColor Green

# [2/4] Push the file
Write-Host "`n[2/4] Pushing Hormozi_Dashboard_v2.html to repo ..." -ForegroundColor Cyan

$tmpDir = "$env:TEMP\hormozi-deploy-$(Get-Random)"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

# Configure git with token
$authUrl = $cloneUrl -replace "https://", "https://$GitHubToken@"

Set-Location $tmpDir
git init -q
git remote add origin $authUrl
Copy-Item $SourceFile "$tmpDir\index.html"
git add index.html
git -c user.email="deploy@hormozi-ops.com" -c user.name="Hormozi Ops" commit -m "deploy: Hormozi Dashboard $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -q
git branch -M main
git push -u origin main -q

Write-Host "    Pushed successfully." -ForegroundColor Green

# [3/4] Open Vercel import page
Write-Host "`n[3/4] Opening Vercel to connect repo ..." -ForegroundColor Cyan
$importUrl = "https://vercel.com/new/import?s=https://github.com/$OrgOrUser/$RepoName&teamId=team_qd9zTuDQ41euDNXJwHVVPocq"
Start-Process $importUrl

Write-Host "`n[4/4] Done! In Vercel:" -ForegroundColor Green
Write-Host "    1. Click 'Import' on the $RepoName repo" -ForegroundColor White
Write-Host "    2. Click 'Deploy' (no config changes needed)" -ForegroundColor White
Write-Host "    3. Your URL will be: https://$RepoName-togetherwe.vercel.app" -ForegroundColor Yellow
Write-Host "`n    Future updates: just re-run this script — Vercel auto-deploys on every push.`n" -ForegroundColor Cyan

# Cleanup
Set-Location $env:USERPROFILE
Remove-Item $tmpDir -Recurse -Force
