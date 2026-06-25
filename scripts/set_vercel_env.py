#!/usr/bin/env python3
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(r"C:\Users\integ\Documents\Claude\Projects\Drop shipping\.env"))
import os, json, urllib.request

TOKEN = os.getenv("VERCEL_TOKEN")
PROJ  = "prj_n2WcwKIhw3eagVoSeqHeyHyH7TZL"
TEAM  = "team_qd9zTuDQ41euDNXJwHVVPocq"
BASE  = f"https://api.vercel.com/v10/projects/{PROJ}/env"
HDRS  = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

patches = [
    ("GPECdWV5RL3uHKdX", "STRIPE_SECRET_KEY",   os.getenv("STRIPE_SECRET_KEY", "")),
    ("1a1SQbDCAF8y2SRG", "QUINN_BRIDGE_SECRET", os.getenv("QUINN_BRIDGE_SECRET", "")),
]

for env_id, key, val in patches:
    body = json.dumps({"value": val}).encode()
    req = urllib.request.Request(
        f"{BASE}/{env_id}?teamId={TEAM}",
        data=body, headers=HDRS, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            print(f"[OK]  {key}")
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        print(f"[ERR] {key}  HTTP {e.code}  {err}")
