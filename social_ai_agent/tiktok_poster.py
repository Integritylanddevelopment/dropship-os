#!/usr/bin/env python3
"""
tiktok_poster.py — Dropship OS TikTok Auto-Poster
===================================================
Posts videos to TikTok using the TikTok Content Posting API.
TikTok is Channel #1 (CPM $0.00 = FREE) with viral_coeff 1.6.

SETUP (user is working on this tonight):
  1. Apply for TikTok Developer Access: https://developers.tiktok.com/
  2. Create an app with scopes: video.publish, video.list, user.info.basic
  3. OAuth flow → get access_token + refresh_token
  4. Set in .env:
       TIKTOK_ACCESS_TOKEN=your_access_token
       TIKTOK_CLIENT_KEY=your_client_key
       TIKTOK_CLIENT_SECRET=your_client_secret
  5. NOTE: TikTok requires ~2 week approval for Content Posting API

USAGE:
  # Post a single video
  python tiktok_poster.py --video path/to/video.mp4 --caption "Hook text #hashtags"

  # Auto-post top products from decision engine
  python tiktok_poster.py --auto

  # Check quota and token status
  python tiktok_poster.py --status

TIKTOK STRATEGY (Gary Vee + Ecom King):
  - Hook: First 2 seconds MUST stop the scroll (question, surprise, bold statement)
  - Trending audio: Use trending sounds for 2-3× algorithm boost
  - Hashtags: 3-5 niche tags + 2 broad tags (not #foryou — that's amateur)
  - Posting times: 6-10 AM, 7-11 PM in viewer's timezone
  - Frequency: 1-3 posts/day minimum (TikTok rewards consistency)
  - Reply to comments: signals to algorithm the content sparks conversation
  - Duet/Stitch viral content in your niche for piggyback reach
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Optional

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

BASE_DIR   = Path(__file__).parent.parent
DECISIONS  = BASE_DIR / "decisions.json"
OUTPUT_DIR = BASE_DIR / "prometheus_output"

TIKTOK_API = "https://open.tiktokapis.com/v2"
ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
CLIENT_KEY   = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")

# ── Hook templates (proven TikTok hooks for dropshipping) ───────────────────
HOOK_TEMPLATES = [
    "POV: You just found the product you didn't know you needed 😮",
    "I bought this so you don't have to make the mistake I did",
    "This {niche} product has 47K 5-star reviews and nobody's talking about it",
    "Stop buying {product_type} before watching this",
    "The {niche} hack that changed my life (this was $12)",
    "Things that make your life better vs things that look nice. This does both.",
    "I've tested 23 {product_type}s. This one won.",
    "If you're not using this {niche} tool yet, you're wasting time",
]

# ── Hashtag strategy by niche ────────────────────────────────────────────────
NICHE_HASHTAGS = {
    "pet accessories":  "#petproducts #doghacks #petlovers #tiktokmademebuyit #petstagram",
    "beauty skincare":  "#skincareroutine #skintok #glowup #beautyfinds #selfcare",
    "home kitchen":     "#homedecor #kitchenhacks #homeorganization #cleaningtiktok #homefinds",
    "fitness tools":    "#fitness #gymtok #workoutroutine #homegym #fitnessgoals",
    "outdoor camping":  "#camping #outdoorlife #hikingtiktok #adventure #campinghacks",
    "desk organizers":  "#desksetup #studytok #productivity #wfh #homeofficetour",
    "led grow lights":  "#plantparent #gardening #plantmom #urbangarden #growyourown",
    "general":          "#tiktokmademebuyit #productreview #mustbuy #lifechanging #worthit",
}

# ── API calls ─────────────────────────────────────────────────────────────────
def api_get(path: str) -> dict:
    import urllib.request
    req = urllib.request.Request(
        f"{TIKTOK_API}{path}",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
        method="GET"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def api_post(path: str, data: dict) -> dict:
    import urllib.request
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{TIKTOK_API}{path}",
        data=body,
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

# ── Status check ─────────────────────────────────────────────────────────────
def check_status() -> dict:
    """Check TikTok API token status and posting quota."""
    if not ACCESS_TOKEN:
        return {"error": "TIKTOK_ACCESS_TOKEN not set", "configured": False}
    try:
        resp = api_get("/user/info/?fields=open_id,union_id,display_name,video_count")
        info = resp.get("data", {}).get("user", {})
        print(f"✅ TikTok Connected: @{info.get('display_name', 'unknown')}")
        print(f"   Videos: {info.get('video_count', '—')}")
        return {"configured": True, "user": info}
    except Exception as e:
        print(f"❌ TikTok error: {e}")
        return {"configured": False, "error": str(e)}

# ── Upload and post video ─────────────────────────────────────────────────────
def post_video(
    video_path: str,
    caption: str,
    privacy_level: str = "PUBLIC_TO_EVERYONE",
    disable_duet: bool = False,
    disable_stitch: bool = False,
    disable_comment: bool = False,
) -> Optional[dict]:
    """
    Upload a video to TikTok using the Direct Post API.
    NOTE: Requires Content Posting API access (apply at developers.tiktok.com)
    """
    if not ACCESS_TOKEN:
        print("❌ TIKTOK_ACCESS_TOKEN not set in .env")
        return None

    video_size = Path(video_path).stat().st_size

    # Step 1: Initialize upload
    print(f"📤 Initializing TikTok upload: {Path(video_path).name} ({video_size/1024/1024:.1f} MB)")
    try:
        init_resp = api_post("/post/publish/video/init/", {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_stitch": disable_stitch,
                "disable_comment": disable_comment,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,  # Single chunk for files < 50MB
                "total_chunk_count": 1,
            }
        })
    except Exception as e:
        print(f"❌ Upload init failed: {e}")
        print("   TikTok Content Posting API may require approval (~2 weeks)")
        return None

    data = init_resp.get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")

    if not upload_url:
        print(f"❌ No upload URL: {init_resp}")
        return None

    # Step 2: Upload video bytes
    print("📡 Uploading video...")
    try:
        import urllib.request
        with open(video_path, "rb") as f:
            video_bytes = f.read()
        req = urllib.request.Request(upload_url, data=video_bytes, method="PUT")
        req.add_header("Content-Type", "video/mp4")
        req.add_header("Content-Length", str(video_size))
        req.add_header("Content-Range", f"bytes 0-{video_size-1}/{video_size}")
        with urllib.request.urlopen(req, timeout=120) as r:
            pass
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

    # Step 3: Poll for publish status
    print(f"⏳ Publishing (ID: {publish_id})...")
    for _ in range(20):
        time.sleep(5)
        try:
            status_resp = api_post("/post/publish/status/fetch/", {"publish_id": publish_id})
            status = status_resp.get("data", {}).get("status", "")
            print(f"   Status: {status}")
            if status == "PUBLISH_COMPLETE":
                video_id = status_resp.get("data", {}).get("publicaly_available_post_id", [""])[0]
                print(f"✅ Posted! Video ID: {video_id}")
                print(f"   URL: https://tiktok.com/@me/video/{video_id}")
                return {"publish_id": publish_id, "video_id": video_id}
            elif status in ("FAILED", "PUBLISH_FAILED"):
                print(f"❌ Publish failed: {status_resp.get('data', {}).get('fail_reason', 'unknown')}")
                return None
        except Exception as e:
            print(f"   Poll error: {e}")

    print("⚠️  Timeout waiting for publish")
    return None

# ── Auto-post from decisions ──────────────────────────────────────────────────
def auto_post(max_posts: int = 3) -> list:
    """Auto-post top products from decision engine to TikTok."""
    if not DECISIONS.exists():
        print("❌ decisions.json not found — run decision_engine.py first")
        return []

    data = json.loads(DECISIONS.read_text())
    # Priority: SCALE combos with TikTok channel
    combos = [c for c in data.get("scale", []) if "tiktok" in c.get("channel", "")]
    if not combos:
        combos = data.get("top_combos", [])
    combos = combos[:max_posts]

    print(f"\n🎵 Auto-posting {len(combos)} products to TikTok...\n")
    posted = []

    for combo in combos:
        product = combo.get("product", "Product")
        niche   = combo.get("niche", "general")
        score   = combo.get("score", 0)

        # Find clip
        video_path = _find_clip(product, "tiktok")
        if not video_path or not Path(video_path).exists():
            print(f"⚠️  No TikTok clip for {product} — run Prometheus first")
            continue

        # Build caption
        hashtags = NICHE_HASHTAGS.get(niche, NICHE_HASHTAGS["general"])
        hook = HOOK_TEMPLATES[0].replace("{niche}", niche).replace("{product_type}", product.lower())
        caption = f"{hook}\n\nLink in bio 👆\n\n{hashtags}"

        print(f"🎵 Posting: {product} (Score: {score})")
        result = post_video(video_path, caption)
        if result:
            posted.append({"product": product, **result})
            time.sleep(3)  # Rate limit

    print(f"\n✅ Posted {len(posted)} videos")
    return posted

def _find_clip(product_name: str, platform: str) -> Optional[str]:
    """Find the most recent clip for a product and platform."""
    if not OUTPUT_DIR.exists():
        return None
    safe = product_name.replace(" ", "_")[:20].lower()
    candidates = list(OUTPUT_DIR.glob(f"*{safe}*/{safe}*_{platform}*.mp4"))
    if not candidates:
        candidates = list(OUTPUT_DIR.glob(f"**/*{platform}*.mp4"))
    if candidates:
        return str(sorted(candidates, key=lambda p: p.stat().st_mtime)[-1])
    return None

# ── OAuth helper ──────────────────────────────────────────────────────────────
def print_oauth_instructions():
    """Print step-by-step TikTok OAuth setup."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║  TikTok Content Posting API Setup                         ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  1. Go to: https://developers.tiktok.com/apps             ║
