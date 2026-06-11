#requires -Version 5.1
# ============================================================
#  PUSH_SHIPSTACK_TO_GITHUB.ps1
#  ShipStack AI GitHub push tool
#  Owner: Alex Alexander
#  Last updated: 2026-06-02
#
#  Pushes all ShipStack changes to GitHub:
#  github.com/Integritylanddevelopment/dropship-os
#
#  Usage:
#    1. Double-click this script
#    2. Enter commit message when prompted
#    3. Script pushes to origin main
#
#  NOTE: This is ShipStack-specific and does NOT touch Quinn codebase
# ============================================================
$ErrorActionPreference = 'Continue'

# Paths
$SHIPSTACK_DIR = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os'
$GIT_EXE = 'C:\Program Files\Git\bin\git.exe'
$LOG_DIR = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs'

# Create log directory
New-Item -ItemType Directory -Force $LOG_DIR | Out-Null

# ---- Helpers ----
function Head($txt) { Write-Host ""; Write-Host "==== $txt ====" -ForegroundColor Magenta }
function OK($txt) { Write-Host "  [OK]   $txt" -ForegroundColor Green }
function E($txt)  { Write-Host "  [FAIL] $txt" -ForegroundColor Red }
function I($txt)  { Write-Host "  [..]   $txt" -ForegroundColor Cyan }

Write-Host ""
Write-Host "  PUSH SHIPSTACK TO GITHUB" -ForegroundColor Cyan
Write-Host "  Repo: github.com/Integritylanddevelopment/dropship-os" -ForegroundColor DarkGray
Write-Host "  Dir : $SHIPSTACK_DIR" -ForegroundColor DarkGray

# Check git exists
if (-not (Test-Path $GIT_EXE)) {
  E "Git not found at: $GIT_EXE"
  Write-Host "Press Enter to exit..."
  Read-Host | Out-Null
  exit 1
}

# Check ShipStack directory exists
if (-not (Test-Path $SHIPSTACK_DIR)) {
  E "ShipStack directory not found at: $SHIPSTACK_DIR"
  Write-Host "Press Enter to exit..."
  Read-Host | Out-Null
  exit 1
}

# Check .git exists
if (-not (Test-Path (Join-Path $SHIPSTACK_DIR '.git'))) {
  E "Not a git repo. Run: cd $SHIPSTACK_DIR && git init"
  Write-Host "Press Enter to exit..."
  Read-Host | Out-Null
  exit 1
}

# Get commit message
Write-Host ""
$message = Read-Host "Enter commit message (or press Enter for default)"
if ([string]::IsNullOrWhiteSpace($message)) {
  $message = 'ShipStack update ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
}

# Log file
$logFile = Join-Path $LOG_DIR "git-push-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

Head "STEP 1 - Clean lock files"
Remove-Item (Join-Path $SHIPSTACK_DIR '.git\index.lock') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $SHIPSTACK_DIR '.git\HEAD.lock') -Force -ErrorAction SilentlyContinue
OK "Lock files cleared"

Head "STEP 2 - Git status"
I "Checking uncommitted changes..."
& $GIT_EXE -C $SHIPSTACK_DIR status 2>&1 | Tee-Object -FilePath $logFile

Head "STEP 3 - Stage all changes"
I "Running: git add -A"
& $GIT_EXE -C $SHIPSTACK_DIR add -A 2>&1 | Tee-Object -FilePath $logFile -Append
OK "Changes staged"

head "STEP 4 - Commit"
I "Running: git commit -m `"$message`""
& $GIT_EXE -C $SHIPSTACK_DIR commit -m "$message" 2>&1 | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -eq 0) {
  OK "Commit successful"
} elseif ($LASTEXITCODE -eq 1) {
  I "Nothing to commit (clean working tree)"
} else {
  E "Commit failed with exit code $LASTEXITCODE - check log at $logFile"
  Write-Host "Press Enter to exit..."
  Read-Host | Out-Null
  exit 1
}

head "STEP 5 - Push to GitHub"
I "Running: git push origin main"
& $GIT_EXE -C $SHIPSTACK_DIR push origin main 2>&1 | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -eq 0) {
  OK "Push successful"
} else {
  E "Push failed with exit code $LASTEXITCODE - check log at $logFile"
  Write-Host "Press Enter to exit..."
  Read-Host | Out-Null
  exit 1
}

head "COMPLETE"
Write-Host ""
Write-Host "  Repository: github.com/Integritylanddevelopment/dropship-os" -ForegroundColor White
Write-Host "  Branch    : main" -ForegroundColor White
Write-Host "  Message   : $message" -ForegroundColor White
Write-Host "  Log file  : $logFile" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Push complete!" -ForegroundColor Green
Write-Host "Press Enter to close..."
Read-Host | Out-Null
