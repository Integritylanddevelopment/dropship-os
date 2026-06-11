#!/usr/bin/env python3
"""
integrations/social_poster.py — Multi-Platform Social Media Poster
Posts content to Pinterest, Instagram, TikTok, YouTube Shorts.
Reads from content_pipeline/post_queue.json.

Requires API credentials in .env — see SETUP_CHECKLIST.md for
step-by-step account + app setup instructions.

Usage:
    python integrations/social_poster.py --platform pinterest --post-now
    python integrations/social_poster.py --platform all --dry-run
    python integrations/social_poster.py --run-queue  # posts everything due now
"""

import json
import os
import sys
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


# ══════════════════════════════════════════════
# PINTEREST API v5
# ══════════════════════════════════════════════

class PinterestPoster:
    """
    Pinterest API v5 — creates pins on your boards.
    Requires: PINTEREST_ACCESS_TOKEN
    Get it at: https://developers.pinterest.com/apps/
    Docs: https://developers.pinterest.com/docs/api/v5/
    """
    BASE_URL = "https://api.pinterest.com/v5"

    def __init__(self):
        self.token = os.getenv("PINTEREST_ACCESS_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def is_configured(self) -> bool:
        return bool(self.token)

    def get_boards(self) -> list:
        if not self.is_configured():
            return []
        resp = requests.get(f"{self.BASE_URL}/boards", headers=self.headers)
        return resp.json().get("items", [])

    def create_pin(self, board_id: str, title: str, description: str,
                   link: str, image_url: str = None) -> dict:
        if not self.is_configured():
            return {"error": "PINTEREST_ACCESS_TOKEN not set"}

        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:500],
            "link": link,
        }
        if image_url:
            payload["media_source"] = {"source_type": "image_url", "url": image_url}

        resp = requests.post(f"{self.BASE_URL}/pins", headers=self.headers, json=payload)
        result = resp.json()
        if resp.status_code == 201:
            print(f"[Pinterest] ✅ Pin created: {result.get('id')} — {title[:50]}")
        else:
            print(f"[Pinterest] ❌ Error: {result}")
        return result

    def post_from_content(self, content: dict, board_id: str, product_link: str) -> dict:
        return self.create_pin(
            board_id=board_id,
            title=content.get("hook", content.get("product", ""))[:100],
            description=content.get("caption", "")[:500],
            link=product_link,
        )


# ══════════════════════════════════════════════
# META (INSTAGRAM) GRAPH API
# ══════════════════════════════════════════════

class MetaPoster:
    """
    Meta Graph API — posts to Instagram Business Account.
    Requires: META_ACCESS_TOKEN, META_IG_ACCOUNT_ID
    Get at: https://developers.facebook.com/apps/
    Docs: https://developers.facebook.com/docs/instagram-api
    """
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.token = os.getenv("META_ACCESS_TOKEN", "")
        self.ig_id = os.getenv("META_IG_ACCOUNT_ID", "")

    def is_configured(self) -> bool:
        return bool(self.token and self.ig_id)

    def post_image(self, image_url: str, caption: str) -> dict:
        if not self.is_configured():
            return {"error": "META_ACCESS_TOKEN or META_IG_ACCOUNT_ID not set"}

        # Step 1: Create container
        container_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_id}/media",
            params={
                "image_url": image_url,
                "caption": caption[:2200],
                "access_token": self.token,
            }
        )
        container = container_resp.json()
        if "id" not in container:
            print(f"[Instagram] ❌ Container error: {container}")
            return container

        # Step 2: Publish
        time.sleep(2)
        publish_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_id}/media_publish",
            params={"creation_id": container["id"], "access_token": self.token}
        )
        result = publish_resp.json()
        if "id" in result:
            print(f"[Instagram] ✅ Posted: {result['id']} — {caption[:50]}")
        else:
            print(f"[Instagram] ❌ Publish error: {result}")
        return result

    def post_reel(self, video_url: str, caption: str) -> dict:
        """Post a Reel (video). Video must be publicly accessible URL."""
        if not self.is_configured():
            return {"error": "Not configured"}

        container_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "access_token": self.token,
            }
        )
        container = container_resp.json()
        if "id" not in container:
            return container

        # Wait for video processing
        for _ in range(10):
            time.sleep(5)
            status_resp = requests.get(
                f"{self.BASE_URL}/{container['id']}",
                params={"fields": "status_code", "access_token": self.token}
            )
            if status_resp.json().get("status_code") == "FINISHED":
                break

        publish_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_id}/media_publish",
            params={"creation_id": container["id"], "access_token": self.token}
        )
        return publish_resp.json()


