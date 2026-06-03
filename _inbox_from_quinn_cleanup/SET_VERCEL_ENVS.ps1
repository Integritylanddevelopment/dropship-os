# Set Vercel Environment Variables for ShipStack
# Run: .\SET_VERCEL_ENVS.ps1

$VERCEL_TOKEN = "vcp_8N63pVPByEUdKfHI6Gau7P64NP9pE6b9ZJ9hUsENiw3kB9rbaj43laKz"
$PROJECT_ID = "prj_n2WcwKIhw3eagVoSeqHeyHyH7TZL"
$TEAM_ID = "team_qd9zTuDQ41euDNXJwHVVPocq"

# Environment variables to set
$ENV_VARS = @(
    @{
        key = "ANTHROPIC_API_KEY"
        value = "sk-ant-v7-5EhRqY5xyzC9X1eP2qL3mN4oP5qR6sT7uV8wX9yZ0aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF"
    },
    @{
        key = "STRIPE_SECRET_KEY"
        value = "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"
    },
    @{
        key = "QUINN_BRIDGE_SECRET"
        value = "dropship-os-quinn-2026-alex"
    }
)

Write-Host "Setting Vercel environment variables for project: $PROJECT_ID"

foreach ($env_var in $ENV_VARS) {
    Write-Host "`nSetting: $($env_var.key)"
    
    $body = @{
        key = $env_var.key
        value = $env_var.value
        target = @("production")
    } | ConvertTo-Json
    
    $headers = @{
        "Authorization" = "Bearer $VERCEL_TOKEN"
        "Content-Type" = "application/json"
    }
    
    try {
        $response = Invoke-WebRequest `
            -Uri "https://api.vercel.com/v10/projects/$PROJECT_ID/env" `
            -Method POST `
            -Headers $headers `
            -Body $body
        
        Write-Host "  Status: $($response.StatusCode) - OK"
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)"
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $reader.BaseStream.Position = 0
            $reader.DiscardBufferedData()
            $responseBody = $reader.ReadToEnd()
            Write-Host "  Response: $responseBody"
        }
    }
}

Write-Host "`n✓ Environment variables set. Vercel will auto-redeploy with new vars."
