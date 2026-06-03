#!/usr/bin/env python3
"""
content_pipeline/post_scheduler.py — Dropship Post Scheduler
Reads content_batch.json, builds a 7-day posting queue,
outputs post_queue.json for manual posting or Buffer/Later upload.
Also runs APScheduler to remind you when it's time to post.

Usage:
    cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping"
    python content_pipeline/post_scheduler.py              # build queue + print today's posts
    python content_pipeline/post_scheduler.py --schedule   # run live scheduler (keeps running)
    python content_pipeline/post_scheduler.py --today      # print today's posts only
"""

import json
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path so integrations can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))
from integrations.social_poster import SocialPoster

BASE_DIR = Path(__file__).parent.parent
CONTENT_DIR = Path(__file__).parent

# Gary Vee posting cadence — optimal times per platform (EST)
POSTING_SCHEDULE = {
    "tiktok":         ["07:00", "12:00", "19:00", "21:00"],  # 4x/day
    "pinterest":      ["08:00", "14:00", "20:00"],            # 3x/day
    "instagram":      ["09:00", "18:00"],                     # 2x/day
    "youtube_shorts": ["10:00"],                              # 1x/day
}

# Days of week emphasis (0=Mon, 6=Sun)
DAY_EMPHASIS = {
    0: {"label": "Monday",    "focus": "Hook content — start the week strong"},
    1: {"label": "Tuesday",   "focus": "Educational / value content"},
    2: {"label": "Wednesday", "focus": "Social proof + testimonial style"},
    3: {"label": "Thursday",  "focus": "Before/after content"},
    4: {"label": "Friday",    "focus": "Viral hooks — highest engagement day"},
    5: {"label": "Saturday",  "focus": "Lifestyle content — lighter tone"},
    6: {"label": "Sunday",    "focus": "Inspiration / curiosity hooks"},
}


def load_content() -> list:
    content_path = CONTENT_DIR / "content_batch.json"
    if content_path.exists():
        data = json.loads(content_path.read_text())
        return data.get("content", [])
    return []


def build_queue(days: int = 7) -> dict:
    content = load_content()
    if not content:
        print("[Scheduler] No content_batch.json. Run generate_content.py first.")
        sys.exit(1)

    queue = {}
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Flatten all content pieces into a pool
    pool = []
    for item in content:
        for platform, piece in item.get("platforms", {}).items():
            pool.append(piece)

    if not pool:
        print("[Scheduler] Empty content pool.")
        sys.exit(1)

    pool_idx = 0

    for day_offset in range(days):
        date = today + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")
        day_of_week = date.weekday()
        day_info = DAY_EMPHASIS[day_of_week]

        day_posts = []
        for platform, times in POSTING_SCHEDULE.items():
            for time_str in times:
                piece = pool[pool_idx % len(pool)]
                pool_idx += 1

                # Only use content for the right platform
                platform_pieces = [p for p in pool if p["platform"] == platform]
                if platform_pieces:
                    piece = platform_pieces[pool_idx % len(platform_pieces)]

                post_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

                day_posts.append({
                    "datetime": post_dt.isoformat(),
                    "date": date_str,
                    "time": time_str,
                    "platform": platform,
                    "product": piece.get("product", ""),
                    "niche": piece.get("niche", ""),
                    "hook": piece.get("hook", ""),
                    "caption": piece.get("caption", ""),
                    "cta": piece.get("cta", ""),
                    "status": "pending",
                    "notes": day_info["focus"],
                })

        queue[date_str] = {
            "date": date_str,
            "day": day_info["label"],
            "focus": day_info["focus"],
            "post_count": len(day_posts),
            "posts": day_posts,
        }

    return queue


def print_today(queue: dict):
    today = datetime.now().strftime("%Y-%m-%d")
    today_data = queue.get(today, {})
    if not today_data:
        print(f"[Scheduler] No posts scheduled for {today}")
        return

    print(f"\n📅 TODAY — {today_data['day']} | Focus: {today_data['focus']}")
    print(f"   {today_data['post_count']} posts scheduled\n")
    print("-" * 60)

    for post in today_data["posts"]:
        print(f"\n  🕐 {post['time']} — {post['platform'].upper()}")
        print(f"  Product: {post['product']}")
        print(f"  Hook: {post['hook']}")
        print(f"  Caption preview: {post['caption'][:120]}...")
        print(f"  CTA: {post['cta']}")


def run_live_scheduler(queue: dict):
    """Run APScheduler to print reminders when it's posting time."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("[Scheduler] apscheduler not installed. Run: pip install apscheduler --break-system-packages")
        sys.exit(1)

    scheduler = BlockingScheduler()

    # Flatten all posts
    all_posts = []
    for day_data in queue.values():
        all_posts.extend(day_data["posts"])

    jobs_added = 0
    now = datetime.now()
    for post in all_posts:
        post_dt = datetime.fromisoformat(post["datetime"])
        if post_dt > now:
            def make_reminder(p):
                def remind():
                    print(f"\n🔔 POST NOW → {p['platform'].upper()}")
                    print(f"   Product: {p['product']}")
                    print(f"   Caption: {p['caption'][:200]}")
                    print(f"   CTA: {p['cta']}\n")
                    SocialPoster().run_queue()
                return remind

            scheduler.add_job(make_reminder(post), "date", run_date=post_dt)
            jobs_added += 1

    print(f"\n[Scheduler] {jobs_added} post reminders scheduled. Running... (Ctrl+C to stop)\n")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("\n[Scheduler] Stopped.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--schedule", action="store_true", help="Run live scheduler")
    parser.add_argument("--today", action="store_true", help="Print today only")
    args = parser.parse_args()

    print("=" * 60)
    print("  POST SCHEDULER — Gary Vee Cadence")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    queue = build_queue(days=args.days)

    # Save queue to JSON
    out_path = CONTENT_DIR / "post_queue.json"
    total_posts = sum(d["post_count"] for d in queue.values())
    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "days": args.days,
        "total_posts": total_posts,
        "queue": queue,
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Queue built: {total_posts} posts over {args.days} days → {out_path}")

    if args.today or not args.schedule:
        print_today(queue)

    if args.schedule:
        run_live_scheduler(queue)
    else:
        print(f"\n💡 To run live scheduler: python content_pipeline/post_scheduler.py --schedule")
        print(f"💡 To upload to Buffer/Later: import post_queue.json into your tool")
        print(f"💡 Buffer CSV import: https://support.buffer.com/article/bulk-scheduling\n")


if __name__ == "__main__":
    main()