║  2. Create App → name it "DropshipOS"                     ║
║  3. Request scopes:                                       ║
║     • video.publish  (to post videos)                     ║
║     • video.list     (to see your videos)                 ║
║     • user.info.basic                                     ║
║  4. Wait for approval (~2 weeks for video.publish)        ║
║  5. Generate access token via OAuth:                      ║
║     https://developers.tiktok.com/doc/login-kit-web       ║
║  6. Add to .env:                                          ║
║     TIKTOK_ACCESS_TOKEN=your_token                        ║
║     TIKTOK_CLIENT_KEY=your_key                            ║
║     TIKTOK_CLIENT_SECRET=your_secret                      ║
║                                                           ║
║  In the meantime: post manually using TikTok desktop app  ║
║  or use TikTok Scheduler at tiktok.com/creator            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")

# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dropship OS — TikTok Auto-Poster")
    parser.add_argument("--status",  action="store_true", help="Check token status")
    parser.add_argument("--setup",   action="store_true", help="Print OAuth setup instructions")
    parser.add_argument("--auto",    action="store_true", help="Auto-post from decisions.json")
    parser.add_argument("--video",   help="Video file path")
    parser.add_argument("--caption", default="", help="Post caption")
    parser.add_argument("--max",     type=int, default=3, help="Max auto-posts")
    args = parser.parse_args()

    if args.setup:
        print_oauth_instructions()
    elif args.status:
        check_status()
    elif args.auto:
        if not ACCESS_TOKEN:
            print("❌ TIKTOK_ACCESS_TOKEN not set")
            print_oauth_instructions()
        else:
            auto_post(args.max)
    elif args.video:
        if not ACCESS_TOKEN:
            print("❌ TIKTOK_ACCESS_TOKEN not set")
            print_oauth_instructions()
        else:
            post_video(args.video, args.caption)
    else:
        parser.print_help()
        print()
        if not ACCESS_TOKEN:
            print_oauth_instructions()
