$desktop = "$env:USERPROFILE\Desktop"
$ws = New-Object -ComObject WScript.Shell

# Remove old name if it exists
$old = "$desktop\LAUNCH SHIPSTACK.lnk"
if (Test-Path $old) { Remove-Item $old -Force }

# Create shortcut with ship icon
$lnk = $ws.CreateShortcut("$desktop\LAUNCH SHIPSTACK AI.lnk")
$lnk.TargetPath       = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\LAUNCH SHIPSTACK AI.bat'
$lnk.WorkingDirectory = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping'
$lnk.IconLocation     = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\shipstack_icon.ico,0'
$lnk.Description      = 'Launch ShipStack AI'
$lnk.Save()

Write-Host "Ship icon shortcut created on desktop!" -ForegroundColor Green
