# update_vercel_endpoint.py
# Reads the active ngrok tunnel URL and updates QUINN_ENDPOINT in Vercel.
# Run this AFTER ngrok is running (START_QUINN_TUNNEL.bat).
# Requires VERCEL_TOKEN in .env

import os, requests, time, sys
from dotenv import load_dotenv

load_dotenv()

VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
PROJECT_ID   = os.getenv("VERCEL_PROJECT_ID", "prj_n2WcwKIhw3eagVoSeqHeyHyH7TZL")
TEAM_ID      = os.getenv("VERCEL_TEAM_ID",    "team_qd9zTuDQ41euDNXJwHVVPocq")

def get_ngrok_url(retries=10):
    for i in range(retries):
        try:
            r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=3)
            tunnels = r.json().get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "https":
                    return t["public_url"]
        except Exception:
            pass
        print(f"  Waiting for ngrok... ({i+1}/{retries})")
        time.sleep(2)
    return None

def get_env_var_id(token, project_id, team_id, key):
    r = requests.get(
        f"https://api.vercel.com/v10/projects/{project_id}/env",
        headers={"Authorization": f"Bearer {token}"},
        params={"teamId": team_id}
    )
    for env in r.json().get("envs", []):
        if env["key"] == key:
            return env["id"]
    return None

def update_env_var(token, project_id, team_id, env_id, value):
    r = requests.patch(
        f"https://api.vercel.com/v10/projects/{project_id}/env/{env_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"teamId": team_id},
        json={"value": value}
    )
    return r.status_code == 200

def trigger_redeploy(token, project_id, team_id):
    # Redeploy latest deployment
    r = requests.get(
        f"https://api.vercel.com/v6/deployments",
        headers={"Authorization": f"Bearer {token}"},
        params={"projectId": project_id, "teamId": team_id, "target": "production", "limit": 1}
    )
    deps = r.json().get("deployments", [])
    if deps:
        dep_id = deps[0]["uid"]
        r2 = requests.post(
            f"https://api.vercel.com/v13/deployments",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params={"teamId": team_id},
            json={"deploymentId": dep_id, "meta": {"action": "tunnel-refresh"}}
        )
        return r2.status_code in (200, 201)
    return False

if __name__ == "__main__":
    if not VERCEL_TOKEN:
        print("[ERROR] VERCEL_TOKEN not set in .env")
        print("  Get it at: https://vercel.com/account/tokens")
        print("  Add to .env: VERCEL_TOKEN=your_token_here")
        sys.exit(1)

    print("Reading ngrok tunnel URL...")
    url = get_ngrok_url()
    if not url:
        print("[ERROR] ngrok not running. Start START_QUINN_TUNNEL.bat first.")
        sys.exit(1)

    print(f"[OK] ngrok URL: {url}")

    print("Finding QUINN_ENDPOINT env var in Vercel...")
    env_id = get_env_var_id(VERCEL_TOKEN, PROJECT_ID, TEAM_ID, "QUINN_ENDPOINT")
    if not env_id:
        print("[ERROR] QUINN_ENDPOINT not found in Vercel project env vars.")
        sys.exit(1)

    print(f"Updating QUINN_ENDPOINT to: {url}")
    ok = update_env_var(VERCEL_TOKEN, PROJECT_ID, TEAM_ID, env_id, url)
    if ok:
        print("[OK] QUINN_ENDPOINT updated in Vercel.")
    else:
        print("[ERROR] Update failed — check VERCEL_TOKEN permissions.")
        sys.exit(1)

    print("Triggering Vercel redeploy...")
    trigger_redeploy(VERCEL_TOKEN, PROJECT_ID, TEAM_ID)
    print("[DONE] Vercel will redeploy in ~30 seconds with new tunnel URL.")
    print(f"[DONE] Chat on dropship-os-hazel.vercel.app now routes through Quinn at {url}")
