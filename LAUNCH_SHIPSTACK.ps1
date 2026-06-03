#requires -Version 5.1
# ============================================================
#  LAUNCH_SHIPSTACK.ps1 - ShipStack AI Dashboard Launcher
#  Owner: Alex Alexander
#  Last updated: 2026-06-02
#
#  Double-click to launch ShipStack dashboard on port 3000.
#  Checks that Quinn Bridge (port 8765) is running first.
#  If Quinn services not ready, offers to launch Quinn.
#
#  ShipStack manages ONLY its own Express.js server.
#  Quinn Bridge (and Qdrant/Ollama) are EXTERNAL dependencies
#  managed by Quinn's own LAUNCH_QUINN.ps1
# ============================================================
$ErrorActionPreference = 'Continue'
$Host.UI.RawUI.WindowTitle = 'LAUNCH SHIPSTACK'

# Self-minimize so PowerShell windows don't pile up on screen
try {
  Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(int h, int s);' -ErrorAction SilentlyContinue
  $h = (Get-Process -Id $PID).MainWindowHandle
  if ($h -ne 0) { [P.W]::ShowWindow($h, 6) | Out-Null }  # 6 = SW_MINIMIZE
} catch {}

# ---- Paths (single source of truth) ----
$SHIPSTACK_DIR = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os'
$SHIPSTACK_LOG = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs'
$QUINN_LAUNCHER = 'C:\Users\integ\quinn-proxy\LAUNCH_QUINN.ps1'
$NPM_EXE = 'npm'
$NODE_EXE = 'node'

# Create log directory
New-Item -ItemType Directory -Force $SHIPSTACK_LOG | Out-Null

# ---- Helpers ----
function Head($txt) { Write-Host ""; Write-Host "==== $txt ====" -ForegroundColor Magenta }
function OK($txt) { Write-Host "  [OK]   $txt" -ForegroundColor Green }
function W($txt)  { Write-Host "  [WARN] $txt" -ForegroundColor Yellow }
function E($txt)  { Write-Host "  [FAIL] $txt" -ForegroundColor Red }
function I($txt)  { Write-Host "  [..]   $txt" -ForegroundColor Cyan }

function Test-Url($u, $timeout=3) {
  try { Invoke-WebRequest $u -TimeoutSec $timeout -UseBasicParsing -EA Stop | Out-Null; return $true }
  catch { return $false }
}

function Wait-Url($u, $sec=30) {
  $end = (Get-Date).AddSeconds($sec)
  while ((Get-Date) -lt $end) {
    if (Test-Url $u) { return $true }
    Start-Sleep 1
  }
  return $false
}

Write-Host ""
Write-Host "  LAUNCH SHIPSTACK" -ForegroundColor Cyan
Write-Host "  Dir  : $SHIPSTACK_DIR"
Write-Host "  Log  : $SHIPSTACK_LOG"

# ============================================================
# STEP 1 - Check Quinn Bridge (external dependency)
# ============================================================
Head "STEP 1 - Verify Quinn Bridge (port 8765)"