# ══════════════════════════════════════════════
# TIKTOK CONTENT POSTING API
# ══════════════════════════════════════════════

class TikTokPoster:
    """
    TikTok Content Posting API.
    Requires: TIKTOK_ACCESS_TOKEN
    Get at: https://developers.tiktok.com/
    Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
    NOTE: TikTok requires video files — captions are attached to video uploads.
    """
    BASE_URL = "https://open.tiktokapis.com/v2"

    def __init__(self):
        self.token = os.getenv("TIKTOK_ACCESS_TOKEN", "")

    def is_configured(self) -> bool:
        return bool(self.token)

    def post_video(self, video_path: str, caption: str, privacy: str = "PUBLIC_TO_EVERYONE") -> dict:
        """
        Upload and post a video to TikTok.
        video_path: local path to .mp4 file
        """
        if not self.is_configured():
            return {"error": "TIKTOK_ACCESS_TOKEN not set"}

        video_path = Path(video_path)
        if not video_path.exists():
            return {"error": f"Video file not found: {video_path}"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Initialize upload
        init_resp = requests.post(
            f"{self.BASE_URL}/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": privacy,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_path.stat().st_size,
                    "chunk_size": video_path.stat().st_size,
                    "total_chunk_count": 1,
                }
            }
        )
        init_data = init_resp.json().get("data", {})
        publish_id = init_data.get("publish_id")
        upload_url = init_data.get("upload_url")

        if not upload_url:
            print(f"[TikTok] ❌ Init failed: {init_resp.json()}")
            return init_resp.json()

        # Upload video
        with open(video_path, "rb") as f:
            upload_resp = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{video_path.stat().st_size - 1}/{video_path.stat().st_size}"},
            )

        if upload_resp.status_code in [200, 201]:
            print(f"[TikTok] ✅ Video uploaded. Publish ID: {publish_id}")
            return {"publish_id": publish_id, "status": "uploaded"}
        else:
            print(f"[TikTok] ❌ Upload failed: {upload_resp.status_code}")
            return {"error": f"Upload failed: {upload_resp.status_code}"}

    def post_caption_only(self, caption: str) -> dict:
        """Schedule a caption-only post (for manual video attachment)."""
        print(f"[TikTok] Caption ready to post manually:")
        print(f"  {caption[:200]}")
        return {"status": "caption_ready", "caption": caption}


# ══════════════════════════════════════════════
# YOUTUBE SHORTS (DATA API v3)
# ══════════════════════════════════════════════

class YouTubePoster:
    """
    YouTube Data API v3 — upload Shorts.
    Requires: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
    Get at: https://console.cloud.google.com/
    Docs: https://developers.google.com/youtube/v3/guides/uploading_a_video
    """

    def __init__(self):
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
        self._access_token = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        )
        self._access_token = resp.json().get("access_token")
        return self._access_token

    def upload_short(self, video_path: str, title: str, description: str,
                     tags: list = None) -> dict:
        if not self.is_configured():
            return {"error": "YouTube credentials not set"}

        video_path = Path(video_path)
        if not video_path.exists():
            return {"error": f"Video not found: {video_path}"}

        token = self._get_access_token()
        if not token:
            return {"error": "Could not get YouTube access token"}

        # Add #Shorts to make it a Short
        if "#Shorts" not in description:
            description = description + "\n\n#Shorts"

        metadata = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": (tags or []) + ["Shorts", "dropshipping"],
                "categoryId": "26",  # Howto & Style
            },
            "status": {"privacyStatus": "public"}
        }

        # Resumable upload
        init_resp = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(video_path.stat().st_size),
            },
            json=metadata,
        )
        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            return {"error": "Could not get upload URL"}

        with open(video_path, "rb") as f:
            upload_resp = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4"},
                data=f,
            )

        result = upload_resp.json()
        if "id" in result:
            print(f"[YouTube] ✅ Short uploaded: https://youtube.com/shorts/{result['id']}")
        else:
            print(f"[YouTube] ❌ Upload error: {result}")
        return result


