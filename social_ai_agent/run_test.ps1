# Pinterest API test — writes result to test_result.txt
$token = (Get-Content "$PSScriptRoot\..\.env" | Where-Object { $_ -match '^PINTEREST_ACCESS_TOKEN=' }) -replace '^PINTEREST_ACCESS_TOKEN=',''
$token = $token.Trim()

$headers = @{ Authorization = "Bearer $token"; Accept = "application/json" }

try {
    $acct = Invoke-RestMethod -Uri "https://api.pinterest.com/v5/user_account" -Headers $headers -Method Get
    $boards = Invoke-RestMethod -Uri "https://api.pinterest.com/v5/boards?page_size=10" -Headers $headers -Method Get

    $out = @"
[OK] Pinterest token VALID
Username: $($acct.username)
Account type: $($acct.account_type)

Boards:
"@
    foreach ($b in $boards.items) {
        $out += "`n  $($b.name)  ID=$($b.id)"
    }
    $out | Out-File "$PSScriptRoot\test_result.txt" -Encoding UTF8
    Write-Host $out
} catch {
    $err = "[ERROR] $($_.Exception.Message)"
    $err | Out-File "$PSScriptRoot\test_result.txt" -Encoding UTF8
    Write-Host $err
}
Write-Host "`nResult saved to test_result.txt"
pause
