#!/usr/bin/env python3
"""
Set Vercel environment variables for ShipStack
Run: python set_vercel_envs.py
"""

import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env (never hardcode keys here)
load_dotenv(Path(__file__).parent.parent / ".env")

VERCEL_TOKEN = os.environ["VERCEL_TOKEN"]
PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", "prj_n2WcwKIhw3eagVoSeqHeyHyH7TZL")

ENV_VARS = {
    "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
    "STRIPE_SECRET_KEY": os.environ["STRIPE_SECRET_KEY"],
    "QUINN_BRIDGE_SECRET": os.environ["QUINN_BRIDGE_SECRET"],
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
