#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Launch ShipStack Dashboard on port 8890
.DESCRIPTION
    Sets proper CWD and PYTHONPATH, then launches dashboard with pythonw.exe
#>

param()

$ErrorActionPreference = 'Continue'

# Minimize window
try {
  Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(int h, int s);' -ErrorAction SilentlyContinue
  $h = (Get-Process -Id $PID).MainWindowHandle
  if ($h -ne 0) { [P.W]::ShowWindow($h, 6) | Out-Null }
} catch {}

# Setup paths
$ShipStackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = $ShipStackRoot

Write-Host "Launching ShipStack Dashboard..."
Write-Host "Root: $ShipStackRoot"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

# Kill any stale process on port 8890
Write-Host "Checking for stale processes on port 8890..."
$staleProcess = netstat -ano 2>$null | Select-String '8890' | ForEach-Object { $_.Split()[4] }
if ($staleProcess) {
    Write-Host "Killing stale process PID $staleProcess..."
    Stop-Process -Id $staleProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# Launch dashboard
Write-Host "Starting engines/shipstack_dashboard.py..."
Start-Process pythonw.exe `
    -ArgumentList "engines\shipstack_dashboard.py" `
    -WorkingDirectory $ShipStackRoot `
    -WindowStyle Hidden `
    -NoNewWindow

Write-Host "Dashboard launching... waiting 5 seconds for startup"
Start-Sleep -Seconds 5

# Verify it's running
Write-Host "Verifying dashboard health..."
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8890/health" -TimeoutSec 3 -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) {
        Write-Host "✅ Dashboard is HEALTHY on port 8890"
        Write-Host "Open: http://127.0.0.1:8890"
    } else {
        Write-Host "⚠️  Dashboard returned status $($resp.StatusCode)"
    }
} catch {
    Write-Host "❌ Dashboard health check failed: $_"
    Write-Host "Dashboard may still be starting. Try opening http://127.0.0.1:8890 in 10 seconds"
}