# ══════════════════════════════════════════════
# UNIFIED POSTER
# ══════════════════════════════════════════════

class SocialPoster:
    """
    Unified interface. Routes content to the right platform poster.
    Reads post_queue.json and posts everything that's due.
    """

    def __init__(self):
        self.pinterest = PinterestPoster()
        self.instagram = MetaPoster()
        self.tiktok = TikTokPoster()
        self.youtube = YouTubePoster()

    def status(self) -> dict:
        return {
            "pinterest": "✅ Ready" if self.pinterest.is_configured() else "❌ Add PINTEREST_ACCESS_TOKEN",
            "instagram":  "✅ Ready" if self.instagram.is_configured()  else "❌ Add META_ACCESS_TOKEN + META_IG_ACCOUNT_ID",
            "tiktok":     "✅ Ready" if self.tiktok.is_configured()     else "❌ Add TIKTOK_ACCESS_TOKEN",
            "youtube":    "✅ Ready" if self.youtube.is_configured()     else "❌ Add YOUTUBE credentials",
        }

    def run_queue(self, dry_run: bool = False) -> list:
        """Post everything in post_queue.json that is due now and not yet posted."""
        queue_path = BASE_DIR / "content_pipeline" / "post_queue.json"
        if not queue_path.exists():
            print("[SocialPoster] No post_queue.json. Run post_scheduler.py first.")
            return []

        queue_data = json.loads(queue_path.read_text())
        now = datetime.now(timezone.utc)
        results = []

        for day_str, day_data in queue_data.get("queue", {}).items():
            for post in day_data.get("posts", []):
                if post.get("status") == "posted":
                    continue
                post_dt = datetime.fromisoformat(post["datetime"])
                if post_dt.tzinfo is None:
                    post_dt = post_dt.replace(tzinfo=timezone.utc)
                if post_dt > now:
                    continue

                platform = post["platform"]
                caption = post.get("caption", post.get("hook", ""))
                product_link = self._get_product_link(post.get("product", ""))

                if dry_run:
                    print(f"[DRY RUN] Would post to {platform}: {caption[:80]}...")
                    results.append({"platform": platform, "status": "dry_run"})
                    continue

                result = self._post_to_platform(platform, caption, product_link)
                post["status"] = "posted"
                post["post_result"] = result
                results.append(result)

        if not dry_run:
            queue_path.write_text(json.dumps(queue_data, indent=2))

        return results

    def _post_to_platform(self, platform: str, caption: str, product_link: str) -> dict:
        if platform == "pinterest":
            board_id = os.getenv("PINTEREST_DEFAULT_BOARD_ID", "")
            if board_id:
                return self.pinterest.create_pin(board_id, caption[:100], caption, product_link)
            return {"error": "PINTEREST_DEFAULT_BOARD_ID not set"}
        elif platform in ("instagram", "meta"):
            # Instagram requires a hosted image — use placeholder
            image_url = os.getenv("DEFAULT_PRODUCT_IMAGE_URL", "")
            return self.instagram.post_image(image_url, caption) if image_url else {"error": "No image URL"}
        elif platform == "tiktok":
            return self.tiktok.post_caption_only(caption)
        elif platform == "youtube_shorts":
            video_path = os.getenv("YOUTUBE_DEFAULT_VIDEO_PATH", "")
            return self.youtube.upload_short(video_path, caption[:100], caption)
        return {"error": f"Unknown platform: {platform}"}

    def _get_product_link(self, product_name: str) -> str:
        """Look up the Stripe payment link for a product."""
        links_path = BASE_DIR / "data" / "stripe_links.json"
        if links_path.exists():
            links = json.loads(links_path.read_text())
            for link in links:
                if link.get("product_name", "").lower() in product_name.lower():
                    return link.get("payment_link_url", "#")
        return "#"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--run-queue", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    poster = SocialPoster()

    if args.status:
        print("\n📡 Social Poster Status:")
        for platform, status in poster.status().items():
            print(f"   {platform}: {status}")

    if args.run_queue:
        results = poster.run_queue(dry_run=args.dry_run)
        print(f"\n✅ Processed {len(results)} posts")
