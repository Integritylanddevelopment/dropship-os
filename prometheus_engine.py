#!/usr/bin/env python3
"""
Prometheus Engine — Video Content Generation
==============================================

Generates viral video content for ShipStack AI products.
Badge-gated HTTP service on port 8766.

Integrates with:
- ShipStack Engine (:8889) — for product data
- Quinn Bridge (:8765) — for AI inference and video generation
- Runway ML API — for video generation
- ElevenLabs API — for voice-over audio
- Suno API — for background music

Prerequisites:
- FFmpeg (for audio/video processing)
- FFMPEG_PATH env var set
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify
from shipstack_badge import get_badge, validate_token, log_action

# Setup
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

PORT = int(os.getenv("PROMETHEUS_ENGINE_PORT", 8766))
QUINN_ENDPOINT = os.getenv("QUINN_ENDPOINT", "http://localhost:8765")
SHIPSTACK_ENDPOINT = os.getenv("SHIPSTACK_ENGINE_PORT", "http://localhost:8889")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "C:\\path\\to\\ffmpeg\\bin")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def require_badge(f):
    """
    Decorator for badge-gated endpoints.
    Checks Authorization header for valid badge token.
    """
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "Missing or invalid Authorization header",
                "expected": "Authorization: Bearer badge-1_...",
            }), 401
        
        token = auth_header[7:]  # Remove "Bearer "
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
    """
    Public health check (no badge required).
    """
    return jsonify({
        "status": "healthy",
        "service": "Prometheus Engine",
        "port": PORT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "quinn_bridge": QUINN_ENDPOINT,
        "shipstack_engine": SHIPSTACK_ENDPOINT,
    }), 200


@app.route("/badge", methods=["GET"])
def get_new_badge():
    """
    Public endpoint to get a new badge token.
    """
    badge = get_badge()
    logger.info(f"Issued badge token: {badge['token'][:20]}... (expires {badge['expires_at']})")
    return jsonify(badge), 200


@app.route("/api/generate-video", methods=["POST"])
@require_badge
def generate_video():
    """
    Generate a viral video for a product.
    
    Badge-gated endpoint.
    
    Request body:
    {
        "product": {
            "id": "product-123",
            "title": "Pet Collar Widget",
            "description": "Comfy, adjustable pet collar...",
            "image_url": "https://...",
        },
        "style": "shorts|tiktok|instagram_reel|youtube_short",
        "duration_seconds": 30,
        "platform": "tiktok|instagram|youtube",
    }
    
    Response:
    {
        "video_id": "prometheus-video-123",
        "status": "processing|completed",
        "video_url": "s3://shipstack-videos/...",
        "duration": 30,
        "estimated_wait": 120,  # seconds if processing
    }
    """
    try:
        data = request.get_json()
        product = data.get("product", {})
        style = data.get("style", "shorts")
        duration = data.get("duration_seconds", 30)
        platform = data.get("platform", "tiktok")
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        product_id = product.get("id", "unknown")
        
        # TODO: Call Quinn bridge for script generation
        # TODO: Call Runway ML for video generation
        # TODO: Call ElevenLabs for voice-over
        # TODO: Call Suno for background music
        # TODO: Use FFmpeg to combine components
        
        result = {
            "video_id": f"prometheus-video-{product_id}",
            "status": "processing",
            "product_id": product_id,
            "style": style,
            "platform": platform,
            "duration": duration,
            "estimated_wait": 120,  # placeholder
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="prometheus_generate_video",
            target="/api/generate-video",
            action="generate",
            result=f"Started video generation for {product_id} ({style}, {duration}s)",
            success=True,
        )
        
        return jsonify(result), 202  # Accepted (async processing)
    except Exception as e:
        logger.error(f"Error in /api/generate-video: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/video-status/<video_id>", methods=["GET"])
@require_badge
def video_status(video_id):
    """
    Check status of a video generation job.
    
    Badge-gated endpoint.
    
    Response:
    {
        "video_id": "prometheus-video-123",
        "status": "processing|completed|failed",
        "progress": 0.75,  # 0-1
        "video_url": "s3://...",  # if completed
        "error": "...",  # if failed
    }
    """
    try:
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Query job status from job queue
        
        result = {
            "video_id": video_id,
            "status": "processing",
            "progress": 0.5,  # placeholder
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="prometheus_check_status",
            target="/api/video-status",
            action="query",
            result=f"Checked status of {video_id}",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/video-status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/publish-video", methods=["POST"])
@require_badge
def publish_video():
    """
    Publish a completed video to social media.
    
    Badge-gated endpoint.
    
    Request body:
    {
        "video_id": "prometheus-video-123",
        "platform": "tiktok|instagram|youtube",
        "caption": "Check out this amazing...",
        "hashtags": ["dropshipping", "producthunt", "..."],
    }
    
    Response:
    {
        "published": true,
        "platform": "tiktok",
        "post_url": "https://tiktok.com/@account/video/123",
        "timestamp": "2026-06-03T12:00:15Z",
    }
    """
    try:
        data = request.get_json()
        video_id = data.get("video_id", "")
        platform = data.get("platform", "tiktok")
        caption = data.get("caption", "")
        hashtags = data.get("hashtags", [])
        
        token = request.headers.get("Authorization", "Bearer ")[7:]
        issued_at = request.headers.get("X-Badge-Issued-At", "")
        
        # TODO: Call Social AI Agent to publish
        
        result = {
            "published": True,
            "platform": platform,
            "video_id": video_id,
            "post_url": f"https://{platform}.com/post/123",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        
        # Log the action
        log_action(
            token=token,
            issued_at_iso=issued_at,
            tool_name="prometheus_publish_video",
            target="/api/publish-video",
            action="publish",
            result=f"Published {video_id} to {platform}",
            success=True,
        )
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/publish-video: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "hint": "Available: /health, /badge, /api/generate-video, /api/video-status/<id>, /api/publish-video",
    }), 404


if __name__ == "__main__":
    logger.info(f"Starting Prometheus Engine on port {PORT}")
    logger.info(f"Quinn bridge: {QUINN_ENDPOINT}")
    logger.info(f"ShipStack engine: {SHIPSTACK_ENDPOINT}")
    logger.info(f"FFmpeg: {FFMPEG_PATH}")
    logger.info("Routes: /health (public), /badge (public), /api/generate-video, /api/video-status/<id>, /api/publish-video (badge-gated)")
    
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