if (Test-Url 'http://127.0.0.1:8765/health' 3) {
  OK "Quinn Bridge responding on :8765"
} else {
  E "Quinn Bridge NOT responding on :8765"
  Write-Host ""
  Write-Host "  Quinn services are required for ShipStack to work:" -ForegroundColor Yellow
  Write-Host "    - Qdrant vector database (port 6333)" -ForegroundColor Yellow
  Write-Host "    - Ollama local inference (port 11434)" -ForegroundColor Yellow
  Write-Host "    - Quinn Bridge (port 8765)" -ForegroundColor Yellow
  Write-Host ""

  $response = Read-Host "  Launch Quinn now? (y/n)"
  if ($response -eq 'y' -or $response -eq 'Y') {
    Write-Host ""
    I "Launching Quinn launcher..."
    if (Test-Path $QUINN_LAUNCHER) {
      Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$QUINN_LAUNCHER`""
      I "Waiting 45 seconds for Quinn to fully boot..."
      Start-Sleep 45

      if (Test-Url 'http://127.0.0.1:8765/health' 3) {
        OK "Quinn Bridge is now responding"
      } else {
        E "Quinn Bridge still not responding. Check Quinn logs at C:\Users\integ\quinn-proxy\logs"
        Write-Host ""
        Write-Host "Press Enter to exit..."
        Read-Host | Out-Null
        exit 1
      }
    } else {
      E "Quinn launcher not found at: $QUINN_LAUNCHER"
      Write-Host "Press Enter to exit..."
      Read-Host | Out-Null
      exit 1
    }
  } else {
    Write-Host ""
    E "Quinn Bridge is required. Cannot continue without it."
    Write-Host "Press Enter to exit..."
    Read-Host | Out-Null
    exit 1
  }
}

# ============================================================
# STEP 2 - Kill stale ShipStack process on port 3000
# ============================================================
Head "STEP 2 - Clear stale ShipStack ports"
foreach ($port in 3000) {
  try {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
      $pid_ = $c.OwningProcess
      if ($pid_ -and $pid_ -ne 0) {
        Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
        I "killed PID $pid_ on port $port"
      }
    }
  } catch {}
}
Start-Sleep 1
OK "Port 3000 cleared"

# ============================================================
# STEP 3 - Ensure npm dependencies installed
# ============================================================
Head "STEP 3 - Verify npm dependencies"
if (-not (Test-Path (Join-Path $SHIPSTACK_DIR 'node_modules'))) {
  I "node_modules not found - running npm install..."
  Push-Location $SHIPSTACK_DIR
  & $NPM_EXE install 2>&1 | Tee-Object -FilePath (Join-Path $SHIPSTACK_LOG 'npm-install.log')
  Pop-Location
  if ($LASTEXITCODE -eq 0) {
    OK "npm install completed"
  } else {
    E "npm install failed - check log at $(Join-Path $SHIPSTACK_LOG 'npm-install.log')"
    Write-Host ""
    Write-Host "Press Enter to exit..."
    Read-Host | Out-Null
    exit 1
  }
} else {
  OK "node_modules already installed"
}

# ============================================================
# STEP 4 - Launch ShipStack Express server
# ============================================================
Head "STEP 4 - Launch ShipStack (port 3000)"
$shipstackLog = Join-Path $SHIPSTACK_LOG 'shipstack.log'
$shipstackErr = "$shipstackLog.err"

Push-Location $SHIPSTACK_DIR
Start-Process -FilePath $NODE_EXE -ArgumentList "server.js" -WindowStyle Minimized -RedirectStandardOutput $shipstackLog -RedirectStandardError $shipstackErr
Pop-Location

if (Wait-Url 'http://127.0.0.1:3000' 15) {
  OK "ShipStack responding on :3000 (log: $shipstackLog)"
} else {
  E "ShipStack NOT responding on :3000 after 15s - check $shipstackErr"
  Write-Host ""
  Write-Host "Tail of error log:"
  Get-Content $shipstackErr -Tail 10
  Write-Host ""
  Write-Host "Press Enter to exit..."
  Read-Host | Out-Null
  exit 1
}

# ============================================================
# SUMMARY
# ============================================================
Head "SHIPSTACK READY"
Write-Host ""
Write-Host "  ShipStack Dashboard  http://127.0.0.1:3000"  -ForegroundColor White
Write-Host "  Quinn Bridge         http://127.0.0.1:8765"  -ForegroundColor White
Write-Host "  Qdrant               http://127.0.0.1:6333"  -ForegroundColor White
Write-Host "  Ollama               http://127.0.0.1:11434" -ForegroundColor White
Write-Host ""
Write-Host "  Logs: $SHIPSTACK_LOG"  -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Dashboard is opening in your browser..." -ForegroundColor DarkGray

# Open browser to dashboard
Start-Process 'http://127.0.0.1:3000'

Write-Host ""
Write-Host "  To STOP ShipStack: close this window or press Ctrl+C" -ForegroundColor DarkGray
Write-Host "  To STOP all services: close Quinn launcher window" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Press Enter to close this window..." -ForegroundColor DarkGray
Read-Host | Out-Null
