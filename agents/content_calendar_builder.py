#!/usr/bin/env python3
"""
Content Calendar Builder — ShipStack AI
========================================
Takes Quinn's content_calendar_30day output and builds a fully scheduled
post calendar following:
  - Kamil Sattar's optimal posting times (7am, 12pm, 8pm Central)
  - Gary Vee's platform-native content rules + repurposing pyramid
  - Hormozi's jab-jab-jab-right-hook ratio (3 value posts per 1 promo)

Output: data/product_collateral/{slug}/content_calendar.json
Total posts per 30 days:
  - TikTok: 3/day = 90 posts
  - Instagram: 1/day = 30 posts
  - YouTube Shorts: 2/week = 8 posts
  ─────────────────────────────
  Total: ~128 posts from 1 product launch
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR       = Path(__file__).parent.parent
COLLATERAL_DIR = BASE_DIR / "data" / "product_collateral"

# DB layer — calendar posts also written to SQLite for dashboard + scheduler queries
try:
    from agents.db import db_conn as _db_conn, init_db as _init_db
    _init_db()
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

# Kamil's optimal posting times (Central Time)
POSTING_TIMES = {
    "tiktok": ["07:00", "12:00", "20:00"],   # 3x per day
    "instagram": ["12:00"],                   # 1x per day (peak lunch window)
    "youtube": ["07:00"],                     # 2x per week (Mon/Thu)
}

YOUTUBE_DAYS = {1, 4}  # Monday=1, Thursday=4 (weekday() 0=Mon)

# Gary Vee content type rotation (3 jabs : 1 right hook)
TIKTOK_ANGLE_ROTATION = [
    "problem_focus",       # Jab 1 — Hormozi hook + Kamil POD
    "demo_focus",          # Jab 2 — Satisfying demo
    "social_proof_focus",  # Right hook — social proof + offer
]

INSTAGRAM_TYPE_ROTATION = [
    "jab_educational",   # Jab — give value, teach
    "jab_entertainment", # Jab — behind the scenes, reaction
    "right_hook_offer",  # Right hook — offer with Hormozi copy
]

YOUTUBE_TYPES = ["shorts_demo", "shorts_review"]

PLATFORM_COLORS = {
    "tiktok": "#ff0050",
    "instagram": "#833ab4",
    "youtube": "#ff0000",
}


def _slugify(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip())[:60].strip("_")


def _get_script_for_angle(quinn_output: dict, angle: str) -> dict:
    """Pull the matching TikTok script by angle from Quinn output."""
    scripts = quinn_output.get("tiktok_scripts", [])
    for s in scripts:
        if s.get("angle") == angle:
            return s
    return scripts[0] if scripts else {}


def _get_instagram_caption(quinn_output: dict, cap_type: str) -> dict:
    """Pull matching Instagram caption by type."""
    captions = quinn_output.get("instagram_captions", [])
    for c in captions:
        if c.get("type") == cap_type:
            return c
    return captions[0] if captions else {}


def _get_youtube_desc(quinn_output: dict, yt_type: str) -> dict:
    """Pull matching YouTube description by type."""
    descs = quinn_output.get("youtube_descriptions", [])
    for d in descs:
        if d.get("type") == yt_type:
            return d
    return descs[0] if descs else {}


def _format_tiktok_script(script: dict, product_name: str) -> str:
    """Turn a Kamil POD script dict into a readable posting script."""
    parts = [
        f"[HOOK 0-3s] {script.get('hook', '')}",
        f"[PROBLEM 3-8s] {script.get('problem', '')}",
        f"[AGITATE 8-13s] {script.get('agitate', '')}",
        f"[SOLUTION 13-20s] {script.get('solution', '')}",
        f"[PROOF 20-25s] {script.get('social_proof', '')}",
        f"[CTA 25-30s] {script.get('cta', '')}",
    ]
    return "\n".join(p for p in parts if p.split("] ")[1])


def build_content_calendar(
    product_name: str,
    slug: str,
    quinn_output: dict,
    logger=None,
) -> dict:
    """
    Build a 30-day content calendar from Quinn's output.
    Returns the calendar dict and writes it to disk.
    """
    if logger is None:
        logger = logging.getLogger("content_calendar_builder")

    logger.info(f"Building 30-day content calendar for: {product_name}")

    start_date = datetime.now().date() + timedelta(days=1)  # Start tomorrow
    hashtags   = quinn_output.get("hashtags", {})
    tiktok_tags    = hashtags.get("tiktok", [])
    instagram_tags = hashtags.get("instagram", [])
    youtube_tags   = hashtags.get("youtube", [])

    posts = []
    post_id = 1
    youtube_post_count = 0

    for day_offset in range(30):
        current_date = start_date + timedelta(days=day_offset)
        day_num      = day_offset + 1
        weekday      = current_date.weekday()  # 0=Mon, 6=Sun

        # Determine Hormozi jab/hook context for this day
        # Pattern: 3 jabs then 1 right hook (every 4th post is the hook)
        is_hook_day = (day_num % 4 == 0)

        # ── TikTok: 3 posts per day ────────────────────────────────────
        for t_idx, post_time in enumerate(POSTING_TIMES["tiktok"]):
            # Rotate through angles; on hook day use social_proof_focus (has offer)
            if is_hook_day:
                angle = "social_proof_focus"
            else:
                angle = TIKTOK_ANGLE_ROTATION[t_idx % len(TIKTOK_ANGLE_ROTATION)]

            script = _get_script_for_angle(quinn_output, angle)
            script_text = _format_tiktok_script(script, product_name)

            posts.append({
                "id":           post_id,
                "day":          day_num,
                "date":         current_date.strftime("%Y-%m-%d"),
                "time":         post_time,
                "platform":     "tiktok",
                "content_type": f"pod_video_{angle}",
                "angle":        angle,
                "framework":    "Kamil POD + Hormozi hook",
                "script":       script_text,
                "caption":      script.get("cta", f"Link in bio — {product_name}"),
                "comment_bait": script.get("comment_bait", quinn_output.get("comment_bait", "")),
                "hashtags":     tiktok_tags,
                "color":        PLATFORM_COLORS["tiktok"],
                "is_hook":      is_hook_day,
                "jab_hook":     "right_hook" if is_hook_day else "jab",
                "status":       "queued",
            })
            post_id += 1

        # ── Instagram: 1 post per day ─────────────────────────────────
        # Gary Vee rotation: jab_educational → jab_entertainment → right_hook_offer
        ig_type = INSTAGRAM_TYPE_ROTATION[(day_num - 1) % len(INSTAGRAM_TYPE_ROTATION)]
        if is_hook_day:
            ig_type = "right_hook_offer"

        ig_caption = _get_instagram_caption(quinn_output, ig_type)

        posts.append({
            "id":           post_id,
            "day":          day_num,
            "date":         current_date.strftime("%Y-%m-%d"),
            "time":         POSTING_TIMES["instagram"][0],
            "platform":     "instagram",
            "content_type": f"reel_{ig_type}",
            "angle":        ig_type,
            "framework":    "Gary Vee Jab-Jab-Right-Hook",
            "script":       ig_caption.get("caption", ""),
            "caption":      ig_caption.get("caption", ""),
            "comment_bait": quinn_output.get("comment_bait", ""),
            "hashtags":     ig_caption.get("hashtags", instagram_tags),
            "color":        PLATFORM_COLORS["instagram"],
            "is_hook":      (ig_type == "right_hook_offer"),
            "jab_hook":     "right_hook" if ig_type == "right_hook_offer" else "jab",
            "status":       "queued",
        })
        post_id += 1

        # ── YouTube Shorts: 2 per week (Mon + Thu) ────────────────────
        if weekday in YOUTUBE_DAYS and youtube_post_count < 8:
            yt_type = YOUTUBE_TYPES[youtube_post_count % len(YOUTUBE_TYPES)]
            yt_desc = _get_youtube_desc(quinn_output, yt_type)

            posts.append({
                "id":           post_id,
                "day":          day_num,
                "date":         current_date.strftime("%Y-%m-%d"),
                "time":         POSTING_TIMES["youtube"][0],
                "platform":     "youtube",
                "content_type": f"shorts_{yt_type}",
                "angle":        yt_type,
                "framework":    "Gary Vee repurposing pyramid",
                "script":       f"{yt_desc.get('hook', '')} {yt_desc.get('body', '')}",
                "caption":      yt_desc.get("hook", ""),
                "description":  yt_desc.get("body", ""),
                "cta":          yt_desc.get("cta", "Subscribe + link in description"),
                "comment_bait": quinn_output.get("comment_bait", ""),
                "hashtags":     yt_desc.get("hashtags", youtube_tags),
                "color":        PLATFORM_COLORS["youtube"],
                "is_hook":      False,
                "jab_hook":     "jab",
                "status":       "queued",
            })
            post_id += 1
            youtube_post_count += 1

    # Build summary stats
    tiktok_count    = sum(1 for p in posts if p["platform"] == "tiktok")
    instagram_count = sum(1 for p in posts if p["platform"] == "instagram")
    youtube_count   = sum(1 for p in posts if p["platform"] == "youtube")

    calendar = {
        "product":      product_name,
        "product_slug": slug,
        "generated":    datetime.now().isoformat(),
        "start_date":   start_date.strftime("%Y-%m-%d"),
        "end_date":     (start_date + timedelta(days=29)).strftime("%Y-%m-%d"),
        "framework":    "Hormozi × Gary Vee × Kamil Sattar",
        "posting_strategy": {
            "tiktok":    "3 posts/day at 7am, 12pm, 8pm CT — Kamil Sattar timing",
            "instagram": "1 post/day at 12pm CT — Gary Vee cadence",
            "youtube":   "2 posts/week (Mon+Thu) at 7am CT — Gary Vee repurposing pyramid",
        },
        "content_ratio": "3 jabs (value) : 1 right hook (offer) — Gary Vee",
        "summary": {
            "total_posts":     len(posts),
            "tiktok_posts":    tiktok_count,
            "instagram_posts": instagram_count,
            "youtube_posts":   youtube_count,
            "hook_posts":      sum(1 for p in posts if p.get("is_hook")),
            "jab_posts":       sum(1 for p in posts if not p.get("is_hook")),
        },
        "posts": posts,
    }

    # Write to disk (post_scheduler still reads the file)
    out_dir = COLLATERAL_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "content_calendar.json"
    out_path.write_text(json.dumps(calendar, indent=2, ensure_ascii=False))

    # Also write posts to SQLite calendar_posts table for dashboard + DB queries
    if _DB_AVAILABLE:
        try:
            now = datetime.now().isoformat()
            with _db_conn() as conn:
                for post in posts:
                    conn.execute("""
                        INSERT OR IGNORE INTO calendar_posts
                        (id, product_slug, platform, content_type, scheduled_time,
                         content, caption, hashtags, status, created)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        post.get("id", str(uuid.uuid4())[:12]),
                        slug,
                        post.get("platform", ""),
                        post.get("content_type", ""),
                        post.get("date", "") + "T" + post.get("time", "00:00") + ":00",
                        post.get("script") or post.get("caption") or post.get("content", ""),
                        post.get("caption", ""),
                        json.dumps(post.get("hashtags", [])),
                        post.get("status", "queued"),
                        now,
                    ))
            logger.info(f"  [DB] Wrote {len(posts)} calendar posts to SQLite ✓")
        except Exception as e:
            logger.warning(f"  [DB] SQLite calendar write skipped: {e}")

    logger.info(
        f"Content calendar saved -> {out_path}\n"
        f"  TikTok: {tiktok_count} | Instagram: {instagram_count} | YouTube: {youtube_count} | Total: {len(posts)}"
    )

    return calendar


# ── CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[Calendar] %(message)s")
    logger = logging.getLogger("content_calendar_builder")

    # Accept slug as CLI arg or scan collateral dir for quinn_copy.json files
    slug_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if slug_arg:
        slugs = [slug_arg]
    else:
        slugs = [p.parent.name for p in COLLATERAL_DIR.glob("*/quinn_copy.json")]

    for slug in slugs:
        quinn_path = COLLATERAL_DIR / slug / "quinn_copy.json"
        if not quinn_path.exists():
            logger.warning(f"No quinn_copy.json found for slug: {slug}")
            continue
        quinn_data = json.loads(quinn_path.read_text())
        product_name = quinn_data.get("product_title", slug.replace("_", " ").title())
        build_content_calendar(product_name, slug, quinn_data, logger)

    print(f"Done. Processed {len(slugs)} product(s).")
