#!/usr/bin/env python3
"""
pinterest_poster.py -- Dropship OS Pinterest Auto-Poster
=========================================================
Automatically posts to Pinterest using the Pinterest API v5.

Priority: Pinterest is Channel #1 (CPM $0.28, viral_coeff 1.4, pins compound 2-4 years)

USAGE:
  python pinterest_poster.py --test               # verify token + list boards
  python pinterest_poster.py --auto               # post top 3 products from decisions.json
  python pinterest_poster.py --auto --max 5       # post top 5
  python pinterest_poster.py --list-boards        # list all your boards
  python pinterest_poster.py --image img.jpg --title "Product" --description "..." --board-id ID

STRATEGY (Gary Vee + Kamil Sattar):
  - Post 3-5 pins per day (Pinterest rewards consistency)
  - Keyword-rich descriptions (Pinterest = search engine)
  - Best times: 8-11 PM EST, 2-4 PM EST
  - Video pins get 3x engagement vs static
  - Image card pins are the fallback when no Prometheus video exists
"""

import os
import sys
import json
import time
import argparse
import tempfile
from pathlib import Path
from typing import Optional

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

BASE_DIR    = Path(__file__).parent.parent
DECISIONS   = BASE_DIR / "decisions.json"
OUTPUT_DIR  = BASE_DIR / "prometheus_output"
CARDS_DIR   = BASE_DIR / "pinterest_cards"

PINTEREST_API = "https://api.pinterest.com/v5"
TOKEN         = os.getenv("PINTEREST_ACCESS_TOKEN", "")
DEFAULT_BOARD = os.getenv("PINTEREST_BOARD_ID", os.getenv("PINTEREST_DEFAULT_BOARD_ID", ""))

FONT_BOLD   = "C:/Windows/Fonts/ARIALNB.TTF"
FONT_REG    = "C:/Windows/Fonts/ARIALN.TTF"

# Brand colors (match ShipStack AI dark theme)
C_BG        = (13,  17,  23)    # #0d1117
C_CARD      = (22,  33,  49)    # #162131
C_TEAL      = (0,   212, 180)   # #00d4b4
C_GREEN     = (34,  197, 94)    # #22c55e
C_GOLD      = (250, 189, 0)     # #fabd00
C_WHITE     = (255, 255, 255)
C_MUTED     = (148, 163, 184)   # #94a3b8
C_ACCENT    = (59,  130, 246)   # #3b82f6


