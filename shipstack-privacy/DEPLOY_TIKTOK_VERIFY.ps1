# Deploy shipstack-privacy with TikTok verification file
# Run this once from PowerShell — then go back to TikTok and click Verify

cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping\shipstack-privacy"

Write-Host "[DEPLOY] Deploying shipstack-privacy to Vercel..."
vercel --prod --yes

Write-Host ""
Write-Host "[DONE] Deployed. Now go to TikTok Developer Portal and click Verify."
Write-Host "       Verification URL: https://shipstack-privacy-togetherwe.vercel.app/tiktok1pOuOfCBVSjCIuykbyZAN2uNgAJNIFCf.txt"
