#!/usr/bin/env python3
"""
Post Scheduler — ShipStack AI
==============================
Reads all content_calendar.json files from data/product_collateral/*/
and dispatches posts that are due based on current date/time.

Kamil Sattar's posting windows (Central Time):
  - 07:00 — Morning commute
  - 12:00 — Lunch break
  - 20:00 — Evening wind-down

Gary Vee's rule: if you missed a window, post it anyway.
Volume beats perfect timing.

Usage:
  python agents/post_scheduler.py              # Check and dispatch due posts
  python agents/post_scheduler.py --dry-run    # Preview without dispatching
  python agents/post_scheduler.py --status     # Show all calendar statuses
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Optional: pytz for Central Time awareness
try:
    from zoneinfo import ZoneInfo
    CENTRAL = ZoneInfo("America/Chicago")
except ImportError:
    CENTRAL = None

BASE_DIR       = Path(__file__).parent.parent
COLLATERAL_DIR = BASE_DIR / "data" / "product_collateral"

# Ensure data/ directory exists before setting up file logger
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)

# DB layer — sync dispatch status back to SQLite
try:
    from agents.db import db_conn as _db_conn, init_db as _init_db
    _init_db()
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Scheduler] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "data" / "scheduler.log"),
    ]
)
logger = logging.getLogger("post_scheduler")


# =========================================================================
# Dispatch stubs — wire these to your actual posting integrations
# =========================================================================

def dispatch_tiktok(post: dict, product_name: str) -> bool:
    """
    Dispatch a TikTok post.
    Wire this to TikTok Content Posting API or your social tool (e.g., Publer, Later).
    Returns True if dispatched successfully.
    """
    logger.info(
        f"[TikTok] DISPATCH — Day {post['day']} | {post['time']} | {post['content_type']}\n"
        f"  Script preview: {post['script'][:120]}..."
    )
    # TODO: Integrate with TikTok API, Publer, or Later
    # Example: requests.post("https://open.tiktokapis.com/v2/post/publish/video/init/", ...)
    return True


def dispatch_instagram(post: dict, product_name: str) -> bool:
    """
    Dispatch an Instagram Reel/post.
    Wire to Meta Graph API or scheduling tool.
    """
    logger.info(
        f"[Instagram] DISPATCH — Day {post['day']} | {post['time']} | {post['content_type']}\n"
        f"  Caption preview: {post['caption'][:120]}..."
    )
    # TODO: Integrate with Meta Graph API or social scheduler
    return True


def dispatch_youtube(post: dict, product_name: str) -> bool:
    """
    Dispatch a YouTube Short.
    Wire to YouTube Data API v3.
    """
    logger.info(
        f"[YouTube] DISPATCH — Day {post['day']} | {post['time']} | {post['content_type']}\n"
        f"  Hook: {post.get('caption', '')}"
    )
    # TODO: Integrate with YouTube Data API v3 (resumable upload)
    return True


DISPATCHERS = {
    "tiktok":    dispatch_tiktok,
    "instagram": dispatch_instagram,
    "youtube":   dispatch_youtube,
}


# =========================================================================
# Core scheduler logic
# =========================================================================

def load_all_calendars() -> list[dict]:
    """Load every content_calendar.json from all product collateral dirs."""
    calendars = []
    for cal_path in COLLATERAL_DIR.glob("*/content_calendar.json"):
        try:
            data = json.loads(cal_path.read_text(encoding="utf-8"))
            data["_path"] = str(cal_path)
            calendars.append(data)
        except Exception as e:
            logger.warning(f"Failed to load calendar {cal_path}: {e}")
    return calendars


def get_current_time_ct() -> datetime:
    """Get current time in Central Time."""
    now_utc = datetime.now(timezone.utc)
    if CENTRAL:
        return now_utc.astimezone(CENTRAL)
    # Fallback: approximate CT as UTC-6 (CST) / UTC-5 (CDT)
    # Not daylight-aware but good enough for scheduling windows
    from datetime import timedelta
    return now_utc.replace(tzinfo=None) - timedelta(hours=6)


def is_due(post: dict, now_ct: datetime, tolerance_minutes: int = 90) -> bool:
    """
    Check if a post is due for dispatch.
    A post is due if:
      - Its date matches today
      - Its scheduled time is within the past `tolerance_minutes`
      - Its status is 'queued'
    Gary Vee rule: 90-minute window — if you're late, post anyway (volume wins).
    """
    if post.get("status") != "queued":
        return False

    try:
        post_date = datetime.strptime(post["date"], "%Y-%m-%d").date()
        post_time = datetime.strptime(post["time"], "%H:%M").time()
        scheduled = datetime.combine(post_date, post_time)

        diff_minutes = (now_ct.replace(tzinfo=None) - scheduled).total_seconds() / 60
        return 0 <= diff_minutes <= tolerance_minutes
    except Exception as e:
        logger.warning(f"Date parse error for post {post.get('id')}: {e}")
        return False


def mark_post(post: dict, status: str, calendar: dict, cal_path: str):
    """Update post status in both the JSON file and SQLite calendar_posts table."""
    now = datetime.now().isoformat()
    post["status"]        = status
    post["dispatched_at"] = now

    # 1. Save to disk (existing behaviour — scheduler rereads this file)
    try:
        path = Path(cal_path)
        path.write_text(json.dumps(calendar, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Failed to save calendar after status update: {e}")

    # 2. Sync status back to SQLite
    if _DB_AVAILABLE:
        try:
            post_id = post.get("id")
            if post_id:
                with _db_conn() as conn:
                    conn.execute(
                        "UPDATE calendar_posts SET status=?, sent_at=? WHERE id=?",
                        (status, now, post_id)
                    )
        except Exception as e:
            logger.warning(f"DB sync skipped for post {post.get('id')}: {e}")


def run_scheduler(dry_run: bool = False) -> dict:
    """
    Main scheduler loop.
    Returns a summary dict of what was dispatched.
    """
    calendars = load_all_calendars()
    if not calendars:
        logger.info("No content calendars found in data/product_collateral/*/")
        return {"dispatched": 0, "skipped": 0, "failed": 0}

    now_ct = get_current_time_ct()
    logger.info(f"Scheduler running — Current CT: {now_ct.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Calendars found: {len(calendars)}")

    dispatched = 0
    skipped    = 0
    failed     = 0

    for calendar in calendars:
        product = calendar.get("product", "Unknown")
        cal_path = calendar.get("_path", "")
        posts    = calendar.get("posts", [])
        due_posts = [p for p in posts if is_due(p, now_ct)]

        if not due_posts:
            continue

        logger.info(f"Product: {product} — {len(due_posts)} posts due")

        for post in due_posts:
            platform   = post.get("platform", "")
            dispatcher = DISPATCHERS.get(platform)

            if not dispatcher:
                logger.warning(f"No dispatcher for platform: {platform}")
                skipped += 1
                continue

            if dry_run:
                logger.info(f"[DRY RUN] Would dispatch: {platform} | Day {post['day']} | {post['time']} | {post['content_type']}")
                skipped += 1
                continue

            try:
                success = dispatcher(post, product)
                if success:
                    mark_post(post, "sent", calendar, cal_path)
                    dispatched += 1
                    logger.info(f"✅ Dispatched: {platform} | Day {post['day']} | {post['content_type']}")
                else:
                    mark_post(post, "failed", calendar, cal_path)
                    failed += 1
                    logger.error(f"❌ Failed: {platform} | Day {post['day']} | {post['content_type']}")
            except Exception as e:
                mark_post(post, "failed", calendar, cal_path)
                failed += 1
                logger.error(f"❌ Exception dispatching {platform} post: {e}")

    summary = {
        "run_at":     now_ct.strftime("%Y-%m-%d %H:%M CT"),
        "dispatched": dispatched,
        "skipped":    skipped,
        "failed":     failed,
        "dry_run":    dry_run,
    }
    logger.info(f"Scheduler complete: dispatched={dispatched} skipped={skipped} failed={failed}")
    return summary


def show_status() -> None:
    """Print a summary of all calendars and post statuses."""
    calendars = load_all_calendars()
    if not calendars:
        print("No calendars found.")
        return

    for calendar in calendars:
        product = calendar.get("product", "Unknown")
        posts   = calendar.get("posts", [])
        queued  = sum(1 for p in posts if p.get("status") == "queued")
        sent    = sum(1 for p in posts if p.get("status") == "sent")
        failed  = sum(1 for p in posts if p.get("status") == "failed")

        print(f"\n{'='*50}")
        print(f"Product: {product}")
        print(f"  Total posts: {len(posts)}")
        print(f"  Queued:  {queued}")
        print(f"  Sent:    {sent}")
        print(f"  Failed:  {failed}")

        # Platform breakdown
        for platform in ["tiktok", "instagram", "youtube"]:
            pf_posts = [p for p in posts if p.get("platform") == platform]
            pf_sent  = sum(1 for p in pf_posts if p.get("status") == "sent")
            print(f"  {platform.capitalize():12s}: {pf_sent}/{len(pf_posts)} sent")


# ── CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--status" in args:
        show_status()
    elif "--dry-run" in args:
        summary = run_scheduler(dry_run=True)
        print(json.dumps(summary, indent=2))
    else:
        summary = run_scheduler(dry_run=False)
        print(json.dumps(summary, indent=2))
