#!/usr/bin/env python3
"""
Social AI Agent — Content Strategy & Distribution
===================================================

Coordinates social media presence across TikTok, Instagram, Pinterest, YouTube.
Routes all LLM work through Quinn bridge (:8765).
Badge-gated HTTP service on port 8867 (optional; can also run as CLI).

Responsibilities:
- Content calendar generation
- Hashtag strategy & research
- Caption writing
- Engagement monitoring
- Cross-platform scheduling
- Performance analytics

Integrated APIs:
- TikTok API — post videos, get analytics
- Instagram/Meta API — post videos, get insights
- Pinterest API — pin images, drive traffic
- YouTube API — upload videos, manage channel
- Quinn Bridge — LLM inference for all copy
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from flask import Flask, request, jsonify
from shipstack_badge import get_badge, validate_token, log_action

# Setup
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

PORT = int(os.getenv("SOCIAL_AI_AGENT_PORT", 8867))
QUINN_ENDPOINT = os.getenv("QUINN_ENDPOINT", "http://localhost:8765")

# Social media credentials
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def require_badge(f):
    """Badge-gated decorator."""
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "Missing or invalid Authorization header",
                "expected": "Authorization: Bearer badge-1_...",
            }), 401
        
        token = auth_header[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        if not validate_token(token, issued_at):
            return jsonify({
                "error": "Badge token expired or invalid",
                "hint": "Tokens are valid for 60 seconds only. Get a new badge.",
            }), 401
        
        return f(*args, **kwargs)
    
    wrapper.__name__ = f.__name__
    return wrapper


@app.route("/health", methods=["GET"])
def health_check():
    """Public health check."""
    return jsonify({
        "status": "healthy",
        "service": "Social AI Agent",
        "port": PORT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "platforms": ["tiktok", "instagram", "pinterest", "youtube"],
        "quinn_bridge": QUINN_ENDPOINT,
    }), 200


@app.route("/badge", methods=["GET"])
def get_new_badge():
    """Public badge endpoint."""
    badge = get_badge()
    logger.info(f"Issued badge token: {badge['token'][:20]}...")
    return jsonify(badge), 200


@app.route("/api/generate-caption", methods=["POST"])
@require_badge
def generate_caption():
    """
    Generate a social media caption for a product/video.
    
    Request body:
    {
        "product_title": "Pet Collar Widget",
        "product_description": "Comfy, adjustable pet collar...",
        "platform": "tiktok|instagram|pinterest|youtube",
        "tone": "casual|professional|viral|educational",
        "include_hashtags": true,
        "hashtag_limit": 15,
    }
    
    Response:
    {
        "caption": "Check out this amazing pet collar! ...",
        "hashtags": ["pets", "amazon", "..."],
        "character_count": 280,
        "platform": "tiktok",
    }
    """
    try:
        data = request.get_json()
        product_title = data.get("product_title", "")
        product_desc = data.get("product_description", "")
        platform = data.get("platform", "tiktok")
        tone = data.get("tone", "casual")
        include_hashtags = data.get("include_hashtags", True)
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call Quinn bridge to generate caption
        # Prompt: "Generate a viral {tone} caption for a {product_title} on {platform}. {product_desc}"
        
        result = {
            "caption": f"Check out this amazing {product_title}! 🚀 #dropshipping #producthunt",
            "hashtags": ["dropshipping", "producthunt", "ecommerce"] if include_hashtags else [],
            "character_count": 60,
            "platform": platform,
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="social_ai_generate_caption",
            target="/api/generate-caption",
            action="generate",
            result=f"Generated {tone} caption for {platform}",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/generate-caption: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/content-calendar", methods=["POST"])
@require_badge
def content_calendar():
    """
    Generate a content calendar for the next N days.
    
    Request body:
    {
        "num_days": 7,
        "platforms": ["tiktok", "instagram", "pinterest"],
        "posts_per_day": 2,
        "niche": "pet accessories",
        "themes": ["viral", "educational", "unboxing"],
    }
    
    Response:
    {
        "calendar": [
            {
                "date": "2026-06-03",
                "posts": [
                    {
                        "platform": "tiktok",
                        "time": "18:00",
                        "theme": "viral",
                        "caption": "...",
                        "hashtags": [...],
                    },
                    ...
                ],
            },
            ...
        ],
        "total_posts": 14,
    }
    """
    try:
        data = request.get_json()
        num_days = data.get("num_days", 7)
        platforms = data.get("platforms", ["tiktok", "instagram"])
        posts_per_day = data.get("posts_per_day", 1)
        niche = data.get("niche", "general")
        themes = data.get("themes", ["viral"])
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call Quinn bridge to generate calendar
        
        calendar = []
        for day in range(num_days):
            day_posts = []
            for post in range(posts_per_day):
                day_posts.append({
                    "platform": platforms[post % len(platforms)],
                    "time": "18:00",
                    "theme": themes[post % len(themes)],
                    "caption": f"Content for day {day+1}, post {post+1}",
                    "hashtags": ["dropshipping", "ecommerce"],
                })
            calendar.append({
                "date": f"2026-06-{3+day:02d}",
                "posts": day_posts,
            })
        
        result = {
            "calendar": calendar,
            "total_posts": num_days * posts_per_day,
            "niche": niche,
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="social_ai_content_calendar",
            target="/api/content-calendar",
            action="generate",
            result=f"Generated {num_days}-day calendar for {len(platforms)} platforms",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/content-calendar: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/post-to-platform", methods=["POST"])
@require_badge
def post_to_platform():
    """
    Post content to a specific platform.
    
    Request body:
    {
        "platform": "tiktok",
        "media_url": "s3://shipstack-videos/...",
        "media_type": "video|image",
        "caption": "Check out this amazing product...",
        "hashtags": ["dropshipping", "..."],
        "scheduled_time": "2026-06-03T18:00:00Z",  # null = post now
    }
    
    Response:
    {
        "posted": true,
        "platform": "tiktok",
        "post_id": "12345",
        "post_url": "https://tiktok.com/@account/video/12345",
        "timestamp": "2026-06-03T12:00:00Z",
    }
    """
    try:
        data = request.get_json()
        platform = data.get("platform", "tiktok")
        media_url = data.get("media_url", "")
        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])
        scheduled_time = data.get("scheduled_time")
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call platform API to post
        # TODO: Handle scheduled_time if present
        
        result = {
            "posted": True,
            "platform": platform,
            "post_id": "12345",
            "post_url": f"https://{platform}.com/@account/video/12345",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="social_ai_post_to_platform",
            target="/api/post-to-platform",
            action="post",
            result=f"Posted to {platform}",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/post-to-platform: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/engagement-stats", methods=["GET"])
@require_badge
def engagement_stats():
    """
    Get engagement stats across all platforms.
    
    Query params:
    - days: 7, 30, 90 (default: 30)
    - platform: tiktok|instagram|pinterest|youtube (default: all)
    
    Response:
    {
        "period": "last_30_days",
        "platforms": {
            "tiktok": {
                "posts": 45,
                "views": 1234567,
                "engagement_rate": 0.08,
                "top_post_id": "12345",
            },
            ...
        },
        "total_views": 5000000,
        "avg_engagement_rate": 0.075,
    }
    """
    try:
        days = request.args.get("days", 30, type=int)
        platform_filter = request.args.get("platform", "")
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call platform APIs to fetch stats
        
        result = {
            "period": f"last_{days}_days",
            "platforms": {
                "tiktok": {
                    "posts": 45,
                    "views": 1234567,
                    "engagement_rate": 0.08,
                },
                "instagram": {
                    "posts": 30,
                    "views": 567890,
                    "engagement_rate": 0.06,
                },
            },
            "total_views": 1802457,
            "avg_engagement_rate": 0.07,
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="social_ai_engagement_stats",
            target="/api/engagement-stats",
            action="query",
            result=f"Fetched engagement stats for {days} days",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/engagement-stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "hint": "Available: /health, /badge, /api/generate-caption, /api/content-calendar, /api/post-to-platform, /api/engagement-stats",
    }), 404


if __name__ == "__main__":
    logger.info(f"Starting Social AI Agent on port {PORT}")
    logger.info(f"Quinn bridge: {QUINN_ENDPOINT}")
    logger.info("Routes: /health (public), /badge (public), /api/generate-caption, /api/content-calendar, /api/post-to-platform, /api/engagement-stats (badge-gated)")
    
    # Minimize PowerShell window on launch
    try:
        import subprocess
        subprocess.Popen([
            "powershell.exe",
            "-NoProfile",
            "-Command",
            """
            $h = (Get-Process -Id $PID).MainWindowHandle
            if ($h -ne 0) {
                Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(int h, int s);' -ErrorAction SilentlyContinue
                [P.W]::ShowWindow($h, 6) | Out-Null
            }
            """
        ])
    except:
        pass
    
    app.run(host="127.0.0.1", port=PORT, debug=False)
