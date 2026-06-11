"""
get_youtube_token.py
Run this once to get your YOUTUBE_REFRESH_TOKEN.
Steps:
  1. python get_youtube_token.py
  2. Open the URL it prints in your browser
  3. Log in as the YouTube channel owner and allow access
  4. Copy the 'code' from the redirect URL
  5. Paste it when prompted
  6. The script prints your refresh token — copy it into .env
"""

import os, json, urllib.parse, urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
REDIRECT_URI  = "https://developers.google.com/oauthplayground"
SCOPE         = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"

# Step 1: Build authorization URL
auth_params = {
    "client_id":     CLIENT_ID,
    "redirect_uri":  REDIRECT_URI,
    "response_type": "code",
    "scope":         SCOPE,
    "access_type":   "offline",
    "prompt":        "consent",
}
auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(auth_params)

print("\n=== YOUTUBE OAUTH FLOW ===")
print("\n1. Open this URL in your browser:")
print(f"\n   {auth_url}\n")
print("2. Sign in & approve. You'll be redirected to developers.google.com/oauthplayground")
print("3. The redirect URL will have ?code=XXXX in it — copy that code.\n")

code = input("Paste the authorization code here: ").strip()

# Step 2: Exchange code for tokens
token_data = urllib.parse.urlencode({
    "code":          code,
    "client_id":     CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri":  REDIRECT_URI,
    "grant_type":    "authorization_code",
}).encode()

req = urllib.request.Request(
    "https://oauth2.googleapis.com/token",
    data=token_data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST"
)

with urllib.request.urlopen(req) as resp:
    tokens = json.loads(resp.read())

print("\n=== SUCCESS ===")
print(f"Access token  : {tokens.get('access_token','')[:30]}...")
print(f"\nREFRESH TOKEN : {tokens.get('refresh_token', 'NOT RETURNED — re-run with prompt=consent')}")
print("\n>>> Add this line to your .env file:")
print(f"YOUTUBE_REFRESH_TOKEN={tokens.get('refresh_token','')}")
