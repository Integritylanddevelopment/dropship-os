import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""GitHub image hosting for Pinterest/social cards.

Pinterest's API requires a publicly reachable image_url. We push card PNGs to
the GitHub repo (GITHUB_PAGES_REPO) via the Contents API and return the
raw.githubusercontent.com URL, which is immediately public.

Env required: GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_PAGES_REPO
"""
import os
import base64
import json
import time
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).parent.parent
    load_dotenv(_root / ".env")
    load_dotenv(_root / ".env.local", override=True)
except ImportError:
    pass

API_BASE = "https://api.github.com"


def _cfg():
    token = os.getenv("GITHUB_TOKEN", "")
    user = os.getenv("GITHUB_USERNAME", "")
    repo = os.getenv("GITHUB_PAGES_REPO", "")
    if not (token and user and repo):
        raise RuntimeError("GitHub hosting not configured: need GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_PAGES_REPO in .env")
    return token, user, repo


def _api(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ShipStack-ImageHost/1.0",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"GitHub API {e.code}: {body}")


def upload_image(local_path: str, dest_name: str | None = None, branch: str = "main") -> str:
    """Upload a local image to GitHub, return the public raw URL."""
    token, user, repo = _cfg()
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(local_path)

    dest = dest_name or f"{int(time.time())}_{p.name}"
    repo_path = f"cards/{dest}"
    url = f"{API_BASE}/repos/{user}/{repo}/contents/{repo_path}"

    content_b64 = base64.b64encode(p.read_bytes()).decode()

    # Check if file exists (need sha to update)
    sha = None
    try:
        existing = _api("GET", f"{url}?ref={branch}", token)
        sha = existing.get("sha")
    except Exception:
        pass

    payload = {
        "message": f"card: {dest}",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    _api("PUT", url, token, payload)
    return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{repo_path}"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(upload_image(sys.argv[1]))
    else:
        print("usage: python github_image_host.py <image_path>")
