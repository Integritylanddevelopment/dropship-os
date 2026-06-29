# ShipStack AI Launcher -- Windows PowerShell
# Each service gets its own minimized console window with visible stdout/stderr.
# If a service crashes, its window stays open so you can read the error.
# Restore a window from the taskbar to see live output.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Get-Item $PSScriptRoot).FullName
Push-Location $root

# Resolve Python
$pythonExe = $null
try { $pythonExe = (Get-Command python -ErrorAction Stop).Source } catch {}
if (-not $pythonExe) {
    try { $pythonExe = (Get-Command py -ErrorAction Stop).Source } catch {}
}
if (-not $pythonExe) {
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
        $match = Select-String -Path $envFile -Pattern "^PYTHON_EXE=(.+)$" | Select-Object -First 1
        if ($match) { $pythonExe = $match.Matches[0].Groups[1].Value.Trim() }
    }
}
if (-not $pythonExe) {
    $pythonExe = "C:\Users\integ\AppData\Local\Programs\Python\Python312\python.exe"
}

Write-Host "================================" -ForegroundColor Cyan
Write-Host "ShipStack AI Launcher" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Python: $pythonExe" -ForegroundColor Gray

# Step 1: Validate config
Write-Host ""
Write-Host "Step 1: Validating configuration..." -ForegroundColor Yellow
& $pythonExe badge/validate_config.py

# Step 2: Kill old processes
Write-Host ""
Write-Host "Step 2: Killing old processes..." -ForegroundColor Yellow

@(8889, 8766, 8867, 8890) | ForEach-Object {
    try {
        $procs = Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $procs) {
            if ($p -and $p -ne 0) {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                Write-Host "  Killed PID $p on port $_" -ForegroundColor Green
            }
        }
    } catch {}
}

Start-Sleep -Seconds 2

# Step 3: Launch each service in its own minimized console window.
#   - Window title = service name (visible in taskbar)
#   - stdout/stderr print directly to the console (not swallowed)
#   - If Python crashes (non-zero exit), the window stays open with a message
Write-Host ""
Write-Host "Step 3: Starting services..." -ForegroundColor Yellow

$services = @(
    @{ Script = "engines\shipstack_engine.py";    Port = 8889; Title = "ShipStack Engine :8889" },
    @{ Script = "engines\prometheus_engine.py";   Port = 8766; Title = "Prometheus Engine :8766" },
    @{ Script = "agents\social_ai_agent.py";      Port = 8867; Title = "Social AI Agent :8867" },
    @{ Script = "engines\shipstack_dashboard.py";  Port = 8890; Title = "Dashboard :8890" }
)

$processes = @()

foreach ($svc in $services) {
    $scriptFull = Join-Path $root $svc.Script

    # cmd /c: runs Python, if it exits non-zero the window stays open for 60s
    $cmdLine = "title $($svc.Title) && cd /d `"$root`" && `"$pythonExe`" `"$scriptFull`" || (echo. && echo =============================== && echo [CRASHED] $($svc.Title) && echo See error above && echo =============================== && timeout /t 60)"

    $proc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", $cmdLine `
        -WorkingDirectory $root `
        -WindowStyle Minimized `
        -PassThru

    $processes += $proc
    Write-Host "  Started $($svc.Title) (PID $($proc.Id))" -ForegroundColor Green
    Start-Sleep -Milliseconds 800
}

# Step 4: Wait for services to bind
Write-Host ""
Write-Host "Step 4: Waiting for services to start (8s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

# Step 5: Health check
Write-Host ""
Write-Host "Step 5: Health checks..." -ForegroundColor Yellow
$allHealthy = $true
foreach ($svc in $services) {
    $url = "http://localhost:$($svc.Port)/health"
    try {
        $null = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-Host "  [OK] $($svc.Title) -- healthy" -ForegroundColor Green
    } catch {
        Write-Host "  [X]  $($svc.Title) -- NOT responding" -ForegroundColor Red
        Write-Host "       Restore its window from the taskbar to see the error" -ForegroundColor DarkYellow
        $allHealthy = $false
    }
}

if ($allHealthy) {
    Write-Host ""
    Write-Host "================================" -ForegroundColor Green
    Write-Host "[OK] All ShipStack services running" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "================================" -ForegroundColor Yellow
    Write-Host "[!] Some services failed" -ForegroundColor Yellow
    Write-Host "    Restore minimized windows to see crash output" -ForegroundColor Yellow
    Write-Host "================================" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  Dashboard:          http://localhost:8890" -ForegroundColor White
Write-Host "  ShipStack Engine:   http://localhost:8889" -ForegroundColor White
Write-Host "  Prometheus Engine:  http://localhost:8766" -ForegroundColor White
Write-Host "  Social AI Agent:    http://localhost:8867" -ForegroundColor White
Write-Host ""
Write-Host "Tip: Each service is a minimized window in your taskbar." -ForegroundColor DarkGray
Write-Host "     Restore it to see live stdout/stderr." -ForegroundColor DarkGray
Write-Host "     If it crashed, the window stays open for 60s." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Keep launcher alive until all services exit or Ctrl+C
while ($true) {
    Start-Sleep -Seconds 3
    $running = $processes | Where-Object { -not $_.HasExited }
    if ($running.Count -eq 0) {
        Write-Host "[!] All services have stopped. Check their windows for errors." -ForegroundColor Yellow
        break
    }
}

Pop-Location
