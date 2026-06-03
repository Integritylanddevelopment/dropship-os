# ShipStack AI — Node.js Dependency Installer
# Installs Node.js dependencies for ShipStack Express server

function Install-ShipStackDeps {
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "ShipStack AI Dependency Installer" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "[1/1] Installing Node.js dependencies..." -ForegroundColor Yellow
    try {
        cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os"
        npm install
        Write-Host "[OK] Dependencies installed" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Installation failed: $_" -ForegroundColor Red
        return
    }
    
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Green
    Write-Host "Installation Complete!" -ForegroundColor Green
    Write-Host "======================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Ensure Quinn Bridge running (port 8765)" -ForegroundColor Gray
    Write-Host "2. Ensure Qdrant running (port 6333)" -ForegroundColor Gray
    Write-Host "3. Ensure Ollama running (port 11434)" -ForegroundColor Gray
    Write-Host "4. Run: npm start" -ForegroundColor Gray
    Write-Host "5. Open http://localhost:3000" -ForegroundColor Gray
    Write-Host ""
}

# Run the installer
Install-ShipStackDeps
