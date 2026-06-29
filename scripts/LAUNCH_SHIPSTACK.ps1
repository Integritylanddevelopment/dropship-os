# ShipStack AI Launcher — Windows PowerShell
# Validates config, kills old processes, launches all services

$ErrorActionPreference = "Stop"

# Minimize window
try {
    Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(int h, int s);' -ErrorAction SilentlyContinue
    $h = (Get-Process -Id $PID).MainWindowHandle
    if ($h -ne 0) {
        [P.W]::ShowWindow($h, 6) | Out-Null
    }
} catch {}

$root = Split-Path -Parent (Get-Item $PSScriptRoot).FullName
Push-Location $root

Write-Host "================================" -ForegroundColor Cyan
Write-Host "ShipStack AI Launcher" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Step 1: Validate config
Write-Host ""
Write-Host "Step 1: Validating configuration..." -ForegroundColor Yellow
python badge/validate_config.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Config validation failed. Fix issues and try again." -ForegroundColor Red
    exit 1
}

# Step 2: Kill old processes
Write-Host ""
Write-Host "Step 2: Killing old processes..." -ForegroundColor Yellow

$ports = @{
    8889 = "ShipStack Engine"
    8766 = "Prometheus Engine"
    8867 = "Social AI Agent"
    8890 = "Dashboard"
}

foreach ($port in $ports.Keys) {
    try {
        $proc = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
        if ($proc) {
            Stop-Process -Id $proc -Force -Confirm:$false
            Write-Host "[OK] Killed port $port" -ForegroundColor Green
        }
    } catch {}
}

Start-Sleep -Seconds 2

# Step 3: Start services
Write-Host ""
Write-Host "Step 3: Starting services..." -ForegroundColor Yellow

$services = @(
    @("engines/shipstack_engine.py", 8889),
    @("engines/prometheus_engine.py", 8766),
    @("agents/social_ai_agent.py", 8867),
    @("engines/shipstack_dashboard.py", 8890)
)

$processes = @()

foreach ($service in $services) {
    $script, $port = $service
    
    $startupInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startupInfo.FileName = "python"
    $startupInfo.Arguments = $script
    $startupInfo.UseShellExecute = $false
    $startupInfo.RedirectStandardOutput = $false
    $startupInfo.CreateNoWindow = $true
    
    $proc = [System.Diagnostics.Process]::Start($startupInfo)
    $processes += $proc
    
    Write-Host "[OK] Started $script (PID $($proc.Id)) on port $port" -ForegroundColor Green
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Step 4: Waiting for services..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Step 5: Run tests
Write-Host ""
Write-Host "Step 5: Running integration tests..." -ForegroundColor Yellow
python tests/test_integration.py
# Don't exit on test failure

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "[OK] ShipStack AI is running" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green

Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  Dashboard:          http://localhost:8890" -ForegroundColor White
Write-Host "  ShipStack Engine:   http://localhost:8889" -ForegroundColor White
Write-Host "  Prometheus Engine:  http://localhost:8766" -ForegroundColor White
Write-Host "  Social AI Agent:    http://localhost:8867" -ForegroundColor White

Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Wait until user interrupts
while ($true) {
    Start-Sleep -Seconds 1
    $running = $processes | Where-Object { -not $_.HasExited }
    if ($running.Count -eq 0) {
        Write-Host "[!] All services have stopped" -ForegroundColor Yellow
        break
    }
}

Pop-Location
