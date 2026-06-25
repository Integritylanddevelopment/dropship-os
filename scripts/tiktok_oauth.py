import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""
tiktok_oauth.py -- TikTok OAuth 2.0 Helper for ShipStack
=========================================================
Walks Alex through the TikTok OAuth flow to obtain an access token
for the Content Posting API.

Usage:
    python scripts/tiktok_oauth.py

Requires TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env.
"""

import os
import json
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
    load_dotenv(Path(__file__).parent.parent / '.env.local', override=True)
except ImportError:
    print("WARNING: python-dotenv not installed. Reading env vars from system environment only.")

# ── Config ───────────────────────────────────────────────────────────────────
CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
CALLBACK_PORT = 8868
REDIRECT_URI  = f"http://localhost:{CALLBACK_PORT}/callback"
SCOPES        = "video.publish,video.upload,video.list,user.info.basic"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"
ENV_LOCAL     = Path(__file__).parent.parent / '.env.local'


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect from TikTok."""

    auth_code = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/callback" and "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization received!</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        elif "error" in params:
            error = params.get("error", ["unknown"])[0]
            desc  = params.get("error_description", [""])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>Error: {error}</h2><p>{desc}</p></body></html>".encode()
            )
            print(f"\nERROR from TikTok: {error} - {desc}")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default request logging
        pass


def exchange_code_for_token(code: str) -> dict:
    """Exchange the authorization code for an access token."""
    import urllib.request

    payload = urllib.parse.urlencode({
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def save_tokens(access_token: str, refresh_token: str = "", expires_in: int = 0):
    """Append or update tokens in .env.local."""
    lines = []
    if ENV_LOCAL.exists():
        lines = ENV_LOCAL.read_text(encoding="utf-8").splitlines()

    # Remove old token lines
    lines = [
        ln for ln in lines
        if not ln.startswith("TIKTOK_ACCESS_TOKEN=")
        and not ln.startswith("TIKTOK_REFRESH_TOKEN=")
        and not ln.startswith("TIKTOK_TOKEN_EXPIRES=")
    ]

    lines.append(f"TIKTOK_ACCESS_TOKEN={access_token}")
    if refresh_token:
        lines.append(f"TIKTOK_REFRESH_TOKEN={refresh_token}")
    if expires_in:
        import time
        expires_at = int(time.time()) + expires_in
        lines.append(f"TIKTOK_TOKEN_EXPIRES={expires_at}")

    ENV_LOCAL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nTokens saved to {ENV_LOCAL}")


def main():
    print("=" * 60)
    print("  TikTok OAuth 2.0 Helper -- ShipStack")
    print("=" * 60)

    # Validate config
    if not CLIENT_KEY:
        print("\nERROR: TIKTOK_CLIENT_KEY not found in .env")
        print("  1. Go to https://developers.tiktok.com/apps")
        print("  2. Create an app or open your existing one")
        print("  3. Copy the Client Key and add to .env:")
        print("       TIKTOK_CLIENT_KEY=your_key_here")
        sys.exit(1)

    if not CLIENT_SECRET:
        print("\nERROR: TIKTOK_CLIENT_SECRET not found in .env")
        print("  Add to .env:  TIKTOK_CLIENT_SECRET=your_secret_here")
        sys.exit(1)

    # Build authorization URL
    auth_params = urllib.parse.urlencode({
        "client_key":    CLIENT_KEY,
        "scope":         SCOPES,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
    })
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{auth_params}"

    print(f"\nStep 1: Make sure your TikTok app's redirect URI is set to:")
    print(f"        {REDIRECT_URI}")
    print()
    print(f"Step 2: Open this URL in your browser:")
    print()
    print(f"  {auth_url}")
    print()
    print(f"Step 3: Log in to TikTok and approve the permissions.")
    print(f"        The browser will redirect to localhost:{CALLBACK_PORT}.")
    print()
    print(f"Waiting for OAuth callback on port {CALLBACK_PORT}...")
    print(f"(Press Ctrl+C to cancel)")
    print()

    # Start callback server
    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 300  # 5-minute timeout

    while OAuthCallbackHandler.auth_code is None:
        server.handle_request()

    server.server_close()
    code = OAuthCallbackHandler.auth_code
    print(f"\nAuthorization code received: {code[:12]}...")

    # Exchange code for token
    print("Exchanging code for access token...")
    try:
        result = exchange_code_for_token(code)
    except Exception as e:
        print(f"\nERROR exchanging code: {e}")
        print("The authorization code may have expired. Run this script again.")
        sys.exit(1)

    # Parse response
    # TikTok v2 returns tokens at the top level or inside "data"
    token_data = result.get("data", result)
    access_token  = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", 0)
    open_id       = token_data.get("open_id", "")
    scope         = token_data.get("scope", "")

    if not access_token:
        print(f"\nERROR: No access token in response:")
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # Display results
    print()
    print("-" * 60)
    print("  SUCCESS -- TikTok OAuth complete")
    print("-" * 60)
    print(f"  Access Token:  {access_token[:20]}...")
    print(f"  Refresh Token: {refresh_token[:20]}..." if refresh_token else "  Refresh Token: (none)")
    print(f"  Expires In:    {expires_in} seconds ({expires_in // 3600} hours)" if expires_in else "  Expires In:    unknown")
    print(f"  Open ID:       {open_id}" if open_id else "")
    print(f"  Scopes:        {scope}" if scope else "")
    print("-" * 60)

    # Save to .env.local
    save_tokens(access_token, refresh_token, expires_in)

    print("\nDone! You can now use:")
    print("  python social_ai_agent/tiktok_poster.py --status")
    print("  python social_ai_agent/tiktok_poster.py --auto")


if __name__ == "__main__":
    main()
