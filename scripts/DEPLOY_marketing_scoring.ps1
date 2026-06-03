# =============================================================
# DEPLOY: Marketing Scoring Sheet → GitHub → Vercel
# =============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken
)

$RepoName   = "marketing-scoring-sheet"
$OrgOrUser  = "togetherwe"
$ScriptDir  = $PSScriptRoot

Write-Host "`n[1/4] Creating GitHub repo: $OrgOrUser/$RepoName ..." -ForegroundColor Cyan

$headers = @{
    Authorization  = "Bearer $GitHubToken"
    Accept         = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

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

Write-Host "`n[2/4] Pushing Marketing_Scoring_Sheet.html to repo ..." -ForegroundColor Cyan

$tmpDir = "$env:TEMP\marketing-scoring-$(Get-Random)"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

$authUrl = $cloneUrl -replace "https://", "https://$GitHubToken@"

Set-Location $tmpDir
git init -q
git remote add origin $authUrl
Copy-Item "$ScriptDir\Marketing_Scoring_Sheet.html" "$tmpDir\index.html"
git add index.html
git -c user.email="deploy@dropship-ops.com" -c user.name="Dropship Ops" commit -m "deploy: Marketing Scoring Sheet $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -q
git branch -M main
git push -u origin main -q

Write-Host "    Pushed successfully." -ForegroundColor Green

Write-Host "`n[3/4] Opening Vercel to connect repo ..." -ForegroundColor Cyan
$importUrl = "https://vercel.com/new/import?s=https://github.com/$OrgOrUser/$RepoName&teamId=team_qd9zTuDQ41euDNXJwHVVPocq"
Start-Process $importUrl

Write-Host "`n[4/4] Done! In Vercel:" -ForegroundColor Green
Write-Host "    1. Click 'Import' on the $RepoName repo" -ForegroundColor White
Write-Host "    2. Click 'Deploy'" -ForegroundColor White
Write-Host "    3. Your URL will be: https://$RepoName.vercel.app" -ForegroundColor Yellow

Set-Location $env:USERPROFILE
Remove-Item $tmpDir -Recurse -Force
