import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""
social_ai_agent.py -- ShipStack Social AI Agent Flask Service
=============================================================
HTTP service on :8867 that orchestrates posting to Pinterest, YouTube,
TikTok, and Meta (Instagram). Wraps the real poster classes from
integrations/social_poster.py and social_ai_agent/pinterest_poster.py.

All LLM calls go through Quinn bridge at http://127.0.0.1:8765.
"""

import os
import json
import time
import uuid
import traceback
from pathlib import Path
from datetime import datetime, timezone

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).parent.parent
    load_dotenv(BASE_DIR / '.env')
    load_dotenv(BASE_DIR / '.env.local', override=True)
except ImportError:
    BASE_DIR = Path(__file__).parent.parent

from flask import Flask, request, jsonify

# ── Graceful imports of posting subsystems ────────────────────────────────────
# integrations/social_poster.py classes
PinterestPoster = None
YouTubePoster = None
TikTokPoster = None
MetaPoster = None

try:
    sys.path.insert(0, str(BASE_DIR))
    from integrations.social_poster import PinterestPoster
except Exception as e:
    print(f"[social_ai_agent] WARN: Could not import PinterestPoster from integrations: {e}")

try:
    from integrations.social_poster import YouTubePoster
except Exception as e:
    print(f"[social_ai_agent] WARN: Could not import YouTubePoster from integrations: {e}")

try:
    from integrations.social_poster import TikTokPoster
except Exception as e:
    print(f"[social_ai_agent] WARN: Could not import TikTokPoster from integrations: {e}")

try:
    from integrations.social_poster import MetaPoster
except Exception as e:
    print(f"[social_ai_agent] WARN: Could not import MetaPoster from integrations: {e}")

# social_ai_agent/pinterest_poster.py -- generate_product_card
generate_product_card = None
try:
    from social_ai_agent.pinterest_poster import generate_product_card
except Exception as e:
    print(f"[social_ai_agent] WARN: Could not import generate_product_card: {e}")

# ── Quinn bridge for LLM calls ───────────────────────────────────────────────
QUINN_BRIDGE = os.getenv("QUINN_BRIDGE_URL", "http://127.0.0.1:8765")
QUINN_CHAT_URL = f"{QUINN_BRIDGE}/v1/chat/completions"

POST_QUEUE_PATH = BASE_DIR / "content_pipeline" / "post_queue.json"
CARDS_DIR = BASE_DIR / "pinterest_cards"

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
START_TIME = time.time()


# ── CORS middleware ───────────────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


# ── Platform credential checks ───────────────────────────────────────────────
def _platform_status():
    """Check which platforms have credentials configured."""
    return {
        "pinterest": {
            "configured": bool(os.getenv("PINTEREST_ACCESS_TOKEN")),
            "env_vars": ["PINTEREST_ACCESS_TOKEN"],
            "board_id": os.getenv("PINTEREST_BOARD_ID", os.getenv("PINTEREST_DEFAULT_BOARD_ID", "")),
        },
        "youtube": {
            "configured": all([
                os.getenv("YOUTUBE_CLIENT_ID"),
                os.getenv("YOUTUBE_CLIENT_SECRET"),
                os.getenv("YOUTUBE_REFRESH_TOKEN"),
            ]),
            "env_vars": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
        },
        "tiktok": {
            "configured": bool(os.getenv("TIKTOK_ACCESS_TOKEN")),
            "env_vars": ["TIKTOK_ACCESS_TOKEN"],
        },
        "meta": {
            "configured": all([
                os.getenv("META_ACCESS_TOKEN"),
                os.getenv("META_IG_ACCOUNT_ID"),
            ]),
            "env_vars": ["META_ACCESS_TOKEN", "META_IG_ACCOUNT_ID"],
        },
    }


def _quinn_generate(prompt: str, max_tokens: int = 512) -> str:
    """Call Quinn bridge for LLM content generation."""
    try:
        import urllib.request
        payload = json.dumps({
            "model": "qwen2.5:7b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            QUINN_CHAT_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"[LLM unavailable: {e}]"


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/health', methods=['GET'])
def health():
    platforms = _platform_status()
    configured_list = [p for p, s in platforms.items() if s["configured"]]
    uptime = round(time.time() - START_TIME, 1)
    return jsonify({
        "status": "ok",
        "service": "social_ai_agent",
        "port": 8867,
        "uptime_seconds": uptime,
        "platforms_configured": configured_list,
        "subsystems": {
            "PinterestPoster": PinterestPoster is not None,
            "YouTubePoster": YouTubePoster is not None,
            "TikTokPoster": TikTokPoster is not None,
            "MetaPoster": MetaPoster is not None,
            "generate_product_card": generate_product_card is not None,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route('/platforms', methods=['GET'])
def platforms():
    return jsonify(_platform_status())


# ── Pinterest ─────────────────────────────────────────────────────────────────
@app.route('/post/pinterest', methods=['POST', 'OPTIONS'])
def post_pinterest():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if not os.getenv("PINTEREST_ACCESS_TOKEN"):
        return jsonify({"error": "Pinterest not configured", "missing": "PINTEREST_ACCESS_TOKEN"}), 503

    if PinterestPoster is None:
        return jsonify({"error": "PinterestPoster module not available"}), 503

    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    description = data.get("description", "")
    image_url = data.get("image_url", "")
    image_path = data.get("image_path", "")
    board_id = data.get("board_id",
                        os.getenv("PINTEREST_DEFAULT_BOARD_ID",
                                  os.getenv("PINTEREST_BOARD_ID", "")))
    link = data.get("link", "")

    if not board_id:
        return jsonify({"error": "No board_id provided and PINTEREST_DEFAULT_BOARD_ID not set"}), 400

    if not title:
        return jsonify({"error": "title is required"}), 400

    try:
        poster = PinterestPoster()

        # If image_path provided but no image_url, the caller should host it
        # PinterestPoster.create_pin expects image_url
        pin_image_url = image_url
        if not pin_image_url and image_path:
            # Store note that local file was referenced -- API requires a URL
            return jsonify({
                "error": "Pinterest API requires a publicly accessible image_url, not a local path. "
                         "Upload the image first or provide image_url.",
                "image_path_provided": image_path,
            }), 400

        result = poster.create_pin(
            board_id=board_id,
            title=title,
            description=description,
            link=link,
            image_url=pin_image_url,
        )

        if "error" in result:
            return jsonify(result), 400

        return jsonify({
            "status": "posted",
            "platform": "pinterest",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "platform": "pinterest"}), 500


# ── YouTube ───────────────────────────────────────────────────────────────────
@app.route('/post/youtube', methods=['POST', 'OPTIONS'])
def post_youtube():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if not all([os.getenv("YOUTUBE_CLIENT_ID"), os.getenv("YOUTUBE_CLIENT_SECRET"),
                os.getenv("YOUTUBE_REFRESH_TOKEN")]):
        return jsonify({"error": "YouTube not configured",
                        "missing": "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN"}), 503

    if YouTubePoster is None:
        return jsonify({"error": "YouTubePoster module not available"}), 503

    data = request.get_json(silent=True) or {}
    video_path = data.get("video_path", "")
    title = data.get("title", "")
    description = data.get("description", "")
    tags = data.get("tags", [])

    if not video_path:
        return jsonify({"error": "video_path is required"}), 400
    if not title:
        return jsonify({"error": "title is required"}), 400

    try:
        poster = YouTubePoster()
        result = poster.upload_short(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
        )

        if "error" in result:
            return jsonify(result), 400

        return jsonify({
            "status": "posted",
            "platform": "youtube",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "platform": "youtube"}), 500


# ── TikTok ────────────────────────────────────────────────────────────────────
@app.route('/post/tiktok', methods=['POST', 'OPTIONS'])
def post_tiktok():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if not os.getenv("TIKTOK_ACCESS_TOKEN"):
        return jsonify({"error": "TikTok not configured", "missing": "TIKTOK_ACCESS_TOKEN"}), 503

    if TikTokPoster is None:
        return jsonify({"error": "TikTokPoster module not available"}), 503

    data = request.get_json(silent=True) or {}
    video_path = data.get("video_path", "")
    title = data.get("title", "")
    description = data.get("description", "")
    caption = data.get("caption", title or description)

    if not video_path:
        return jsonify({"error": "video_path is required"}), 400

    try:
        poster = TikTokPoster()
        result = poster.post_video(
            video_path=video_path,
            caption=caption,
        )

        if "error" in result:
            return jsonify(result), 400

        return jsonify({
            "status": "posted",
            "platform": "tiktok",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "platform": "tiktok"}), 500


# ── Auto-post to all configured platforms ─────────────────────────────────────
@app.route('/post/auto', methods=['POST', 'OPTIONS'])
def post_auto():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json(silent=True) or {}
    product = data.get("product", {})

    if not product:
        return jsonify({"error": "product data is required"}), 400

    product_name = product.get("name", product.get("product", "Unknown Product"))
    niche = product.get("niche", product.get("category", "general"))
    margin = product.get("margin", product.get("margin_pct", 0))
    score = product.get("score", product.get("total_score", 0))
    description = product.get("description", "")
    link = product.get("link", product.get("url", ""))
    video_path = product.get("video_path", "")
    image_url = product.get("image_url", "")

    # Generate description via Quinn if not provided
    if not description:
        description = _quinn_generate(
            f"Write a short, compelling 2-sentence product description for a "
            f"dropshipping product called '{product_name}' in the {niche} niche. "
            f"Include relevant keywords for SEO. No hashtags.",
            max_tokens=200,
        )

    results = {}
    platforms = _platform_status()

    # Pinterest: generate card image if possible, then post
    if platforms["pinterest"]["configured"] and PinterestPoster is not None:
        try:
            card_path = None
            if generate_product_card is not None and not image_url:
                CARDS_DIR.mkdir(parents=True, exist_ok=True)
                card_path = generate_product_card(
                    product=product_name,
                    niche=niche,
                    margin=float(margin),
                    score=float(score),
                    output_path=str(CARDS_DIR / f"card_{int(time.time())}.png"),
                )

            # Pinterest API needs a URL, not a local path
            # If we only have a local card, note it but skip the API call
            if image_url:
                poster = PinterestPoster()
                board_id = platforms["pinterest"]["board_id"]
                if board_id:
                    result = poster.create_pin(
                        board_id=board_id,
                        title=product_name[:100],
                        description=description[:500],
                        link=link,
                        image_url=image_url,
                    )
                    results["pinterest"] = {"status": "posted", "result": result}
                else:
                    results["pinterest"] = {"status": "skipped", "reason": "no board_id configured"}
            elif card_path:
                results["pinterest"] = {
                    "status": "card_generated",
                    "card_path": card_path,
                    "reason": "Local card generated but Pinterest API requires image_url. Upload card to get a URL.",
                }
            else:
                results["pinterest"] = {"status": "skipped", "reason": "no image_url and card generation unavailable"}
        except Exception as e:
            results["pinterest"] = {"status": "error", "error": str(e)}

    # YouTube: post if video exists
    if platforms["youtube"]["configured"] and YouTubePoster is not None and video_path:
        try:
            poster = YouTubePoster()
            result = poster.upload_short(
                video_path=video_path,
                title=product_name[:100],
                description=description,
            )
            results["youtube"] = {"status": "posted" if "id" in result else "error", "result": result}
        except Exception as e:
            results["youtube"] = {"status": "error", "error": str(e)}

    # TikTok: post if video exists
    if platforms["tiktok"]["configured"] and TikTokPoster is not None and video_path:
        try:
            poster = TikTokPoster()
            # Generate TikTok-style caption via Quinn
            tiktok_caption = _quinn_generate(
                f"Write a TikTok caption (under 150 chars) with a hook for "
                f"'{product_name}' in {niche}. Include 3-5 hashtags.",
                max_tokens=100,
            )
            result = poster.post_video(
                video_path=video_path,
                caption=tiktok_caption[:150],
            )
            results["tiktok"] = {"status": "posted" if "error" not in result else "error", "result": result}
        except Exception as e:
            results["tiktok"] = {"status": "error", "error": str(e)}

    # Meta/Instagram: post image if URL available
    if platforms["meta"]["configured"] and MetaPoster is not None:
        try:
            poster = MetaPoster()
            if video_path:
                result = poster.post_reel(video_url=video_path, caption=description[:2200])
            elif image_url:
                result = poster.post_image(image_url=image_url, caption=description[:2200])
            else:
                result = {"status": "skipped", "reason": "no image_url or video_path"}
            results["meta"] = {"status": "posted" if "id" in result else "skipped", "result": result}
        except Exception as e:
            results["meta"] = {"status": "error", "error": str(e)}

    posted_count = sum(1 for r in results.values() if r.get("status") == "posted")
    return jsonify({
        "status": "complete",
        "product": product_name,
        "platforms_posted": posted_count,
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Post queue ────────────────────────────────────────────────────────────────
@app.route('/queue', methods=['GET'])
def get_queue():
    if not POST_QUEUE_PATH.exists():
        return jsonify({"queue": [], "message": "No post queue file found", "path": str(POST_QUEUE_PATH)})

    try:
        with open(POST_QUEUE_PATH, 'r', encoding='utf-8') as f:
            queue = json.load(f)
        return jsonify({"queue": queue, "count": len(queue) if isinstance(queue, list) else 0})
    except Exception as e:
        return jsonify({"error": f"Failed to read queue: {e}"}), 500


# ── Generate product card ─────────────────────────────────────────────────────
@app.route('/generate-card', methods=['POST', 'OPTIONS'])
def gen_card():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if generate_product_card is None:
        return jsonify({"error": "generate_product_card not available (Pillow or pinterest_poster import failed)"}), 503

    data = request.get_json(silent=True) or {}
    product_name = data.get("product", data.get("name", ""))
    niche = data.get("niche", data.get("category", "general"))
    margin = float(data.get("margin", data.get("margin_pct", 0)))
    score = float(data.get("score", data.get("total_score", 50)))

    if not product_name:
        return jsonify({"error": "product name is required"}), 400

    try:
        CARDS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in product_name)[:40].strip().replace(" ", "_")
        output_path = str(CARDS_DIR / f"card_{safe_name}_{int(time.time())}.png")

        result_path = generate_product_card(
            product=product_name,
            niche=niche,
            margin=margin,
            score=score,
            output_path=output_path,
        )

        if result_path:
            return jsonify({
                "status": "generated",
                "card_path": result_path,
                "product": product_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        else:
            return jsonify({"error": "Card generation returned None (check Pillow / font availability)"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── Legacy compatibility routes ───────────────────────────────────────────────
@app.route('/agents', methods=['GET'])
def agents():
    platforms = _platform_status()
    return jsonify({
        "agents": [
            {"name": name, "status": "configured" if info["configured"] else "unconfigured"}
            for name, info in platforms.items()
        ]
    })


@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "pinterest")
    topic = data.get("topic", "product")

    draft = _quinn_generate(
        f"Write a short social media post for {platform} about: {topic}. "
        f"Keep it under 200 characters. Include relevant hashtags.",
        max_tokens=150,
    )

    return jsonify({
        "platform": platform,
        "topic": topic,
        "draft": draft,
        "status": "draft",
        "generated_by": "quinn_bridge",
    })


@app.route('/post', methods=['POST', 'OPTIONS'])
def post_legacy():
    """Legacy single-post endpoint -- routes to the platform-specific handler."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "").lower()

    if platform == "pinterest":
        return post_pinterest()
    elif platform == "youtube":
        return post_youtube()
    elif platform == "tiktok":
        return post_tiktok()
    else:
        return jsonify({
            "status": "queued",
            "platform": platform or "unknown",
            "id": f"queued-{uuid.uuid4()}",
            "message": f"Platform '{platform}' not yet supported for direct posting",
        })


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Kill stale process on port 8867
    import subprocess
    try:
        result = subprocess.run(
            ['netstat', '-ano'], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if ':8867' in line and 'LISTENING' in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    print(f"[social_ai_agent] Killing stale process on :8867 (PID {pid})")
                    subprocess.run(['taskkill', '/F', '/PID', pid],
                                   capture_output=True, timeout=5)
                    time.sleep(0.5)
    except Exception as e:
        print(f"[social_ai_agent] Port cleanup note: {e}")

    print(f"[social_ai_agent] Starting on http://127.0.0.1:8867")
    platforms = _platform_status()
    configured = [p for p, s in platforms.items() if s["configured"]]
    print(f"[social_ai_agent] Configured platforms: {configured or 'none'}")
    print(f"[social_ai_agent] Quinn bridge: {QUINN_CHAT_URL}")

    app.run(host='127.0.0.1', port=8867, debug=False, use_reloader=False)
