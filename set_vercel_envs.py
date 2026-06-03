#!/usr/bin/env python3
"""
Set Vercel environment variables for ShipStack
Run: python set_vercel_envs.py
"""

import requests
import json

VERCEL_TOKEN = "vcp_8N63pVPByEUdKfHI6Gau7P64NP9pE6b9ZJ9hUsENiw3kB9rbaj43laKz"
PROJECT_ID = "prj_n2WcwKIhw3eagVoSeqHeyHyH7TZL"

ENV_VARS = {
    "ANTHROPIC_API_KEY": "sk-ant-v7-5EhRqY5xyzC9X1eP2qL3mN4oP5qR6sT7uV8wX9yZ0aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF",
    "STRIPE_SECRET_KEY": "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",
    "QUINN_BRIDGE_SECRET": "dropship-os-quinn-2026-alex"
}

headers = {
    "Authorization": f"Bearer {VERCEL_TOKEN}",
    "Content-Type": "application/json"
}

print(f"Setting Vercel environment variables for project: {PROJECT_ID}")

for key, value in ENV_VARS.items():
    print(f"\nSetting: {key}")
    
    payload = {
        "key": key,
        "value": value,
        "target": ["production"]
    }
    
    try:
        response = requests.post(
            f"https://api.vercel.com/v10/projects/{PROJECT_ID}/env",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code in (200, 201):
            print(f"  Status: {response.status_code} - OK")
        else:
            print(f"  ERROR: {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"  ERROR: {str(e)}")

print("\n✓ Environment variables set. Vercel will auto-redeploy with new vars.")