# ── API helpers ───────────────────────────────────────────────────────────────
def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def api_get(path: str) -> dict:
    import urllib.request
    req = urllib.request.Request(f"{PINTEREST_API}{path}", headers=_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def api_post(path: str, data: dict) -> dict:
    import urllib.request
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{PINTEREST_API}{path}", data=body, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# ── Token test ────────────────────────────────────────────────────────────────
def test_connection() -> bool:
    """Verify the Pinterest token is valid and list boards."""
    if not TOKEN:
        print("[ERROR] PINTEREST_ACCESS_TOKEN not set in .env")
        return False
    try:
        me = api_get("/user_account")
        print(f"[OK] Connected as: {me.get('username', '?')} ({me.get('account_type', '?')})")
        print(f"     Follower count: {me.get('follower_count', 0)}")
        boards = list_boards()
        print(f"\n[OK] Token valid. {len(boards)} board(s) found.")
        return True
    except Exception as e:
        print(f"[ERROR] Token invalid or expired: {e}")
        print("       Refresh at: https://developers.pinterest.com/apps/")
        return False


# ── List boards ───────────────────────────────────────────────────────────────
def list_boards() -> list:
    try:
        resp = api_get("/boards?page_size=25")
        boards = resp.get("items", [])
        print(f"\n[BOARDS] Your Pinterest Boards ({len(boards)} total):\n")
        print(f"{'Board ID':<30} {'Name':<40} Pins")
        print("-" * 80)
        for b in boards:
            print(f"{b['id']:<30} {b['name']:<40} {b.get('pin_count', 0)}")
        print()
        return boards
    except Exception as e:
        print(f"[ERROR] listing boards: {e}")
        return []


# ── Image card generator ──────────────────────────────────────────────────────
def generate_product_card(
    product: str,
    niche: str,
    margin: float,
    score: float,
    output_path: str = None,
) -> Optional[str]:
    """
    Generate a 1000x1500 Pinterest-optimized product card image using Pillow.
    Returns the path to the saved PNG, or None on failure.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[WARN] Pillow not installed. Run: pip install Pillow")
        return None

    W, H = 1000, 1500
    img  = Image.new("RGB", (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    # ── Load fonts ────────────────────────────────────────────────────────────
    def load_font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    f_huge   = load_font(FONT_BOLD, 72)
    f_large  = load_font(FONT_BOLD, 52)
    f_medium = load_font(FONT_BOLD, 38)
    f_small  = load_font(FONT_REG,  30)
    f_tiny   = load_font(FONT_REG,  24)

    # ── Top accent bar ────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, 12], fill=C_TEAL)

    # ── Brand chip top-right ──────────────────────────────────────────────────
    draw.rounded_rectangle([W-200, 28, W-28, 72], radius=8, fill=C_CARD)
    draw.text((W-198+12, 38), "ShipStack AI", font=f_tiny, fill=C_TEAL)

    # ── Niche tag ─────────────────────────────────────────────────────────────
    niche_display = niche.upper().replace("_", " ")
    tag_w = 260
    draw.rounded_rectangle([40, 28, 40+tag_w, 72], radius=8, fill=C_TEAL)
    draw.text((55, 35), niche_display, font=f_tiny, fill=C_BG)

    # ── Score badge ───────────────────────────────────────────────────────────
    badge_label = f"Score {score:.0f}/100"
    draw.rounded_rectangle([40, 88, 200, 126], radius=6, fill=(30, 50, 80))
    draw.text((54, 94), badge_label, font=f_tiny, fill=C_GOLD)

    # ── Divider ───────────────────────────────────────────────────────────────
    draw.rectangle([40, 148, W-40, 150], fill=(30, 50, 80))

    # ── Product name ──────────────────────────────────────────────────────────
    # Word-wrap long product names
    words = product.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=f_large)
        if bbox[2] < W - 80:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)

    y = 180
    for ln in lines[:3]:
        draw.text((40, y), ln, font=f_large, fill=C_WHITE)
        y += 68

    # ── Margin callout box ────────────────────────────────────────────────────
    y += 30
    draw.rounded_rectangle([40, y, W-40, y+160], radius=16, fill=C_CARD)
    draw.rounded_rectangle([40, y, W-40, y+8], radius=8, fill=C_GREEN)
    margin_label = f"{margin:.0f}%"
    draw.text((80, y+30), margin_label, font=f_huge, fill=C_GREEN)
    draw.text((80, y+115), "avg. profit margin", font=f_small, fill=C_MUTED)
    draw.text((W//2, y+30), "Why people", font=f_small, fill=C_MUTED)
    draw.text((W//2, y+62), "keep buying:", font=f_small, fill=C_MUTED)

    y += 190

    # ── Bullet points ─────────────────────────────────────────────────────────
    bullets = _get_niche_bullets(niche, product)
    for i, b in enumerate(bullets):
        bx, by = 40, y + i * 54
        draw.ellipse([bx, by+6, bx+22, by+28], fill=C_TEAL)
        draw.text((bx+32, by), b, font=f_small, fill=C_WHITE)

    y += len(bullets) * 54 + 30

    # ── Social proof bar ──────────────────────────────────────────────────────
    draw.rounded_rectangle([40, y, W-40, y+80], radius=12, fill=(20, 40, 60))
    draw.text((60, y+14), "Trending NOW  |  Ships fast  |  5-star reviews", font=f_small, fill=C_MUTED)
    draw.text((60, y+46), "TikTok viral  |  Low competition  |  High demand", font=f_small, fill=C_MUTED)

    y += 100

    # ── CTA box ───────────────────────────────────────────────────────────────
    cta_y = H - 220
    draw.rounded_rectangle([40, cta_y, W-40, cta_y+120], radius=16, fill=C_TEAL)
    draw.text((W//2, cta_y+18), "LINK IN BIO", font=f_medium, fill=C_BG, anchor="mt")
    draw.text((W//2, cta_y+68), "Get yours before it sells out ->", font=f_small, fill=C_BG, anchor="mt")

    # ── Bottom bar ────────────────────────────────────────────────────────────
    draw.rectangle([0, H-12, W, H], fill=C_TEAL)

    # ── Save ──────────────────────────────────────────────────────────────────
    if not output_path:
        CARDS_DIR.mkdir(parents=True, exist_ok=True)
        safe = product.replace(" ", "_")[:30].lower()
        output_path = str(CARDS_DIR / f"{safe}_card.png")

    img.save(output_path, "PNG", quality=95)
    print(f"  [CARD] Generated: {Path(output_path).name}")
    return output_path


def _get_niche_bullets(niche: str, product: str) -> list:
    """Return 3 niche-specific bullet points for the product card."""
    bullets_map = {
        "pet accessories":  ["Sold out in 48h on Amazon", "Pet owners buy 3+ per year", "Vet recommended quality"],
        "beauty skincare":  ["Dermatologist tested formula", "Results in 7 days or less", "Sells out every restock"],
        "home kitchen":     ["Saves 30 min every single day", "Top gifted item of 2024", "Works in any home setup"],
        "fitness tools":    ["Used by 50,000+ athletes", "No gym membership needed", "Results in first session"],
        "outdoor camping":  ["Survival-grade durability", "Packs down to pocket size", "5-star on every platform"],
        "desk organizers":  ["Productivity up 40% instantly", "Works from day one setup", "Clears your head space"],
        "led grow lights":  ["Plants thrive in any room", "Energy cost: pennies/day", "Harvest in 6-8 weeks"],
    }
    return bullets_map.get(niche, [
        "Trending in top 1% of products",
        "Repeat customers every month",
        "Ships in 3-5 business days",
    ])


# ── Upload image & create pin ─────────────────────────────────────────────────
def create_image_pin(
    board_id: str,
    image_path: str,
    title: str,
    description: str,
    link: str = "",
    alt_text: str = "",
) -> Optional[dict]:
    """Upload image and create a Pinterest pin."""
    if not TOKEN:
        print("[ERROR] PINTEREST_ACCESS_TOKEN not set")
        return None

    print(f"  [UPLOAD] {Path(image_path).name}")
    try:
        upload_resp = api_post("/media", {"media_type": "image"})
        upload_url  = upload_resp.get("upload_url")
        media_id    = upload_resp.get("media_id")

        if not upload_url:
            print(f"  [ERROR] No upload URL: {upload_resp}")
            return None

        import urllib.request
        with open(image_path, "rb") as f:
            image_data = f.read()
        req = urllib.request.Request(upload_url, data=image_data, method="PUT")
        req.add_header("Content-Type", "image/png")
        with urllib.request.urlopen(req, timeout=60):
            pass

        print(f"  [OK] Uploaded (media_id: {media_id})")
    except Exception as e:
        print(f"  [ERROR] Upload failed: {e}")
        return None

    pin_data = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "alt_text": (alt_text or title)[:500],
        "media_source": {"source_type": "media_id", "media_id": media_id},
    }
    if link:
        pin_data["link"] = link

    try:
        resp = api_post("/pins", pin_data)
        pin_id = resp.get("id")
        print(f"  [PIN] Created! https://pinterest.com/pin/{pin_id}")
        return resp
    except Exception as e:
        print(f"  [ERROR] Pin creation failed: {e}")
        return None


# ── Create video pin ──────────────────────────────────────────────────────────
def create_video_pin(
    board_id: str,
    video_path: str,
    title: str,
    description: str,
    link: str = "",
) -> Optional[dict]:
    """Upload video and create a Pinterest video pin (3x engagement)."""
    if not TOKEN:
        print