#!/usr/bin/env python3
"""
TikTok Shop OAuth Status Check
Validates TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN
Calls TikTok Shop API to verify seller account authorization
Appends result to DISPATCH_STATUS.md
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment
dropship_dir = Path(__file__).parent
load_dotenv(dropship_dir / ".env")

tiktok_client_key = os.getenv("TIKTOK_CLIENT_KEY")
tiktok_client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
tiktok_access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

# Check credentials
client_key_present = bool(tiktok_client_key)
client_secret_present = bool(tiktok_client_secret)
access_token_present = bool(tiktok_access_token)

print(f"[INFO] TikTok Shop Status Check — {datetime.now().isoformat()}")
print(f"[INFO] Client Key present: {client_key_present}")
print(f"[INFO] Client Secret present: {client_secret_present}")
print(f"[INFO] Access Token present: {access_token_present}")

shop_authorized = False
shop_status = "PENDING"

# If access token exists, try to validate it
if access_token_present:
    try:
        import requests
        headers = {"x-tts-access-token": tiktok_access_token}
        response = requests.get(
            "https://open-api.tiktokshops.com/api/shop/get_authorized_shop",
            headers=headers,
            timeout=10
        )
        print(f"[INFO] TikTok API response: {response.status_code}")
        if response.status_code == 200:
            shop_authorized = True
            shop_status = "ACTIVE"
            print("[OK] TikTok Shop seller account is authorized.")
        else:
            print(f"[WARN] TikTok API returned {response.status_code}")
            shop_status = "PENDING"
    except Exception as e:
        print(f"[ERROR] Failed to validate token: {str(e)}")
        shop_status = "PENDING"
else:
    print("[INFO] Access token not found. Shop authorization cannot be verified.")
    shop_status = "PENDING"

# Build dispatch status entry
today = datetime.now().strftime("%Y-%m-%d")
status_line = "PENDING" if shop_status == "PENDING" else "ACTIVE"
indicator = "[PENDING]" if status_line == "PENDING" else "[ACTIVE]"

dispatch_entry = f"""---
**{today} TikTok Shop Status Check**
- Client Key present: {"YES" if client_key_present else "NO"}
- Access Token present: {"YES" if access_token_present else "NO"}
- Shop authorized: {"YES" if shop_authorized else "NO"}
- Status: {indicator} {shop_status} — {'TikTok Shop connected. Access token is valid.' if shop_authorized else 'TikTok Shop seller account awaiting approval. Visit seller-us.tiktok.com to check application status.'}
"""

# Read existing dispatch log
dispatch_file = dropship_dir / "DISPATCH_STATUS.md"
if dispatch_file.exists():
    with open(dispatch_file, "r", encoding="utf-8") as f:
        existing = f.read()
else:
    existing = "# ShipStack AI Dispatch Log\n\n"

# Prepend new entry
updated = existing.split("\n# ShipStack AI Dispatch Log\n\n", 1)
if len(updated) > 1:
    new_content = "# ShipStack AI Dispatch Log\n\n" + dispatch_entry + "\n" + updated[1]
else:
    new_content = "# ShipStack AI Dispatch Log\n\n" + dispatch_entry + "\n" + existing

# Write updated log
with open(dispatch_file, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"[OK] DISPATCH_STATUS.md updated")
print(f"[OK] Task complete. Status: {shop_status}")

# Return result
result = {
    "status": shop_status,
    "client_key_present": client_key_present,
    "access_token_present": access_token_present,
    "shop_authorized": shop_authorized,
    "timestamp": datetime.now().isoformat()
}
print(json.dumps(result, indent=2))
